""" Implementation of CamTrap Deployment """

# pylint: disable=too-many-instance-attributes
class Deployment:
    """ Contains Deployment data:
    https://github.com/tdwg/camtrap-dp/blob/1.0.1/deployments-table-schema.json
    """
    # pylint: disable=too-few-public-methods

    def __init__(self, deployment_id: str):
        """ Initialize class instance
        Arguments:
            deployment_id: the ID of the deployment
        """
        self.deployment_id = deployment_id
        self.location_id = ""
        self.location_name = ""
        self.longitude = 0.0
        self.latitude = 0.0
        self.coordinate_uncertainty = 0
        self.deployment_start = ""      # timestamp
        self.deployment_end = ""        # timestamp
        self.setup_by = ""
        self.camera_id = ""
        self.camera_model = ""
        self.camera_delay = 0
        self.camera_height = 0.0
        self.camera_depth = 0.0
        self.camera_tilt = 0.0
        self.camera_heading = 0
        self.detection_distance = 0.0
        self.timestamp_issues = False
        self.bait_use = ""
        self.feature_type = ""
        self.habitat = ""
        self.deployment_groups = ""
        self.deployment_tags = ""
        self.deployment_comments = ""
