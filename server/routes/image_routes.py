""" Image editing and species routes for SPARCd server """

from flask import Blueprint, jsonify
from flask_cors import cross_origin

import handlers.image as himage
from sparcd_config import ALLOWED_ORIGINS, WORKING_PASSCODE, authenticated_route, \
                          make_handler_response, temp_species_filename

image_bp = Blueprint('image', __name__)


@image_bp.route('/imageSpecies', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def image_species(*, db, user_info, s3_info, **_):
    """ Handles updating the species and counts for an image
    Arguments:
        db: the database instance (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object indicating success
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
        406: if the species update parameters are invalid
    """
    print(f'IMAGE SPECIES user={user_info.name}', flush=True)

    resp = himage.handle_image_species(db, user_info, s3_info, WORKING_PASSCODE)

    return make_handler_response({'success': True} if resp else resp)


@image_bp.route('/imageEditComplete', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def image_edit_complete(*, db, user_info, s3_info, **_):
    """ Handles updating one image with the changes made
    Arguments:
        db: the database instance (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing the edit result
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
        406: if the edit parameters are invalid or the edit cannot be completed
    """
    print(f'IMAGE EDIT COMPLETE user={user_info.name}', flush=True)

    resp = himage.handle_image_edit_complete(db,
                                             user_info,
                                             s3_info,
                                             WORKING_PASSCODE,
                                             temp_species_filename(s3_info.id))
    if not resp:
        return 'Not Found', 406

    return resp


@image_bp.route('/imagesAllEdited', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def images_all_edited(*, db, user_info, s3_info, **_):
    """ Handles completing changes after all images in an upload have been edited
    Arguments:
        db: the database instance (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object indicating whether the upload metadata and image URLs were updated
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
        406: if the edit completion parameters are invalid or the operation cannot be completed
    """
    print(f'IMAGES ALL FINISHED user={user_info.name}', flush=True)

    updated, kept_urls = himage.handle_images_all_edited(db, user_info, s3_info)

    if updated is None or kept_urls is None:
        return 'Not Found', 406

    return jsonify({'success': True,
                    'message': 'The images have been successfully updated',
                    'updatedUpload': bool(updated),
                    'imagesReloaded': not kept_urls})


@image_bp.route('/speciesKeybind', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def species_keybind(*, db, user_info, s3_info, **_):
    """ Handles adding or changing a species keybind for an image
    Arguments:
        db: the database instance (injected by authenticated_route)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object indicating success
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
        406: if the keybind parameters are invalid or the update cannot be completed
    """
    print(f'SPECIES KEYBIND user={user_info.name}', flush=True)

    if not himage.handle_species_keybind(db, user_info, s3_info,
                                         temp_species_filename(s3_info.id)):
        return 'Not Found', 406

    return jsonify({'success': True})


@image_bp.route('/imageTimestamp', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def image_timestamps(*, s3_info, **_):
    """ Fetches the first timestamp found in the list of uploaded files
    Arguments:
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing success status and the timestamp in ISO format if found
        401: if the session token is invalid or expired
        404: if the request is malformed or no timestamp can be found
        406: if the timestamp parameters are invalid
    """
    print('IMAGE TIMESTAMP', flush=True)

    file_ts = himage.handle_image_timestamp(s3_info, WORKING_PASSCODE)

    return make_handler_response(
        {'success': True, 'timestamp': file_ts.isoformat()}
            if file_ts
                else file_ts
    )


@image_bp.route('/adjustTimestamps', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def adjust_timestamps(*, s3_info, **_):
    """ Adjusts the timestamps for image files in an upload
    Arguments:
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object indicating success or failure with a message
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
        406: if the timestamp adjustment parameters are invalid
    """
    print('ADJUST TIMESTAMPS', flush=True)

    res = himage.handle_adjust_timestamp(s3_info)
    if res is False:
        return 'Not Found', 406
    if res is None:
        return jsonify({'success': False,
                        'message': 'Unable to get media information from server'})

    return jsonify({'success': True})
