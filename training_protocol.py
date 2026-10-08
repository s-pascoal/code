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


    def __init__(self) -> None:
        super().__init__()

    def default_training_settings(self) -> None:
        # Mandatory settings
        self.settings.next_task = "Habituation"
        self.settings.refractory_period = 240 * 60  # 4 hours between sessions
        self.settings.minimum_duration = 10 * 60  # 10 min minimum session length
        self.settings.maximum_duration = 15 * 60  # 15 min max session length

        # Task-dependent settings (persist across sessions)
        self.settings.water_volume = 5
        # Initial lickport distance from headport for the first session
        self.settings.lickport_distance = self.task.motor_box3.set_position(self.task.settings.motor_position)
        

    def update_training_settings(self) -> None:
        if self.last_task == "Habituation":
            df_habituation = self.df[self.df["task"] == "Habituation"]

            if len(df_habituation) >= 1:
                self.settings.next_task = "LickHeadportTeaching"
                self.settings.minimum_duration = 25 * 60  # 25 min for lick teaching
                self.settings.maximum_duration = 45 * 60  # 45 min for lick teaching

        elif self.last_task == "LickHeadportTeaching":
            # Picks last value of lickport distance from the last session and subtracts 3mm for the next session
            df_lickheadportteaching = self.df[self.df["task"] == "LickHeadportTeaching"]
            previous_lickport_distance = df_lickheadportteaching.iloc[-1]["lickport_distance"] if len(df_lickheadportteaching) > 0 else 0.0
            # Below it might not be 3 - not sure what the units are
            self.settings.lickport_distance = max(previous_lickport_distance - 3.0, 0.0)
            
            self.settings.next_task = "LickHeadportTeaching"
            self.settings.minimum_duration = 25 * 60  # 25 min for lick teaching
            self.settings.maximum_duration = 45 * 60  # 45 min for lick teaching

        elif self.last_task == "LickHeadportTeaching":
            # Picks last value of lickport distance from the last session and subtracts 3mm for the next session
            df_lickheadportteaching = self.df[self.df["task"] == "LickHeadportTeaching"]

            # Insert a condition for >30 switches & 15mm lickport distance to move to fixation



    def define_gui_tabs(self) -> None:
        pass

    