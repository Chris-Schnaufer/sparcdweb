import pytest

def pytest_addoption(parser):
    parser.addoption('--s3_endpoint', action='store')
    parser.addoption('--s3_name', action='store')
    parser.addoption('--s3_secret', action='store')
    parser.addoption('--s3_test_bucket', action='store', default='sparcd-test-data')
    parser.addoption('--s3_test_upload', action='store', default='2025.12.22.12.21.22_schnaufer')
