""" Functions to handle /_next requests for SPARCd server """

import io
import os
from typing import Optional, Union
from PIL import Image

# Starting point for uploading files from server
RESOURCE_START_PATH = os.path.abspath(os.path.dirname(__file__))

def __parse_width_param(w_param: str) -> Union[float, None, bool]:
    """Parse and validate the width parameter.
    Arguments:
        w_param: the width parameter from the request
    Returns:
        float if valid, None if not provided, False if invalid.
    """
    if not w_param:
        return None
    try:
        return float(w_param)
    except ValueError:
        print('   INVALID width parameters')
        return False


def __parse_quality_param(q_param: str) -> Union[int, bool]:
    """Parse and validate the quality parameter.
    Arguments:
        q_param: the quality parameter from the request
    Returns:
        int if valid or not provided (defaults to 100), False if invalid.
    """
    if not q_param:
        return 100
    try:
        value = int(q_param)
        if value <= 0 or value > 100:
            return 100
        if value < 5:
            return 5
        return value
    except ValueError:
        print('   INVALID quality parameters')
        return False


def __load_sized_image(filepath: str, width: int, quality: int, mime_type: str) -> io.BytesIO:
    """ Loads and resizes the image
    Arguments:
        filepath: the path of the file to load
        width: the width of the returned image
        quality: the desired image quality
        mime_type: the type of image
    Return:
        Returns the loaded and resized image bytes as a memory stream
    """
    img = Image.open(filepath)

    height = float(img.size[1]) * (width / float(img.size[0]))
    img = img.resize((round(width), round(height)), Image.Resampling.LANCZOS)

    img_byte_array = io.BytesIO()
    img.save(img_byte_array, mime_type.upper(), quality=quality)

    img_byte_array.seek(0)  # move to the beginning of file after writing

    return img_byte_array


def handle_next_static(path_fragment: str, allowed_extensions: tuple) -> Optional[str]:
    """ Handle when a _next/static file is to be returned
    Arguments:
        path_fragment: The passed in path fragment of file to fetch
        allowed_extensions: the list of file extensions we're allowed to return
    Return:
        Returns the full path of the file if it's allowed to be loaded. None is returned otherwise
    """

    # Check that the file is allowed
    if not os.path.splitext(path_fragment)[1].lower() in allowed_extensions:
        return None

    fullpath = os.path.realpath(os.path.join(RESOURCE_START_PATH, '_next', 'static',\
                                                                        path_fragment.lstrip('/')))

    # Make sure we're only serving something that's in the same location that we are in and that
    # it exists
    if not fullpath or not os.path.exists(fullpath) or not fullpath.startswith(RESOURCE_START_PATH):
        return None

    return fullpath

def handle_next_image(image_path: str, w_param: str, q_param: str, \
                                                                allowed_extensions: tuple) -> tuple:
    """ Handles loading the request for loading an image
    Arguments:
        image_path: the path to the image to load
        w_param: the desired width of the returned image
        q_param: the quality parameter
        allowed_extensions: the list of file extensions we're allowed to return
    Return:
        Returns a tuple containing the file name, the loaded bytes as an in memory byte stream, and
        the image mime type upon success. If the file name is the only non-None return value, the
        file requested is intended to be sent "as is". If all the returned values are None, the
        request was bad. Otherwise, the second and third returned value will contain the image
        bytes as an im-memory byte stream and the image mime type
    """
    fullpath, img_byte_array, image_type = None, None, None

    w_param = __parse_width_param(w_param)
    q_param = __parse_quality_param(q_param)

    if image_path and w_param is not False and q_param is not False:
        # Get the full file path and file extension (for the image type)
        fullpath = os.path.realpath(os.path.join(RESOURCE_START_PATH, image_path.lstrip('/')))
        image_type = os.path.splitext(image_path)[1][1:].lower()
        print(f"   FILE PATH: {fullpath}", flush=True)

        valid_extension = f'.{image_type}' in allowed_extensions
        valid_path = fullpath and os.path.exists(fullpath) and \
                                                            fullpath.startswith(RESOURCE_START_PATH)

        if valid_extension and valid_path:
            if w_param is not None and w_param > 1.0:
                if image_type == 'jpg':
                    image_type = 'jpeg'
                img_byte_array = __load_sized_image(fullpath, w_param, q_param, image_type)
            else:
                image_type = None
        else:
            fullpath, image_type = None, None

    return fullpath, img_byte_array, image_type
