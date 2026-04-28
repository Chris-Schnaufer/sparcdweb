""" S3 admin, configuration, and installation operations for SPARCd """

import dataclasses
import json
import os
from time import sleep
from typing import Optional
import uuid

from minio import S3Error

from spd_types.s3info import S3Info
from s3.s3_connect import s3_connect
from s3.s3_access_helpers import (COLLECTIONS_FOLDER, SPARCD_PREFIX, SETTINGS_FOLDER,
                                SETTINGS_BUCKET_PREFIX, COLLECTION_JSON_FILE_NAME,
                                PERMISSIONS_JSON_FILE_NAME, CONFIGURATION_FILES_LIST,
                                MAX_NEW_BUCKET_TRIES, temp_s3_file, make_s3_path, get_s3_file,
                                put_s3_file, find_settings_bucket, create_new_bucket)
from s3.s3_uploads import S3UploadConnection


@dataclasses.dataclass
class S3AdminConnection:
    """ Contains functions for admin, configuration, and installation operations on an S3 instance
    """

    @staticmethod
    def get_configuration(conn_info: S3Info, filename: str):
        """ Returns the configuration contained in the file
        Arguments:
            conn_info: the connection information for the S3 endpoint
            filename: the name of the configuration to download
        """
        minio = s3_connect(conn_info)

        settings_bucket = find_settings_bucket(minio)
        if not settings_bucket:
            return None

        with temp_s3_file() as temp_path:
            file_path = make_s3_path((SETTINGS_FOLDER, filename))
            config_data = None
            try:
                config_data = get_s3_file(minio, settings_bucket, file_path, temp_path)
            except S3Error as ex:
                print(f'Unable to get configuration file {filename} from {settings_bucket}')
                print(ex)

        return config_data

    @staticmethod
    def put_configuration(conn_info: S3Info, filename: str, config: str):
        """ Updates the server with the configuration string in the file
        Arguments:
            conn_info: the connection information for the S3 endpoint
            filename: the name of the configuration to update
            config: the configuration to write to the file
        """
        minio = s3_connect(conn_info)

        settings_bucket = find_settings_bucket(minio)
        if not settings_bucket:
            print(f'Unable to find settings bucket at {conn_info.url}')
            return

        with temp_s3_file() as temp_path:
            file_path = make_s3_path((SETTINGS_FOLDER, filename))
            try:
                with open(temp_path, 'w', encoding='utf-8') as ofile:
                    ofile.write(config)
                put_s3_file(minio, settings_bucket, file_path, temp_path,
                            content_type='application/json')
            except S3Error as ex:
                print(f'Unable to put configuration file {filename} to {settings_bucket}')
                print(ex)

    @staticmethod
    def save_collection_info(conn_info: S3Info, bucket: str, coll_info: object) -> None:
        """ Saves the collection information on the S3 server
        Arguments:
            conn_info: the connection information for the S3 endpoint
            bucket: the bucket to upload to
            coll_info: the collection information to save
        """
        coll_info_path = make_s3_path((COLLECTIONS_FOLDER, bucket[len(SPARCD_PREFIX):],
                                       COLLECTION_JSON_FILE_NAME))
        S3UploadConnection.upload_file_data(conn_info, bucket, coll_info_path,
                                            json.dumps(
                                                {'nameProperty': coll_info['name'],
                                                 'organizationProperty': coll_info['organization'],
                                                 'contactInfoProperty': coll_info['email'],
                                                 'descriptionProperty': coll_info['description'],
                                                 'idProperty': bucket[len(SPARCD_PREFIX):],
                                                 'bucketProperty': bucket,
                                                 }, indent=4),
                                            content_type='application/json')

    @staticmethod
    def save_collection_permissions(conn_info: S3Info, bucket: str, perm_info: tuple) -> None:
        """ Saves the permissions information on the S3 server
        Arguments:
            conn_info: the connection information for the S3 endpoint
            bucket: the bucket to upload to
            perm_info: the tuple of permissions information
        """
        perms_info_path = make_s3_path((COLLECTIONS_FOLDER, bucket[len(SPARCD_PREFIX):],
                                        PERMISSIONS_JSON_FILE_NAME))
        S3UploadConnection.upload_file_data(conn_info, bucket, perms_info_path,
                                            json.dumps(
                                                [{'usernameProperty': one_perm['usernameProperty'],
                                                  'readProperty': one_perm['readProperty'],
                                                  'uploadProperty': one_perm['uploadProperty'],
                                                  'ownerProperty': one_perm['ownerProperty'],
                                                  } for one_perm in perm_info],
                                                indent=4),
                                            content_type='application/json')

    @staticmethod
    def add_collection(conn_info: S3Info, coll_info: object, perm_info: tuple) -> Optional[str]:
        """ Adds a new collection to the S3 server
        Arguments:
            conn_info: the connection information for the S3 endpoint
            coll_info: the collection information to save
            perm_info: the tuple of permissions information
        Return:
            The name of the newly created bucket
        """
        minio = s3_connect(conn_info)

        collection_bucket = create_new_bucket(minio, SPARCD_PREFIX)
        if collection_bucket is None:
            print(f'Unable to create a new collection bucket after {MAX_NEW_BUCKET_TRIES} tries',
                  flush=True)
            return False

        del minio

        coll_id = collection_bucket[len(SPARCD_PREFIX):]  # pylint: disable=unsubscriptable-object
        S3AdminConnection.save_collection_info(conn_info, collection_bucket,
                                               coll_info | {'idProperty': coll_id,
                                                            'bucketProperty': collection_bucket})
        S3AdminConnection.save_collection_permissions(conn_info, collection_bucket, perm_info)

        return collection_bucket

    @staticmethod
    def needs_repair(conn_info: S3Info) -> tuple:
        """ Checks if the S3 endpoint needs repair by looking for buckets and certain files
        Arguments:
            conn_info: the connection information for the S3 endpoint
        Return:
            Returns a tuple for if the install is broken, and if the install appears intact.
            The first element contains True if the S3 endpoint has collections, or a settings
            bucket, and is missing configuration files. Also, True will be returned if a
            settings bucket is missing. False is returned if everything appears to be in order.
            The second element contains True if all elements checked are there and False if
            none of the elements are there. None is returned if the install needs repair.
        """
        minio = s3_connect(conn_info)

        settings_bucket = find_settings_bucket(minio)

        found_count = 0
        if settings_bucket is not None:
            for one_obj in minio.list_objects(settings_bucket, prefix=SETTINGS_FOLDER + '/'):
                if not one_obj.is_dir:
                    check_name = os.path.basename(one_obj.object_name)
                    if check_name.lower() in CONFIGURATION_FILES_LIST:
                        found_count += 1

        have_collection = False
        for one_bucket in minio.list_buckets():
            if one_bucket.name.startswith(SPARCD_PREFIX):
                have_collection = True
                break

        return (settings_bucket is not None and
                (found_count != len(CONFIGURATION_FILES_LIST)) or
                (settings_bucket is None and have_collection),
                True if settings_bucket is not None and
                        found_count == len(CONFIGURATION_FILES_LIST)
                else False if settings_bucket is None and found_count == 0 and not have_collection
                else None)

    @staticmethod
    def check_new_install_possible(conn_info: S3Info) -> tuple:
        """ Checks to see if we can create buckets, upload files, and download files
        Arguments:
            conn_info: the connection information for the S3 endpoint
        Return:
            A tuple with True is returned if the checks pass and False otherwise, and the
            name of the test bucket if it couldn't be removed
        """
        minio = s3_connect(conn_info)

        tries = 0
        max_tries = 5
        created_bucket = None
        while tries < max_tries:
            tries += 1
            try:
                new_bucket = 'delete-testing-' + uuid.uuid4().hex
                if minio.bucket_exists(new_bucket):
                    continue
                minio.make_bucket(new_bucket)
                created_bucket = new_bucket
                break
            except S3Error as ex:
                print(f'ERROR: Exception caught while checking if we can create a new bucket:'
                      f' {tries} of {max_tries} attempts', flush=True)
                print(f'     : exception code: {ex.code}', flush=True)
                print(ex, flush=True)
                sleep(1)

        if created_bucket is None:
            return False, None

        with temp_s3_file() as temp_path:
            with open(temp_path, 'w', encoding='utf-8') as ofile:
                ofile.write('HERE IS SOME TESTING DATA')

            try:
                success = False
                try:
                    put_s3_file(minio, created_bucket, 'testing.txt', temp_path)
                    success = True
                except S3Error as ex:
                    print('ERROR: Unable to put a test file onto the S3 server')
                    print(ex, flush=True)

                if success is True:
                    success = get_s3_file(minio, created_bucket, 'testing.txt',
                                          temp_path) is not None
            finally:
                try:
                    for one_obj in minio.list_objects(created_bucket, recursive=True):
                        if not one_obj.is_dir:
                            minio.remove_object(created_bucket, one_obj.object_name)
                except S3Error as ex:
                    print(f'ERROR: Unable to remove file from created bucket '
                          f'{one_obj.object_name}', flush=True)
                    print(f'     : exception code: {ex.code}', flush=True)
                    print(ex, flush=True)

                try:
                    minio.remove_bucket(created_bucket)
                    created_bucket = None
                except S3Error as ex:
                    print('ERROR: Unable to remove created bucket', flush=True)
                    print(f'     : exception code: {ex.code}', flush=True)
                    print(ex, flush=True)

        return success is True, created_bucket

    @staticmethod
    def create_sparcd(conn_info: S3Info, settings_folder: str) -> bool:
        """ Creates the remote instance of SPARCd
        Arguments:
            conn_info: the connection information for the S3 endpoint
            settings_folder: the path of the folder to find the settings files in
        Return:
            True is returned if the instance was created and False otherwise
        """
        minio = s3_connect(conn_info)

        if find_settings_bucket(minio) is not None:
            return False

        settings_bucket = create_new_bucket(minio, SETTINGS_BUCKET_PREFIX)
        if settings_bucket is None:
            print(f'Unable to create a settings bucket after {MAX_NEW_BUCKET_TRIES} tries',
                  flush=True)
            return False

        uploaded_count = 0
        for one_file in CONFIGURATION_FILES_LIST:
            source = os.path.join(settings_folder, one_file)
            dest = make_s3_path((SETTINGS_FOLDER, one_file))
            try:
                put_s3_file(minio, settings_bucket, dest, source,
                            content_type='application/json')
                uploaded_count += 1
            except S3Error as ex:
                print('ERROR: Unable to upload to settings bucket {dest}', flush=True)
                print(f'     : exception code: {ex.code}', flush=True)
                print(ex, flush=True)

        return uploaded_count == len(CONFIGURATION_FILES_LIST)

    @staticmethod
    def repair_sparcd(conn_info: S3Info, settings_folder: str) -> bool:
        """ Repairs the remote instance of SPARCd
        Arguments:
            conn_info: the connection information for the S3 endpoint
            settings_folder: the path of the folder to find the settings files in
        Return:
            True is returned if the instance was could be repaired and False otherwise
        """
        minio = s3_connect(conn_info)

        settings_bucket = find_settings_bucket(minio)
        if settings_bucket is None:
            settings_bucket = create_new_bucket(minio, SETTINGS_BUCKET_PREFIX)
        if settings_bucket is None:
            return False

        found_files = []
        for one_obj in minio.list_objects(settings_bucket, prefix=SETTINGS_FOLDER + '/'):
            if not one_obj.is_dir:
                file_name = os.path.basename(one_obj.object_name)
                if file_name in CONFIGURATION_FILES_LIST:
                    found_files.append(file_name)

        upload_count = 0
        for one_file in list(set(CONFIGURATION_FILES_LIST) - set(found_files)):
            source = os.path.join(settings_folder, one_file)
            dest = make_s3_path((SETTINGS_FOLDER, one_file))
            try:
                put_s3_file(minio, settings_bucket, dest, source,
                            content_type='application/json')
                upload_count += 1
            except S3Error as ex:
                print('ERROR: Unable to upload missing file to settings bucket {dest}', flush=True)
                print(f'     : exception code: {ex.code}', flush=True)
                print(ex, flush=True)

        return upload_count + len(found_files) == len(CONFIGURATION_FILES_LIST)
