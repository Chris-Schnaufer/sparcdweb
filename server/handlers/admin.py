""" Functions to handle requests starting with /image for SPARCd server """

from dataclasses import dataclass
import json
from typing import Optional, Union

from flask import request

import sparcd_collections as sdc
from sparcd_db import SPARCdDatabase
from spd_types.userinfo import UserInfo
from spd_types.s3info import S3Info
import sparcd_utils as sdu
from s3_access import S3Connection, SPECIES_JSON_FILE_NAME, SPARCD_PREFIX
import s3_utils as s3u
from text_formatters.coordinate_utils import deg2utm, deg2utm_code, utm2deg


# Convertion factor of feet to metes
FEET_TO_METERS = 0.3048000097536



@dataclass
class LocationUtmInfo:
    """ Internal class which contains the UTM coordinate information for a location request """
    utm_zone: Optional[str]
    utm_letter: Optional[str]
    utm_x: Optional[str]
    utm_y: Optional[str]


@dataclass
class LocationCoordInfo:
    """ Internal class which contains the coordinate information for a location request """
    coordinate: Optional[str]
    new_lat: Optional[str]
    new_lng: Optional[str]
    old_lat: Optional[str]
    old_lng: Optional[str]
    utm: LocationUtmInfo


@dataclass
class LocationEditParams:
    """ Internal class which contains the parameters for a location edit request """
    loc_id: Optional[str]
    loc_name: Optional[str]
    loc_active: Optional[str]
    measure: Optional[str]
    loc_ele: Optional[str]
    description: Optional[str]
    coords: LocationCoordInfo


@dataclass
class CollectionEditParams:
    """ Internal class which contains the parameters for a collection edit request """
    col_id: str
    col_name: str
    col_desc: str
    col_email: str
    col_org: str
    col_all_perms: str


def __check_incomplete_param() -> Optional[str]:
    """ Returns the verified parameter for checking incomplete uploads
    Return:
        Returns the collections list upon success, None if there is a problem
        with the parameter
    """
    cur_colls = request.form.get('collections', None)
    if cur_colls is None:
        return None

    # Get the list of collections
    try:
        cur_colls = json.loads(cur_colls)
    except json.JSONDecodeError as ex:
        print('ERROR: Received invalid collections list to check for incomplete uploads',flush=True)
        print(ex, flush=True)
        return None

    return cur_colls


def __check_location_edit_params(params: LocationEditParams) -> bool:
    """ Checks the parameters for the needed consistency
    Arguments:
        params: the Parameters to check
    Return:
        Returns True if the parameters are consistent and False if not
    """
    # Check what we have from the requestor
    if not all(item for item in [params.loc_name, params.loc_id, params.loc_active, \
                                                        params.measure, params.coords.coordinate]):
        return False
    if params.measure not in ['feet', 'meters'] or \
                                                params.coords.coordinate not in ['UTM', 'LATLON']:
        return False
    if params.coords.coordinate == 'UTM' and \
            not all(item for item in [params.coords.utm.utm_zone, params.coords.utm.utm_letter, \
                                                params.coords.utm.utm_x, params.coords.utm.utm_y]):
        return False
    if not all(item for item in [params.coords.new_lat, params.coords.new_lng]):
        return False
    if params.loc_ele is None:
        return False

    return True


def __collection_update_request_params() -> Optional[CollectionEditParams]:
    """ Gets and validates the collection update parameters for editing
    Return:
        Returns the parameters in CollectionEditParams when successful and None if validation
        fails
    """
    # Get the rest of the request parameters
    params = CollectionEditParams(
                        col_id = request.form.get('id'),
                        col_name = request.form.get('name'),
                        col_desc = request.form.get('description', ''),
                        col_email = request.form.get('email', ''),
                        col_org = request.form.get('organization', ''),
                        col_all_perms = request.form.get('allPermissions')
                    )

    # Check what we have from the requestor
    if not all(item for item in [params.col_id, params.col_name, params.col_all_perms]):
        return None

    return params


