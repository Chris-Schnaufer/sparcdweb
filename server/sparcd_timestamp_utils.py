""" Timestamp adjustment utilities for SPARCd server """

import calendar
import concurrent.futures
import os
import tempfile
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.relativedelta import relativedelta

from camtrap.v016 import camtrap
import image_utils
from s3.s3_access_helpers import SPARCD_PREFIX, download_s3_file
from s3.s3_connect import s3_connect
from s3.s3_uploads import S3UploadConnection
from spd_types.s3info import S3Info


@dataclass
class TimestampAdjustContext:
    """ Shared context for timestamp adjustment operations """
    s3_info: S3Info
    bucket: str
    media_info: dict
    time_adjust: relativedelta


def add_to_datetime(dt: datetime, ta: relativedelta) -> datetime:
    """ Adjusts the datetime according to the offset parameters. Handles leap years
        correctly. Doesn't adjust time offsets smaller than seconds
    Arguments:
        dt: The starting datetime
        ta: Contains the offsets to the various timestamp parts
    Returns:
        A new datetime with all offsets applied.
    """
    total_months = dt.month - 1 + ta.month
    total_months += ta.year * 12

    new_year = dt.year + total_months // 12
    new_month = total_months % 12 + 1

    max_day = calendar.monthrange(new_year, new_month)[1]
    new_day = min(dt.day, max_day)

    result = dt.replace(year=new_year, month=new_month, day=new_day)
    result += timedelta(days=ta.day, hours=ta.hour, minutes=ta.minute, seconds=ta.second)

    return result


def get_tz_offset(tz_offset: str) -> float:
    """ Converts a timezone offset or name to a numeric value. If the passed in parameter can't
        be converted, the local offset is used
    Arguments:
        tz_offset: the number offset of the timezone in hours, or the timezone name
                   (eg: "America/Phoenix")
    Return:
        Returns the timezone offset in hours as a float
    """
    if tz_offset is not None:
        try:
            tz_offset = int(tz_offset)
        except ValueError:
            pass

        if not isinstance(tz_offset, int):
            try:
                tz_offset = datetime(2025, 10, 9, 0, 0, 0, 0, ZoneInfo(tz_offset)).strftime('%z')
                off_hours, off_min = divmod(int(tz_offset), 100.0)
                tz_offset = off_hours + (off_min / 60)
            except (ZoneInfoNotFoundError, ValueError):
                tz_offset = None

    if tz_offset is None:
        tz_offset = time.localtime().tm_gmtoff / (60.0 * 60.0)

    return tz_offset


def __apply_timestamp_result(timestamp_result: tuple, context: TimestampAdjustContext) -> None:
    """ Applies a timestamp adjustment result to the media info dict in place
    Arguments:
        timestamp_result: the tuple of (filename, mapped_name, new_ts) from adjust_timestamp_thread
        context: the shared context containing media_info and time_adjust
    """
    if timestamp_result is None or len(timestamp_result) < 3 or timestamp_result[2] is None:
        return

    _, mapped_file, new_ts = timestamp_result

    if new_ts:
        context.media_info[mapped_file][camtrap.CAMTRAP_MEDIA_TIMESTAMP_IDX] = \
            new_ts.isoformat()
        return

    existing_ts = context.media_info[mapped_file][camtrap.CAMTRAP_MEDIA_TIMESTAMP_IDX]
    if not existing_ts:
        return

    try:
        media_ts = datetime.fromisoformat(existing_ts)
        if media_ts:
            context.media_info[mapped_file][camtrap.CAMTRAP_MEDIA_TIMESTAMP_IDX] = \
                add_to_datetime(media_ts, context.time_adjust).isoformat()
    except ValueError:
        pass


def adjust_timestamp_thread(context: TimestampAdjustContext,
                            filename: str, mapped_name: str) -> Optional[tuple]:
    """ Called to update the timestamp of an image file
    Arguments:
        context: the shared S3 and media context
        filename: the name of the file to update
        mapped_name: the mapped filename for the media info
    Return:
        Returns a tuple of the original name, mapped name, and updated timestamp when successful.
        Otherwise, None is returned
    """
    if mapped_name is None or mapped_name not in context.media_info:
        return None

    minio = s3_connect(context.s3_info)
    if not minio:
        return None

    file_path = context.media_info[mapped_name][camtrap.CAMTRAP_MEDIA_FILE_PATH_IDX]
    temp_file = tempfile.mkstemp(suffix=os.path.splitext(mapped_name)[1],
                                 prefix=SPARCD_PREFIX)
    os.close(temp_file[0])

    if not download_s3_file(minio, context.bucket, file_path, temp_file[1]):
        print(f'Warning: Unable to find file to change timestamp {context.bucket} {filename}',
              flush=True)
        if os.path.exists(temp_file[1]):
            os.unlink(temp_file[1])
        return None

    new_ts = image_utils.update_timestamp(temp_file[1], context.time_adjust)

    if new_ts is not None:
        S3UploadConnection.upload_file(context.s3_info, context.bucket, file_path, temp_file[1])

    if os.path.exists(temp_file[1]):
        os.unlink(temp_file[1])

    return filename, mapped_name, new_ts


def adjust_timestamps(files: tuple, context: TimestampAdjustContext) -> dict:
    """ Adjusts the timestamps of the specified image files
    Arguments:
        files: the list of files to change
        context: the shared S3 and media context
    Returns:
        Returns the media information with any adjustments made
    """
    if not files:
        return context.media_info

    media_map = {os.path.splitext(one_key)[0]: one_key
                 for one_key in context.media_info.keys()}

    with concurrent.futures.ThreadPoolExecutor() as executor:
        cur_futures = {executor.submit(adjust_timestamp_thread, context,
                                       one_file, media_map[one_file]):
                       one_file for one_file in files if one_file in media_map}

        for future in concurrent.futures.as_completed(cur_futures):
            try:
                __apply_timestamp_result(future.result(), context)
            except Exception as ex:  # pylint: disable=broad-exception-caught
                print(f'Generated exception: {ex}', flush=True)
                traceback.print_exception(ex)

    return context.media_info
