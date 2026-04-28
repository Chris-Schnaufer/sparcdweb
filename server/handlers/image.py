""" Functions to handle requests starting with /image for SPARCd server """

from dataclasses import dataclass
import datetime
import json
import os
import tempfile
from typing import Optional, Union
from dateutil.relativedelta import relativedelta

from flask import request

from camtrap.v016 import camtrap
import camtrap_utils as ctu
import image_utils
from sparcd_db import SPARCdDatabase
import sparcd_collections as sdc
import spd_crypt as crypt
from spd_types.userinfo import UserInfo
from spd_types.s3info import S3Info
import sparcd_utils as sdu
import sparcd_timestamp_utils as sdtsu
import sparcd_upload_utils as sdupu
from s3.s3_access_helpers import make_s3_path, download_s3_file, COLLECTIONS_FOLDER, \
                                MEDIA_CSV_FILE_NAME, OBSERVATIONS_CSV_FILE_NAME, \
                                SPECIES_JSON_FILE_NAME, SPARCD_PREFIX, S3_UPLOADS_PATH_PART
from s3.s3_collections import S3CollectionConnection
from s3.s3_connect import s3_connect
from s3.s3_uploads import S3UploadConnection
import s3_utils as s3u


@dataclass
class ImageEditParams:
    """ Contains the parameters for an image edit complete request """
    coll_id: str
    upload_id: str
    path_encrypted: str
    path: str
    last_reqid: str


@dataclass
class ImageAllEditedParams:
    """ Contains the parameters for when the user has finished editing images """
    user_name: str
    coll_id: str
    upload_id: str
    last_request_id: str
    timestamp: str
    force_all_changes: bool

@dataclass
class AdjustTimestamp:
    """ Contains the timestamp parameters """
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int


@dataclass
class AdjustTimestampParams:
    """ Contains the parameters for adjusting timestamps """
    collection_id: str
    upload_id: str
    files: list
    timestamp: AdjustTimestamp


def __adjust_timestamp_params() -> Optional[AdjustTimestampParams]:
    """ Gets and validates the adjust timestamp parameters
    Returns:
        The parameters in AdjustTimestampParams when successful, and None when not
    """
    # Get the rest of the request parameters
    try:
        collection_id = request.form.get('collection')
        upload_id = request.form.get('upload')
        year = int(request.form.get('year', 0))
        month = int(request.form.get('month', 0))
        day = int(request.form.get('day', 0))
        hour = int(request.form.get('hour', 0))
        minute = int(request.form.get('minute', 0))
        second = int(request.form.get('second', 0))
        all_files = request.form.get('files')
    except ValueError:
        return None

    # Check for mandatory parameters
    if not all([collection_id, upload_id]):
        return None

    # Get all the file names
    if all_files is not None:
        all_files = sdu.get_request_files()
        if all_files is None:
            return None

    if not all_files:
        all_files = []

    return AdjustTimestampParams(
        collection_id=collection_id,
        upload_id=upload_id,
        files=all_files,
        timestamp=AdjustTimestamp(year=year,
                                  month=month,
                                  day=day,
                                  hour=hour,
                                  minute=minute,
                                  second=second
                                )
        )


def __has_last_edit(edit_files_info: list, last_reqid: str) -> bool:
    """ Checks if the last edit request has been received
    Arguments:
        edit_files_info: the list of edit file information
        last_reqid: the last request ID to check for
    Return:
        Returns True if the last edit request has been received, False otherwise
    """
    return any('request_id' in one_edit and
               one_edit['request_id'] and
               one_edit['request_id'] == last_reqid
               for one_edit in edit_files_info)


def __has_last_edit_or_forced(edited_files_info: list,
                               last_request_id: Optional[str],
                               force_all_changes: bool) -> bool:
    """ Checks if the last edit request has been received or changes are forced
    Arguments:
        edited_files_info: the list of edited file information
        last_request_id: the last request ID to check for, or None to force save
        force_all_changes: whether to force all changes regardless of last edit
    Return:
        Returns True if we should proceed with saving changes, False otherwise
    """
    if last_request_id is None or force_all_changes:
        return True
    return any(one_edit['request_id'] == last_request_id
               for one_edit in edited_files_info)


