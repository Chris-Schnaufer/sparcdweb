""" Species statistics utilities for SPARCd server """

import concurrent.futures
import json
import os
import tempfile
import time
import traceback
from typing import Optional

import sparcd_collections as sdc
import sparcd_file_utils as sdfu
from s3.s3_collections import S3CollectionConnection
from s3.s3_access_helpers import SPARCD_PREFIX
from sparcd_constants import TEMP_SPECIES_STATS_FILE_NAME_POSTFIX, \
                             TEMP_SPECIES_STATS_FILE_TIMEOUT_SEC
from sparcd_db import SPARCdDatabase
from spd_types.s3info import S3Info

# Uploads table timeout length
TIMEOUT_UPLOADS_SEC = 3 * 60 * 60

# Collection table timeout length
TIMEOUT_COLLECTIONS_FILE_SEC = 12 * 60 * 60
# Name of temporary collections file
TEMP_COLLECTION_FILE_NAME = SPARCD_PREFIX + 'coll.json'

# Maximum tries to get a lock for loading collections
MAX_STAT_FETCH_TRIES = 10
# Maximum number of seconds to wait for collections to get loaded before giving up
MAX_STAT_FETCH_WAIT_SEC = 5 * 60
# Sleep interval value while waiting for collections to load
STAT_FETCH_WAIT_INTERVAL_SEC = MAX_STAT_FETCH_WAIT_SEC / \
                               ((MAX_STAT_FETCH_TRIES + 1) * MAX_STAT_FETCH_TRIES / 2)


def list_uploads_thread(s3_info: S3Info, bucket: str) -> object:
    """ Used to load upload information from an S3 instance
    Arguments:
        s3_info: the connection information for the S3 instance
        bucket: the bucket to look in
    Return:
        Returns an object with the loaded uploads
    """
    uploads_info = S3CollectionConnection.list_uploads(s3_info, bucket)
    return {'bucket': bucket, 'uploads_info': uploads_info}


def __load_db_uploads(db: SPARCdDatabase, s3_id: str,
                      colls: tuple, s3_uploads: list) -> list:
    """ Loads upload data from the database for all collections
    Arguments:
        db: the database connection
        s3_id: the S3 instance ID
        colls: the list of collections to load
        s3_uploads: list to append bucket names to when DB data is missing
    Return:
        Returns the list of upload dicts loaded from the database
    """
    all_results = []
    for one_coll in colls:
        cur_bucket = one_coll['bucket']
        uploads_info = db.get_uploads(s3_id, cur_bucket, TIMEOUT_UPLOADS_SEC)
        if uploads_info:
            all_results.extend([{'bucket': cur_bucket,
                                  'name': one_upload['name'],
                                  'info': json.loads(one_upload['json'])
                                          if one_upload['json'] else {}}
                                 for one_upload in uploads_info])
        else:
            s3_uploads.append(cur_bucket)
    return all_results


def __load_s3_uploads(db: SPARCdDatabase, s3_id: str,
                      s3_info: S3Info, s3_uploads: list) -> list:
    """ Loads upload data from S3 asynchronously for buckets missing from the database
    Arguments:
        db: the database connection
        s3_id: the S3 instance ID
        s3_info: the S3 connection information
        s3_uploads: the list of bucket names to fetch from S3
    Return:
        Returns the list of upload dicts loaded from S3
    """
    all_results = []
    # TODO: Change this so that multiple calls get blocked until the first one succeeds
    with concurrent.futures.ThreadPoolExecutor() as executor:
        cur_futures = {executor.submit(list_uploads_thread, s3_info, bucket): bucket
                       for bucket in s3_uploads}

        for future in concurrent.futures.as_completed(cur_futures):
            try:
                uploads_results = future.result()
                if not uploads_results.get('uploads_info'):
                    continue
                uploads_info = [{'bucket': uploads_results['bucket'],
                                  'name': one_upload['name'],
                                  'info': one_upload,
                                  'json': json.dumps(one_upload)}
                                 for one_upload in uploads_results['uploads_info']]
                db.save_uploads(s3_id, uploads_results['bucket'], uploads_info)
                all_results.extend(uploads_info)
            except Exception as ex:  # pylint: disable=broad-exception-caught
                print(f'Generated exception: {ex}', flush=True)
                traceback.print_exception(ex)

    return all_results


def __count_species(all_results: list) -> dict:
    """ Builds a species count dict from a list of upload results
    Arguments:
        all_results: the list of upload dicts each containing an 'info' dict with 'images'
    Return:
        Returns a dict keyed by species name containing count and scientificName
    """
    ret_stats = {}
    for one_result in all_results:
        for one_image in one_result.get('info', {}).get('images', []):
            for one_species in one_image.get('species', []):
                species_name = (one_species.get('name') or '').strip()
                if not species_name:
                    continue
                if species_name in ret_stats:
                    ret_stats[species_name]['count'] += 1
                else:
                    ret_stats[species_name] = {'count': 1,
                                               'scientificName': one_species['scientificName']}
    return ret_stats


def species_stats(db: SPARCdDatabase, colls: tuple,
                  s3_id: str, s3_info: S3Info) -> Optional[dict]:
    """ Builds species statistics from collection upload data
    Arguments:
        db: the database connection
        colls: the list of collections
        s3_id: the ID of the S3 instance
        s3_info: the connection information for the S3 instance
    Returns:
        Returns the species stats dict keyed by species name
    """
    s3_uploads = []
    all_results = __load_db_uploads(db, s3_id, colls, s3_uploads)

    if s3_uploads:
        all_results.extend(__load_s3_uploads(db, s3_id, s3_info, s3_uploads))

    return __count_species(all_results)


def load_species_stats(db: SPARCdDatabase, is_admin: bool, s3_info: S3Info) -> Optional[tuple]:
    """ Generates the species stats
    Arguments:
        db: the database to access
        is_admin: True if the user is an admin
        s3_info: the connection information for the S3 instance
    Return:
        Returns the loaded stats or None if a problem is found
    """
    lock_name = 'species_stats'
    stats_temp_filename = os.path.join(tempfile.gettempdir(),
                                       s3_info.id + TEMP_SPECIES_STATS_FILE_NAME_POSTFIX)

    loaded_stats = sdfu.load_timed_info(stats_temp_filename, TEMP_SPECIES_STATS_FILE_TIMEOUT_SEC)
    if loaded_stats is not None:
        return loaded_stats

    have_lock = False
    lock_id = None
    try:
        lock_id = db.get_lock(lock_name)
        if lock_id is not None:
            have_lock = True

            coll_info = sdc.load_collections(db, is_admin, s3_info)
            if coll_info:
                loaded_stats = species_stats(db, coll_info, s3_info.id, s3_info)

            db.release_lock(lock_name, lock_id)
            have_lock = False
            lock_id = None

            if loaded_stats is not None:
                sdfu.save_timed_info(stats_temp_filename, loaded_stats)
        else:
            tries = 0
            while tries < MAX_STAT_FETCH_TRIES:
                tries += 1
                time.sleep(tries * STAT_FETCH_WAIT_INTERVAL_SEC)
                loaded_stats = sdfu.load_timed_info(stats_temp_filename,
                                                    TEMP_SPECIES_STATS_FILE_TIMEOUT_SEC)
                if loaded_stats:
                    tries += MAX_STAT_FETCH_TRIES
    finally:
        if have_lock and lock_id is not None:
            db.release_lock(lock_name, lock_id)

    return loaded_stats
