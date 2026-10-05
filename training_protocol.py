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
        - next_task (str): Name of the first task the subject will run.
        - refractory_period (int): Seconds the subject must wait between sessions.
        - minimum_duration (int): Seconds before door 2 opens (subject may leave).
        - maximum_duration (int): Seconds before the task stops automatically.
    
    In addition to these variables, all the necessary variables to modify the state
    of the tasks can be included.

    When a task is run the values of the variables are read from the json file.
    When the task ends, the values of the variables are updated in the json file,
    following the logic in the update method."""


    REWARDS_TO_PROGRESS = 20  # rewarded trials within a single session

    def __init__(self) -> None:
        super().__init__()

    def default_training_settings(self) -> None:
        # Mandatory settings
        self.settings.next_task = "Habituation"
        self.settings.refractory_period = 240 * 60  # 4 hours between sessions
        self.settings.minimum_duration = 5 * 60  # 5 min minimum session length
        self.settings.maximum_duration = 15 * 60  # 15 min max session length

        # Task-dependent settings (persist across sessions)
        self.settings.water_volume = 5
        self.settings.lickport_distance = 0

    def update_training_settings(self) -> None:
        if self.last_task == "Habituation":
            self.settings.next_task = "LickTeaching"

        elif self.last_task == "LickTeaching":
            df_habituation = self.df[self.df["task"] == "Habituation"]
            n_rewards = df_habituation.iloc[-1]["trial"].iloc[-1]  # every trial ends in a reward

            if n_rewards > self.REWARDS_TO_PROGRESS:
                self.settings.next_task = "HeadportEntryTeaching"

    def define_gui_tabs(self) -> None:
        pass

    