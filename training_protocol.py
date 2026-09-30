from village.custom_classes.training_protocol_base import TrainingProtocolBase
import numpy as np

class TrainingProtocol(TrainingProtocolBase):
    """
    This class defines how the training protocol is going to be.
    This is, how variables change depending on different conditions (e.g. performance),
    and/or which tasks are going to be run.

    In this class 2 methods need to be implemented:
    - __init__
    - default_training_settings
    - update_training_settings

    In default_training_settings all the variables that can modify the state of 
    the training protocol must be defined.
    In update_training_settings the variables are updated depeding on the
    performance of the animal.
    When a new subject is created, a new row is added to the data/subjects.csv file,
    with these variables and its values.

    The following variables are needed:
    - self.next_task
    - self.refractory_period
    - self.minimum_duration
    - self.maximum_duration
    In addition to these variables, all the necessary variables to modify the state
    of the tasks can be included.

    When a task is run the values of the variables are read from the json file.
    When the task ends, the values of the variables are updated in the json file,
    following the logic in the update method."""

    def __init__(self) -> None:
        super().__init__()

        
    def default_training_settings(self) -> None:
        """
        This method is called when a new subject is created.
        It sets the default values for the training protocol.
        """

        # Settings in this block are mandatory for everything
        # that runs on Traning Village
        # TODO
        self.settings.next_task = "LickTeaching"
        self.settings.refractory_period = 240 * 60 # 4 hours
        self.settings.minimum_duration = 5 * 60
        self.settings.maximum_duration =  15 * 60 # lasts 15 mins
        self.settings.maximum_number_of_trials = 200

        # Settings in this block are dependent on each task,
        # and the user needs to create and define them here
        self.settings.water_volume = 5
        self.settings.number_of_switches = 0
        self.settings.lickport_distance = 0


    def update_training_settings(self) -> None:
        """
        This method is called every time a session finishes.
        It is used to make the animal progress in the training protocol.
        """

        if self.last_task == "LickTeaching":
            pass

    def define_gui_tabs(self) -> None:
        pass

    