def __image_edit_request_params(passcode: str) -> Optional[ImageEditParams]:
    """ Gets and validates the request parameters for an image edit complete request
    Arguments:
        passcode: the working passcode
    Return:
        Returns the request parameters in ImageEditParams when successful, or None if not
    """
    coll_id = request.form.get('collection')
    upload_id = request.form.get('upload')
    path_encrypted = request.form.get('path')
    last_reqid = request.form.get('lastReqid')

    if not all(item for item in [coll_id, upload_id, path_encrypted]):
        return None

    path = crypt.do_decrypt(passcode, path_encrypted)
    if upload_id not in path or coll_id not in path:
        return None

    return ImageEditParams(coll_id=coll_id, upload_id=upload_id,
                           path_encrypted=path_encrypted, path=path,
                           last_reqid=last_reqid)


def __images_all_edited_params(user_name: str) -> Optional[ImageAllEditedParams]:
    """ Gets and validates the request parameters for an images all edited request
    Arguments:
        user_name: the user's name
    Return:
        Returns the request parameters in ImageAllEditedParams when successful, and None if not
    """
    coll_id = request.form.get('collection', None)
    upload_id = request.form.get('upload', None)
    last_request_id = request.form.get('requestId', None)
    timestamp = request.form.get('timestamp', datetime.datetime.now().isoformat())
    force_all_changes = request.form.get('force', None)

    # Check what we have from the requestor
    if not all(item for item in [coll_id, upload_id]):
        return "Not Found", 406

    if force_all_changes is not None and not isinstance(force_all_changes, bool):
        force_all_changes = sdu.make_boolean(force_all_changes)
    elif force_all_changes is None:
        force_all_changes = False

    return ImageAllEditedParams(coll_id=coll_id, upload_id=upload_id,
                                last_request_id=last_request_id, timestamp=timestamp,
                                force_all_changes=force_all_changes,
                                user_name=user_name)



def __make_edit_response(params: ImageEditParams, success: bool,
                         message: str, retry: bool, error: bool) -> dict:
    """ Builds a standard image edit response dict
    Arguments:
        params: the image edit parameters
        success: whether the edit was successful
        message: the message to return
        retry: whether the client should retry
        error: whether there was an error
    Return:
        Returns a dict containing the response information
    """
    return {'success': success,
            'retry': retry,
            'message': message,
            'error': error,
            'collection': params.coll_id,
            'upload_id': params.upload_id,
            'path': params.path_encrypted,
            'filename': os.path.basename(params.path)}


def __update_metadata_and_collection(db: SPARCdDatabase,
                                     s3_info: S3Info,
                                     s3_bucket: str,
                                     s3_path: str,
                                     params: ImageAllEditedParams) -> tuple:
    """ Updates upload metadata and collection after image edits
    Arguments:
        db: the database instance
        s3_info: the S3 endpoint information
        s3_bucket: the S3 bucket
        s3_path: the S3 path
        params: the images all edited parameters
    Return:
        Returns a tuple of (updated, kept_urls) booleans
    """
    all_images, kept_urls = sdc.get_upload_images(db, s3_bucket, params.coll_id,
                                                  params.upload_id, s3_info,
                                                  force_refresh=True, keep_image_url=True)

    image_with_species = sum(1 for one_image in all_images
                             if 'species' in one_image and len(one_image['species']) > 0)

    edit_comment = f'Edited by {params.user_name} on ' + \
                   datetime.datetime.fromisoformat(params.timestamp).strftime("%Y.%m.%d.%H.%M.%S")

    updated, _ = S3UploadConnection.update_upload_metadata(s3_info, s3_bucket, s3_path,
                                                     edit_comment, image_with_species)
    if updated:
        updated_collection = S3CollectionConnection.get_collection_info(s3_info, s3_bucket)
        if updated_collection:
            sdc.collection_update(db, s3_info.id, sdupu.normalize_collection(updated_collection))

    return updated, kept_urls


