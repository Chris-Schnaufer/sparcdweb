""" Implementation of CamTrap Observation """

# pylint: disable=too-many-instance-attributes
class Observation:
    """ Contains Observation data:
    https://github.com/tdwg/camtrap-dp/blob/1.0.2/observations-table-schema.json
    """
    # pylint: disable=too-few-public-methods
    def __init__(self, observation_id: str):
        """ Instance initialization
        Arguments:
            observation_id: the ID of this observation
        """
        self.observation_id = observation_id
        self.deployment_id = ""
        self.media_id = ""
        self.event_id = ""
        self.event_start = ""    # timestamp
        self.event_end = ""      # timestamp
        self.observation_level = ""
        self.observation_type = ""
        self.camera_setup_type = ""
        self.scientific_name = ""
        self.count = 0
        self.life_stage = ""
        self.sex = ""
        self.behaviour = ""
        self.individual_id = ""
        self.individual_position_radius = ""
        self.individual_position_angle = 0
        self.individual_speed = 0
        self.bbox_x = 0
        self.bbox_y = 0
        self.bbox_width = 0
        self.bbox_height = 0
        self.classification_method = ""
        self.classified_by = ""
        self.classification_timestamp = ""
        self.classification_probability = 1.0000
        self.observation_tags = ""
        self.observation_comments = ""
