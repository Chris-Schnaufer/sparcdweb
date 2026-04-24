""" Upload routes for SPARCd server """

from flask import Blueprint, jsonify, request
from flask_cors import cross_origin

import handlers.upload as hupload
from sparcd_config import ALLOWED_ORIGINS, WORKING_PASSCODE, TEMP_SPECIES_FILE_NAME, \
                          authenticated_route, temp_species_filename

upload_bp = Blueprint('upload', __name__)


@upload_bp.route('/uploadImages', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def upload_images(*, db, _token, user_info, s3_info):
    """ Returns the list of images from a collection's upload
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON list of images for the specified upload
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
        406: if the collection ID or upload ID parameters are missing, or no images are found
    """
    print(f'UPLOAD IMAGES user={user_info.name}', flush=True)

    params = hupload.UploadImagesParams(passcode=WORKING_PASSCODE,
                                        temp_species_filename=temp_species_filename(s3_info.id))
    all_images = hupload.handle_upload_images(db, user_info, s3_info, params)

    if not all_images:
        return 'Not Found', 406

    return jsonify(all_images)


@upload_bp.route('/uploadLocation', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def image_location(*, db, _token, user_info, s3_info):
    """ Handles updating the location information for images in an upload
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Form parameters:
        timestamp - the timestamp of the location change
        collection - the collection ID
        upload - the upload ID
        locId - the new location ID
        locName - the new location name
        locElevation - the new location elevation
        locLat - the new location latitude
        locLon - the new location longitude
    Returns:
        200: JSON object indicating success
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
        406: if any required parameters are missing or the update fails
    """
    print(f'UPLOAD LOCATION user={user_info.name}', flush=True)

    if not hupload.handle_upload_location(db, user_info, s3_info,
                                          temp_species_filename(s3_info.id)):
        return 'Not Found', 406

    return jsonify({'success': True})