def __location_update_request_params() -> Optional[LocationEditParams]:
    """ Gets and valudates the request parameters for a location edit request
    Return:
        Returns the request parameters in LocationEditParams
    """
    utm = LocationUtmInfo(
        utm_zone=request.form.get('utm_zone'),
        utm_letter=request.form.get('utm_letter'),
        utm_x=request.form.get('utm_x'),
        utm_y=request.form.get('utm_y')
    )
    coords = LocationCoordInfo(
        coordinate=request.form.get('coordinate'),
        new_lat=request.form.get('new_lat'),
        new_lng=request.form.get('new_lon'),
        old_lat=request.form.get('old_lat'),
        old_lng=request.form.get('old_lon'),
        utm=utm
    )
    params = LocationEditParams(
        loc_id=request.form.get('id'),
        loc_name=request.form.get('name'),
        loc_active=request.form.get('active'),
        measure=request.form.get('measure'),
        loc_ele=request.form.get('elevation'),
        description=request.form.get('description'),
        coords=coords
    )

    if not __check_location_edit_params(params):
        return None

    # Change data to a format we can use (also used to check what we've received)
    try:
        params.loc_ele = float(params.loc_ele)
        if params.coords.new_lat:
            params.coords.new_lat = float(params.coords.new_lat)
        if params.coords.new_lng:
            params.coords.new_lng = float(params.coords.new_lng)
        if params.coords.old_lat:
            params.coords.old_lat = float(params.coords.old_lat)
        if params.coords.old_lng:
            params.coords.old_lng = float(params.coords.old_lng)
    except ValueError:
        return None

    if params.loc_active is not None:
        if isinstance(params.loc_active, str):
            params.loc_active = params.loc_active.upper() == 'TRUE'
        else:
            params.loc_active = bool(params.loc_active)
    else:
        params.loc_active = None

    return params


def __validate_collection_update_params(user_info: UserInfo,
                                        must_be_admin: bool) -> Optional[CollectionEditParams]:
    """ Validates and returns the collection update request parameters
    Arguments:
        user_info: the user information
        must_be_admin: set to False if the user shouldn't be an admin
    Return:
        Returns the validated parameters, or None if validation fails
    """
    if bool(user_info.admin) != must_be_admin:
        return None

    params = __collection_update_request_params()
    if params is None:
        return None

    try:
        params.col_all_perms = json.loads(params.col_all_perms)
    except json.JSONDecodeError as ex:
        print(f'Unable to convert permissions for collection update: '
              f'{params.col_id} {user_info.name}', flush=True)
        print(ex)
        return None

    if not params.col_all_perms:
        return None

    return params


def handle_admin_collection_details(db: SPARCdDatabase, user_info: UserInfo, s3_info: S3Info,
                                                must_be_admin: bool=True) -> Union[dict,bool, None]:
    """ Implementation for getting collection details
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        must_be_admin: set to False if the user shouldn't be an admin
    Return:
        Returns the loaded collection data upon success. Returns False if there's a problem with
        the request paramters. None is returned if the collection can't be found and the user is
        an administrator, otherwise False is returned if the collection can't be found
    """
    bucket = request.form.get('bucket', None)
    if bucket is None:
        return False

    # Check if the user has the correct admin permissions level
    is_admin = bool(user_info.admin)
    if is_admin != must_be_admin:
        return False

    # Get the collection information
    collection = None

    return_colls = sdc.load_collections(db, is_admin, s3_info)
    if return_colls:
        found_colls = [one_coll for one_coll in return_colls if one_coll['bucket'] == bucket]
        if found_colls:
            collection = found_colls[0]

    if not collection:
        collection = S3Connection.get_collection_info(s3_info, bucket)
        if collection:
            collection = sdu.normalize_collection(collection)

    if not collection:
        return None if is_admin else False

    # If we're not an admin, we need to have collection level permissions
    if not is_admin:
        if not collection['permissions']['usernameProperty'] == user_info.name or not \
                                                collection['permissions']['ownerProperty'] is True:
            return False


    return collection


def handle_admin_location_details(user_info: UserInfo, s3_info: S3Info) -> Union[dict,bool, None]:
    """ Implementation for getting location details for administrators
    Arguments:
        user_info: the user information
        s3_info: the S3 endpoint information
    Return:
        Returns the location information identified in the request upon success. False
        is returned if there is a problem with the request parameterss. None is returned
        if the location can't be found
    """
    # Make sure this user is an admin
    if not bool(user_info.admin):
        return False

    loc_id = request.form.get('id', None)
    if loc_id is None:
        return False

    # Get the location information
    location = None

    cur_locations = sdu.load_locations(s3_info, True)

    if cur_locations:
        found_locs = [one_loc for one_loc in cur_locations if one_loc['idProperty'] == loc_id]
        if found_locs:
            location = found_locs[0]

    return location


