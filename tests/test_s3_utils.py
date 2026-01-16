"""This script contains testing of the utility functions that support S3
"""

import json
import os
import tempfile

import spd_crypt as crypt
import pytest
from minio import Minio, S3Error

import s3_utils
from s3_access import make_s3_path, SETTINGS_BUCKET_LEGACY, SETTINGS_BUCKET_PREFIX, SPARCD_PREFIX, \
                      SPECIES_JSON_FILE_NAME


def __get_settings_bucket(minio: Minio) -> str:
    """ Returns the bucket containing the settings folder
    """
    # Find the name of our settings bucket
    settings_bucket = None
    for one_bucket in minio.list_buckets():
        if one_bucket.name == SETTINGS_BUCKET_LEGACY:
            settings_bucket = one_bucket.name
            break
        if one_bucket.name.startswith(SETTINGS_BUCKET_PREFIX):
            settings_bucket = one_bucket.name

    return settings_bucket


@pytest.fixture(scope='session')
def s3_endpoint(pytestconfig):
    """ S3 endpoint command line argument fixture"""
    endpoint_value = pytestconfig.getoption("s3_endpoint")
    return endpoint_value

@pytest.fixture(scope='session')
def s3_name(pytestconfig):
    """ S3 user name command line argument fixture"""
    name_value = pytestconfig.getoption("s3_name")
    return name_value

@pytest.fixture(scope='session')
def s3_secret(pytestconfig):
    """ S3 user secret command line argument fixture"""
    secret_value = pytestconfig.getoption("s3_secret")
    return secret_value

@pytest.fixture(scope='session')
def s3_test_bucket(pytestconfig):
    """ S3 test bucket command line argument fixture"""
    test_value = pytestconfig.getoption("s3_test_bucket")
    return test_value

@pytest.fixture(scope='session')
def s3_test_upload(pytestconfig):
    """ S3 test upload folder name under bucket command line argument fixture"""
    upload_value = pytestconfig.getoption("s3_test_upload")
    return upload_value

def test_web_to_s3_url() -> None:
    """ Tests converting a web path to an S3 acceptable format
    """
    password = '12345678901234567890'
    passcode=crypt.get_fernet_key_from_passcode(password)

    res = s3_utils.web_to_s3_url('http://sparcd.arizona.edu/', None)
    assert res == 'sparcd.arizona.edu:80'

    res = s3_utils.web_to_s3_url('https://sparcd.arizona.edu/', None)
    assert res == 'sparcd.arizona.edu:443'

    encoded_url = crypt.do_encrypt(passcode, 'https://sparcd.arizona.edu/')
    res = s3_utils.web_to_s3_url(encoded_url, lambda x: crypt.do_decrypt(passcode, x))
    assert res == 'sparcd.arizona.edu:443'

    res = s3_utils.web_to_s3_url('7777777777777777', lambda x: crypt.do_decrypt(passcode, x))
    assert res == '7777777777777777'

# pylint: disable=redefined-outer-name
def test_load_sparcd_config(s3_endpoint, s3_name, s3_secret) -> None:
    """ Tests loading a configuration file
    """
    # Local file name to put data
    timed_filename = SPARCD_PREFIX + 'test_s3_utils.timed'
    temp_file = os.path.join(tempfile.gettempdir(), timed_filename)

    try:
        # Get the data
        res = s3_utils.load_sparcd_config(SPECIES_JSON_FILE_NAME, timed_filename, s3_endpoint,
                                                                    s3_name, lambda: s3_secret)

        assert res is not None
        assert isinstance(res, list)

        # Get the data again (this time it should be from the cache and not S3)
        new_res = s3_utils.load_sparcd_config(SPECIES_JSON_FILE_NAME, timed_filename,
                                                                                None, None, None)

        assert new_res is not None
        assert new_res == res
    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)

# pylint: disable=redefined-outer-name
def test_save_sparcd_config(s3_endpoint, s3_name, s3_secret) -> None:
    """ Tests saving configuration data to the S3 endpoint
    """
    # pylint: disable=too-many-locals

    # Local file name to put data
    remote_test_file_name = 'testing_species.json'
    timed_filename = SPARCD_PREFIX + 'test_s3_utils.timed'
    timed_path = os.path.join(tempfile.gettempdir(), timed_filename)

    # Testing data
    data = \
            {'type': 'testing data',
             'meaning': 'This data is used to test settings file upload'
            }

    # Local file name to put data
    temp_file = tempfile.mkstemp(prefix=SPARCD_PREFIX)
    os.close(temp_file[0])
    if os.path.exists(temp_file[1]):
        os.unlink(temp_file[1])

    # Minio initialization
    minio = Minio(s3_endpoint, access_key=s3_name, secret_key=s3_secret)
    settings_bucket = __get_settings_bucket(minio)
    remote_test_file = make_s3_path(('Settings', remote_test_file_name))

    print(f'test_save_sparcd_config: Uploading settings file to {settings_bucket} ' \
                                                                            f'{remote_test_file}')

    try:
        # Put the data
        s3_utils.save_sparcd_config(data, remote_test_file_name, timed_filename,
                                                        s3_endpoint, s3_name, lambda: s3_secret)

        # Get the configuration information from the server
        minio.fget_object(settings_bucket, remote_test_file, temp_file[1])

        # Read in the configuration
        with open(temp_file[1], 'r', encoding='utf-8') as ifile:
            config = json.loads(ifile.read())

        assert config == data

        # Get the data again (this time it should be from the cache and not S3)
        new_res = s3_utils.load_sparcd_config(remote_test_file_name, timed_filename,
                                                                                None, None, None)

        assert new_res == data

    finally:
        if os.path.exists(temp_file[1]):
            os.unlink(temp_file[1])
        if os.path.exists(timed_path):
            os.unlink(timed_path)
        try:
            minio.remove_object(settings_bucket, remote_test_file)
        except S3Error as ex:
            print(f'WARNING: Unable to remove settings test file {settings_bucket} ' \
                                                                            f'{remote_test_file}')
            print(ex)
