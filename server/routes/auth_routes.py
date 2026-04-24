""" Authentication and session routes for SPARCd server """

import hashlib

from flask import Blueprint, jsonify, make_response, request
from flask_cors import cross_origin

import handlers.base as hbase
from sparcd_db import SPARCdDatabase
from sparcd_config import ALLOWED_ORIGINS, WORKING_PASSCODE, DEFAULT_DB_PATH, \
                          SESSION_EXPIRE_SECONDS, TEMP_SPECIES_FILE_NAME, \
                          IMAGE_BROWSER_CACHE_TIMEOUT_SEC, DEFAULT_IMAGE_FETCH_TIMEOUT_SEC, \
                          authenticated_route, get_s3_info, make_handler_response
import sparcd_utils as sdu
import s3_utils as s3u
import spd_crypt as crypt

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def login_token():
    """ Returns a token representing the login
    Arguments: (POST)
        url - the S3 database URL
        user - the user name
        password - the user credentials
        token - the token to check for validity
    Returns:
        200: JSON object containing the session token and user information
        404: if the login credentials are invalid or the user cannot be found
    Notes:
        If a token is provided it is checked for expiration first. If the token
        is invalid, missing, or expired and valid credentials are provided, a new
        token is issued. The S3 ID is not yet known at login time so only the
        species file name without ID prefix is passed to the handler.
    """
    db = SPARCdDatabase(DEFAULT_DB_PATH)
    print('LOGIN', flush=True)

    result = hbase.handle_login(db,
                                WORKING_PASSCODE,
                                SESSION_EXPIRE_SECONDS,
                                TEMP_SPECIES_FILE_NAME,
                                crypt.hash2str)
    if not result:
        return 'Not Found', 404

    return jsonify(result)