def handle_admin_users(db:SPARCdDatabase, user_info: UserInfo,
                                                        s3_info: S3Info) -> Union[tuple,bool, None]:
    """ Implementation of getting user details when an administrator
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
    Return:
        Returns a tuple of the user details when successful. False is returned if there was a
        problem with the request parameters. None is returned if the request couldn't be
        completed
    """
    is_admin = bool(user_info.admin)

    # Make sure this user is an admin
    if not is_admin:
        return False

    # Get the users and fill in the collection information
    all_users = db.get_admin_edit_users(s3_info.id)

    if not all_users:
        return []

    # Organize the collection permissions by user
    all_collections = sdc.load_collections(db, is_admin, s3_info)
    user_collections = {}
    if all_collections:
        for one_coll in all_collections:
            if 'allPermissions' in one_coll and one_coll['allPermissions'] is not None:
                for one_perm in one_coll['allPermissions']:
                    if one_perm['usernameProperty'] not in user_collections:
                        user_collections[one_perm['usernameProperty']] = []
                    user_collections[one_perm['usernameProperty']].append({
                        'name':one_coll['name'],
                        'id':one_coll['id'],
                        'owner':one_perm['ownerProperty'] if 'ownerProperty' in \
                                                                        one_perm else False,
                        'read':one_perm['readProperty'] if 'readProperty' in \
                                                                        one_perm else False,
                        'write':one_perm['uploadProperty'] if 'uploadProperty' in \
                                                                        one_perm else False,
                        })

    # Put it all together
    return_users = []
    for one_user in all_users:
        return_users.append({'name': one_user[0], 'email': sdu.secure_email(one_user[1]), \
                         'admin': one_user[2] == 1, 'autoAdded': one_user[3] == 1,
                         'collections': user_collections[one_user[0]] if \
                                    user_collections and one_user[0] in user_collections else []})

    return return_users


def handle_admin_species(user_info: UserInfo,
                            s3_info: S3Info, species_temp_filename: str) -> Union[tuple,bool, None]:
    """ Implementation of getting species details when an administrator
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        species_temp_filename: the temporary filename used to store species information
    Return:
        Returns a tuple of the species details when successful. False is returned if there was a
        problem with the request parameters. None is returned if the request couldn't be
        completed
    """
    is_admin = bool(user_info.admin)

    # Make sure this user is an admin
    if not is_admin:
        return None

    cur_species = s3u.load_sparcd_config(SPECIES_JSON_FILE_NAME,
                                         species_temp_filename,
                                         s3_info)

    return cur_species


def handle_user_update(db:SPARCdDatabase, user_info: UserInfo,
                                                        s3_info: S3Info) -> Union[dict,bool, None]:
    """ Implementation of updating user details when an administrator
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
    Return:
        Returns a status dict when successful. False is returned if there was
        a problem with the request parameters. None is returned if the request couldn't be
        completed
    """
    # Make sure the user requesting the change is an admin
    if not bool(user_info.admin):
        return None

    # Get the rest of the request parameters
    old_name = request.form.get('oldName')
    new_email = request.form.get('newEmail')
    admin = request.form.get('admin')

    # Check what we have from the requestor
    if not old_name or new_email is None:
        return False

    old_user_info = db.get_user(s3_info.id, old_name)
    if old_user_info is None:
        return {'success': False, 'message': f'User "{old_name}" not found'}

    if admin is not None:
        admin = sdu.make_boolean(admin)

    db.update_user(s3_info.id, old_name, new_email, admin)

    return {'success': True, 'message': f'Successfully updated user "{old_name}"', \
            'email': sdu.secure_email(new_email)}


