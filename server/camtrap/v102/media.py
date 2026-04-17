""" Implementation of CamTrap Media """

# pylint: disable=too-many-instance-attributes
class Media:
    """ Contains Media data:
    https://github.com/tdwg/camtrap-dp/blob/1.0.2/media-table-schema.json
    """
    # pylint: disable=too-few-public-methods

    def __init__(self, media_id: str):
        """ Instance initialization
        Arguments:
            media_id: the ID of the media
        """
        self.media_id = media_id
        self.deployment_id = ""
        self.capture_method = ""
        self.timestamp = ""
        self.file_path = ""
        self.file_public = False
        self.file_name = ""
        self.file_media_type = ""
        self.exif_data = ""
        self.favorite = False
        self.media_comments = ""
