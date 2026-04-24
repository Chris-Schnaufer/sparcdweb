""" Message and user routes for SPARCd server """

from flask import Blueprint, jsonify
from flask_cors import cross_origin

import handlers.message as hmessage
from sparcd_config import ALLOWED_ORIGINS, authenticated_route, make_handler_response

message_bp = Blueprint('message', __name__)


@message_bp.route('/messageAdd', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def message_add(*, db, _token, user_info, s3_info):
    """ Adds a message to the database
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object indicating success
        401: if the session token is invalid or expired
        404: if the message cannot be added
        406: if the request is malformed or the message parameters are invalid
    """
    print(f'ADD MESSAGE user={user_info.name}', flush=True)

    return make_handler_response(hmessage.handle_message_add(db, user_info, s3_info))


@message_bp.route('/userNames', methods=['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def user_names(*, db, _token, _user_info, s3_info):
    """ Returns the list of known users for message addressing
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        _user_info: the authenticated user's information (injected by authenticated_route, unused)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing the list of user names
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
    """
    print('USER NAMES', flush=True)

    return jsonify({'success': True,
                    'users': db.user_names(s3_info.id),
                    'message': 'All user names returned'})


@message_bp.route('/messageGet', methods=['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def message_get(*, db, _token, user_info, s3_info):
    """ Returns all messages for the authenticated user
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing the list of messages
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
    """
    print(f'GET MESSAGE user={user_info.name}', flush=True)

    return jsonify({'success': True,
                    'messages': db.messages_get(s3_info.id, user_info.name,
                                                bool(user_info.admin)),
                    'message': 'All messages received'})


@message_bp.route('/messageRead', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def message_read(*, db, _token, user_info, s3_info):
    """ Marks messages as read
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object indicating success
        401: if the session token is invalid or expired
        404: if the messages cannot be found
        406: if the request is malformed or the message parameters are invalid
    """
    print(f'READ MESSAGE user={user_info.name}', flush=True)

    return make_handler_response(hmessage.handle_message_read(db, user_info, s3_info))


@message_bp.route('/messageDelete', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route()
def message_delete(*, db, _token, user_info, s3_info):
    """ Handles deleting messages
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object indicating success
        401: if the session token is invalid or expired
        404: if the messages cannot be found
        406: if the request is malformed or the message parameters are invalid
    """
    print(f'DELETE MESSAGE user={user_info.name}', flush=True)

    return make_handler_response(hmessage.handle_message_delete(db, user_info, s3_info))
