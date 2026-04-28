""" Query utilities """

from dataclasses import dataclass
import re

@dataclass
class LocationCsvFormat:
    """ Contains the resolved format settings for location CSV output """
    location_keys: list
    elevation_keys: list


@dataclass
class RawCsvFormat:
    """ Contains the resolved format settings for raw CSV output """
    location_keys: list
    elevation_keys: list
    timestamp_keys: object  # str or dict depending on date mod


def __apply_location_mods(settings: dict, mods: tuple) -> LocationCsvFormat:
    """ Resolves the format settings from modifiers and user settings
    Arguments:
        settings: the user settings
        mods: the modifications to apply
    Return:
        Returns a LocationCsvFormat instance with resolved format settings
    """
    location_keys = ['locX', 'locY']
    elevation_keys = ['locElevation']

    if mods is None:
        return LocationCsvFormat(location_keys, elevation_keys)

    for one_mod in mods:
        if 'type' not in one_mod:
            continue
        match one_mod['type']:
            case 'hasLocations':
                if settings.get('coordinatesDisplay', 'LATLON') == 'UTM':
                    location_keys = ['utm_code', 'utm_x', 'utm_y']
            case 'hasElevation':
                if settings.get('measurementFormat', 'meters') == 'feet':
                    elevation_keys = ['locElevationFeet']

    return LocationCsvFormat(location_keys, elevation_keys)


def __apply_raw_mods(settings: dict, mods: tuple) -> RawCsvFormat:
    """ Resolves the format settings from modifiers and user settings
    Arguments:
        settings: the user settings
        mods: the modifications to apply
    Return:
        Returns a RawCsvFormat instance with resolved format settings
    """
    location_keys = ['locX', 'locY']
    elevation_keys = ['locElevation']
    timestamp_keys = 'date'

    if mods is None:
        return RawCsvFormat(location_keys, elevation_keys, timestamp_keys)

    for one_mod in mods:
        if 'type' not in one_mod:
            continue
        match one_mod['type']:
            case 'hasLocations':
                if settings.get('coordinatesDisplay', 'LATLON') == 'UTM':
                    location_keys = ['utm_code', 'utm_x', 'utm_y']
            case 'hasElevation':
                if settings.get('measurementFormat', 'meters') == 'feet':
                    elevation_keys = ['locElevationFeet']
            case 'date':
                date_format = settings.get('dateFormat', 'MDY')
                time_format = settings.get('timeFormat', '24')
                timestamp_keys = {'date': 'date' + date_format,
                                  'time': 'time' + time_format}

    return RawCsvFormat(location_keys, elevation_keys, timestamp_keys)


def __build_raw_row(one_row: dict, fmt: RawCsvFormat) -> str:
    """ Builds a single CSV row from a raw query result
    Arguments:
        one_row: the row data to format
        fmt: the resolved format settings
    Return:
        Returns the formatted CSV row string
    """
    cur_row = [one_row['image'] if one_row['image'] else '']

    if isinstance(fmt.timestamp_keys, str):
        cur_row.append('"' + one_row['date'] + '"')
    else:
        cur_row.append('"' + one_row[fmt.timestamp_keys['date']] + ' ' +
                       one_row[fmt.timestamp_keys['time']] + '"')

    cur_row.append(one_row['locName'] if one_row['locName'] else 'Unknown')
    cur_row.append(one_row['locId'] if one_row['locId'] else 'unknown')

    for one_key in fmt.location_keys:
        cur_row.append(str(one_row[one_key]) if one_row[one_key] else '0')
    for one_key in fmt.elevation_keys:
        cur_row.append(re.sub(r'[^\d\.]', '', str(one_row[one_key])
                              if one_row[one_key] else '0'))

    cur_idx = 1
    while True:
        if all(f'{field}{cur_idx}' in one_row
               for field in ('scientific', 'common', 'count')):
            cur_row.append(one_row[f'scientific{cur_idx}'])
            cur_row.append(one_row[f'common{cur_idx}'])
            cur_row.append(str(one_row[f'count{cur_idx}']))
            cur_idx += 1
        else:
            break

    return ','.join(cur_row) + '\n'


def query_raw2csv(raw_data: tuple, settings: dict, mods: tuple = None) -> str:
    """ Returns the CSV of the specified raw query results
    Arguments:
        raw_data: the query data to convert
        settings: user settings
        mods: modifications to make on the data based upon user settings
    """
    fmt = __apply_raw_mods(settings, mods)
    return ''.join(__build_raw_row(one_row, fmt) for one_row in raw_data)


def query_location2csv(location_data: tuple, settings: dict, mods: dict = None) -> str:
    """ Returns the CSV of the specified location query results
    Arguments:
        location_data: the location data to convert
        settings: user settings
        mods: modifications to make on the data based upon user settings
    """
    fmt = __apply_location_mods(settings, mods)

    def build_row(one_row: dict) -> str:
        cur_row = [one_row['name'], one_row['id']]
        for one_key in fmt.location_keys:
            cur_row.append(str(one_row[one_key]))
        for one_key in fmt.elevation_keys:
            cur_row.append(re.sub(r'[^\d\.]', '', str(one_row[one_key])))
        return ','.join(cur_row) + '\n'

    return ''.join(build_row(one_row) for one_row in location_data)


def query_species2csv(species_data: tuple, settings: dict, mods: dict=None) -> str:
    """ Returns the CSV of the specified species query results
    Arguments:
        species_data: the species data to convert
        settings: user settings
        mods: modifictions to make on the data based upon user settings
    """
    # pylint: disable=unused-argument
    all_results = ''
    for one_row in species_data:
        all_results += ','.join([one_row['common'], one_row['scientific']]) + '\n'

    return all_results


def query_allpictures2csv(allpictures_data: tuple, settings: dict, mods: dict = None) -> str:
    """ Returns the CSV of the specified Sanderson all pictures query results
    Arguments:
        allpictures_data: the all pictures data to convert
        settings: user settings
        mods: modifictions to make on the data based upon user settings
    """
    # pylint: disable=unused-argument
    all_results = ''
    for one_row in allpictures_data:
        all_results += ','.join([one_row['location'], one_row['species'], one_row['image']]) + '\n'

    return all_results
