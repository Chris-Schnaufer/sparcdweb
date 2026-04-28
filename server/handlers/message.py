""" Functions to handle requests starting with /message for SPARCd server """

import json
from typing import Union

from flask import request

from sparcd_db import SPARCdDatabase
from spd_types.userinfo import UserInfo
from spd_types.s3info import S3Info

def handle_message_add(db: SPARCdDatabase, user_info: UserInfo,
														s3_info: S3Info) -> Union[dict, bool, None]:
    """ Implementation of adding messages
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
    Return:
        Returns a status dict when successful. Fals is returned if there's a problem with the
        request parameters. None is returned if the request couldn't be completed
      """
    # Get the rest of the request parameters
    receiver = request.form.get('receiver')
    subject = request.form.get('subject')
    message = request.form.get('message')
    priority = request.form.get('priority')

    # Check what we have from the requestor
    if not all(item for item in [receiver, subject]):
        return False

    # Check the parameters
    if not message:
        message = ""
    if priority is None:
        priority = "normal"

    all_receivers = [one_rec.strip() for one_rec in receiver.split(',')]

    # Add the messages
    for one_rec in all_receivers:
        db.message_add(s3_info.id, user_info.name, one_rec, subject, message, priority)

    return {'success': True, 'message': 'All messages stored'}


def handle_message_read(db: SPARCdDatabase, user_info: UserInfo,
														s3_info: S3Info) -> Union[dict, bool, None]:
    """ Implementation of marking messages as read
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
    Return:
        Returns a status dict when successful. Fals is returned if there's a problem with the
        request parameters. None is returned if the request couldn't be completed
      """
    # Get the rest of the request parameters
    ids = request.form.get('ids', None)
    if ids is None:
        return False
    ids = json.loads(ids)

    all_ids = [int(one_id) for one_id in ids]
    db.messages_are_read(s3_info.id, user_info.name, all_ids)
    if bool(user_info.admin):
        db.messages_are_read(s3_info.id, 'admin', all_ids)

    return {'success': True, 'message': 'Messages were marked as read'}


def handle_message_delete(db: SPARCdDatabase, user_info: UserInfo,
														s3_info: S3Info) -> Union[dict, bool, None]:
    """ Implementation of deleting messages
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
    Return:
        Returns a status dict when successful. Fals is returned if there's a problem with the
        request parameters. None is returned if the request couldn't be completed
      """

    # Get the rest of the request parameters
    ids = request.form.get('ids', None)
    if ids is None:
        return False
    ids = json.loads(ids)

    all_ids = [int(one_id) for one_id in ids]
    db.messages_are_deleted(s3_info.id, user_info.name, all_ids)
    if bool(user_info.admin):
        db.messages_are_deleted(s3_info.id, 'admin', all_ids)

    return {'success': True, 'message': 'Messages were marked as deleted'}
