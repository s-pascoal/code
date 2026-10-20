from village.custom_classes.task_base import BpodEvent, TaskBase
from village.scripts.time_utils import time_utils


class test_task(TaskBase):

    def __init__(self):
        super().__init__()

        self.info = """
Test Task
----------------------------------------------------------------
Every trial just waits 10 s, with no outputs. Useful to check that the
system runs a Bpod task.
"""

    def start(self):
        # Used by gpio_trigger.py, scale_trigger.py and online_plot.py
        self.start_timestamp = time_utils.now_timestamp()
        self.number_of_switches = 0
        self.switch_on = False
        self.state_weight = "Normal"
        self.scale_weight = 0.0
        self.switch_log = []  # (timestamp, "on" / "off")
        self.weight_log = []  # (timestamp, weight in g)
        self.state_log = []  # (timestamp, "Jumping" / "Normal" / "Heavy")

    def create_trial(self):

        self.bpod.add_state(
            state_name="stay",
            state_timer=10,
            state_change_conditions={BpodEvent.Tup: "exit"},
            output_actions=[],
        )


    def after_trial(self):
        pass

    def close(self):
        pass
