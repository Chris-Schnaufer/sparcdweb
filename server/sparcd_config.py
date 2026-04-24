""" Configuration and shared utilities for SPARCd server """

import os
import sys
import tempfile
from typing import Callable, Optional

from flask import jsonify
from flask_cors import cross_origin

from route_decorators import make_authenticated_route
from sparcd_db import SPARCdDatabase
from spd_types.userinfo import UserInfo
from spd_types.s3info import S3Info
import spd_crypt as crypt
from s3_access import SPARCD_PREFIX
import s3_utils as s3u


# =============================================================================
# Environment variable names
# =============================================================================

# Environment variable name for allowed origins
ENV_ALLOWED_ORIGINS = 'SPARCD_ALLOWED_ORIGINS'
# Environment variable name for database
ENV_NAME_DB = 'SPARCD_DB'
# Environment variable name for passcode
ENV_NAME_PASSCODE = 'SPARCD_CODE'
# Environment variable name for session expiration timeout
ENV_NAME_SESSION_EXPIRE = 'SPARCD_SESSION_TIMEOUT'
# Environment variable name for default settings files
ENV_DEFAULT_SETTINGS_PATH = 'SPARCD_DEFAULT_SETTINGS_PATH'


# =============================================================================
# Environment variable values
# =============================================================================

# The allowed origins
DEFAULT_ALLOWED_ORIGINS = 'http://localhost:3000'
ALLOWED_ORIGINS = os.environ.get(ENV_ALLOWED_ORIGINS, DEFAULT_ALLOWED_ORIGINS)

# Working database storage path
DEFAULT_DB_PATH = os.environ.get(ENV_NAME_DB, None)

# Working passcode
_CURRENT_PASSCODE = os.environ.get(ENV_NAME_PASSCODE, None)

# Working amount of time after last action before session is expired
SESSION_EXPIRE_DEFAULT_SEC = 10 * 60 * 60
SESSION_EXPIRE_SECONDS = os.environ.get(ENV_NAME_SESSION_EXPIRE, SESSION_EXPIRE_DEFAULT_SEC)

# Folder that has the template settings files used to setup a new SPARCd instance or repair one
DEFAULT_SETTINGS_PATH = os.environ.get(ENV_DEFAULT_SETTINGS_PATH,
                                       os.path.join(os.getcwd(), 'defaultSettings'))


# =============================================================================
# Timeout constants
# =============================================================================

# Collection table timeout length
TIMEOUT_COLLECTIONS_SEC = 12 * 60 * 60
# Timeout for one upload folder file information
TIMEOUT_UPLOADS_FILE_SEC = 15 * 60
# Timeout for query results on disk
QUERY_RESULTS_TIMEOUT_SEC = 24 * 60 * 60
# Timeout for login page cache
LOGIN_PAGE_BROWSER_CACHE_TIMEOUT_SEC = 10800
# Timeout for image browser cache
IMAGE_BROWSER_CACHE_TIMEOUT_SEC = 10800
# Default timeout when requesting an image
DEFAULT_IMAGE_FETCH_TIMEOUT_SEC = 10.0
# Timeout for upload stats file
TEMP_UPLOAD_STATS_FILE_TIMEOUT_SEC = 1 * 60 * 60


# =============================================================================
# File name constants
# =============================================================================

# Starting point for uploading files from server
RESOURCE_START_PATH = os.path.abspath(os.path.dirname(__file__))

# Name of temporary species file
TEMP_SPECIES_FILE_NAME = SPARCD_PREFIX + 'species.json'

# Name of temporary upload stats file postfix
TEMP_UPLOAD_STATS_FILE_NAME_POSTFIX = '-' + SPARCD_PREFIX + 'upload-stats.json'

# Name of temporary other species file postfix
TEMP_OTHER_SPECIES_FILE_NAME_POSTFIX = '-' + SPARCD_PREFIX + 'other-species.json'

# Temporary directory path
TEMP_DIR = tempfile.gettempdir()

# Name of temporary upload stats file
TEMP_SPECIES_STATS_FILE_NAME_POSTFIX = '-' + SPARCD_PREFIX + 'species-stats.json'
TEMP_SPECIES_STATS_FILE_TIMEOUT_SEC = 12 * 60 * 60


# =============================================================================
# Request constants
# =============================================================================

# Allowed file extensions for static file serving
REQEST_ALLOWED_FILE_EXTENSIONS = ['.png', '.jpg', '.jepg', '.ico', '.gif',
                                   '.html', '.css', '.js', '.woff2']

# Allowed image extensions
REQEST_ALLOWED_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.ico', '.gif']

# List of known query form variable keys
KNOWN_QUERY_KEYS = ['collections', 'dayofweek', 'elevations', 'endDate', 'hour',
                    'locations', 'month', 'species', 'startDate', 'years']

# Species that aren't part of the statistics
SPECIES_STATS_EXCLUDE = ('Ghost', 'None', 'Test')

# UI definitions for serving
DEFAULT_TEMPLATE_PAGE = 'index.html'


# =============================================================================
# Startup validation
# =============================================================================

if not DEFAULT_DB_PATH or not os.path.exists(DEFAULT_DB_PATH):
    sys.exit(f'Database not found. Set the {ENV_NAME_DB} environment variable to the full '
             f'path of a valid file')

if not _CURRENT_PASSCODE:
    sys.exit(f'Passcode not found. Set the {ENV_NAME_PASSCODE} environment variable to a '
             f'strong passcode (password)')

WORKING_PASSCODE = crypt.get_fernet_key_from_passcode(_CURRENT_PASSCODE)


# =============================================================================
# Shared helper functions
# =============================================================================

def get_password(token: str, db: SPARCdDatabase) -> Optional[str]:
    """ Returns the password associated with the token in plain text
    Arguments:
        token: the user's token
        db: the database instance
    Return:
        The plain text password
    """
    return crypt.do_decrypt(WORKING_PASSCODE, db.get_password(token))


def get_s3_info(token: str, db: SPARCdDatabase, user_info: UserInfo,
                eager_password: bool = False) -> S3Info:
    """ Returns the S3 endpoint information for the current user
    Arguments:
        token: the session token
        db: the database instance
        user_info: the authenticated user's information
        eager_password: if True, fetches the password immediately rather than
                        lazily, required for multithreaded operations where
                        database calls cannot be made from worker threads
    Return:
        Returns the S3 endpoint information
    """
    password = get_password(token, db) if eager_password else lambda: get_password(token, db)
    return s3u.get_s3_info(user_info.url,
                           user_info.name,
                           password,
                           lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

def make_handler_response(resp) -> tuple:
    """ Converts a standard handler result to a Flask response
    Arguments:
        resp: the handler result - False returns 406, None returns 404,
              otherwise the response is jsonified and returned
    Return:
        Returns a Flask response tuple
    """
    if resp is False:
        return 'Not Found', 406
    if resp is None:
        return 'Not Found', 404
    return jsonify(resp)


def temp_species_filename(s3_id: str) -> str:
    """ Returns the temporary species filename for the given S3 ID
    Arguments:
        s3_id: the S3 endpoint ID
    Return:
        Returns the temporary species filename
    """
    return s3_id + '-' + TEMP_SPECIES_FILE_NAME


# =============================================================================
# Authenticated route decorator
# =============================================================================

authenticated_route = make_authenticated_route(DEFAULT_DB_PATH,
                                               SESSION_EXPIRE_SECONDS,
                                               get_s3_info)