@auth_bp.route('/image', methods=['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def image():
    """ Returns an image from S3 storage
    Arguments: (GET)
        t - the session token
        i - the encrypted key identifying the image
    Returns:
        200: the image content with browser cache headers set
        401: if the session token is invalid or expired
        404: if the user agent header is missing or the image cannot be found
    Notes:
        This route does not use authenticated_route because image requests may
        originate from any IP address (e.g. via browser image tags), so origin
        IP checking is deliberately skipped. The user agent is still validated
        as a basic sanity check on the request.
    """
    db = SPARCdDatabase(DEFAULT_DB_PATH)
    token = request.args.get('t')
    print('IMAGE', request, flush=True)

    client_user_agent = request.environ.get('HTTP_USER_AGENT', None)
    if not client_user_agent:
        return 'Not Found', 404

    user_agent_hash = hashlib.sha256(client_user_agent.encode('utf-8')).hexdigest()

    # Wildcard IP allows requests from any origin since images are loaded via browser tags
    token_valid, user_info = sdu.token_is_valid(token, '*', user_agent_hash, db,
                                                SESSION_EXPIRE_SECONDS)
    if not token_valid or not user_info:
        return 'Unauthorized', 401

    s3_info = get_s3_info(token, db, user_info)
    res = hbase.handle_image(db,
                             s3_info,
                             request.args.get('i'),
                             DEFAULT_IMAGE_FETCH_TIMEOUT_SEC,
                             WORKING_PASSCODE)

    response = make_response(res.content)
    response.headers.set('Cache-Control',
                         f'public, max-age={IMAGE_BROWSER_CACHE_TIMEOUT_SEC}')
    return response


@auth_bp.route('/settings', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def set_settings(*, db, _token, user_info, s3_info):
    """ Updates the authenticated user's application settings
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Form parameters:
        autonext - whether to automatically advance to the next image
        dateFormat - the preferred date display format
        measurementFormat - the preferred measurement unit format
        sandersonDirectory - the Sanderson output directory
        sandersonOutput - the Sanderson output format
        timeFormat - the preferred time display format
        coordinatesDisplay - the preferred coordinate display format
        email - the user's email address
    Returns:
        200: JSON object containing the updated user settings
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
    """
    print(f'SET SETTINGS user={user_info.name}', flush=True)

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

    user_info = hbase.handle_settings(db, user_info, s3_info, new_settings, new_email)
    return jsonify(user_info.settings)


@auth_bp.route('/adminCheck', methods=['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def admin_check(*, _db, _token, user_info, _s3_info):
    """ Returns whether the authenticated user has administrator privileges
    Arguments:
        _db: the database instance (injected by authenticated_route, unused)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        _s3_info: the S3 endpoint information (injected by authenticated_route, unused)
    Returns:
        200: JSON object with 'value' set to True if admin, False otherwise
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
    """
    print('ADMIN CHECK', flush=True)
    return {'value': bool(user_info.admin)}


@auth_bp.route('/settingsAdmin', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def settings_admin(*, _db, _token, user_info, _s3_info):
    """ Verifies an administrator's S3 password before allowing admin-level edits
    Arguments:
        _db: the database instance (injected by authenticated_route, unused)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        _s3_info: the S3 endpoint information (injected by authenticated_route, unused)
    Form parameters:
        value - the S3 password to verify
    Returns:
        200: JSON object with 'success' True if the password is correct
        401: if the session token is invalid, expired, or password verification fails
        404: if the request is malformed or the user cannot be found
        406: if the password parameter is missing
    Notes:
        Constructs a fresh S3 connection using the submitted password rather than
        the session-derived credentials in order to verify the password is correct
    """
    print(f'ADMIN SETTINGS user={user_info.name}', flush=True)

    pw = request.form.get('value')
    if not pw:
        return 'Not Found', 406

    pw_s3_info = s3u.get_s3_info(user_info.url,
                                  user_info.name,
                                  pw,
                                  lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    pw_ok = hbase.handle_settings_admin(user_info, pw_s3_info)
    if pw_ok is False:
        return 'Not Found', 406
    if pw_ok is None:
        return 'Not Found', 401

    return jsonify({'success': pw_ok})


@auth_bp.route('/settingsOwner', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(non_admin_only=True)
def settings_owner(*, _db, _token, user_info, _s3_info):
    """ Verifies a collection owner's S3 password before allowing owner-level edits
    Arguments:
        _db: the database instance (injected by authenticated_route, unused)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        _s3_info: the S3 endpoint information (injected by authenticated_route, unused)
    Form parameters:
        value - the S3 password to verify
    Returns:
        200: JSON object with 'success' True if the password is correct
        401: if the session token is invalid, expired, or password verification fails
        404: if the request is malformed or the user cannot be found
        406: if the password parameter is missing
    Notes:
        Constructs a fresh S3 connection using the submitted password rather than
        the session-derived credentials in order to verify the password is correct.
        This route is restricted to non-admin users only.
    """
    print(f'OWNER CHECK user={user_info.name}', flush=True)

    pw = request.form.get('value')
    if not pw:
        return 'Not Found', 406

    pw_s3_info = s3u.get_s3_info(user_info.url,
                                  user_info.name,
                                  pw,
                                  lambda x: crypt.do_decrypt(WORKING_PASSCODE, x))

    pw_ok = hbase.handle_settings_owner(user_info, pw_s3_info)
    if pw_ok is False:
        return 'Not Found', 404
    if pw_ok is None:
        return 'Not Found', 401

    return jsonify({'success': pw_ok})


@auth_bp.route('/locationInfo', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def location_info(*, _db, _token, _user_info, s3_info):
    """ Returns details on a location from the S3 endpoint
    Arguments:
        _db: the database instance (injected by authenticated_route, unused)
        _token: the session token (injected by authenticated_route, unused)
        _user_info: the authenticated user's information (injected by authenticated_route, unused)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing location details
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
        406: if the location information cannot be retrieved
    """
    print('LOCATION INFO', flush=True)

    loc_info = hbase.handle_location_info(s3_info)
    if not loc_info:
        return 'Not Found', 406

    return jsonify(loc_info)


@auth_bp.route('/setUploadComplete', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def set_upload_complete(*, db, _token, user_info, s3_info):
    """ Marks an incomplete upload as completed
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object indicating success
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
        406: if the upload cannot be marked complete
    """
    print(f'SET UPLOAD COMPLETE user={user_info.name}', flush=True)
    return make_handler_response(hbase.handle_upload_complete(db, user_info, s3_info))
