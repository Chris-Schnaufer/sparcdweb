""" Shared constants for SPARCd server — no local module dependencies """

from s3.s3_access_helpers import SPARCD_PREFIX

# Name of temporary species stats file postfix
TEMP_SPECIES_STATS_FILE_NAME_POSTFIX = '-' + SPARCD_PREFIX + 'species-stats.json'

# Timeout for species stats file
TEMP_SPECIES_STATS_FILE_TIMEOUT_SEC = 12 * 60 * 60
