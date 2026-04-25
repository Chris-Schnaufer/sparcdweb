""" S3 collection and upload discovery operations for SPARCd """

import concurrent.futures
import dataclasses
import traceback
from typing import Optional

from minio import Minio

from s3.s3_connect import s3_connect
from spd_types.s3info import S3Info
from s3.s3_access_helpers import (SPARCD_PREFIX, S3_UPLOADS_PATH_PART, COLLECTIONS_FOLDER,
                                temp_s3_file, load_s3_json, load_deployment_location,
                                load_upload_observations, make_s3_path, get_s3_file,
                                get_user_collections, get_uploaded_folders, update_user_collections,
                                get_upload_data_thread, check_incomplete_thread, load_upload_meta,
                                S3_UPLOAD_META_JSON_FILE_NAME)


@dataclasses.dataclass
class S3CollectionConnection:
    """ Contains functions for collection and upload discovery on an S3 instance """

    @staticmethod
    def list_collections(conn_info: S3Info) -> Optional[tuple]:
        """ Returns the collection information
        Arguments:
            conn_info: the connection information for the S3 endpoint
        Returns:
            Returns the collections, or None
        """
        minio = s3_connect(conn_info)
        all_buckets = minio.list_buckets()
        found_buckets = [one_bucket.name for one_bucket in all_buckets
                         if one_bucket.name.startswith(SPARCD_PREFIX)]
        return get_user_collections(minio, conn_info.access_key, found_buckets)

    @staticmethod
    def get_collections(conn_info: S3Info) -> Optional[tuple]:
        """ Returns the collection information with upload details
        Arguments:
            conn_info: the connection information for the S3 endpoint
        Returns:
            Returns the collections, or None
        """
        minio = s3_connect(conn_info)
        all_buckets = minio.list_buckets()
        found_buckets = [one_bucket.name for one_bucket in all_buckets
                         if one_bucket.name.startswith(SPARCD_PREFIX)]
        user_collections = get_user_collections(minio, conn_info.access_key, found_buckets)
        return update_user_collections(minio, user_collections)

    @staticmethod
    def get_collection_info(conn_info: S3Info, bucket: str,
                            upload_path: str = None) -> Optional[dict]:
        """ Returns information for one collection
        Arguments:
            conn_info: the connection information for the S3 endpoint
            bucket: the bucket of interest
            upload_path: a specific upload path to return information on. Otherwise all the uploads
                        are returned
        Return:
            Returns the information on the collection or None if the collection isn't found
        """
        minio = s3_connect(conn_info)
        all_buckets = minio.list_buckets()
        found_buckets = [one_bucket.name for one_bucket in all_buckets
                         if one_bucket.name == bucket]
        if not found_buckets:
            return None

        user_collections = get_user_collections(minio, conn_info.access_key, found_buckets)
        if not user_collections:
            return None

        if upload_path is None:
            return update_user_collections(minio, user_collections)[0]

        for one_coll in user_collections:
            upload_results = get_upload_data_thread(minio, bucket, (upload_path,), one_coll)
            if upload_results:
                one_coll['uploads'] = upload_results['uploads']

        return user_collections[0]

    @staticmethod
    def get_upload_info(conn_info: S3Info, bucket: str, upload_path: str) -> Optional[dict]:
        """ Returns information for one upload in a collection
        Arguments:
            conn_info: the connection information for the S3 endpoint
            bucket: the bucket of interest
            upload_path: a specific upload path to return information on
        Return:
            Returns the information on the upload or None if not found
        """
        minio = s3_connect(conn_info)
        all_buckets = minio.list_buckets()
        found_buckets = [one_bucket.name for one_bucket in all_buckets
                         if one_bucket.name == bucket]
        if not found_buckets:
            return None

        coll_info = load_upload_meta(minio, bucket, upload_path, 'get_upload_info')
        if not coll_info:
            return None

        with temp_s3_file() as temp_path:
            loc_data = load_deployment_location(minio, bucket, upload_path, temp_path)
            if loc_data is None:
                return None

            return {
                'path': upload_path,
                'info': coll_info,
                'location': loc_data['location'],
                'elevation': loc_data['elevation'],
                'key': __import__('os').path.basename(upload_path.rstrip('/\\')),
                'uploaded_folders': get_uploaded_folders(minio, bucket, upload_path)
            }

    @staticmethod
    def list_uploads(conn_info: S3Info, bucket: str,
                     extended_location: bool = False) -> Optional[tuple]:
        """ Returns the upload information for a collection
        Arguments:
            conn_info: the connection information for the S3 endpoint
            bucket: the bucket of the uploads
            extended_location: returns additional location information when set to True
        Returns:
            Returns the uploads, or None
        """
        import os
        if not bucket.startswith(SPARCD_PREFIX):
            print(f'Invalid bucket name specified: {bucket}')
            return None

        uploads_path = make_s3_path(('Collections', bucket[len(SPARCD_PREFIX):],
                                     S3_UPLOADS_PATH_PART)) + '/'
        minio = s3_connect(conn_info)
        coll_uploads = []

        for one_obj in minio.list_objects(bucket, prefix=uploads_path):
            if not one_obj.is_dir or one_obj.object_name == uploads_path:
                continue

            with temp_s3_file() as temp_path:
                upload_info_path = make_s3_path((one_obj.object_name,
                                                 S3_UPLOAD_META_JSON_FILE_NAME))
                meta_info_data = load_s3_json(minio, bucket, upload_info_path,
                                                temp_path, 'list_uploads')
                if not meta_info_data:
                    continue

                meta_info_data['name'] = os.path.basename(one_obj.object_name.rstrip('/\\'))
                meta_info_data['loc'] = None

                loc_data = load_deployment_location(minio, bucket,
                                                      one_obj.object_name, temp_path)
                if loc_data is None:
                    continue

                meta_info_data['loc'] = loc_data['location']
                meta_info_data['elevation'] = loc_data['elevation']
                if extended_location:
                    meta_info_data['loc_name'] = loc_data['loc_name']
                    meta_info_data['loc_lon'] = loc_data['loc_lon']
                    meta_info_data['loc_lat'] = loc_data['loc_lat']

                meta_info_data['images'] = load_upload_observations(minio, bucket,
                                                                       one_obj.object_name,
                                                                       temp_path)
                coll_uploads.append(meta_info_data)

        return coll_uploads

    @staticmethod
    def check_incomplete_uploads(conn_info: S3Info, buckets: tuple) -> Optional[tuple]:
        """ Checks for incomplete uploads in the requested buckets
        Arguments:
            conn_info: the connection information for the S3 endpoint
            buckets: tuple of buckets to check
        Return:
            Information on failed uploads is returned upon success with an empty tuple possible.
            None is returned if a problem is found
        """
        minio = s3_connect(conn_info)

        found_incomplete = []
        if len(buckets) > 1:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                cur_futures = {executor.submit(check_incomplete_thread, minio, one_bucket):
                               one_bucket for one_bucket in buckets}

                for future in concurrent.futures.as_completed(cur_futures):
                    cur_incomplete = future.result()
                    if len(cur_incomplete) > 0:
                        found_incomplete = found_incomplete + cur_incomplete
        else:
            found_incomplete = check_incomplete_thread(minio, buckets[0])

        return found_incomplete
