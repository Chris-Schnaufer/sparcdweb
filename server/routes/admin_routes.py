""" Admin and collection owner routes for SPARCd server """

from flask import Blueprint, jsonify
from flask_cors import cross_origin

import handlers.admin as hadmin
from sparcd_config import ALLOWED_ORIGINS, authenticated_route, make_handler_response, \
                          temp_species_filename

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/adminCheckChanges', methods=['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def admin_check_changes(*, db, _token, user_info, s3_info):
    """ Checks if there are pending admin changes to locations or species
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object indicating whether location or species changes are pending
        401: if the session token is invalid or expired
        404: if the request is malformed or the user cannot be found
    """
    print(f'ADMIN CHECK CHANGES user={user_info.name}', flush=True)

    changed = db.have_admin_changes(s3_info.id, user_info.name)
    return jsonify({'success': True,
                    'locationsChanged': changed['locationsCount'] > 0,
                    'speciesChanged': changed['speciesCount'] > 0})


@admin_bp.route('/adminCollectionDetails', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def admin_collection_details(*, db, _token, user_info, s3_info):
    """ Returns detailed collection information for admin editing
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing detailed collection information
        401: if the session token is invalid or expired
        404: if the collection cannot be found or the request is malformed
    """
    print(f'ADMIN COLLECTION DETAILS user={user_info.name}', flush=True)

    # Collection can be None so we handle that differently than most of the code
    collection = hadmin.handle_admin_collection_details(db, user_info, s3_info)
    if collection is False:
        return 'Not Found', 404

    return jsonify(collection)


@admin_bp.route('/ownerCollectionDetails', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(non_admin_only=True)
def owner_collection_details(*, db, _token, user_info, s3_info):
    """ Returns detailed collection information for collection owner editing
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing detailed collection information
        401: if the session token is invalid or expired
        404: if the collection cannot be found or the request is malformed
    Notes:
        Performs additional permission checks since must_be_admin is False.
        Unlike the admin version, None is not returned on permission failure.
    """
    print(f'OWNER COLLECTION DETAILS user={user_info.name}', flush=True)

    # Collection can be None so we handle that differently than most of the code
    collection = hadmin.handle_admin_collection_details(db, user_info, s3_info, False)
    if collection is False:
        return 'Not Found', 404

    return jsonify(collection)


@admin_bp.route('/adminLocationDetails', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def admin_location_details(*, _db, _token, user_info, s3_info):
    """ Returns detailed location information for admin editing
    Arguments:
        _db: the database instance (injected by authenticated_route, unused)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing detailed location information
        401: if the session token is invalid or expired
        404: if the location cannot be found
        406: if the request is malformed
    """
    print(f'ADMIN LOCATION DETAILS user={user_info.name}', flush=True)

    location = hadmin.handle_admin_location_details(user_info, s3_info)

    return make_handler_response(location)


@admin_bp.route('/adminUsers', methods=['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def admin_users(*, db, _token, user_info, s3_info):
    """ Returns user information for admin editing
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing user information
        401: if the session token is invalid or expired
        404: if the users cannot be found or the request is malformed
    """
    print(f'ADMIN USERS user={user_info.name}', flush=True)

    users = hadmin.handle_admin_users(db, user_info, s3_info)
    if users is False or users is None:
        return 'Not Found', 404

    return jsonify(users)


@admin_bp.route('/adminSpecies', methods=['GET'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def admin_species(*, _db, _token, user_info, s3_info):
    """ Returns the official species list for admin editing
    Arguments:
        _db: the database instance (injected by authenticated_route, unused)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing the official species list
        401: if the session token is invalid or expired
        404: if the species list cannot be found
        406: if the request is malformed
    Notes:
        Returns the official species list, not user-specific species
    """
    print(f'ADMIN SPECIES user={user_info.name}', flush=True)

    cur_species = hadmin.handle_admin_species(user_info, s3_info,
                                              temp_species_filename(s3_info.id))

    return make_handler_response(cur_species)


@admin_bp.route('/adminUserUpdate', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def admin_user_update(*, db, _token, user_info, s3_info):
    """ Updates a user with the specified information
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing the updated user information
        401: if the session token is invalid or expired
        404: if the user cannot be found
        406: if the request is malformed or the update parameters are invalid
    """
    print(f'ADMIN USER UPDATE user={user_info.name}', flush=True)

    return make_handler_response(hadmin.handle_user_update(db, user_info, s3_info))


@admin_bp.route('/adminSpeciesUpdate', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def admin_species_update(*, db, _token, user_info, s3_info):
    """ Adds or updates a species entry in the official species list
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing the updated species information
        401: if the session token is invalid or expired
        404: if the species cannot be found
        406: if the request is malformed or the update parameters are invalid
    """
    print(f'ADMIN SPECIES UPDATE user={user_info.name}', flush=True)

    return make_handler_response(hadmin.handle_species_update(db, user_info, s3_info,
                                                              temp_species_filename(s3_info.id)))


@admin_bp.route('/adminLocationUpdate', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def admin_location_update(*, db, _token, user_info, s3_info):
    """ Adds or updates location information
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing the updated location information
        401: if the session token is invalid or expired
        404: if the location cannot be found
        406: if the request is malformed or the update parameters are invalid
    """
    print(f'ADMIN LOCATION UPDATE user={user_info.name}', flush=True)

    return make_handler_response(hadmin.handle_location_update(db, user_info, s3_info))


@admin_bp.route('/adminCollectionUpdate', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def admin_collection_update(*, db, _token, user_info, s3_info):
    """ Updates collection information
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing the updated collection information
        401: if the session token is invalid or expired
        404: if the collection cannot be found
        406: if the request is malformed or the update parameters are invalid
    """
    print(f'ADMIN COLLECTION UPDATE user={user_info.name}', flush=True)

    return make_handler_response(hadmin.handle_collection_update(db, user_info, s3_info))


@admin_bp.route('/adminCollectionAdd', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def admin_collection_add(*, db, _token, user_info, s3_info):
    """ Adds a new collection
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing the new collection information
        401: if the session token is invalid or expired
        404: if the collection cannot be created
        406: if the request is malformed or the collection parameters are invalid
    """
    print(f'ADMIN COLLECTION ADD user={user_info.name}', flush=True)

    return make_handler_response(hadmin.handle_collection_add(db, user_info, s3_info))


@admin_bp.route('/ownerCollectionUpdate', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(non_admin_only=True)
def owner_collection_update(*, db, _token, user_info, s3_info):
    """ Adds or updates collection information for a collection owner
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing the updated collection information
        401: if the session token is invalid or expired
        404: if the collection cannot be found
        406: if the request is malformed or the update parameters are invalid
    Notes:
        Restricted to non-admin users only. Performs additional ownership
        permission checks inside the handler.
    """
    print(f'OWNER COLLECTION UPDATE user={user_info.name}', flush=True)

    return make_handler_response(hadmin.handle_collection_update(db, user_info, s3_info,
                                                                 must_be_admin=False))


@admin_bp.route('/adminCheckIncomplete', methods=['POST'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def admin_check_incomplete(*, db, _token, user_info, s3_info):
    """ Looks for incomplete uploads in collections
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object containing incomplete upload information
        401: if the session token is invalid or expired
        404: if the incomplete upload information cannot be found
        406: if the request is malformed
    """
    print(f'ADMIN CHECK INCOMPLETE UPLOADS user={user_info.name}', flush=True)

    return make_handler_response(hadmin.handle_check_incomplete(db, user_info, s3_info))


@admin_bp.route('/adminCompleteChanges', methods=['PUT'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def admin_complete_changes(*, db, _token, user_info, s3_info):
    """ Applies all pending location and species changes to the S3 data
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object indicating success
        401: if the session token is invalid or expired
        404: if the changes cannot be found
        406: if the request is malformed or the changes cannot be applied
    """
    print(f'ADMIN COMPLETE THE CHANGES user={user_info.name}', flush=True)

    return make_handler_response(hadmin.handle_complete_changes(db, user_info, s3_info,
                                                                temp_species_filename(s3_info.id)))


@admin_bp.route('/adminAbandonChanges', methods=['PUT'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
@authenticated_route(admin_only=True)
def admin_abandon_changes(*, db, _token, user_info, s3_info):
    """ Discards all pending location and species changes
    Arguments:
        db: the database instance (injected by authenticated_route)
        _token: the session token (injected by authenticated_route, unused)
        user_info: the authenticated user's information (injected by authenticated_route)
        s3_info: the S3 endpoint information (injected by authenticated_route)
    Returns:
        200: JSON object indicating success
        401: if the session token is invalid or expired
        404: if the changes cannot be found
        406: if the request is malformed
    """
    print(f'ADMIN ABANDON THE CHANGES user={user_info.name}', flush=True)

    return make_handler_response(hadmin.handle_abandon_changes(db, user_info, s3_info))