def handle_species_update(db:SPARCdDatabase, user_info: UserInfo,
                            s3_info: S3Info, species_temp_filename: str) -> Union[tuple,bool, None]:
    """ Implementation of updating species details when an administrator
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        species_temp_filename: the temporary filename used to store species information
    Return:
        Returns a status dict when successful. False is returned if there was
        a problem with the request parameters. None is returned if the request couldn't be
        completed
    """
    # Make sure this user is an admin
    if not bool(user_info.admin):
        return None

    # Get the rest of the request parameters
    new_name = request.form.get('newName')
    old_scientific = request.form.get('oldScientific')
    new_scientific = request.form.get('newScientific')
    key_binding = request.form.get('keyBinding', '')
    icon_url = request.form.get('iconURL')

    # Check what we have from the requestor
    if not all(item for item in [new_name, new_scientific, icon_url]):
        return False

    # Get the species
    cur_species = s3u.load_sparcd_config(SPECIES_JSON_FILE_NAME,
                                            species_temp_filename,
                                            s3_info)

    # Make sure this is OK to do
    find_scientific = old_scientific if old_scientific else new_scientific
    found_match = [one_species for one_species in cur_species if \
                                                one_species['scientificName'] == find_scientific]

    # If we're replacing, we should have found the entry
    if old_scientific is not None and (not found_match or len(found_match) <= 0):
        return {'success': False, 'message': f'Species "{old_scientific}" not found'}
    # If we're not replaceing, we should NOT find the entry
    if old_scientific is None and (found_match and len(found_match) > 0):
        return {'success': False, 'message': f'Species "{new_scientific}" already exists'}

    # Put the change in the DB
    if db.update_species(s3_info.id, user_info.name, old_scientific, new_scientific, \
                                                                new_name, key_binding, icon_url):
        return {'success': True, 'message': f'Successfully updated species "{find_scientific}"'}

    return {'success': False, \
                'message': f'A problem ocurred while updating species "{find_scientific}"'}


def handle_location_update(db:SPARCdDatabase, user_info: UserInfo,
                                                        s3_info: S3Info) -> Union[tuple,bool, None]:
    """ Implementation of updating species details when an administrator
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
    Return:
        Returns a status dict when successful. False is returned if there was
        a problem with the request parameters. None is returned if the request couldn't be
        completed
    """
    # Make sure this user is an admin
    if not bool(user_info.admin):
        return None

    params = __location_update_request_params()
    if not params:
        return False

    # Get the locations to work with
    cur_locations = sdu.load_locations(s3_info, True)

    # Make sure this is OK to do by finding the location
    if params.coords.old_lat and params.coords.old_lng:
        found_match = [one_location for one_location in cur_locations if \
                                one_location['idProperty'] == params.loc_id and
                                float(one_location['latProperty']) == params.coords.old_lat and
                                float(one_location['lngProperty']) == params.coords.old_lng]

        # If we're replacing, we should have found the entry
        if not found_match or len(found_match) <= 0:
            return {'success': False, 'message': f'Location {params.loc_id} not found ' \
                        f'with Lat/Lon {params.coords.old_lat}, {params.coords.old_lng}'}
    else:
        found_match = [one_location for one_location in cur_locations if \
                                one_location['idProperty'] == params.loc_id and
                                float(one_location['latProperty']) == params.coords.new_lat and
                                float(one_location['lngProperty']) == params.coords.new_lng]

        # If we're not replacing, we should NOT find the entry
        if found_match and len(found_match) > 0:
            return {'success': False, 'message': f'Location {params.loc_id} already exists with ' \
                        f'Lat/Lon {params.coords.new_lat}, {params.coords.new_lng}'}

    # Convert elevation to meters if needed
    if params.measure.lower() == 'feet':
        params.loc_ele = round((params.loc_ele * FEET_TO_METERS) * 100) / 100

    # Convert UTM to Lat/Lon if needed
    if params.coords.coordinate == 'UTM':
        params.coords.new_lat, params.coords.new_lng = \
                                    utm2deg(params.coords.utm.utm_x,
                                            params.coords.utm.utm_y,
                                            params.coords.utm.utm_zone,
                                            params.coords.utm.utm_letter)
        utm_code = params.coords.utm.utm_zone+params.coords.utm.utm_letter
    else:
        params.coords.utm.utm_x, params.coords.utm.utm_y = \
                                            deg2utm(params.coords.new_lat, params.coords.new_lng)
        utm_code = ''.join([str(one_item) for one_item in deg2utm_code(params.coords.new_lat,
                                                                       params.coords.new_lng)
                            ])

    # Put the change in the DB
    if db.update_location(s3_info.id,
                          user_info.name,
                          params.loc_name,
                          params.loc_id,
                          params.loc_active,
                          params.loc_ele,
                          params.coords.old_lat,
                          params.coords.old_lng,
                          params.coords.new_lat,
                          params.coords.new_lng,
                          params.description):

        return_lat = round(params.coords.new_lat, 3)
        return_lng = round(params.coords.new_lng, 3)
        return_utm_x, return_utm_y = deg2utm(return_lat, return_lng)
        return {'success': True, 'message': f'Successfully updated location {params.loc_name}',
                'data':{'nameProperty': params.loc_name, 'idProperty': params.loc_id, \
                        'elevationProperty': params.loc_ele, 'activeProperty': params.loc_active, \
                        'latProperty': return_lat, 'lngProperty': return_lng, \
                        'utm_code': utm_code, 'utm_x': int(return_utm_x), 'utm_y': int(return_utm_y)
                        }
                }

    return {'success': False, \
                'message': f'A problem ocurred while updating location {params.loc_name}'}


