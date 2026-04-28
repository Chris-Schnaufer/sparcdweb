""" Upload and species change processing utilities for SPARCd server """

import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from typing import Optional

import image_utils
from s3.s3_access_helpers import SPARCD_PREFIX
from s3.s3_images import S3ImageConnection
from s3.s3_uploads import S3UploadConnection
from spd_types.s3info import S3Info

# Allowed movie extensions for upload
UPLOAD_KNOWN_MOVIE_EXT = ['.mp4', '.mov', '.avi']


@dataclass
class UploadChangeParams:
    """ Parameters describing what changes to apply to an upload """
    collection_id: str
    upload_name: str
    species_timed_file: str
    change_locations: Optional[dict] = None
    files_info: Optional[tuple] = None


@dataclass
class UploadEditContext:
    """ Internal class with constant context shared across all files in a single upload
        edit operation """
    edit_folder: str
    file_info_dict: dict
    change_locations: Optional[dict]


def get_later_timestamp(cur_ts: object, new_ts: object) -> Optional[object]:
    """ Returns the later of the two dates
    Arguments:
        cur_ts: the date and time to compare against
        new_ts: the date and time to check if it's later
    Return:
        Returns the later date. If cur_ts is None, then new_ts is returned.
        If new_ts is None, then cur_ts is returned
    """
    # pylint: disable=too-many-return-statements,too-many-branches
    if cur_ts is None:
        return new_ts
    if new_ts is None:
        return cur_ts

    if 'date' in cur_ts and 'date' in new_ts and cur_ts['date'] and new_ts['date']:
        if 'year' in cur_ts['date'] and 'year' in new_ts['date']:
            if int(cur_ts['date']['year']) < int(new_ts['date']['year']):
                return new_ts
        if 'month' in cur_ts['date'] and 'month' in new_ts['date']:
            if int(cur_ts['date']['month']) < int(new_ts['date']['month']):
                return new_ts
        if 'day' in cur_ts['date'] and 'day' in new_ts['date']:
            if int(cur_ts['date']['day']) < int(new_ts['date']['day']):
                return new_ts

    if 'time' in cur_ts and 'time' in new_ts and cur_ts['time'] and new_ts['time']:
        if 'hour' in cur_ts['time'] and 'hour' in new_ts['time']:
            if int(cur_ts['time']['hour']) < int(new_ts['time']['hour']):
                return new_ts
        if 'minute' in cur_ts['time'] and 'minute' in new_ts['time']:
            if int(cur_ts['time']['minute']) < int(new_ts['time']['minute']):
                return new_ts
        if 'second' in cur_ts['time'] and 'second' in new_ts['time']:
            if int(cur_ts['time']['second']) < int(new_ts['time']['second']):
                return new_ts
        if 'nano' in cur_ts['time'] and 'nano' in new_ts['time']:
            if int(cur_ts['time']['nano']) < int(new_ts['time']['nano']):
                return new_ts

    return cur_ts


def format_upload_date(date_json: object) -> str:
    """ Returns the date string from an upload's date JSON
    Arguments:
        date_json: the JSON containing the 'date' and 'time' objects
    Returns:
        Returns the formatted date and time, or an empty string if a problem is found
    """
    return_str = ''

    if 'date' in date_json and date_json['date']:
        cur_date = date_json['date']
        if 'year' in cur_date and 'month' in cur_date and 'day' in cur_date:
            return_str += f'{cur_date["year"]:4d}-{cur_date["month"]:02d}-{cur_date["day"]:02d}'

    if 'time' in date_json and date_json['time']:
        cur_time = date_json['time']
        if 'hour' in cur_time and 'minute' in cur_time:
            return_str += f' at {cur_time["hour"]:02d}:{cur_time["minute"]:02d}'

    return return_str


def normalize_upload(upload_entry: dict) -> dict:
    """ Normalizes an S3 upload
    Arguments:
        upload_entry: the upload to normalize
    Return:
        The normalized upload
    """
    return_entry = {'name': upload_entry['info']['uploadUser'] + ' on ' +
                            format_upload_date(upload_entry['info']['uploadDate']),
                    'description': upload_entry['info']['description'],
                    'imagesCount': upload_entry['info']['imageCount'],
                    'imagesWithSpeciesCount': upload_entry['info']['imagesWithSpecies'],
                    'location': upload_entry['location'],
                    'edits': upload_entry['info']['editComments'],
                    'key': upload_entry['key'],
                    'date': upload_entry['info']['uploadDate'],
                    'folders': upload_entry['uploaded_folders']}

    return_entry.update({'complete': upload_entry['complete']}
                        if 'complete' in upload_entry else {})
    return_entry.update({'path': upload_entry['path']}
                        if 'path' in upload_entry else {})
    return_entry.update({'uploadUser': upload_entry['info']['uploadUser']})

    return return_entry


