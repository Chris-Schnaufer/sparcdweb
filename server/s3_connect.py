""" This script contains the code to create an S3 connection instance
"""

from minio import Minio
from minio.error import MinioException
import os

# Environment variable name for session expiration timeout
ENV_S3_INSECURE_NAME = 'S3_INSECURE'

# Try and get the configured S3 connection security type
S3_CONNECTION_INSECURE = os.environ.get(ENV_S3_INSECURE_NAME,  False)


def s3_connect(url: str, access_key: str, secret_key: str, secure: bool=None) -> Minio:
    """ Creates an instance of the S3 connection
    Arguments:
        url: the URL of the S3 instance
        access_key: the access identifier to connect with
        secret_key: the access_key's associated secret
        secure: will use a secure connection when True (over https for example). Otherwise,
                an insecure connection will be used
    Return:
        The S3 connection instance
    """
    minio = None
    is_secure = not S3_CONNECTION_INSECURE if secure is None else not not secure

    try:
        minio = Minio(url, access_key=access_key, secret_key=secret_key, secure=is_secure)
    except MinioException as ex:
        print('S3 exception caught:', ex, flush=True)

    return minio