def handle_collection_update(db:SPARCdDatabase, user_info: UserInfo, s3_info: S3Info,
                                            must_be_admin: bool=True) -> Union[tuple,bool, None]:
    """ Implementation of updating collection details when an administrator
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        must_be_admin: set to False if the user shouldn't be an admin
    Return:
        Returns a status dict when successful. False is returned if there was
        a problem with the request parameters. None is returned if the request couldn't be
        completed
    """
    params = __validate_collection_update_params(user_info, must_be_admin)
    if params is None:
        return False

    is_admin = bool(user_info.admin)
    s3_bucket = SPARCD_PREFIX + params.col_id
    all_collections = sdc.load_collections(db, is_admin, s3_info)

    # Update the entry to what we need
    found_coll = None
    for one_coll in all_collections:
        if one_coll['id'] == params.col_id:
            one_coll['name'] = params.col_name
            one_coll['description'] = params.col_desc
            one_coll['email'] = params.col_email
            one_coll['organization'] = params.col_org
            found_coll = one_coll
            break

    if found_coll is None:
        return {'success': False, 'message': "Unable to find collection in list to update"}

    # Check that the caller has permission to modify
    if not must_be_admin:
        if not found_coll['permissions']['usernameProperty'] == user_info.name or not \
                                                found_coll['permissions']['ownerProperty'] is True:
            return None

    # Upload the changes
    S3Connection.save_collection_info(s3_info, found_coll['bucket'], found_coll)

    S3Connection.save_collection_permissions(s3_info, found_coll['bucket'], params.col_all_perms)

    # Update the collection to reflect the changes
    updated_collection = S3Connection.get_collection_info(s3_info, s3_bucket)
    if updated_collection:
        updated_collection = sdu.normalize_collection(updated_collection)

        # Update the collection entry in the database
        sdc.collection_update(db, s3_info.id, updated_collection)

    return {'success':True, 'data': updated_collection, \
            'message': "Successfully updated the collection"}


def handle_collection_add(db:SPARCdDatabase, user_info: UserInfo, s3_info: S3Info,
                                            must_be_admin: bool=True) -> Union[tuple,bool, None]:
    """ Implementation of adding a collection when an administrator
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        must_be_admin: set to False if the user shouldn't be an admin
    Return:
        Returns a status dict when successful. False is returned if there was
        a problem with the request parameters. None is returned if the request couldn't be
        completed
    """
    # Check if the user has the correct admin permissions level
    is_admin = bool(user_info.admin)
    if is_admin != must_be_admin:
        return False

    # Get the rest of the request parameters
    col_name = request.form.get('name')
    col_desc = request.form.get('description', '')
    col_email = request.form.get('email', '')
    col_org = request.form.get('organization', '')
    col_all_perms = request.form.get('allPermissions')

    # Check what we have from the requestor
    if not all(item for item in [col_name, col_all_perms]):
        return "Not Found", 406

    if col_desc is None:
        col_desc = ''
    if col_email is None:
        col_email = ''
    if col_org is None:
        col_org = ''

    try:
        col_all_perms = json.loads(col_all_perms)
    except json.JSONDecodeError as ex:
        print('Unable to convert permissions for collection update: ' \
                                                f'{col_name} {user_info.name}', flush=True)
        print(ex)
        return False
    if not col_all_perms:
        return False

    # Add the collection
    s3_bucket = S3Connection.add_collection(s3_info,
                                {   'name': col_name,
                                    'description': col_desc,
                                    'email': col_email,
                                    'organization': col_org,
                                },
                                col_all_perms)
    print(f'INFO: Created new collection: {s3_bucket}', flush=True)

    # Update the collection to reflect the changes
    updated_collection = S3Connection.get_collection_info(s3_info, s3_bucket)
    if updated_collection:
        updated_collection = sdu.normalize_collection(updated_collection)

        # Update the collection entry in the database
        sdc.collection_add(db, s3_info.id, updated_collection)

    return {'success':True, 'data': updated_collection, \
            'message': "Successfully updated the collection"}