def normalize_collection(coll: dict) -> dict:
    """ Takes a collection from the S3 instance and normalizes the data for the website
    Arguments:
        coll: the collection to normalize
    Return:
        The normalized collection
    """
    cur_col = {'name': coll['nameProperty'],
               'bucket': coll['bucket'],
               'organization': coll['organizationProperty'],
               'email': coll['contactInfoProperty'],
               'description': coll['descriptionProperty'],
               'id': coll['idProperty'],
               'permissions': coll['permissions'],
               'allPermissions': coll['all_permissions'],
               'uploads': []}

    cur_uploads = []
    last_upload_date = None
    for one_upload in coll['uploads']:
        last_upload_date = get_later_timestamp(last_upload_date,
                                               one_upload['info']['uploadDate'])
        cur_uploads.append(normalize_upload(one_upload))

    cur_col['uploads'] = cur_uploads
    cur_col['last_upload_ts'] = last_upload_date
    return cur_col


def __apply_species_edits(cur_species: list, file_edits: dict) -> Optional[list]:
    """ Merges species edits into the current species list
    Arguments:
        cur_species: the current species list from the image
        file_edits: the edits to apply containing a 'species' list
    Return:
        Returns the updated species list if any changes were made, or None if unchanged.
        Species with a count of zero are removed from the result.
    """
    changed = False
    for new_species in file_edits['species']:
        found = False
        for orig_species in cur_species:
            if orig_species['scientific'] == new_species['scientific']:
                if orig_species['common'] != new_species['common']:
                    orig_species['common'] = new_species['common']
                    changed = True
                if orig_species['count'] != new_species['count']:
                    orig_species['count'] = new_species['count']
                    changed = True
                found = True
                break

        if not found:
            cur_species.append({'common': new_species['common'],
                                 'scientific': new_species['scientific'],
                                 'count': new_species['count']})
            changed = True

    if not changed:
        return None

    return [s for s in cur_species if int(s['count']) > 0]


def __process_upload_file(s3_info: S3Info, one_file: dict, idx: int,
                          context: UploadEditContext) -> tuple:
    """ Downloads, edits, and re-uploads a single image file
    Arguments:
        s3_info: the S3 connection information
        one_file: the file info dict containing name, s3_path, and bucket
        idx: the index of the file used to create a unique temp filename
        context: the shared edit context containing folder, edits lookup, and location change
    Return:
        Returns a tuple of (success: bool, file_or_error: dict) where file_or_error
        is the file dict on success or the error entry on failure
    """
    file_ext = os.path.splitext(one_file['s3_path'])[1].lower()
    temp_file_name = ('-' + str(idx)).join(
        os.path.splitext(os.path.basename(one_file['s3_path'])))
    save_path = os.path.join(context.edit_folder, temp_file_name)
    file_key = one_file['name'] + one_file['s3_path'] + one_file['bucket']
    file_edits = context.file_info_dict.get(file_key)

    if not file_edits and not context.change_locations:
        return True, one_file

    if file_ext not in UPLOAD_KNOWN_MOVIE_EXT:
        S3ImageConnection.download_image(s3_info, one_file['bucket'],
                                         one_file['s3_path'], save_path)
        cur_species, cur_location, _ = image_utils.get_embedded_image_info(save_path)
        cur_species = cur_species or []
    else:
        cur_species, cur_location = [], None

    save_species = __apply_species_edits(cur_species, file_edits) if file_edits else None

    save_location = None
    if context.change_locations and (cur_location is None or
                                     context.change_locations['loc_id'] != cur_location['id']):
        save_location = image_utils.ImageLocationData(
            loc_id=context.change_locations['loc_id'],
            loc_name=context.change_locations['loc_name'],
            loc_ele=context.change_locations['loc_ele'],
            loc_lat=context.change_locations['loc_lat'],
            loc_lon=context.change_locations['loc_lon']
        )

    if not save_species and not save_location:
        return True, one_file

    if file_ext in UPLOAD_KNOWN_MOVIE_EXT:
        return True, one_file

    if image_utils.update_image_file_exif(save_path, location=save_location,
                                           species_data=save_species):
        S3UploadConnection.upload_file(s3_info, one_file['bucket'],
                                       one_file['s3_path'], save_path)
        result = True, one_file
    else:
        result = False, context.file_info_dict.get(file_key, one_file | {'species': []})

    for cleanup_path in [save_path + '_original', save_path]:
        if cleanup_path and os.path.exists(cleanup_path):
            os.unlink(cleanup_path)

    return result


def process_upload_changes(s3_info: S3Info, params: UploadChangeParams) -> tuple:
    """ Updates the image files with the information passed in
    Argument:
        s3_info: the information for the S3 endpoint
        params: the parameters describing what changes to apply and where
    Return:
        Returns a tuple of (success_files, failed_files). If a location is specified,
        failed_files can include files not found in the original list
    """
    file_info_dict = {f['name'] + f['s3_path'] + f['bucket']: f
                      for f in params.files_info} if params.files_info else {}

    update_files = params.files_info if not params.change_locations else \
        S3ImageConnection.get_image_paths(s3_info, params.collection_id, params.upload_name)

    context = UploadEditContext(
        edit_folder=tempfile.mkdtemp(prefix=SPARCD_PREFIX + 'edits_' + uuid.uuid4().hex),
        file_info_dict=file_info_dict,
        change_locations=params.change_locations
    )
    success_files = []
    failed_files = []

    try:
        for idx, one_file in enumerate(update_files):
            succeeded, result = __process_upload_file(s3_info, one_file, idx, context)
            (success_files if succeeded else failed_files).append(result)
    finally:
        shutil.rmtree(context.edit_folder)

    return success_files, failed_files