def __update_observations(s3_info: S3Info,
                          s3_bucket: str,
                          s3_path: str,
                          edited_files_info: list,
                          timestamp: str) -> None:
    """ Updates the observations CSV file with edited image information
    Arguments:
        s3_info: the S3 endpoint information
        s3_bucket: the S3 bucket
        s3_path: the S3 path
        edited_files_info: the list of edited file information
        timestamp: the timestamp of the edit
    """
    deployment_info = ctu.load_camtrap_deployments(s3_info, s3_bucket, s3_path, True)
    obs_info = ctu.load_camtrap_observations(s3_info, s3_bucket, s3_path, True)

    for one_file in edited_files_info:
        obs_info = ctu.update_observations(s3_path, obs_info,
                        [one_species | {'filename': one_file['filename'],
                                        'timestamp': timestamp}
                         for one_species in one_file['species']],
                        deployment_info[0][camtrap.CAMTRAP_DEPLOYMENT_ID_IDX])

    row_groups = (obs_info[one_key] for one_key in obs_info)
    S3UploadConnection.upload_camtrap_data(s3_info, s3_bucket,
                                     make_s3_path((s3_path, OBSERVATIONS_CSV_FILE_NAME)),
                                     [one_row for one_set in row_groups for one_row in one_set])


def handle_image_species(db: SPARCdDatabase, user_info: UserInfo,
                                            s3_info: S3Info, passcode: str) -> Union[bool, None]:
    """ Implementation for adding an species entry for a file into the database
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        passcode: the working passcode
    Return:
        Returns True if the database could be successfully updated, and False otherwise. If the
        image path is invalid, None is returned
    """
    # Get the rest of the request parameters
    timestamp = request.form.get('timestamp')
    coll_id = request.form.get('collection')
    upload_id = request.form.get('upload')
    path = request.form.get('path') # Image path on S3 under bucket
    common_name = request.form.get('common')
    scientific_name = request.form.get('species') # Scientific name
    count = request.form.get('count')
    reqid = request.form.get('reqid', 0)  # Unique request identifier keeps track of requests

    # Check what we have from the requestor
    if not all(item for item in [timestamp, coll_id, upload_id, path, common_name, \
                                                                        scientific_name, count]):
        return False

    path = crypt.do_decrypt(passcode, path)
    if upload_id not in path or coll_id not in path:
        return None

    bucket = SPARCD_PREFIX + coll_id

    db.add_image_species_edit(s3_info.id, bucket, path, user_info.name, timestamp,
                                                common_name, scientific_name, count, str(reqid))

    return True


def handle_image_edit_complete(db: SPARCdDatabase, user_info: UserInfo, s3_info: S3Info, \
                                    passcode: str, temp_species_filename: str) -> Optional[dict]:
    """ Implementation for updating one image with the changes made
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        passcode: the working passcode
        temp_species_filename: the filename of the temporary species storeage
    Return:
        Returns the dict of information to return to the server, or None if there's a problen
    """
    params = __image_edit_request_params(passcode)
    if not params:
        return None

    edit_files_info = db.get_next_files_info(s3_info.id, user_info.name, params.path)
    if not edit_files_info:
        return __make_edit_response(params, success=True, retry=True, error=False,
                                    message='No changes found for file')

    if not __has_last_edit(edit_files_info, params.last_reqid):
        return __make_edit_response(params, success=True, retry=True, error=False,
                                    message=f'All edits have not been received yet '
                                            f'({params.last_reqid})')

    edit_files_info = [one_file | {'name': one_file['s3_path']
                       [one_file['s3_path'].index(params.upload_id) + len(params.upload_id) + 1:]}
                       for one_file in edit_files_info]

    success_files, errored_files = sdupu.process_upload_changes(s3_info,
                                                sdupu.UploadChangeParams(
                                                        collection_id=params.coll_id,
                                                        upload_name=params.upload_id,
                                                        species_timed_file=temp_species_filename,
                                                        files_info=edit_files_info
                                                )
                                            )
    if success_files:
        db.complete_image_edits(user_info.name, success_files)

    if errored_files:
        return __make_edit_response(params, success=False, retry=True, error=True,
                                    message='Not all the edits could be completed')

    return {'success': True, 'message': 'The images have been successfully updated', 'error': False}