def handle_check_incomplete(db:SPARCdDatabase, user_info: UserInfo,
                                                        s3_info: S3Info) -> Union[tuple,bool, None]:
    """ Implementation of checking for incomplete uploads when an administrator
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
    Return:
        Returns a status dict when successful. False is returned if there was
        a problem with the request parameters. None is returned if the request couldn't be
        completed
    """
    # Make sure this user is an admin
    if not bool(user_info.admin):
        return None

    # Check the parameters we've received
    cur_colls = __check_incomplete_param()
    if cur_colls is None:
        return None

    # Check if we're all done
    if len(cur_colls) <= 0:
        return {'success': True}

    # Get the locations and species changes logged in the database

    incomplete = S3Connection.check_incomplete_uploads(s3_info, cur_colls)

    if incomplete is None:
        print('ERROR: unable to check for incomplete uploads in indicated collections', cur_colls,
                                                                                        flush=True)
        return {'success': False}

    # Nothing found
    if len(incomplete) == 0:
        return {'success': True}

    # Update the database with unknown incomplete uploads
    db.sandbox_new_incomplete_uploads(s3_info.id, incomplete)

    return {'success': True, 'count':len(incomplete)}


def handle_complete_changes(db:SPARCdDatabase, user_info: UserInfo, s3_info: S3Info,
                                                species_temp_filename: str) -> Union[tuple, None]:
    """ Implementation of completing admin changes
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        species_temp_filename: the temporary filename used to store species information
    Return:
        Returns a status dict when successful. None is returned if the request couldn't be
        completed
    """
    # Make sure this user is an admin
    if not bool(user_info.admin):
        return None

    changes = db.get_admin_changes(s3_info.id, user_info.name)
    if not changes:
        return {'success': True, 'message': "There were no changes found to apply"}

    # Update the location
    if 'locations' in changes and changes['locations']:
        if not sdu.update_admin_locations(s3_info, changes):
            return 'Unable to update the locations', 422
    # Mark the locations as done in the DB
    db.clear_admin_location_changes(s3_info.id, user_info.name)

    # Update the species
    if 'species' in changes and changes['species']:
        updated_species = sdu.update_admin_species(s3_info, changes)
        if updated_species is None:
            return 'Unable to update the species. Any changed locations were updated', 422

        s3u.save_sparcd_config(updated_species, SPECIES_JSON_FILE_NAME,
                                            species_temp_filename,
                                            s3_info)
    # Mark the species as done in the DB
    db.clear_admin_species_changes(s3_info.id, user_info.name)

    return {'success': True, 'message': "All changes were successully applied"}


def handle_abandon_changes(db:SPARCdDatabase, user_info: UserInfo,
                                                            s3_info: S3Info) -> Union[tuple, None]:
    """ Implementation of abandoning admin changes
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
    Return:
        Returns a status dict when successful. None is returned if the request couldn't be
        completed
    """
    # Make sure this user is an admin
    if not bool(user_info.admin):
        return None

    # Mark the locations as done in the DB
    db.clear_admin_location_changes(s3_info.id, user_info.name)

    # Mark the species as done in the DB
    db.clear_admin_species_changes(s3_info.id, user_info.name)

    return {'success': True, 'message': "All changes were successully abandoned"}
