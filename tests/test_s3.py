"""This script contains testing of the interface to an S3 instance
"""

import json
import os
import tempfile

import pytest
from minio import Minio

import s3_access

def __get_s3_updown_test_data(bucket: str, upload: str) -> tuple:
    """ Returns the data used for testing uploading
    Arguments:
        bucket: the bucket to upload/download to/from
        upload: the name of the upload folder to pu/get data from
    """
    coll_name = bucket[len(s3_access.SPARCD_PREFIX):]
    return [
                {'path': ['Collections', coll_name, 'data.json'],
                  'value': json.dumps({"bucketProperty": "sparcd-test-data",
                              "nameProperty": "Automated Testing Data",
                              "organizationProperty": "UA Wild Cat Research and Conservation",
                              "contactInfoProperty": "smalusa@arizona.edu",
                              "descriptionProperty": "Collection ID # \ntest-data",
                              "idProperty": "test-data"
                            }, indent=2),
                  'content_type': 'application/json',
                  'value_is_path': False,
                }, {
                  'path': ['Collections', coll_name, 'data.txt'],
                  'value': '',
                  'content_type': None,
                  'value_is_path': False,
                }, {
                  'path': ['Collections', coll_name, 'Uploads', upload, 'TESTIMAG001.JPG'],
                  'value': [os.getcwd().replace('\\', '/'), 'tests', 'data', \
                                                                'NSCF----_250816105127_0003.JPG'],
                  'content_type': 'image/jpeg',
                  'value_is_path': True,
                }
                ]

def __get_s3_expected_coll_data() -> tuple:
    """ Returns the minimum set of collection data that is expected
    """
    return tuple([
          {
            "bucketProperty": "sparcd-automated-test",
            "nameProperty": "Automated Testing Data",
            "organizationProperty": "UA Wild Cat Research and Conservation",
            "contactInfoProperty": "smalusa@arizona.edu",
            "descriptionProperty": "Collection ID # \nautomated-test",
            "idProperty": "automated-test",
            "bucket": "sparcd-automated-test",
            "base_path": "Collections/automated-test",
            "permissions": {
              "usernameProperty": "schnaufer",
              "readProperty": True,
              "uploadProperty": True,
              "ownerProperty": True
            },
            "all_permissions": [
              {
                "usernameProperty": "smalusa",
                "readProperty": True,
                "uploadProperty": True,
                "ownerProperty": True
              },
              {
                "usernameProperty": "schnaufer",
                "readProperty": True,
                "uploadProperty": True,
                "ownerProperty": True
              }
            ]
          }
        ])

def __get_s3_upload_expected_image_folders() -> tuple:
    """ Returns a tuple of expected image folders for the uploads
    """
    return ('444HCOIM',)


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

def test_make_s3_path() -> None:
    """ Tests making an S3 path
    """
    test_data = [['foo','test'],
                 ['foo/', 'path\\'],
                 ['longer/','test/','path.csv']]

    for idx, one_test in enumerate(test_data):
        print(f'test_make_s3_path: test index {idx}', flush=True)
        answer = "/".join([part.rstrip('/').rstrip('\\') for part in one_test])
        assert s3_access.make_s3_path(one_test) == answer

# pylint: disable=redefined-outer-name
def test_put_s3_file(s3_endpoint, s3_name, s3_secret, s3_test_bucket, s3_test_upload) -> None:
    """ Tests putting a file into the S3 test bucket
    """
    assert s3_endpoint is not None
    assert s3_name is not None
    assert s3_secret is not None
    assert s3_test_bucket is not None
    assert s3_test_upload is not None

    minio = Minio(s3_endpoint, access_key=s3_name, secret_key=s3_secret)

    # Run this test more than once to make sure we overwrite existing data
    max_run = 2
    for run in range(0, max_run):
        for idx, one_test in enumerate(__get_s3_updown_test_data(s3_test_bucket, s3_test_upload)):
            print(f'test_put_s3_file: Run: {run+1} of {max_run}  Test index {idx}', flush=True)
            if 'value_is_path' in one_test and not one_test['value_is_path']:
                try:
                    temp_file = tempfile.mkstemp(prefix=s3_access.SPARCD_PREFIX)
                    os.close(temp_file[0])

                    with open(temp_file[1], 'w', encoding='utf-8') as ofile:
                        ofile.write(one_test['value'])

                    s3_path = one_test['path'] if isinstance(one_test['path'], str) else \
                                                            s3_access.make_s3_path(one_test['path'])
                    s3_access.put_s3_file(minio, s3_test_bucket, s3_path, temp_file[1],
                                                                        one_test['content_type'])
                finally:
                    os.unlink(temp_file[1])
            else:
                s3_path = one_test['path'] if isinstance(one_test['path'], str) else \
                                                            s3_access.make_s3_path(one_test['path'])
                source_path = one_test['value'] if isinstance(one_test['path'], str) else \
                                                        s3_access.make_s3_path(one_test['value'])
                s3_access.put_s3_file(minio, s3_test_bucket, s3_path, source_path,
                                                                        one_test['content_type'])