def handle_images_all_edited(db: SPARCdDatabase, user_info: UserInfo,
                                                                s3_info: S3Info) -> Optional[tuple]:
    """ Implementation for completing changes after all images have been edited
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
    Return:
        Returns a tuple containing a boolean indicating whether (True) or not (False) information
        was updated with None being returned if there's a problem, and another bool indication
        indicating if the image URLs were updated (True) or kept the same (False) or None if there
        was a problem
    """
    # Get the rest of the request parameters
    params = __images_all_edited_params(user_info.name)
    if not params:
        return None

    # Get any and all changes
    edited_files_info = db.get_edited_files_info(s3_info.id, user_info.name, params.upload_id, True)

    if not edited_files_info:
        return {'success': True, 'retry': True, 'foundEdits': 0,  \
                'message': "No changes found for to the upload", \
                'collection': params.coll_id, 'upload_id': params.upload_id
               }

    if not __has_last_edit_or_forced(edited_files_info, params.last_request_id,
                                                                        params.force_all_changes):
        return {'success': True, 'retry': True, 'foundEdits': len(edited_files_info),  \
                'message': "Last change not found for to the upload", \
                'collection': params.coll_id, 'upload_id': params.upload_id}

    # Update the image and the observations information
    edited_files_info = [one_file|{'filename': one_file['s3_path']\
                            [one_file['s3_path'].index(params.upload_id)+len(params.upload_id)+1:]}\
                                for one_file in edited_files_info]

    s3_bucket = SPARCD_PREFIX + params.coll_id
    s3_path = make_s3_path((COLLECTIONS_FOLDER, params.coll_id, S3_UPLOADS_PATH_PART,
                                                                                params.upload_id))

    # Start updating the CAMTRAP information starting with observations
    __update_observations(s3_info, s3_bucket, s3_path, edited_files_info, params.timestamp)

    db.finish_image_edits(user_info.name, edited_files_info)

    # Update the upload metadata and and save the collection information
    updated, kept_urls = __update_metadata_and_collection(db, s3_info, s3_bucket,
                                                          s3_path, params)

    return bool(updated), kept_urls


def handle_species_keybind(db: SPARCdDatabase, user_info: UserInfo, s3_info: S3Info,
                                        temp_species_filename: str) -> bool:
    """ Implementation for updating a user's species keybind
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        temp_species_filename: the name of the temporary species file
    Return:
        Returns True if updating the keybinding worked out, and False if not
    """
    # Get the rest of the request parameters
    common = request.form.get('common') # Species name
    scientific = request.form.get('scientific') # Species scientific name
    new_key = request.form.get('key')

    # Check what we have from the requestor
    if not common or not scientific or not new_key:
        return False

    # Get the species
    if user_info.species:
        cur_species = user_info.species
    else:
        cur_species = s3u.load_sparcd_config(SPECIES_JSON_FILE_NAME,
                                            temp_species_filename,
                                            s3_info)

    # Update the species
    found = False
    for one_species in cur_species:
        if one_species['scientificName'] == scientific:
            one_species['keyBinding'] = new_key[0]
            found = True
            break

    # Add entry if it's not in the species
    if not found:
        cur_species.append({'name':common, 'scientificName':scientific, 'keyBinding':new_key[0], \
                                            "speciesIconURL": "https://i.imgur.com/4qz5mI0.png"})

    db.save_user_species(s3_info.id, user_info.name, json.dumps(cur_species))

    return True


