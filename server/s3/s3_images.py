""" S3 image retrieval and download operations for SPARCd """

import dataclasses
from typing import Optional, Callable
import traceback
import concurrent.futures

from minio import Minio

from s3.s3_connect import s3_connect
from spd_types.s3info import S3Info
from s3.s3_access_helpers import (SPARCD_PREFIX, S3_UPLOADS_PATH_PART, temp_s3_file,
                                apply_media_timestamps, apply_observation_species,
                                make_s3_path, get_uploaded_folders, get_image_counts,
                                get_s3_images, download_data_thread)


@dataclasses.dataclass
class S3ImageConnection:
    """ Contains functions for image retrieval and download on an S3 instance """

    @staticmethod
    def get_image_paths(conn_info: S3Info, collection_id: str,
                        upload_name: str) -> Optional[tuple]:
        """ Returns the information on the images found for an upload to the collection
        Arguments:
            conn_info: the connection information for the S3 endpoint
            collection_id: the ID of the collection of the upload
            upload_name: the name of the upload to get image data on
        Returns:
            Returns the information on the images, or None. Each returned image dict contains
            the image file name, bucket s3_path, and unique key
        """
        bucket = SPARCD_PREFIX + collection_id
        upload_path = make_s3_path(('Collections', collection_id, 'Uploads', upload_name)) + '/'
        minio = s3_connect(conn_info)
        return get_s3_images(minio, bucket, [upload_path])

    @staticmethod
    def have_images(conn_info: S3Info, bucket: str, path: str) -> bool:
        """ Checks if the path has images
        Arguments:
            conn_info: the connection information for the S3 endpoint
            bucket: the bucket to download from
            path: the path to the search on
        Return:
            True is returned if image files were found and False otherwise
        """
        minio = s3_connect(conn_info)
        loaded_folders = get_uploaded_folders(minio, bucket, path)

        for one_folder in loaded_folders:
            count = get_image_counts(minio, bucket, [one_folder])
            if count > 0:
                return True

        return False

    @staticmethod
    def get_images(conn_info: S3Info, collection_id: str,
                   upload_name: str, need_url: bool = True) -> Optional[tuple]:
        """ Returns the image information for an upload of a collection
        Arguments:
            conn_info: the connection information for the S3 endpoint
            collection_id: the ID of the collection of the upload
            upload_name: the name of the upload to get image data on
            need_url: set to False if a remote URL to the image isn't needed
        Returns:
            Returns the images, or None
        """
        bucket = SPARCD_PREFIX + collection_id
        upload_path = make_s3_path(('Collections', collection_id,
                                    S3_UPLOADS_PATH_PART, upload_name)) + '/'
        minio = s3_connect(conn_info)
        images = get_s3_images(minio, bucket, [upload_path], need_url)
        images_dict = {obj['s3_path']: obj for obj in images}

        with temp_s3_file() as temp_path:
            apply_media_timestamps(minio, bucket, upload_path, images_dict, temp_path)
            apply_observation_species(minio, bucket, upload_path, images_dict, temp_path)

        return images

    @staticmethod
    def download_image(conn_info: S3Info, bucket: str, s3_path: str,
                       dest_file_path: str) -> None:
        """ Downloads the file to the destination path
        Arguments:
            conn_info: the connection information for the S3 endpoint
            bucket: the bucket to download from
            s3_path: the path to the file on S3
            dest_file_path: the location to download the file to
        """
        minio = s3_connect(conn_info)
        minio.fget_object(bucket, s3_path, dest_file_path)

    @staticmethod
    def download_images_cb(conn_info: S3Info, files: tuple, dest_path: str,
                           callback: Callable, callback_data) -> None:
        """ Downloads files into the destination path and calls the callback for each file
            downloaded
        Arguments:
            conn_info: the connection information for the S3 endpoint
            files: a tuple containing the bucket, path, and (optionally) the destination path of the
                    downloaded file
            dest_path: the starting location to download files to
            callback: called for each file downloaded
            callback_data: data to pass to the callback as the first parameter (caller can use None)
        Notes:
            If a destination path is not specified for a file, the S3 path is used (starting at the
            root of the dest_path)
        """
        minio = s3_connect(conn_info)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            cur_futures = {executor.submit(download_data_thread, minio, one_file, dest_path):
                           one_file for one_file in files}

            for future in concurrent.futures.as_completed(cur_futures):
                try:
                    bucket, s3_path, downloaded_file = future.result()
                    callback(callback_data, bucket, s3_path, downloaded_file)
                # pylint: disable=broad-exception-caught
                except Exception as ex:
                    print(f'Generated download images callback exception: {ex}', flush=True)
                    traceback.print_exception(ex)

        # Final callback to indicate processing is done
        callback(callback_data, None, None, None)

    @staticmethod
    def get_object_urls(conn_info: S3Info, object_info: tuple) -> tuple:
        """ Returns the URLs of the objects listed in object_info
        Arguments:
            conn_info: the connection information for the S3 endpoint
            object_info: tuple containing tuple pairs of bucket name and the object path
        Return:
            Returns a tuple containing the S3 URLs for the objects (each url subject to timeout)
        """
        minio = s3_connect(conn_info)
        return [minio.presigned_get_object(one_obj[0], one_obj[1]) for one_obj in object_info]