# pylint: disable=redefined-outer-name
def test_gut_s3_file(s3_endpoint, s3_name, s3_secret, s3_test_bucket, s3_test_upload) -> None:
    """ Tests getting files non-binary from the S3 test bucket
    """
    assert s3_endpoint is not None
    assert s3_name is not None
    assert s3_secret is not None
    assert s3_test_bucket is not None
    assert s3_test_upload is not None

    # Make sure the data is up on S3
    test_put_s3_file(s3_endpoint, s3_name, s3_secret, s3_test_bucket, s3_test_upload)

    minio = Minio(s3_endpoint, access_key=s3_name, secret_key=s3_secret)

    # Make sure what we put up there can also be downloaded
    for idx, one_test in enumerate(__get_s3_updown_test_data(s3_test_bucket, s3_test_upload)):
        print(f'test_get_s3_file: Test index {idx}', flush=True)

        if one_test['value_is_path'] is True:
            print(f'test_get_s3_file:        SKIPPING FILE TEST', flush=True)
            continue

        temp_file = tempfile.mkstemp(prefix=s3_access.SPARCD_PREFIX)
        os.close(temp_file[0])
        try:
            s3_path = one_test['path'] if isinstance(one_test['path'], str) else \
                                                            s3_access.make_s3_path(one_test['path'])
            data = s3_access.get_s3_file(minio, s3_test_bucket, s3_path, temp_file[1])

            assert data == one_test['value']
        finally:
            os.unlink(temp_file[1])

# pylint: disable=redefined-outer-name
def test_get_user_collections(s3_endpoint, s3_name, s3_secret, s3_test_bucket) -> None:
    """ Tests getting the user collection information
    """
    assert s3_endpoint is not None
    assert s3_name is not None
    assert s3_secret is not None
    assert s3_test_bucket is not None

    minio = Minio(s3_endpoint, access_key=s3_name, secret_key=s3_secret)

    colls = s3_access.get_user_collections(minio, s3_name, [s3_test_bucket])
    expected = __get_s3_expected_coll_data()

    assert len(expected) > 0 and len(expected) <= len(colls)
    
    colls_dict = {one_coll['bucket']: one_coll for one_coll in colls}

    for one_expected in expected:
        print(f'test_get_user_collections: Testing bucket \"{one_expected["bucket"]}\"', flush=True)
        assert one_expected['bucket'] in colls_dict

        print('test_get_user_collections:         Testing bucket details', flush=True)
        assert one_expected == colls_dict[one_expected['bucket']]


# pylint: disable=redefined-outer-name
def test_get_uploaded_folders(s3_endpoint, s3_name, s3_secret, s3_test_bucket, s3_test_upload) -> None:
    """ Tests getting the upload folders of images
    """
    assert s3_endpoint is not None
    assert s3_name is not None
    assert s3_secret is not None
    assert s3_test_bucket is not None
    assert s3_test_upload is not None

    minio = Minio(s3_endpoint, access_key=s3_name, secret_key=s3_secret)

    # Getting the S3 path we want
    coll_name = s3_test_bucket[len(s3_access.SPARCD_PREFIX):]
    target_path = s3_access.make_s3_path(['Collections', coll_name, 'Uploads', s3_test_upload])

    folders = s3_access.get_uploaded_folders(minio, s3_test_bucket, target_path)
    expected = __get_s3_upload_expected_image_folders()

    assert len(expected) > 0 and len(expected) <= len(folders)

    for one_expected in expected:
        print(f'test_get_uploaded_folders: Testing folder \"{one_expected}\"', flush=True)
        assert one_expected in folders
