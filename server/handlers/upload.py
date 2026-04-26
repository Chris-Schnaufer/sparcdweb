""" Functions to handle requests starting with /upload for SPARCd server """

from dataclasses import dataclass
import json
import os
import types
from typing import Optional

from flask import request, url_for

from camtrap.v016 import camtrap
import camtrap_utils as ctu
import sparcd_collections as sdc
from sparcd_db import SPARCdDatabase
import spd_crypt as crypt
from spd_types.userinfo import UserInfo
from spd_types.s3info import S3Info
import sparcd_upload_utils as sdupu
import s3_utils as s3u
from s3.s3_access_helpers import make_s3_path, COLLECTIONS_FOLDER, DEPLOYMENT_CSV_FILE_NAME, \
                                MEDIA_CSV_FILE_NAME, OBSERVATIONS_CSV_FILE_NAME, \
                                SPECIES_JSON_FILE_NAME, SPARCD_PREFIX, S3_UPLOADS_PATH_PART
from s3.s3_collections import S3CollectionConnection
from s3.s3_uploads import S3UploadConnection

@dataclass
class UploadImagesParams:
    """ Contains the parameters for getting upload images calls """
    passcode: str
    temp_species_filename: str

@dataclass
class UploadLocationId:
    """ Contains the identity parameters for an upload location request """
    timestamp: str
    coll_id: str
    upload_id: str

@dataclass
class LocationInfo:
    """ Contains the location parameters for an upload location request """
    loc_id: str
    loc_name: str
    loc_ele: str
    loc_lat: str
    loc_lon: str

@dataclass
class UploadLocationInfo:
    """ Contains the parameters needed for updating location information for an upload """
    upload: UploadLocationId
    location: LocationInfo


def __apply_species_edits(user_info: UserInfo,
                          s3_info: S3Info,
                          one_image: dict,
                          species_edits: list,
                          temp_species_filename: str) -> dict:
    """ Applies species edits to a single image
    Arguments:
        user_info: the user information
        s3_info: the S3 endpoint information
        one_image: the image to apply edits to
        species_edits: the list of species edits to apply
        temp_species_filename: the name of the temporary species file
    Return:
        Returns the image with the edits applied
    """
    one_image = {**one_image, 'species': list(one_image['species'])}
    have_deletes = False
    for one_species in species_edits:
        found = False

        # Look for exiting species in image
        for one_img_species in one_image['species']:
            if one_species[0] == one_img_species['scientificName']:
                one_img_species['count'] = one_species[1]
                have_deletes = one_species[1] <= 0
                found = True

        # Add it in if not found
        if not found:
            check_species = user_info.species or s3u.load_sparcd_config(
                                                        SPECIES_JSON_FILE_NAME,
                                                        temp_species_filename,
                                                        s3_info)
            found_species = next((item for item in check_species
                                  if item['scientificName'] == one_species[0]),
                                 {'name': 'Unknown'})
            one_image['species'].append({'name': found_species['name'],
                                         'scientificName': one_species[0],
                                         'count': one_species[1]})

    if have_deletes:
        one_image['species'] = [s for s in one_image['species'] if int(s['count']) > 0]

    return one_image


def __apply_image_edits(db: SPARCdDatabase,
                        user_info: UserInfo,
                        s3_info: S3Info,
                        all_images: tuple,
                        temp_species_filename: str) -> list:
    """ Applies any species edits to all images
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        all_images: the images to apply edits to
        temp_species_filename: the name of the temporary species file
    """
    images = list(all_images)
    edits = {}
    for idx, one_image in enumerate(images):
        upload_path = os.path.dirname(one_image['s3_path'])
        edit_key = one_image['bucket'] + ':' + upload_path
        if edit_key not in edits:
            edits = {**edits,
                     **db.get_image_species_edits(s3_info.id, one_image['bucket'], upload_path)}
        if one_image['s3_path'] in edits[edit_key]:
            images[idx] = __apply_species_edits(user_info,
                                                s3_info,
                                                one_image,
                                                edits[edit_key][one_image['s3_path']],
                                                temp_species_filename
                                               )
    return images


