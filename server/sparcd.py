#!/usr/bin/python3
"""This script contains the API for the SPARC'd server
"""

import hashlib
import json
import os
import sys
import tempfile
from typing import Optional

from flask import Flask, jsonify, make_response, render_template, request, send_file, \
                  send_from_directory
from flask_cors import cross_origin

import handlers.admin as hadmin
import handlers.base as hbase
import handlers.image as himage
import handlers.next as hnext
import handlers.query as hquery
import handlers.sandbox as hsand
import handlers.species as hspecies
import handlers.upload as hupload
from route_decorators import make_authenticated_route
from sparcd_db import SPARCdDatabase
import sparcd_collections as sdc
import sparcd_utils as sdu
# TODO: Move the code using the following to sparcd_utils
from sparcd_utils import TEMP_SPECIES_STATS_FILE_NAME_POSTFIX, TEMP_SPECIES_STATS_FILE_TIMEOUT_SEC
import spd_crypt as crypt
from s3_access import S3Connection, SPARCD_PREFIX
import s3_utils as s3u


# The allowed origins
DEFAULT_ALLOWED_ORIGINS="http://localhost:3000"

# Starting point for uploading files from server
RESOURCE_START_PATH = os.path.abspath(os.path.dirname(__file__))

# Allowed file extensions
REQEST_ALLOWED_FILE_EXTENSIONS=['.png','.jpg','.jepg','.ico','.gif','.html','.css','.js','.woff2']

# Allowed image extensions
REQEST_ALLOWED_IMAGE_EXTENSIONS=['.png','.jpg','.jpeg','.ico','.gif']

# Environment allowed origin names
ENV_ALLOWED_ORIGINS = 'SPARCD_ALLOWED_ORIGINS'
# Environment variable name for database
ENV_NAME_DB = 'SPARCD_DB'
# Environment variable name for passcode
ENV_NAME_PASSCODE = 'SPARCD_CODE'
# Environment variable name for session expiration timeout
ENV_NAME_SESSION_EXPIRE = 'SPARCD_SESSION_TIMEOUT'
# Environment variable name for default settings files
ENV_DEFAULT_SETTINGS_PATH = 'SPARCD_DEFAULT_SETTINGS_PATH'
# Default timeout in seconds
SESSION_EXPIRE_DEFAULT_SEC = 10 * 60 * 60
# Working database storage path
DEFAULT_DB_PATH = os.environ.get(ENV_NAME_DB,  None)
# Working passcode
CURRENT_PASSCODE = os.environ.get(ENV_NAME_PASSCODE, None)
# Working amount of time after last action before session is expired
SESSION_EXPIRE_SECONDS = os.environ.get(ENV_NAME_SESSION_EXPIRE, SESSION_EXPIRE_DEFAULT_SEC)
# Collection table timeout length
TIMEOUT_COLLECTIONS_SEC = 12 * 60 * 60
# Timeout for one upload folder file information
TIMEOUT_UPLOADS_FILE_SEC = 15 * 60
# Timeout for query results on disk
QUERY_RESULTS_TIMEOUT_SEC = 24 * 60 * 60

# Allowed origins
ALLOWED_ORIGINS = os.environ.get(ENV_ALLOWED_ORIGINS, DEFAULT_ALLOWED_ORIGINS)

# Folder that has the template settings files used to setup a new SPARCd instance or repair an
# existing one
DEFAULT_SETTINGS_PATH = os.environ.get(ENV_DEFAULT_SETTINGS_PATH,
                                                        os.path.join(os.getcwd(),"defaultSettings"))

# Timeout for login page cache
LOGIN_PAGE_BROWSER_CACHE_TIMEOUT_SEC = 10800

# Timeout for image browser cache
IMAGE_BROWSER_CACHE_TIMEOUT_SEC = 10800

# Name of temporary species file
TEMP_SPECIES_FILE_NAME = SPARCD_PREFIX + 'species.json'

# Name of temporary upload stats file
TEMP_UPLOAD_STATS_FILE_NAME_POSTFIX = '-' + SPARCD_PREFIX + 'upload-stats.json'
TEMP_UPLOAD_STATS_FILE_TIMEOUT_SEC = 1 * 60 * 60

# Default timeout when requesting an image
DEFAULT_IMAGE_FETCH_TIMEOUT_SEC = 10.0

# Name of temporary upload stats file
TEMP_OTHER_SPECIES_FILE_NAME_POSTFIX = '-' + SPARCD_PREFIX + 'other-species.json'

# UI definitions for serving
DEFAULT_TEMPLATE_PAGE = 'index.html'

# List of known query form variable keys
KNOWN_QUERY_KEYS = ['collections','dayofweek','elevations','endDate','hour','locations',
                    'month','species','startDate','years']

# Species that aren't part of the statistics
SPECIES_STATS_EXCLUDE = ('Ghost', 'None', 'Test')

# Don't run if we don't have a database or passcode
if not DEFAULT_DB_PATH or not os.path.exists(DEFAULT_DB_PATH):
    sys.exit(f'Database not found. Set the {ENV_NAME_DB} environment variable to the full path ' \
                'of a valid file')
if not CURRENT_PASSCODE:
    sys.exit(f'Passcode not found. Set the {ENV_NAME_PASSCODE} environment variable a strong ' \
                'passcode (password)')
WORKING_PASSCODE=crypt.get_fernet_key_from_passcode(CURRENT_PASSCODE)

# Initialize server
app = Flask(__name__)
# Secure cookie settings
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=600,
)
app.config.from_object(__name__)

# Intialize the database connection
_db = SPARCdDatabase(DEFAULT_DB_PATH)
_db.connect()
del _db
_db = None
print(f'Using database at {DEFAULT_DB_PATH}', flush=True)
print(f'Temporary folder at {tempfile.gettempdir()}', flush=True)

authenticated_route = make_authenticated_route(DEFAULT_DB_PATH, SESSION_EXPIRE_SECONDS)

def hash2str(text: str) -> str:
    """ Returns the hash of the passed in string
    Arguments:
        text: the string to hash
    Return:
        The hash value as a string
    """
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def get_password(token: str, db: SPARCdDatabase) -> Optional[str]:
    """ Returns the password associated with the token in plain text
    Arguments:
        token: the user's token
        db: the database instance
    Return:
        The plain text password
    """
    return crypt.do_decrypt(WORKING_PASSCODE, db.get_password(token))


