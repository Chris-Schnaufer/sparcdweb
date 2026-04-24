""" Route decorators for SPARCd server """

import functools
from flask import request
from sparcd_db import SPARCdDatabase
import sparcd_utils as sdu

def make_authenticated_route(db_path: str, session_expire_seconds: int):
    """ Factory function that returns a route authentication decorator.    
    Args:
        db_path: path to the SPARCd database
        session_expire_seconds: number of seconds before a session expires
    Returns:
        A decorator that handles auth boilerplate for route handlers,
        injecting `db`, `token`, and `user_info` as keyword arguments.
    """
    def authenticated_route(admin_only: bool = False, non_admin_only: bool = False):
        """ Route handling function
        Arguments:
            admin_only: set to True if the user needs to be an admin
            non_admin_only: set to True if the user should not be an admin
        Return:
            Returns the route decorator function
        """
        def decorator(func):
            """ The decorator function
            Arguments:
                func: The function to call with the added parameters
            Return:
                Returns the results of the function
            """
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                """ Handles the authentication and calls the handling function
                Return:
                    Returns the result of calling the function, or error codes
                    upon failure
                """
                db = SPARCdDatabase(db_path)
                token = request.args.get('t')

                token_valid, user_info = sdu.token_user_valid(db, request, token,
                                                              session_expire_seconds)
                if token_valid is None or user_info is None:
                    return "Not Found", 404
                if not token_valid or not user_info:
                    return "Unauthorized", 401
                if admin_only and not bool(user_info.admin):
                    return "Not Found", 404
                if non_admin_only and bool(user_info.admin):
                    return "Not Found", 404

                return func(*args, db=db, token=token, user_info=user_info, **kwargs)
            return wrapper
        return decorator
    return authenticated_route