def __prepare_image_response(all_images: tuple,
                             collection_id: str,
                             collection_upload: str,
                             passcode: str) -> list:
    """ Prepares images for the response by building URLs and encrypting paths
    Arguments:
        all_images: the images to prepare
        collection_id: the collection ID
        collection_upload: the collection upload ID
        passcode: the passcode for encryption
    """
    images = list(all_images)
    for one_img in images:
        one_img['url'] = url_for('auth.image', _external=True,
                                 i=crypt.do_encrypt(passcode,
                                     json.dumps({'k': one_img['key'],
                                                 'p': f'{collection_id}:{collection_upload}'})))

        one_img['s3_path'] = crypt.do_encrypt(passcode, one_img['s3_path'])
        one_img['upload'] = collection_upload
        del one_img['bucket']
        del one_img['s3_url']
        del one_img['key']

    return images


def __update_camtrap_files(s3_info: S3Info,
                           bucket: str,
                           upload_path: str,
                           loc_params: UploadLocationInfo) -> None:
    """ Updates the camtrap CSV files with new location information
    Arguments:
        s3_info: the S3 endpoint information
        bucket: the S3 bucket
        upload_path: the S3 upload path
        loc_params: the upload location parameters
    """
    deployment_id = loc_params.upload.coll_id + ':' + loc_params.location.loc_id

    # Update the Deployments file
    deployment_info = ctu.load_camtrap_deployments(s3_info, bucket, upload_path)
    deployment_info[0][camtrap.CAMTRAP_DEPLOYMENT_ID_IDX] = deployment_id
    deployment_info[0][camtrap.CAMTRAP_DEPLOYMENT_LOCATION_ID_IDX] = loc_params.location.loc_id
    deployment_info[0][camtrap.CAMTRAP_DEPLOYMENT_LOCATION_NAME_IDX] = loc_params.location.loc_name
    deployment_info[0][camtrap.CAMTRAP_DEPLOYMENT_LONGITUDE_IDX] = loc_params.location.loc_lat
    deployment_info[0][camtrap.CAMTRAP_DEPLOYMENT_LATITUDE_IDX] = loc_params.location.loc_lon
    deployment_info[0][camtrap.CAMTRAP_DEPLOYMENT_CAMERA_HEIGHT_IDX] = loc_params.location.loc_ele
    S3UploadConnection.upload_camtrap_data(s3_info, bucket,
                                     make_s3_path((upload_path, DEPLOYMENT_CSV_FILE_NAME)),
                                     deployment_info)

    # Update the Media file
    media_info = ctu.load_camtrap_media(s3_info, bucket, upload_path)
    for one_media in media_info:
        media_info[one_media][camtrap.CAMTRAP_MEDIA_DEPLOYMENT_ID_IDX] = deployment_id
    S3UploadConnection.upload_camtrap_data(s3_info, bucket,
                                     make_s3_path((upload_path, MEDIA_CSV_FILE_NAME)),
                                     [media_info[one_key] for one_key in media_info.keys()])

    # Update the Observations file
    obs_info = ctu.load_camtrap_observations(s3_info, bucket, upload_path)
    for one_file in obs_info:
        for one_obs in obs_info[one_file]:
            one_obs[camtrap.CAMTRAP_OBSERVATION_DEPLOYMENT_ID_IDX] = deployment_id
    row_groups = [obs_info[one_key] for one_key in obs_info]
    S3UploadConnection.upload_camtrap_data(s3_info, bucket,
                                     make_s3_path((upload_path, OBSERVATIONS_CSV_FILE_NAME)),
                                     [one_row for one_set in row_groups for one_row in one_set])


def __upload_location_request_params() -> Optional[UploadLocationInfo]:
    """ Gets the request parameters for the upload locations request
    Return:
        Returns the request parameters in UploadLocationInfo when successful, or None if not
    """
    timestamp = request.form.get('timestamp')
    coll_id = request.form.get('collection')
    upload_id = request.form.get('upload')
    loc_id = request.form.get('locId')
    loc_name = request.form.get('locName')
    loc_ele = request.form.get('locElevation')
    loc_lat = request.form.get('locLat')
    loc_lon = request.form.get('locLon')

    if not all(item for item in [coll_id, upload_id, loc_id, loc_name, loc_ele, timestamp]):
        return None

    return UploadLocationInfo(
        upload=UploadLocationId(timestamp=timestamp, coll_id=coll_id, upload_id=upload_id),
        location=LocationInfo(loc_id=loc_id, loc_name=loc_name, loc_ele=loc_ele,
                              loc_lat=loc_lat, loc_lon=loc_lon)
    )