@app.route('/', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def index():
    """Default page"""
    print("RENDERING TEMPLATE",DEFAULT_TEMPLATE_PAGE,os.getcwd(),flush=True)
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('HTTP_ORIGIN', \
                                    request.environ.get('HTTP_REFERER',request.remote_addr) \
                                    ))
    client_user_agent =  request.environ.get('HTTP_USER_AGENT', None)
    if not client_ip or client_ip is None or not client_user_agent or client_user_agent == '-':
        return 'Resource not found', 404

    response = make_response(render_template(DEFAULT_TEMPLATE_PAGE))
    response.headers.set('Cache-Control', f'public, max-age={LOGIN_PAGE_BROWSER_CACHE_TIMEOUT_SEC}')
    return response


@app.route('/favicon.ico', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def favicon():
    """ Return the favicon """
    return send_from_directory(app.root_path,
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/mapImage.png', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def mapimage():
    """ Return the image """
    return send_from_directory(app.root_path,
                               'mapImage.png', mimetype='image/png')


@app.route('/badimage.png', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def badimage():
    """ Return the image """
    return send_from_directory(app.root_path,
                               'badimage.png', mimetype='image/png')


@app.route('/sparcd.png', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def sparcdpng():
    """ Return the image """
    return send_from_directory(app.root_path,
                               'sparcd.png', mimetype='image/png')


@app.route('/wildcatResearch.png', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def wildcatresearch():
    """ Return the image """
    return send_from_directory(app.root_path,
                               'wildcatResearch.png', mimetype='image/png')


@app.route('/loading.gif', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def loading():
    """ Return the image """
    return send_from_directory(app.root_path,
                               'loading.gif', mimetype='image/gif')


@app.route('/sanimalBackground.JPG', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def sanimalbackground():
    """ Return the image """
    return send_from_directory(app.root_path,
                               'sanimalBackground.JPG', mimetype='image/jpeg')


@app.route('/_next/static/<path:path_fragment>', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def sendnextfile(path_fragment: str):
    """Return files"""
    print("RETURN _next FILENAME:",path_fragment,flush=True)
    return_path = hnext.handle_next_static(path_fragment, REQEST_ALLOWED_FILE_EXTENSIONS)
    if not return_path:
        return 'Resource not found', 404
    return send_file(return_path)


@app.route('/_next/image', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def sendnextimage():
    """Return image files"""
    print("RETURN _next IMAGE:",flush=True)
    file_path, img_byte_array, image_type = hnext.handle_next_image(request.args.get('url'),
                                                                    request.args.get('w'),
                                                                    request.args.get('q'),
                                                                    REQEST_ALLOWED_FILE_EXTENSIONS
                                                                   )

    if not all(val for val in [file_path, img_byte_array, image_type]):
        return 'Resource not found', 404

    if file_path and not img_byte_array:
        return send_file(file_path)

    return send_file(img_byte_array, mimetype="image/" + image_type.lower())


@app.route('/login', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def login_token():
    """ Returns a token representing the login. No checks are made on the parameters
    Arguments: (POST or GET)
        url - the S3 database URL
        user - the user name
        password - the user credentials
        token - the token to check for
    Return:
        Returns the session key and associated user information
    Notes:
        All parameters can be specified. If a token is specified, it's checked
        for expiration first. If valid login information is specified, and the token
        is invalid/missing/expired, a new token is returned
    """
    db = SPARCdDatabase(DEFAULT_DB_PATH)
    print('LOGIN',flush=True)

    result = hbase.handle_login(db,
                                WORKING_PASSCODE,
                                SESSION_EXPIRE_SECONDS,
                                # We don't have the S3 ID yet so only pass in the name
                                TEMP_SPECIES_FILE_NAME,
                                hash2str
                               )
    if not result:
        return "Not Found", 404

    return jsonify(result)


@app.route('/collections', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def collections(*, db, token, user_info):
    """ Returns the list of collections and their uploads
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: a JSON list of sandbox upload collections accessible to the user.
             Non-admin users only see their own uploads.
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
    """
    print('COLLECTIONS', request, flush=True)

    # The S3 endpoint information
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    return_colls = sdc.load_collections(db, bool(user_info.admin), s3_info)

    if return_colls is None:
        return 'Unable to load collections', 423

    # Return the collections
    if not bool(user_info.admin):
        # Filter out collections if not an admin
        return_colls = [one_coll for one_coll in return_colls if 'permissions' in one_coll and \
                                                                            one_coll['permissions']]

    return jsonify([one_coll|{'allPermissions':None} for one_coll in return_colls])


@app.route('/sandbox', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def sandbox(*, db, token, user_info):
    """ Returns the list of sandbox uploads
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: a JSON list of sandbox upload collections accessible to the user.
             Non-admin users only see their own uploads.
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
    """
    print(f'SANDBOX user={user_info.name} admin={bool(user_info.admin)}', flush=True)

    # The S3 endpoint information
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    return jsonify(hsand.handle_sandbox(db, user_info, s3_info))


@app.route('/locations', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def locations(*, db, token, user_info):
    """ Returns the list of locations
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: a JSON list of sandbox upload collections accessible to the user.
             Non-admin users only see their own uploads.
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
    """
    print('LOCATIONS', request, flush=True)

    # Get the locations to return
    # The S3 endpoint information
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    cur_locations = sdu.load_locations(s3_info)

    # Return the locations
    return jsonify(cur_locations)


@app.route('/species', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def species(*, db, token, user_info):
    """ Returns the list of species
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: a JSON list of sandbox upload collections accessible to the user.
             Non-admin users only see their own uploads.
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
    """
    print(f'SPECIES user={user_info.name}', flush=True)

    # Get the species to return
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    ret_species, is_json = hbase.handle_species(db,
                                                user_info,
                                                s3_info,
                                                s3_info.id+'-'+TEMP_SPECIES_FILE_NAME)

    if is_json is True:
        return ret_species

    return jsonify(ret_species)


@app.route('/speciesStats', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def species_stats(*, db, token, user_info):
    """ Returns the statistics on species
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: a JSON list of sandbox upload collections accessible to the user.
             Non-admin users only see their own uploads.
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
    """
    print('SPECIES STAT', request, flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    # Check if we already have the stats
    stats = sdu.load_species_stats( db,
                                bool(user_info.admin),
                                s3_info)

    if stats is None:
        return "Not Found", 404

    # Remove the unofficial species file so that it can be recreated
    otherspecies_temp_filename = os.path.join(tempfile.gettempdir(),  \
                                                s3_info.id+TEMP_OTHER_SPECIES_FILE_NAME_POSTFIX)
    if os.path.exists(otherspecies_temp_filename):
        os.unlink(otherspecies_temp_filename)

    return jsonify([[key, value['count']] for key, value in stats.items() if key \
                                                                    not in SPECIES_STATS_EXCLUDE])


@app.route('/speciesOther', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def species_other(*, db, token, user_info):
    """ Returns the species that are not part of the official set
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: a JSON list of sandbox upload collections accessible to the user.
             Non-admin users only see their own uploads.
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
    """
    print('SPECIES OTHER', request, flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    other_species = hspecies.handle_species_other(s3_info,
                                hspecies.OtherSpeciesParams(
                                other_filename=s3_info.id + TEMP_OTHER_SPECIES_FILE_NAME_POSTFIX,
                                stat_filename=s3_info.id + TEMP_SPECIES_STATS_FILE_NAME_POSTFIX,
                                stat_timeout_sec=TEMP_SPECIES_STATS_FILE_TIMEOUT_SEC,
                                temp_species_filename=s3_info.id+'-'+TEMP_SPECIES_FILE_NAME,
                                )
                            )
    return jsonify(other_species)


@app.route('/uploadImages', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def upload_images(*, db, token, user_info):
    """ Returns the list of images from a collection's upload
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: a JSON list of sandbox upload collections accessible to the user.
             Non-admin users only see their own uploads.
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'UPLOAD user={user_info.name}', flush=True)

    # The S3 information
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    params = hupload.UploadImagesParams(passcode=WORKING_PASSCODE,
                                        temp_species_filename=s3_info.id+'-'+TEMP_SPECIES_FILE_NAME
                                       )
    all_images = hupload.handle_upload_images(db, user_info, s3_info, params)

    if not all_images:
        return "Not Found", 406

    return jsonify(all_images)


@app.route('/image', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def image():
    """ Returns the image from the S3 storage
    Arguments: (GET)
        token - the session token
        i - the key of the image
    Return:
        Returns the image
    Notes:
         If the token is invalid, or a problem occurs, a 404 error is returned
   """
    db = SPARCdDatabase(DEFAULT_DB_PATH)
    token = request.args.get('t')
    print('IMAGE', request, flush=True)

    # Check the credentials
    # We aren't concerned with the requestors origin IP
    client_user_agent =  request.environ.get('HTTP_USER_AGENT', None)
    if not client_user_agent or client_user_agent is None:
        return "Not Found", 404
    user_agent_hash = hashlib.sha256(client_user_agent.encode('utf-8')).hexdigest()

    # Allow a timely request from everywhere
    token_valid, user_info = sdu.token_is_valid(token, '*', user_agent_hash, db,
                                                                            SESSION_EXPIRE_SECONDS)
    if not token_valid or not user_info:
        return "Unauthorized", 401

    # The S3 endpoint information
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    res = hbase.handle_image(db,
                             s3_info,
                             request.args.get('i'),
                             DEFAULT_IMAGE_FETCH_TIMEOUT_SEC,
                             WORKING_PASSCODE,
                            )

    response = make_response(res.content)
    response.headers.set('Cache-Control', f'public, max-age={IMAGE_BROWSER_CACHE_TIMEOUT_SEC}')
    return response


@app.route('/checkChanges', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def check_changes(*, db, token, user_info):
    """ Checks if changes have been made to an upload and are stored in the database
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: a JSON list of sandbox upload collections accessible to the user.
             Non-admin users only see their own uploads.
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print('CHECK CHANGES', request, flush=True)

    # Check the rest of the request parameters
    collection_id = request.form.get('id', None)
    collection_upload = request.form.get('up', None)

    if not collection_id or not collection_upload:
        return "Not Found", 406

    # The S3 endpoint information
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    have_changes = db.have_upload_changes(s3_info.id, SPARCD_PREFIX+collection_id,
                                                                                collection_upload)

    return jsonify({'changesMade': have_changes})


@app.route('/query', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def query(*, db, token, user_info):
    """ Returns a token representing the login. No checks are made on the parameters
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: a JSON list of sandbox upload collections accessible to the user.
             Non-admin users only see their own uploads.
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
    Notes:
        All parameters can be specified. If a token is specified, it's checked
        for expiration first. If valid login information is specified, and the token
        is invalid/missing/expired, a new token is returned
    """
    print(f'QUERY user={user_info.name} token={token}', request)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    # We let the handler do everything
    return_info = hquery.handle_query(db,
                                      user_info,
                                      s3_info,
                                      token,
                                      s3_info.id+'-'+TEMP_SPECIES_FILE_NAME)
    if return_info is None:
        return "Not Found", 406

    return jsonify(return_info)


@app.route('/query_dl', methods = ['GET'])
@cross_origin(origins="*", supports_credentials=True)
@authenticated_route()
def query_dl(*, db, token, user_info):
    """ Returns the results of a query
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: a JSON list of sandbox upload collections accessible to the user.
             Non-admin users only see their own uploads.
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """

    # Check the rest of the request parameters
    tab = request.args.get('q')
    target = request.args.get('d')
    print(f'QUERY DOWNLOAD user={user_info.name} tab={tab} target={target}', request, flush=True)

    # Check what we have from the requestor
    if not tab:
        return "Not Found", 406

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    have_results, response = hquery.handle_query_download(db,
                                          user_info,
                                          s3_info,
                                          hquery.QueryDownloadParams(token=token,
                                                             tab_name=tab,
                                                             target=target,
                                                             timeout_sec=QUERY_RESULTS_TIMEOUT_SEC
                                                             )
                                        )
    if not have_results:
        return "Not Found", 422
    if not response:
        return "Not Found", 404

    return response


@app.route('/settings', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def set_settings(*, db, token, user_info):
    """ Updates the user's settings
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: a JSON list of sandbox upload collections accessible to the user.
             Non-admin users only see their own uploads.
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'SET SETTINGS user={user_info.name}', flush=True)

    # Check the rest of the request parameters
    new_settings = {
        'autonext': request.form.get('autonext'),
        'dateFormat': request.form.get('dateFormat'),
        'measurementFormat': request.form.get('measurementFormat'),
        'sandersonDirectory': request.form.get('sandersonDirectory'),
        'sandersonOutput': request.form.get('sandersonOutput'),
        'timeFormat': request.form.get('timeFormat'),
        'coordinatesDisplay': request.form.get('coordinatesDisplay')
    }
    new_email = request.form.get('email')

    # The S3 endpoint information
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    user_info = hbase.handle_settings(db, user_info, s3_info, new_settings, new_email)

    return jsonify(user_info.settings)


@app.route('/locationInfo', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def location_info(*, db, token, user_info):
    """ Returns details on a location
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: a JSON list of sandbox upload collections accessible to the user.
             Non-admin users only see their own uploads.
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print('LOCATION INFO', flush=True)

    # The S3 endpoint information
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    loc_info = hbase.handle_location_info(s3_info)
    if not loc_info:
        return "Not Found", 406

    return jsonify(loc_info)


@app.route('/sandboxStats', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def sandbox_stats(*, db, token, user_info):
    """ Returns the upload statistics for display
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: a JSON list of sandbox statistics
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
    """
    print('SANDBOX STATS', request, flush=True)

    # The S3 endpoint information
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    return jsonify(hsand.handle_sandbox_stats(db,
                                              user_info,
                                              s3_info,
                                              s3_info.id + TEMP_UPLOAD_STATS_FILE_NAME_POSTFIX,
                                              TEMP_UPLOAD_STATS_FILE_TIMEOUT_SEC
                                              )
                  )


@app.route('/sandboxPrev', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def sandbox_prev(*, db, token, user_info):
    """ Checks if a sandbox item has been previously uploaded
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object with the following fields:
                 exists (bool): whether a previous upload exists for the given path
                 path (str): the relative path of the upload
                 uploadedFiles: the list of previously uploaded files, or None if none exist
                 elapsed_sec: the number of seconds since the upload was started, or None
                 id: the upload ID, or None if no previous upload exists
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
    """
    print('SANDBOX PREV user={user_info.name}', flush=True)

    # Check the rest of the request parameters
    rel_path = request.form.get('path')
    if not rel_path:
        return "Not Found", 406

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    # Check with the DB if the upload has been started before ignoring the previous upload ID
    elapsed_sec, uploaded_files, upload_id, _ = db.sandbox_get_upload(s3_info.id,
                                                                        user_info.name,
                                                                        rel_path,
                                                                        True)
    return jsonify({'exists': (uploaded_files is not None),
                    'path': rel_path,
                    'uploadedFiles': uploaded_files,
                    'elapsed_sec': elapsed_sec,
                    'id': upload_id
                  })


@app.route('/sandboxRecoveryUpdate', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def sandbox_recovery_update(*, db, token, user_info):
    """ Updates the sandbox information in the database upon upload recovery
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print('SANDBOX RECOVERY UPDATE user={user_info.name}', flush=True)

    # Check the rest of the request parameters
    coll_id = request.form.get('id', None)
    upload_key = request.form.get('key', None)
    loc_id = request.form.get('loc', None)
    source_path = request.form.get('path', None)

    if not all(item for item in [token, source_path, upload_key, coll_id]):
        return "Not Found", 406

    # The S3 endpoint information
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    # Handle the sandbox recovery updates
    result = hsand.handle_sandbox_recovery_update(db, user_info, s3_info,
                        hsand.SandboxRecoveryParams(coll_id=coll_id, upload_key=upload_key,
                                                loc_id=loc_id, source_path=source_path) )

    if result is False:
        return "Not Found", 404

    if result is None:
        return jsonify({'success': False,
                            'message': 'Unable to update the upload to receive the files'})

    return jsonify({'success': True, 'id': result[0], 'files': result[1],
                        'message': 'Successfully updated for the file upload'})


@app.route('/sandboxCheckContinueUpload', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def sandbox_check_continue_upload(*, db, token, user_info):
    """ Checks if a sandbox file already uploaded matches what we've just received
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
    """
    print('SANDBOX CHECK CONTINUE UPLOAD', flush=True)

    # Get the rest of the request parameters
    upload_id = request.form.get('id', None)

    # Check what we have from the requestor
    if not upload_id:
        return "Not Found", 406

    # The S3 information
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    all_match, message = hsand.handle_sandbox_check_continue_upload(db,
                                                              user_info,
                                                              s3_info,
                                                              upload_id,
                                                              request.files)

    return jsonify({'success': all_match is True,
                        'missing': all_match == 'missing',
                        'message': message})


@app.route('/sandboxNew', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def sandbox_new(*, db, token, user_info):
    """ Adds a new sandbox upload to the database
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
    """
    print('SANDBOX NEW user={user_info.name}', flush=True)

    # Check the rest of the request parameters
    location_id = request.form.get('location', None)
    collection_id = request.form.get('collection', None)
    comment = request.form.get('comment', None)
    rel_path = request.form.get('path', None)
    timestamp = request.form.get('ts', None)
    timezone = request.form.get('tz', None)

    # Check what we have from the requestor
    if not all(item for item in [location_id, collection_id, comment, rel_path, \
                                                                            timestamp, timezone]):
        return "Not Found", 406

    all_files = sdu.get_request_files() # Uses request directly
    if all_files is None:
        return "Not Found", 406

    # The S3 information
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    upload_id = hsand.handle_sandbox_new(db, user_info, s3_info,
                                        hsand.SandboxNewParams(location_id=location_id,
                                                         collection_id=collection_id,
                                                         comment=comment,
                                                         rel_path=rel_path,
                                                         all_files=all_files,
                                                         timestamp=timestamp,
                                                         timezone=timezone
                                                        )
                                   )

    if upload_id is None:
        return "Not Found", 406

    # Return the new ID
    return jsonify({'id': upload_id})


@app.route('/sandboxFile', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def sandbox_file(*, db, token, user_info):
    """ Handles the upload for a new image
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
    """
    print('SANDBOX FILE user={user_info.name}', flush=True)

    # Get the rest of the request parameters
    upload_id = request.form.get('id', None)
    tz_offset = request.form.get('tz_off', None)

    # Check what we have from the requestor
    if not upload_id or len(request.files) <= 0:
        return "Not Found", 406

    # Get the location to upload to
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))


    hsand.handle_sandbox_file(db,
                              user_info,
                              s3_info,
                              hsand.SandboxFileParams(upload_id=upload_id,
                                                      tz_offset=tz_offset,
                                                      files=request.files
                                                      )
                             )

    return jsonify({'success': True})


@app.route('/sandboxCounts', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def sandbox_counts(*, db, _token, user_info):
    """ Returns the counts of the sandbox upload
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print('SANDBOX COUNTS', flush=True)

    # Check what we have from the requestor
    upload_id = request.args.get('i')
    if not upload_id:
        return "Not Found", 406

    # Get the count of uploaded files
    counts = db.sandbox_upload_counts(user_info.name, upload_id)

    return jsonify({'total': counts[0], 'uploaded': counts[1]})


@app.route('/sandboxUnloadedFiles', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def sandbox_unloaded_files(*, db, _token, user_info):
    """ Returns the list of files that are not loaded
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print('SANDBOX UNLOADED FILES user={user_info.name}', flush=True)

    # Check what we have from the requestor
    upload_id = request.args.get('i')
    if not upload_id:
        return "Not Found", 406

    # Get the list of files not uploaded
    return jsonify(db.sandbox_files_not_uploaded(user_info.name, upload_id))


@app.route('/sandboxReset', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def sandbox_reset(*, db, _token, user_info):
    """ Resets the sandbox to start an upload from the beginning
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print('SANDBOX RESET user={user_info.name}', flush=True)

    # Get the rest of the request parameters
    upload_id = request.form.get('id', None)
    all_files = request.form.get('files', None)
    if not upload_id or not all_files:
        return "Not Found", 406

    # Get all the file names
    try:
        all_files = json.loads(all_files)
    except json.JSONDecodeError as ex:
        print('ERROR: Unable to load file list JSON', ex, flush=True)
        return "Not Found", 406

    # Check with the DB if the upload has been started before
    upload_id = db.sandbox_reset_upload(user_info.name, upload_id, all_files)

    return jsonify({'id': upload_id})


@app.route('/sandboxAbandon', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def sandbox_abandon(*, db, _token, user_info):
    """ Removes the sandbox and any uploaded files
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print('SANDBOX ABANDON user={user_info.name}', flush=True)

    # Get the rest of the request parameters
    upload_id = request.form.get('id', None)
    if not upload_id:
        return "Not Found", 406

    # Get the upload path
    # Not needed since we aren't yet removing files from S3
    #s3_bucket, s3_path = db.sandbox_get_s3_info(user_info.name, upload_id)

    # Remove the upload from the DB
    completed_count = db.sandbox_upload_counts(user_info.name, upload_id)
    db.sandbox_upload_complete(user_info.name, upload_id)

    # We don't remove the actual data because it's not recoverable
    # Remove the files from S3
    #if upload_info:
    #    s3_info = s3u.get_s3_info(user_info.url,
    #                         user_info.name,
    #                         lambda: get_password(token, db),
    #                         lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))
    #
    #    S3Connection.remove_upload(s3_info, s3_bucket, s3_path)

    return jsonify({'id': upload_id, 'completed': completed_count})


@app.route('/sandboxCompleted', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def sandbox_completed(*, db, token, user_info):
    """ Marks a sandbox as completely uploaded
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print('SANDBOX COMPLETED user={user_info.name}', flush=True)

    # Get the rest of the request parameters
    upload_id = request.form.get('id', None)
    if not upload_id:
        return "Not Found", 406

    # Get the sandbox information
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    if not hsand.handle_sandbox_completed(db, user_info, s3_info, upload_id):
        return "Not Found", 404

    return jsonify({'success': True})


@app.route('/uploadLocation', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def image_location(*, db, token, user_info):
    """ Handles the location for images changing
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print('UPLOAD LOCATION user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    if not hupload.handle_upload_location(db,
                                          user_info,
                                          s3_info,
                                          s3_info.id+'-'+TEMP_SPECIES_FILE_NAME
                                         ):
        return "Not Found", 406

    return jsonify({'success': True})


@app.route('/imageSpecies', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def image_species(*, db, token, user_info):
    """ Handles the species and counts for an image changing
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print('IMAGE SPECIES user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    resp = himage.handle_image_species(db, user_info, s3_info, WORKING_PASSCODE)

    if resp is None:
        return "Not Found", 404
    if resp is False:
        return "Not Found", 406

    return jsonify({'success': True})


@app.route('/imageEditComplete', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def image_edit_complete(*, db, token, user_info):
    """ Handles updating one image with the changes made
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'IMAGE EDIT COMPLETE user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    resp = himage.handle_image_edit_complete(db,
                                             user_info,
                                             s3_info,
                                             WORKING_PASSCODE,
                                             s3_info.id+'-'+TEMP_SPECIES_FILE_NAME
                                             )

    if not resp:
        return "Not Found", 406

    return resp


@app.route('/imagesAllEdited', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def images_all_edited(*, db, token, user_info):
    """ Handles completing changes after all images have been edited
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'IMAGES ALL FINISHED user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    updated, kept_urls = himage.handle_images_all_edited(db, user_info, s3_info)

    if updated is None or kept_urls is None:
        return "Not Found", 406

    return {'success': True,
            'message': "The images have been successfully updated", \
            'updatedUpload': bool(updated),
            'imagesReloaded': not kept_urls,
            }


@app.route('/speciesKeybind', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def species_keybind(*, db, token, user_info):
    """ Handles the adding/changing a species keybind
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'IMAGE SPECIES user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    if not himage.handle_species_keybind(db,
                                         user_info,
                                         s3_info,
                                         s3_info.id+'-'+TEMP_SPECIES_FILE_NAME):
        return "Not Found", 406

    return jsonify({'success': True})


@app.route('/imageTimestamp', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def image_timestamps(*, db, token, user_info):
    """ Fetches the first timestamp found in the list of files
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print('IMAGE TIMESTAMP user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    file_ts = himage.handle_image_timestamp(s3_info, WORKING_PASSCODE)
    if file_ts is False:
        return 'Not found', 404
    if file_ts is None:
        return "Not Found", 406

    return jsonify({'success': file_ts is not None,
                    'timestamp': file_ts.isoformat() if file_ts else None
                   })


@app.route('/adjustTimestamps', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def adjust_timestamps(*, db, token, user_info):
    """ Adjust timestamps for the images files
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADJUST TIMESTAMP user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    res = himage.handle_adjust_timestamp(s3_info)
    if res is False:
        return "Not Found", 406
    if res is None:
        return jsonify({'success':False,
                        'message':'Unable to get media information from erver'})

    return jsonify({'success':True})


@app.route('/adminCheck', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def admin_check(*, _db, _token, user_info):
    """ Checks if the user might be an admin
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print('ADMIN CHECK', flush=True)
    return {'value': bool(user_info.admin)}


@app.route('/adminCheckChanges', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Must be an admin to do this
def admin_check_changes(*, db, token, user_info):
    """ Checks if the user might be an admin
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN CHECK CHANGES user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    # Check for changes in the db
    changed = db.have_admin_changes(s3_info.id, user_info.name)

    return {'success': True, 'locationsChanged': changed['locationsCount'] > 0, \
            'speciesChanged': changed['speciesCount'] > 0}


@app.route('/settingsAdmin', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Must be an admin to do this
def settings_admin(*, _db, _token, user_info):
    """ Confirms the password is correct for admin editing
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN SETTINGS user={user_info.name}', flush=True)

    # Get the rest of the request parameters
    pw = request.form.get('value', None)
    if not pw:
        return "Not Found", 406

    s3_info = s3u.get_s3_info(user_info.url,
                          user_info.name,
                          pw,
                          lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    pw_ok = hbase.handle_settings_admin(user_info, s3_info)
    if pw_ok is False:
        return "Not Found", 406
    if pw_ok is None:
        return "Not Found", 401

    return jsonify({'success': pw_ok})



@app.route('/settingsOwner', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(non_admin_only=True)   # An admin can't do this
def settings_owner(*, _db, _token, user_info):
    """ Confirms the password is correct for collection editing
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'OWNER CHECK user={user_info.name}', flush=True)

    # Get the rest of the request parameters
    pw = request.form.get('value', None)
    if not pw:
        return "Not Found", 406

    s3_info = s3u.get_s3_info(user_info.url,
                          user_info.name,
                          pw,
                          lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    pw_ok = hbase.handle_settings_owner(user_info, s3_info)
    if pw_ok is False:
        return "Not Found", 404
    if pw_ok is None:
        return "Not Found", 401

    return jsonify({'success': pw_ok})


@app.route('/adminCollectionDetails', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Only for admins
def admin_collection_details(*, db, token, user_info):
    """ Returns detailed collection information for admin editing
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN COLLECTION DETAILS user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    collection = hadmin.handle_admin_collection_details(db, user_info, s3_info)
    if collection is False:
        return "Not Found", 404

    return jsonify(collection)


@app.route('/ownerCollectionDetails', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(non_admin_only=True)   # An admin can't do this
def owner_collection_details(*, db, token, user_info):
    """ Returns detailed collection information for owner editing
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'OWNER COLLECTION DETAILS user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    # Extra checks if must_be_admin parameter is False (also None is not returned)
    collection = hadmin.handle_admin_collection_details(db, user_info, s3_info, False)
    if collection is False:
        return "Not Found", 404

    return jsonify(collection)


@app.route('/adminLocationDetails', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Only for admins
def admin_location_details(*, db, token, user_info):
    """ Returns detailed location for admin editing
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN LOCATION DETAILS user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    location = hadmin.handle_admin_location_details(user_info, s3_info)
    if location is False:
        return "Not Found", 406
    if location is None:
        return "Not Found", 404

    return jsonify(location)


@app.route('/adminUsers', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Only for admins
def admin_users(*, db, token, user_info):
    """ Returns user information for admin editing
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN USERS user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    users = hadmin.handle_admin_users(db, user_info, s3_info)
    if users is False or users is None:
        return "Not Found", 404

    return jsonify(users)


@app.route('/adminSpecies', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Only for admins
def admin_species(*, db, token, user_info):
    """ Returns "official" species for admin editing (not user-specific)
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN SPECIES user={user_info.name}', flush=True)

    # Get the species
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    cur_species = hadmin.handle_admin_species(user_info, s3_info,
                                                            s3_info.id+'-'+TEMP_SPECIES_FILE_NAME)
    if cur_species is False:
        return "Not Found", 406
    if cur_species is None:
        return "Not Found", 404

    return jsonify(cur_species)


@app.route('/adminUserUpdate', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Only for admins
def admin_user_update(*, db, token, user_info):
    """ Updates the user with the speciefied information
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN USER UDPATE user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    user_updated = hadmin.handle_user_update(db, user_info, s3_info)
    if user_updated is False:
        return "Not Found", 406
    if user_updated is None:
        return "Not Found", 404

    return jsonify(user_updated)


@app.route('/adminSpeciesUpdate', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Only for admins
def admin_species_update(*, db, token, user_info):
    """ Adds/updates a species entry
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN SPECIES UDPATE user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    resp = hadmin.handle_species_update(db, user_info, s3_info,
                                        s3_info.id+'-'+TEMP_SPECIES_FILE_NAME)
    if resp is False:
        return "Not Found", 406
    if resp is None:
        return "Not Found", 404

    return jsonify(resp)


@app.route('/adminLocationUpdate', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Only for admins
def admin_location_update(*, db, token, user_info):
    """ Adds/updates a location information
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN LOCATION UDPATE user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    resp = hadmin.handle_location_update(db, user_info, s3_info)
    if resp is False:
        return "Not Found", 406
    if resp is None:
        return "Not Found", 404

    return jsonify(resp)


@app.route('/adminCollectionUpdate', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Only for admins
def admin_collection_update(*, db, token, user_info):
    """ Updates a collection information
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN COLLECTION UDPATE user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    resp = hadmin.handle_collection_update(db, user_info, s3_info)
    if resp is False:
        return "Not Found", 406
    if resp is None:
        return "Not Found", 404

    return jsonify(resp)


@app.route('/adminCollectionAdd', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Only for admins
def admin_collection_add(*, db, token, user_info):
    """ Adds a collection information
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN COLLECTION UDPATE user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    resp = hadmin.handle_collection_add(db, user_info, s3_info)
    if resp is False:
        return "Not Found", 406
    if resp is None:
        return "Not Found", 404

    return jsonify(resp)


@app.route('/ownerCollectionUpdate', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(non_admin_only=True)   # An admin can't do this
def ownercollection_update(*, db, token, user_info):
    """ Adds/updates a collection information
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'OWNER COLLECTION UDPATE user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    resp = hadmin.handle_collection_update(db, user_info, s3_info, must_be_admin=False)
    if resp is False:
        return "Not Found", 406
    if resp is None:
        return "Not Found", 404

    return jsonify(resp)


@app.route('/adminCheckIncomplete', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Only for admins
def admin_check_incomplete(*, db, token, user_info):
    """ Looks for incomplete updated in collections
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN CHECK INCOMPLETE UPLOADS user={user_info.name}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    resp = hadmin.handle_check_incomplete(db, user_info, s3_info)
    if resp is False:
        return "Not Found", 406
    if resp is None:
        return "Not Found", 404

    return jsonify(resp)


@app.route('/adminCompleteChanges', methods = ['PUT'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Only for admins
def admin_complete_changes(*, db, token, user_info):
    """ Adds/updates a saved location and species information
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN COMPLETE THE CHANGES user={user_info.user}', flush=True)

    # Get the locations and species changes logged in the database
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    resp = hadmin.handle_complete_changes(db, user_info, s3_info,
                                                            s3_info.id+'-'+TEMP_SPECIES_FILE_NAME)
    if resp is False:
        return "Not Found", 406
    if resp is None:
        return "Not Found", 404

    return jsonify(resp)


@app.route('/adminAbandonChanges', methods = ['PUT'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)   # Only for admins
def admin_abandon_changes(*, db, token, user_info):
    """ Adds/updates a saved location and species information
    Arguments:
        db: the database instance (injected by authenticated_route)
        token: the session token (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
    Returns:
        200: JSON object
        401: if the session token is invalid or expired.
        404: if the request is malformed or the user cannot be found.
   """
    print(f'ADMIN ABANDON THE CHANGES user={user_info.admin}', flush=True)

    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    resp = hadmin.handle_abandon_changes(db, user_info, s3_info)
    if resp is False:
        return "Not Found", 406
    if resp is None:
        return "Not Found", 404

    return jsonify(resp)

@app.route('/installCheck', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def new_install_check():
    """ Checks if the S3 endpoint can support a new installation
    Arguments: (GET)
        t - the session token
    Return:
        Returns True/False if the endpoint appears to be able to support a new S3 installation
        (or not), if there are already collections on the remote endpoint, if the user is in the
        database already for this endpoint and is/is not admin.
    Notes:
         If the token is invalid, or a problem occurs, a 404 error is returned
   """
    db = SPARCdDatabase(DEFAULT_DB_PATH)
    token = request.args.get('t')
    print('NEW INSTALL CHECK', flush=True)

    # Check the credentials
    token_valid, user_info = sdu.token_user_valid(db, request, token, SESSION_EXPIRE_SECONDS)
    if token_valid is None or user_info is None:
        return "Not Found", 404
    if not token_valid or not user_info:
        return "Unauthorized", 401

    # Perform the checks on the S3 instance to see that we can support a new installation
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    # Return data
    return_data = { 'success':False,
                    'admin': bool(user_info.admin),
                    'needsRepair': False,
                    'failedPerms': False,
                    'newInstance': False,
                    'message': 'Success'
                   }

    # Check if the S3 instance needs repairs and not a new install
    needs_repair, has_everything = S3Connection.needs_repair(s3_info)
    if needs_repair:
        return_data['needsRepair'] = True
        return_data['message'] = 'You can try to perform a repair on the S3 endpoint'
        return jsonify(return_data)
    if has_everything:
        # The endpoint has everything needed (what are they up to?)
        return_data['success'] = True
        return_data['admin'] = False
        return_data['message'] = 'The endpoint already is configured for SPARCd'
        return jsonify(return_data)

    # Check if they can make a new install
    can_create, test_bucket = S3Connection.check_new_install_possible(s3_info)
    if not can_create:
        return_data['failedPerms'] = True
        return_data['message'] = 'Unable to install SPARCd at the S3 endpoint. Please ' \
                                        'contact your S3 administrator about permissions'
        return jsonify(return_data)

    # Check that there aren't any administrators for this endpoint in the database
    # If it's a new install, there shouldn't be an admin in the database (the endpoint is
    # unknown so no one should be an admin)
    if not bool(user_info.admin):
        if db.have_any_known_admin(s3_info.id):
            return_data['admin'] = False        # always false or we wouldn't be here
            return_data['message'] = 'You are not authorized to make a new installation or ' \
                                            'repair an existing one. Please contact your ' \
                                            'administrator'
            return jsonify(return_data)

    # TODO: When have messages to users and the test bucket isn't removed, inform the admin(s)
    if test_bucket is not None:
        print(f'WARNING: unable to delete testing bucket {test_bucket}', flush=True)

    return_data['success'] = True
    return_data['newInstance'] = True
    return jsonify(return_data)

@app.route('/installNew', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def install_new():
    """ Attempts to create a new SPARCd installation
    Arguments: (GET)
        t - the session token
    Return:
        Returns True success if the endpoint could be configured for SPARCd and
        False if not.
    Notes:
         If the token is invalid, or a problem occurs, a 404 error is returned
   """
    db = SPARCdDatabase(DEFAULT_DB_PATH)
    token = request.args.get('t')
    print('NEW INSTALL', flush=True)

    # Check the credentials
    token_valid, user_info = sdu.token_user_valid(db, request, token, SESSION_EXPIRE_SECONDS)
    if token_valid is None or user_info is None:
        return "Not Found", 404
    if not token_valid or not user_info:
        return "Unauthorized", 401

    # Perform the checks on the S3 instance to see that we can support a new installation
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    # Check that we can create
    sole_user = False
    if not bool(user_info.admin):
        if not db.is_sole_user(s3_info.id, user_info.name):
            return jsonify({'success': False,
                                'message': 'You are not authorized to create a new ' \
                                            'SPARCd configuration'})
        sole_user = True

    # Check if the S3 instance needs repairs and of is all set
    needs_repair, has_everything = S3Connection.needs_repair(s3_info)

    if needs_repair or has_everything:
        return jsonify({'success': False, 'message': 'There is already an existing SPARCd ' \
                                                        'configuration'})

    # The user is apparently the sole user or an admin, and the S3 instance is not setup for SPARCd
    if not S3Connection.create_sparcd(s3_info, DEFAULT_SETTINGS_PATH):
        return jsonify({'success': False, 'message': 'Unable to configure new SPARCd instance'})

    # Make this user the admin if they're the only one in the DB
    if sole_user:
        db.update_user(s3_info.id, user_info.name, user_info.email, True)

    return jsonify({'success': True})

@app.route('/installRepair', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def install_repair():
    """ Attempts to repair an existing SPARCd installation
    Arguments: (GET)
        t - the session token
    Return:
        Returns True success if the endpoint could be repaired and False if not.
    Notes:
         If the token is invalid, or a problem occurs, a 404 error is returned
   """
    db = SPARCdDatabase(DEFAULT_DB_PATH)
    token = request.args.get('t')
    print('REPAIR INSTALL', flush=True)

    # Check the credentials
    token_valid, user_info = sdu.token_user_valid(db, request, token, SESSION_EXPIRE_SECONDS)
    if token_valid is None or user_info is None:
        return "Not Found", 404
    if not token_valid or not user_info:
        return "Unauthorized", 401

    # Perform the checks on the S3 instance to see that we can support a new installation
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    # Check that we can create
    if not bool(user_info.admin):
        return jsonify({'success': False, 'message': 'You are not authorized to repair the ' \
                                                    'SPARCd configuration'})

    # Check if the S3 instance needs repairs and of is all set
    needs_repair, has_everything = S3Connection.needs_repair(s3_info)

    if not needs_repair or has_everything:
        return jsonify({'success': True, \
                            'message': 'The SPARCd installation doesn\'t need repair'})

    # Make repairs
    if not S3Connection.repair_sparcd(s3_info, DEFAULT_SETTINGS_PATH):
        return jsonify({'success': False, 'message': 'Unable to repair this SPARCd instance'})

    return jsonify({'success': True})

@app.route('/setUploadComplete', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def set_upload_complete():
    """ Marks an incomplete upload as completed
    Arguments: (POST)
        t - the session token
    Return:
        Returns True success if the upload could be marked as completed and False otherwise
    Notes:
         If the token is invalid, or a problem occurs, a 404 error is returned
   """
    db = SPARCdDatabase(DEFAULT_DB_PATH)
    token = request.args.get('t')
    print('SET UPLOAD COMPLETE', flush=True)

    # Check the credentials
    token_valid, user_info = sdu.token_user_valid(db, request, token, SESSION_EXPIRE_SECONDS)
    if token_valid is None or user_info is None:
        return "Not Found", 404
    if not token_valid or not user_info:
        return "Unauthorized", 401

    # Get the rest of the request parameters
    col_id = request.form.get('collectionId', None)
    up_key = request.form.get('uploadKey', None)

    # Check what we have from the requestor
    if not all(item for item in [col_id, up_key]):
        return "Not Found", 406

    # Mark the setup as complete
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    # Get the collection we need
    all_colls = sdc.load_collections(db, bool(user_info.admin), s3_info)
    if not all_colls:
        return jsonify({'success': False,
                            'message': "Unable to load collections for marking upload complete"})

    coll = [one_coll for one_coll in all_colls if one_coll["id"] == col_id]
    if not coll:
        return jsonify({'success': False,
                            'message': 'Unable to find the collection needed to mark upload as ' \
                                        'completed'})
    coll = coll[0]

    # Find the upload in the collection
    upload = [one_up for one_up in coll['uploads'] if one_up["key"] == up_key]
    if not upload:
        return jsonify({'success': False,
                            'message': 'Unable to find the incomplete upload in the collections'})
    upload = upload[0]

    # Make sure this user has permissions to do this
    if not bool(user_info.admin) and user_info.name == upload['uploadUser']:
        return "Not Found", 404

    # Update the counts of the uploaded images to reflect what's on the server
    S3Connection.upload_recalculate_image_count(s3_info, coll['bucket'], upload['key'])

    # Remove the upload from the database
    db.sandbox_upload_complete_by_info(s3_info.id, user_info.name, coll['bucket'],
                                                                                    upload['key'])

    return jsonify({'success': True, 'message': 'Successfully marked upload as completed'})


@app.route('/messageAdd', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def message_add():
    """ Adds a message to the database
    Arguments: (POST)
        t - the session token
    Return:
        Returns True success if the message could be added and False otherwise
    Notes:
         If the token is invalid, or a problem occurs, a 404 error is returned
   """
    db = SPARCdDatabase(DEFAULT_DB_PATH)
    token = request.args.get('t')
    print('ADD MESSAGE', flush=True)

    # Check the credentials
    token_valid, user_info = sdu.token_user_valid(db, request, token, SESSION_EXPIRE_SECONDS)
    if token_valid is None or user_info is None:
        return "Not Found", 404
    if not token_valid or not user_info:
        return "Unauthorized", 401

    # Get the rest of the request parameters
    receiver = request.form.get('receiver', None)
    subject = request.form.get('subject', None)
    message = request.form.get('message', None)
    priority = request.form.get('priority', None)

    # Check what we have from the requestor
    if not all(item for item in [receiver, subject]):
        return "Not Found", 406

    # Check the parameters
    if not message:
        message = ""
    if priority is None:
        priority = "normal"

    # Add the message
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    all_receivers = [one_rec.strip() for one_rec in receiver.split(',')]

    # Add the messages
    for one_rec in all_receivers:
        db.message_add(s3_info.id, user_info.name, one_rec, subject, message, priority)

    return jsonify({'success': True, 'message': 'All messages stored'})


@app.route('/userNames', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def user_names():
    """ Returns the list of known users
    Arguments: (GET)
        t - the session token
    Return:
        Returns True success if the messages count be marked as read and False otherwise
    Notes:
         If the token is invalid, or a problem occurs, a 404 error is returned
   """
    db = SPARCdDatabase(DEFAULT_DB_PATH)
    token = request.args.get('t')
    print('USER NAMES', flush=True)

    # Check the credentials
    token_valid, user_info = sdu.token_user_valid(db, request, token, SESSION_EXPIRE_SECONDS)
    if token_valid is None or user_info is None:
        return "Not Found", 404
    if not token_valid or not user_info:
        return "Unauthorized", 401

    # Get the messages
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    users = db.user_names(s3_info.id)

    return jsonify({'success': True, 'users': users, 'message': 'All user names returned'})


@app.route('/messageGet', methods = ['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def message_get():
    """ Gets messages for the user
    Arguments: (GET)
        t - the session token
    Return:
        Returns True success and the messages if they could be retrieved and False otherwise
    Notes:
         If the token is invalid, or a problem occurs, a 404 error is returned
   """
    db = SPARCdDatabase(DEFAULT_DB_PATH)
    token = request.args.get('t')
    print('GET MESSAGE', flush=True)

    # Check the credentials
    token_valid, user_info = sdu.token_user_valid(db, request, token, SESSION_EXPIRE_SECONDS)
    if token_valid is None or user_info is None:
        return "Not Found", 404
    if not token_valid or not user_info:
        return "Unauthorized", 401

    # Get the messages
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    messages = db.messages_get(s3_info.id, user_info.name, bool(user_info.admin))

    return jsonify({'success': True, 'messages': messages, 'message': 'All messages received'})


@app.route('/messageRead', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def message_read():
    """ Marks messages are read
    Arguments: (POST)
        t - the session token
    Return:
        Returns True success if the messages count be marked as read and False otherwise
    Notes:
         If the token is invalid, or a problem occurs, a 404 error is returned
   """
    db = SPARCdDatabase(DEFAULT_DB_PATH)
    token = request.args.get('t')
    print('READ MESSAGE', flush=True)

    # Check the credentials
    token_valid, user_info = sdu.token_user_valid(db, request, token, SESSION_EXPIRE_SECONDS)
    if token_valid is None or user_info is None:
        return "Not Found", 404
    if not token_valid or not user_info:
        return "Unauthorized", 401

    # Get the rest of the request parameters
    ids = request.form.get('ids', None)
    if ids is None:
        return "Not Found", 406
    ids = json.loads(ids)

    # Get the messages
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    all_ids = [int(one_id) for one_id in ids]
    db.messages_are_read(s3_info.id, user_info.name, all_ids)
    if bool(user_info.admin):
        db.messages_are_read(s3_info.id, 'admin', all_ids)

    return jsonify({'success': True, 'message': 'Messages were marked as read'})


@app.route('/messageDelete', methods = ['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def message_delete():
    """ Gets messages for the user
    Arguments: (POST)
        t - the session token
    Return:
        Returns True success if the messages could me marked as deleted and False otherwise
    Notes:
         If the token is invalid, or a problem occurs, a 404 error is returned
   """
    db = SPARCdDatabase(DEFAULT_DB_PATH)
    token = request.args.get('t')
    print('DELETE MESSAGE', flush=True)

    # Check the credentials
    token_valid, user_info = sdu.token_user_valid(db, request, token, SESSION_EXPIRE_SECONDS)
    if token_valid is None or user_info is None:
        return "Not Found", 404
    if not token_valid or not user_info:
        return "Unauthorized", 401

    # Get the rest of the request parameters
    ids = request.form.get('ids', None)
    if ids is None:
        return "Not Found", 406
    ids = json.loads(ids)

    # Get the messages
    s3_info = s3u.get_s3_info(user_info.url,
                              user_info.name,
                              lambda: get_password(token, db),
                              lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    all_ids = [int(one_id) for one_id in ids]
    db.messages_are_deleted(s3_info.id, user_info.name, all_ids)
    if bool(user_info.admin):
        db.messages_are_deleted(s3_info.id, 'admin', all_ids)

    return jsonify({'success': True, 'message': 'Messages were marked as deleted'})