def handle_image_timestamp(s3_info: S3Info, passcode: str) -> Union[datetime.datetime, bool, None]:
    """ Implementation of fetching the first found timestamp in a file on S3
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        passcode: the working passcode
    Return:
        Returns the first found timestamp when successful, False is returned if there's a problem
        with the request, and None if unable to get a timestamp
    """
    # Get the rest of the request parameters
    collection_id = request.form.get('collection')
    upload_id = request.form.get('upload')
    all_files = request.form.get('files')

    # Check for mandatory parameters
    if not all([collection_id, upload_id, all_files]):
        return False

    all_files = sdu.get_request_files()
    if all_files is None:
        return False

    # Setup for getting timestamps
    s3_bucket = SPARCD_PREFIX + collection_id

    minio = s3_connect(s3_info)
    if not minio:
        return None

    # Keep trying to get a file timestamp
    file_ts = None
    for one_file in all_files:
        s3_file = crypt.do_decrypt(passcode, one_file)

        # Get the image from the server
        temp_file = tempfile.mkstemp(suffix=os.path.splitext(s3_file)[1],
                                        prefix=SPARCD_PREFIX)
        os.close(temp_file[0])

        if not download_s3_file(minio, s3_bucket, s3_file, temp_file[1]):
            print('Warning: Unable to find file to change timestamp', flush=True)
            # Clean up the temp file
            if os.path.exists(temp_file[1]):
                os.unlink(temp_file[1])
            continue

        # Try to change the timestamp in the image
        new_ts = image_utils.get_image_timestamp(temp_file[1])

        # Clean up the temp file
        if os.path.exists(temp_file[1]):
            os.unlink(temp_file[1])

        if new_ts is not None:
            file_ts = new_ts
            break

    return file_ts


def handle_adjust_timestamp(s3_info: S3Info) -> Union[bool, None]:
    """ Handles the adjust timestamps for the images files request
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
    Return:
        Returns True if everything has worked out, False if there's a problem with
        the parameters, and None if there was a problem
    """
    params = __adjust_timestamp_params()
    if params is None:
        return False

    # If the time adjustments are all zero, we're done
    if all(val == 0 for val in [params.timestamp.year,
                                params.timestamp.month,
                                params.timestamp.day,
                                params.timestamp.hour,
                                params.timestamp.minute,
                                params.timestamp.second]):
        return True

    # If we don't have any files, we're done
    if len(params.files) <= 0:
        return True

    s3_bucket = SPARCD_PREFIX + params.collection_id
    s3_path = make_s3_path((COLLECTIONS_FOLDER, params.collection_id, S3_UPLOADS_PATH_PART,
                                                                                params.upload_id))

    # Get the media file so we can update - use the file name as the index
    media_info = ctu.load_camtrap_media(s3_info, s3_bucket, s3_path,
                                                    key_field=camtrap.CAMTRAP_MEDIA_FILE_NAME_IDX)
    if not media_info:
        return None

    # Loop through the file names and update the timestamp both in the file (if possible)
    # and in the media
    time_adjust = relativedelta(year=params.timestamp.year,
                                month=params.timestamp.month,
                                day=params.timestamp.day,
                                hour=params.timestamp.hour,
                                minute=params.timestamp.minute,
                                second=params.timestamp.second)

    new_media_info = sdtsu.adjust_timestamps(params.files,
                                            sdtsu.TimestampAdjustContext(time_adjust=time_adjust,
                                                                        bucket=s3_bucket,
                                                                        s3_info=s3_info,
                                                                        media_info=media_info
                                                                     )

                                            )

    # Upload the MEDIA csv file to the server
    S3UploadConnection.upload_camtrap_data(s3_info,
                                     s3_bucket,
                                     make_s3_path((s3_path, MEDIA_CSV_FILE_NAME)),
                                     new_media_info.values())

    return True