def handle_upload_images(db: SPARCdDatabase,
                          user_info: UserInfo,
                          s3_info: S3Info,
                          params: UploadImagesParams) -> Optional[list]:
    """ Returns the files that are part of an image upload
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        params: the additional parameters for this call
    Return:
        Returns a list of the files that are part of the specified upload upon success, and None
        if there's a bad parameter
    """

    # Check the rest of the request parameters
    collection_id = request.form.get('id')
    collection_upload = request.form.get('up')

    if not collection_id or not collection_upload:
        return None

    # Get the bucket
    s3_bucket = collection_id if not collection_id.startswith(SPARCD_PREFIX) else \
                                                        collection_id[len(SPARCD_PREFIX):]

    all_images, _ = sdc.get_upload_images(db, s3_bucket, collection_id,
                                                                collection_upload, s3_info)

    if isinstance(all_images, types.GeneratorType):
        all_images = tuple(all_images)

    # Check that we have images
    if not all_images:
        return []

    all_images = __apply_image_edits(db, user_info, s3_info, all_images,
                                     params.temp_species_filename)
    all_images = __prepare_image_response(all_images, collection_id,
                                          collection_upload, params.passcode)
    return all_images


def handle_upload_location(db: SPARCdDatabase, user_info: UserInfo, s3_info: S3Info,
                                temp_species_filename: str) -> bool:
    """ Handles updating the location information in an upload
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        temp_species_filename: the path to the temporary species filename
    Return:
        True is returned upon success, and False if there was an issue
    """
    # Get the request parameters
    loc_params = __upload_location_request_params()
    if not loc_params:
        return None

    bucket = SPARCD_PREFIX + loc_params.upload.coll_id
    upload_path = make_s3_path((COLLECTIONS_FOLDER, loc_params.upload.coll_id,
                                S3_UPLOADS_PATH_PART, loc_params.upload.upload_id))

    db.add_collection_edit(s3_info.id, bucket, upload_path, user_info.name,
                           loc_params.upload.timestamp, loc_params.location.loc_id,
                           loc_params.location.loc_name, loc_params.location.loc_ele)

    sdupu.process_upload_changes(s3_info,
                            sdupu.UploadChangeParams(
                                       collection_id=loc_params.upload.coll_id,
                                       upload_name=loc_params.upload.upload_id,
                                       species_timed_file=temp_species_filename,
                                       change_locations={
                                           'loc_id': loc_params.location.loc_id,
                                           'loc_name': loc_params.location.loc_name,
                                           'loc_ele': loc_params.location.loc_ele,
                                           'loc_lat': loc_params.location.loc_lat,
                                           'loc_lon': loc_params.location.loc_lon,
                                       }
                            )
                    )

    __update_camtrap_files(s3_info, bucket, upload_path, loc_params)

    # Update the collection to reflect the new upload location
    updated_collection = S3CollectionConnection.get_collection_info(s3_info, bucket)
    if updated_collection:
        # Update the collection entry in the database
        sdc.collection_update(db, s3_info.id, sdupu.normalize_collection(updated_collection))

    return True


def handle_update_upload_details(db: SPARCdDatabase, s3_info: S3Info, collection_id: str,
                                                upload_id: str, description: str) -> Optional[dict]:
    """ Updates the details of an upload
    Arguments:
        db: the database instance
        s3_info: the S3 endpoint information
        collection_id: the ID of the collection the upload belongs to
        upload_id: the ID of the upload
        description: the updated description to save
    Return:
        Returns the updated collection upon successful update and None when the update fails
    """
    bucket = SPARCD_PREFIX + collection_id
    upload_path = make_s3_path((COLLECTIONS_FOLDER, collection_id, S3_UPLOADS_PATH_PART, upload_id))

    if not S3UploadConnection.update_upload_metadata_description(s3_info, bucket, upload_path,
                                                                                    description):
        return None

    # Update the collection to reflect the new upload metadata
    updated_collection = S3CollectionConnection.get_collection_info(s3_info, bucket)
    if updated_collection:
        updated_collection = sdupu.normalize_collection(updated_collection)

        # Update the collection entry in the database
        sdc.collection_update(db, s3_info.id, updated_collection)

    return updated_collection
