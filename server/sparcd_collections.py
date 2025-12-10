""" Collection functions for SPARCd server """

import time
from typing import Callable, Optional

from s3_access import S3Connection
from sparcd_db import SPARCdDatabase
import sparcd_utils as sdu

# Collections information timeout length
TIMEOUT_COLLECTIONS_SEC = 12 * 60 * 60
# Maximum tries to get a lock for loading collections
MAX_COLL_FETCH_TRIES = 10
# Maximium number of seconds to wait for collections to get loaded before giving up
MAX_COLL_FETCH_WAIT_SEC = 5 * 60
# Sleep interval value while waiting for collections to load
COLL_FETCH_WAIT_INTERVAL_SEC = (MAX_COLL_FETCH_WAIT_SEC) / \
                                                ((MAX_COLL_FETCH_TRIES+1)*MAX_COLL_FETCH_TRIES/2)


def __get_loaded_collections(db: SPARCdDatabase, s3_id: str, s3_url: str, user_name: str, \
                                                    fetch_password: Callable) -> Optional[tuple]:
    """ Loads the collections from S3 and saves them in the database
    Arguments:
        db: the database to access
        s3_id: the unique ID of the S3 instance
        s3_url: the URL to the S3 instance
        user_name: the S3 user name
        fetch_password: callable that returns the S3 password
    Return:
        Returns the collection information associated with the S3 ID
    """
    loaded_colls = None

    # Get the collection information from the server
    # If we can get the lock we load the collections, otherwise wait for the collections to load
    have_lock = False
    lock_id = None
    try:
        lock_id = db.get_lock('fetch_collection')
        if lock_id is not None:
            have_lock = True

            all_collections = S3Connection.get_collections(s3_url, user_name, fetch_password())

            loaded_colls = []
            for one_coll in all_collections:
                loaded_colls.append(sdu.normalize_collection(one_coll))

            db.save_all_collections(s3_id, loaded_colls)

            db.release_lock('fetch_collection', lock_id)
            have_lock = False
            lock_id = None
        else:
            # We wait for the collections to get loaded
            # This uses a linear wait/sleep but that can be changed
            tries = 0
            while tries < MAX_COLL_FETCH_TRIES:
                tries += 1
                time.sleep(tries * COLL_FETCH_WAIT_INTERVAL_SEC)

                loaded_colls = db.get_all_collections(s3_id, TIMEOUT_COLLECTIONS_SEC)
                if loaded_colls:
                    tries += MAX_COLL_FETCH_TRIES
    finally:
        # If we have the lock, something must have happened so we release the lock
        if have_lock is True and lock_id is not None:
            db.release_lock('fetch_collection', lock_id)

    return loaded_colls


# pylint: disable=too-many-positional-arguments,too-many-arguments
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
        loaded_colls = __get_loaded_collections(db, s3_id, s3_url, user_name, fetch_password)

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
