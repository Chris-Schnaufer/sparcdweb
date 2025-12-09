""" Collection functions for SPARCd server """

from typing import Callable, Optional

from s3_access import S3Connection
from sparcd_db import SPARCdDatabase
import sparcd_utils as sdu

# Collections information timeout length
TIMEOUT_COLLECTIONS_SEC = 12 * 60 * 60

def load_collections(db: SPARCdDatabase, s3_id: str, admin: bool, s3_url: str=None, \
                    user_name: str=None, fetch_password: Callable=None) -> Optional[tuple]:
    """ Loads collections from the database or S3 endpoint
    Arguments:
        db: the database to access
        s3_id: the unique ID of the S3 instance
        admin: boolean value indicating admin privileges when set to True
        s3_url: the URL to the S3 instance
        user_name: the S3 user name
        fetch_password: callable that returns the S3 password
    Return:
        Returns the collection information associated with the S3 ID
    Notes:
        If the desired information is not in the database, the collection information is fetched
        from the S3 endpoint and then stored in the database.
        If one of s3_url, user_name, or fetch_password is None then S3 will not be queried for
        collections
    """
    loaded_colls = db.get_all_collections(s3_id, TIMEOUT_COLLECTIONS_SEC)

    if not loaded_colls and all(item for item in [s3_url, user_name, fetch_password]):
        # TODO: USE IPC TO CHECK IF NEED TO LOAD COLLECTIONS FROM S3
        # Get the collection information from the server
        all_collections = S3Connection.get_collections(s3_url, user_name, fetch_password())

        loaded_colls = []
        for one_coll in all_collections:
            loaded_colls.append(sdu.normalize_collection(one_coll))

        db.save_all_collections(s3_id, loaded_colls)

    # Make sure we have something
    if not loaded_colls:
        return None

    # Make sure we have a boolean value for admin and not Truthiness
    if not admin in [True, False]:
        admin = False

    # Get this user's permissions
    user_coll = []
    for one_coll in loaded_colls:
        user_has_permissions = False
        new_coll = one_coll
        new_coll['permissions'] = None
        if 'allPermissions' in one_coll and one_coll['allPermissions']:
            try:
                for one_perm in one_coll['allPermissions']:
                    if one_perm and 'usernameProperty' in one_perm and \
                                one_perm['usernameProperty'] == user_name:
                        new_coll['permissions'] = one_perm
                        user_has_permissions = True
                        break
            finally:
                pass

        # Only return collections that the user has permissions to
        if admin is True or user_has_permissions is True:
            user_coll.append(new_coll)

    # Return the collections
    return user_coll


def collection_update(db: SPARCdDatabase, s3_id: str, collection: dict) -> None:
    """ Updates the collection in the database if the collection data hasn't expired
    Arguments:
        db: the database to access
        s3_id: the unique ID of the S3 instance
        collection: collection information including the collection name and other values
    Note:
        If the data in the database is determined to be too old, the database is not updated
    """
    db.collection_update(s3_id, collection, TIMEOUT_COLLECTIONS_SEC)
