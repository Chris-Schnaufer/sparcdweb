""" Functions to handle requests starting with /query for SPARCd server """

from dataclasses import dataclass
import datetime
import json
import os
import tempfile
import threading
from typing import Optional
import uuid

from flask import request, Response

import query_helpers
import query_utils
import sparcd_collections as sdc
from sparcd_db import SPARCdDatabase
import sparcd_file_utils as sdfu
import sparcd_utils as sdu
from spd_types.userinfo import UserInfo
from spd_types.s3info import S3Info
from s3_access import SPARCD_PREFIX, SPECIES_JSON_FILE_NAME
import s3_utils as s3u
from text_formatters.results import Results
import zip_utils as zu

# Default query interval
DEFAULT_QUERY_INTERVAL = 60


@dataclass
class RunQueryContext:
    """ Contains additional information for running queries """
    filters: tuple
    interval: int
    temp_species_filename: str

@dataclass
class QueryDownloadParams:
    """ Contains the parameters for downloading query result calls """
    token: str
    tab_name: str
    target: str
    timeout_sec: int


def __build_download_response(s3_info: S3Info,
                               user_info: UserInfo,
                               query_results: dict,
                               tab: str,
                               target: str) -> Response:
    """ Builds the download response for a query
    Arguments:
        s3_info: the S3 endpoint information
        user_info: the user information
        query_results: the query results
        tab: the tab name
        target: the target filename
    Return:
        Returns a Flask Response for the download, or None if the tab is not recognised
    """
    col_mods = query_results['columnsMods'].get(tab)

    match tab:
        case 'DrSandersonOutput':
            dl_name = target or 'drsanderson.txt'
            content = query_results[tab]
            mimetype = 'text/text'

        case 'DrSandersonAllPictures':
            dl_name = target or 'drsanderson_all.csv'
            content = query_utils.query_allpictures2csv(query_results[tab],
                                                        user_info.settings, col_mods)
            mimetype = 'application/csv'

        case 'csvRaw':
            dl_name = target or 'allresults.csv'
            content = query_utils.query_raw2csv(query_results[tab],
                                                user_info.settings, col_mods)
            mimetype = 'text/csv'

        case 'csvLocation':
            dl_name = target or 'locations.csv'
            content = query_utils.query_location2csv(query_results[tab],
                                                     user_info.settings, col_mods)
            mimetype = 'text/csv'

        case 'csvSpecies':
            dl_name = target or 'species.csv'
            content = query_utils.query_species2csv(query_results[tab],
                                                    user_info.settings, col_mods)
            mimetype = 'text/csv'

        case 'imageDownloads':
            dl_name = target or 'allimages.gz'
            read_fd, write_fd = os.pipe()
            # pylint: disable=consider-using-with
            download_finished_lock = threading.Semaphore(1)
            download_finished_lock.acquire()
            dl_thread = threading.Thread(target=zu.generate_zip,
                                         args=(s3_info,
                                               [row['name'] for row in query_results[tab]],
                                               write_fd, download_finished_lock))
            dl_thread.start()
            content = zu.zip_iterator(read_fd)
            mimetype = 'application/gzip'

        case _:
            return None

    return Response(content, mimetype=mimetype,
                    headers={'Content-disposition': f'attachment; filename="{dl_name}"'})

def __get_request_params() -> tuple:
    """ Gets the parameters from the request
    Return:
        Returns a tuple containing: the interval to use, a bool indicating whether or not the
        filters were gotten (True) or if an error was encountered (False), and a list of filters
        if successful (otherwise None)
    """
    interval = request.args.get('i', DEFAULT_QUERY_INTERVAL)
    try:
        interval = int(interval)
    except ValueError:
        interval = DEFAULT_QUERY_INTERVAL
    finally:
        if not interval or interval < 0:
            interval = DEFAULT_QUERY_INTERVAL

    filters = []
    have_error = False
    for key, value in request.form.items(multi=True):
        match key:
            case 'collections' | 'dayofweek' | 'elevations' | 'hour' | 'locations' | \
                 'month' | 'species' | 'years':
                try:
                    filters.append((key, json.loads(value)))
                except json.JSONDecodeError:
                    print(f'Error: bad query data for key: {key}')
                    have_error = True
            case 'endDate' | 'startDate':
                filters.append((key, datetime.datetime.fromisoformat(value)))
            case _:
                print(f'Error: unknown query key detected: {key}')
                have_error = True

    return interval, have_error, filters


def __run_query(db: SPARCdDatabase, user_info: UserInfo, s3_info: S3Info,
                                                            context: RunQueryContext) -> Results:
    """ Gets the results from the query
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        context: additional context for running the query
    Return:
        The results of the query
    """
    # Get collections from the database
    coll_info = sdc.load_collections(db, bool(user_info.admin), s3_info)

    # Filter collections
    filter_colls = []
    for one_filter in context.filters:
        if one_filter[0] == 'collections':
            filter_colls = filter_colls + \
                                    [coll for coll in coll_info if coll['bucket'] in one_filter[1]]
    if not filter_colls:
        filter_colls = coll_info

    # Get uploads information to further filter images
    all_results = query_helpers.filter_collections(db, filter_colls, s3_info, context.filters)

    # Get the species and locations
    cur_species = s3u.load_sparcd_config(SPECIES_JSON_FILE_NAME,
                                         context.temp_species_filename,
                                         s3_info)
    cur_locations = sdu.load_locations(s3_info)

    return Results(all_results, cur_species, cur_locations, s3_info, user_info.settings,
                                                                                context.interval)



def handle_query(db: SPARCdDatabase, user_info: UserInfo, s3_info: S3Info, token: str,
                                                    temp_species_filename: str) -> Optional[dict]:
    """ Entirely handles a query request
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        token: the request token
        temp_species_filename; the path to the temporary species file
    Return:
        Returns the dict containing the query results information upon success. Returns None if
        there's a problem
    """
    # Check the request parameters
    interval, have_error, filters = __get_request_params()

    # Check what we have from the requestor
    if have_error:
        print('INVALID QUERY:', user_info.name, have_error)
        return None
    if not filters:
        print('NO FILTERS SPECIFIED')
        return None

    results = __run_query(db,
                          user_info,
                          s3_info,
                          RunQueryContext(filters=filters,
                                          interval=interval,
                                          temp_species_filename=temp_species_filename
                                         )
                         )

    # Format and return the results
    results_id = uuid.uuid4().hex
    return_info = query_helpers.query_output(results, results_id)

    # Check for old queries and clean them up
    sdu.cleanup_old_queries(db, token)

    # Save the query for lookup when downloading results
    save_path = os.path.join(tempfile.gettempdir(), SPARCD_PREFIX + 'query_' + \
                                                                results_id + '.json')
    sdfu.save_timed_info(save_path, return_info)
    db.save_query_path(token, save_path)

    return return_info


def handle_query_download(db:SPARCdDatabase, user_info: UserInfo, s3_info: S3Info,
                                                            params: QueryDownloadParams) -> tuple:
    """ Returns the requested download from a query
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        params: additional parameters for this request
    Return:
        A tuple continaing a bool indicating that we were able to load the stored query information
        (True) or now (False), the Flask Response to return as-is upon success and None otherwise
    """

    # Get the query information
    query_info_path, _ = db.get_query(params.token)

    # Try and load the query results
    query_results = sdfu.load_timed_info(query_info_path, params.timeout_sec)
    if not query_results:
        return False, None

    return True, __build_download_response(s3_info,
                                            user_info,
                                            query_results,
                                            params.tab_name,
                                            params.target
                                           )
