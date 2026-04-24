""" Functions to handle requests starting with /species for SPARCd server """

from dataclasses import dataclass
import os
import tempfile

import sparcd_file_utils as sdfu
from spd_types.s3info import S3Info
from s3_access import SPECIES_JSON_FILE_NAME
import s3_utils as s3u


@dataclass
class OtherSpeciesParams:
    """ Contains the parameters for other species calls """
    other_filename: str
    stat_filename: str
    stat_timeout_sec: int
    temp_species_filename: str


def handle_species_other(s3_info: S3Info, params: OtherSpeciesParams) -> list:
    """ Handles loading non-standard species
    Arguments:
        db: the database instance
        user_info: the user information
        s3_info: the S3 endpoint information
        params: parameters for this call
    Return:
        Return a list of the other species, or an empty list if not found are there are no
        non-standard species
    """
    # Check if we have the unofficial species already
    # The temporary file expires after 30 days, it will get regenerated when species load again
    otherspecies_temp_filename = os.path.join(tempfile.gettempdir(), params.other_filename)

    others = sdfu.load_timed_info(otherspecies_temp_filename, 30 *24 * 60 * 60)

    if others:
        return others

    # Check if we have the stats needed to regenerate the unofficial species
    stats_temp_filename = os.path.join(tempfile.gettempdir(), params.stat_filename)

    cur_stats = sdfu.load_timed_info(stats_temp_filename, params.stat_timeout_sec)
    if cur_stats is None:
        return []

    # Get the official species
    cur_species = s3u.load_sparcd_config(SPECIES_JSON_FILE_NAME,
                                         params.temp_species_filename,
                                         s3_info)
    if not cur_species:
        return []

    # For each species in the official list, we mark that species
    for one_species in cur_species:
        if one_species['name'] in cur_stats:
            cur_stats[one_species['name']]['count'] = -22

    # Collect the unofficial species names by filtering out our matches
    other_species = [{'name':one_key, 'scientificName':cur_stats[one_key]['scientificName']} \
                                    for one_key in cur_stats if cur_stats[one_key]['count'] != -22]

    sdfu.save_timed_info(otherspecies_temp_filename, other_species)

    return other_species
