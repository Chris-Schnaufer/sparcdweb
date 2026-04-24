""" Functions to handle requests starting with /install for SPARCd server """

from sparcd_db import SPARCdDatabase
from spd_types.userinfo import UserInfo
from spd_types.s3info import S3Info
from s3_access import S3Connection


def handle_new_install_check(db:SPARCdDatabase, user_info: UserInfo, s3_info: S3Info) -> dict:
    """ Implementation of checking if the login is a new install
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
    Return:
        Returns a new instance check dict
      """
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
        return return_data

    if has_everything:
        # The endpoint has everything needed (what are they up to?)
        return_data['success'] = True
        return_data['admin'] = False
        return_data['message'] = 'The endpoint already is configured for SPARCd'
        return return_data

    # Check if they can make a new install
    can_create, test_bucket = S3Connection.check_new_install_possible(s3_info)
    if not can_create:
        return_data['failedPerms'] = True
        return_data['message'] = 'Unable to install SPARCd at the S3 endpoint. Please ' \
                                        'contact your S3 administrator about permissions'
        return return_data

    # Check that there aren't any administrators for this endpoint in the database
    # If it's a new install, there shouldn't be an admin in the database (the endpoint is
    # unknown so no one should be an admin)
    if not bool(user_info.admin):
        if db.have_any_known_admin(s3_info.id):
            return_data['admin'] = False        # always false or we wouldn't be here
            return_data['message'] = 'You are not authorized to make a new installation or ' \
                                            'repair an existing one. Please contact your ' \
                                            'administrator'
            return return_data

    # TODO: When have messages to users and the test bucket isn't removed, inform the admin(s)
    if test_bucket is not None:
        print(f'WARNING: unable to delete testing bucket {test_bucket}', flush=True)

    return_data['success'] = True
    return_data['newInstance'] = True
    return return_data


def handle_new_install(db:SPARCdDatabase, user_info: UserInfo, s3_info: S3Info,
																		settings_path: str) -> dict:
    """ Implementation of a new install
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        settings_path: path to where the settings files are kept
    Return:
        Returns a new instance dict
      """

    # Check that we can create
    sole_user = False
    if not bool(user_info.admin):
        if not db.is_sole_user(s3_info.id, user_info.name):
            return {'success': False,
                    'message': 'You are not authorized to create a new SPARCd configuration'}
        sole_user = True

    # Check if the S3 instance needs repairs and of is all set
    needs_repair, has_everything = S3Connection.needs_repair(s3_info)

    if needs_repair or has_everything:
        return {'success': False, 'message': 'There is already an existing SPARCd ' \
                                                        'configuration'}

    # The user is apparently the sole user or an admin, and the S3 instance is not setup for SPARCd
    if not S3Connection.create_sparcd(s3_info, settings_path):
        return {'success': False, 'message': 'Unable to configure new SPARCd instance'}

    # Make this user the admin if they're the only one in the DB
    if sole_user:
        db.update_user(s3_info.id, user_info.name, user_info.email, True)

    return {'success': True}


def handle_repair_install(user_info: UserInfo, s3_info: S3Info, settings_path: str) -> dict:
    """ Implementation of repairing an installation
    Arguments:
        user_info: the user information
        s3_info: the S3 endpoint information
        settings_path: path to where the settings files are kept
    Return:
        Returns a repair instance dict
      """
    # Check that we can create
    if not bool(user_info.admin):
        return {'success': False, 'message': 'You are not authorized to repair the ' \
                                                    'SPARCd configuration'}

    # Check if the S3 instance needs repairs and of is all set
    needs_repair, has_everything = S3Connection.needs_repair(s3_info)

    if not needs_repair or has_everything:
        return {'success': True, \
                 'message': 'The SPARCd installation doesn\'t need repair'}

    # Make repairs
    if not S3Connection.repair_sparcd(s3_info, settings_path):
        return {'success': False, 'message': 'Unable to repair this SPARCd instance'}

    return {'success': True}
