""" Sandbox collection handling utilities for SPARCd server """

from typing import Optional

from s3.s3_collections import S3CollectionConnection
from spd_types.s3info import S3Info
from sparcd_upload_utils import normalize_collection, normalize_upload


def __apply_sandbox_metadata(upload: dict, one_item: dict) -> dict:
    """ Applies sandbox-specific metadata fields to an upload dict
    Arguments:
        upload: the upload dict to update
        one_item: the sandbox item containing metadata to apply
    Return:
        Returns the updated upload dict
    """
    if 'complete' in one_item:
        upload['uploadCompleted'] = one_item['complete']
    if 'user' in one_item:
        upload['uploadUser'] = one_item['user']
    if 'path' in one_item:
        upload['path'] = one_item['path']
    return upload


def __find_or_fetch_collection(s3_info: S3Info, bucket: str, s3_path: str,
                               all_collections: tuple, bucket_state: dict) -> tuple:
    """ Finds a collection by bucket, fetching from S3 if not in the provided list
    Arguments:
        s3_info: the S3 connection information
        bucket: the bucket to find the collection for
        s3_path: the S3 path of the item
        all_collections: the list of known collections, or None to fetch from S3
        bucket_state: the tracking dict for S3-sourced collections
    Return:
        Returns a tuple of (found_collection, is_s3_collection)
    """
    if all_collections:
        found = next((c for c in all_collections if c['bucket'] == bucket), None)
        return found, False

    found = S3CollectionConnection.get_collection_info(s3_info, bucket, s3_path)
    if found:
        bucket_state[bucket]['s3_collection'] = True
    return found, bool(found)


def __find_or_fetch_upload(s3_info: S3Info, bucket: str, s3_path: str,
                           found: dict, is_s3_collection: bool) -> tuple:
    """ Finds an upload within a collection, fetching from S3 if needed
    Arguments:
        s3_info: the S3 connection information
        bucket: the bucket to search
        s3_path: the S3 path of the item
        found: the collection dict to search within
        is_s3_collection: True if the collection was fetched from S3
    Return:
        Returns a tuple of (upload_dict, is_s3_upload)
    """
    if found and 'uploads' in found:
        suffix = '/' if is_s3_collection else ''
        matching = [u for u in found['uploads']
                    if s3_path.endswith(u['key'] + suffix)
                    or (is_s3_collection and s3_path == u.get('path'))]
        if matching:
            return matching[0], is_s3_collection

    cur_upload = S3CollectionConnection.get_upload_info(s3_info, bucket, s3_path)
    if cur_upload is None:
        print(f'ERROR: Unable to retrieve upload for bucket {bucket}: Path: "{s3_path}"')
    return cur_upload, True


def __process_sandbox_item(s3_info: S3Info, one_item: dict, all_collections: tuple,
                           bucket_state: dict, collections_out: list) -> None:
    """ Processes a single sandbox item and updates bucket_state and collections_out in place
    Arguments:
        s3_info: the S3 connection information
        one_item: the sandbox item to process
        all_collections: the list of known collections, or None to fetch from S3
        bucket_state: the tracking dict of uploads and S3 state keyed by bucket
        collections_out: the list of collections being assembled
    """
    bucket = one_item['bucket']
    item_path = one_item['s3_path']

    known_collection = next((c for c in collections_out if c['bucket'] == bucket), None)

    # Short-circuit if we already have this upload tracked
    if known_collection and 'uploads' in known_collection:
        known_upload = next((u for u in known_collection['uploads']
                             if item_path.endswith(u['key'])), None)
        if known_upload is not None:
            bucket_state[bucket]['uploads'].append(known_upload)
            return

    is_new_collection = known_collection is None

    collection, is_s3_collection = __find_or_fetch_collection(
        s3_info, bucket, item_path, all_collections, bucket_state)
    if not collection:
        print(f'ERROR: Unable to find collection bucket {bucket}. Continuing')
        return

    upload, is_s3_upload = __find_or_fetch_upload(
        s3_info, bucket, item_path, collection, is_s3_collection)
    if upload is None:
        return

    if is_s3_upload and not bucket_state[bucket]['s3_collection']:
        upload = normalize_upload(upload)

    bucket_state[bucket]['uploads'].append(__apply_sandbox_metadata(upload, one_item))

    if is_new_collection:
        collections_out.append(collection)


def get_sandbox_collections(s3_info: S3Info, items: tuple,
                             all_collections: tuple = None) -> tuple:
    """ Returns the sandbox information as collection information
    Arguments:
        s3_info: the information for connecting to the S3 instance
        items: the sandbox items as returned by the database
        all_collections: the list of known collections
    Return:
        Returns the sandbox entries in collection format
    """
    bucket_state = {}
    collections_out = []

    for one_item in items:
        bucket = one_item['bucket']
        if bucket not in bucket_state:
            bucket_state[bucket] = {'s3_collection': False, 'uploads': []}
        __process_sandbox_item(s3_info, one_item, all_collections,
                               bucket_state, collections_out)

    for idx, collection in enumerate(collections_out):
        collection['uploads'] = bucket_state[collection['bucket']]['uploads']
        if bucket_state[collection['bucket']]['s3_collection']:
            collections_out[idx] = normalize_collection(collection)

    return collections_out
