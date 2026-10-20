from village.custom_classes.task_base import BpodEvent, BpodOutput, TaskBase
from village.scripts.time_utils import time_utils


class Habituation(TaskBase):

    def __init__(self):
        super().__init__()

        self.info = """
Habituation Task
----------------------------------------------------------------
Habituation to the box, no head fixation and no reward. In the first trial the
lickport advances towards the headport; then every trial just waits 10 s.
After one session -> LickHeadportTeaching (see training_protocol.py).

Softcodes (direct_functions):
8 = advance motor3 (lickport)
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

        advance_softcode = BpodOutput.SoftCode8


        if self.current_trial == 1:
            self.bpod.add_state(
                state_name="advance_motor",
                state_timer=1,
                state_change_conditions={BpodEvent.Tup: "stay"},
                output_actions=[advance_softcode],
            )

        self.bpod.add_state(
            state_name="stay",
            state_timer=10,
            state_change_conditions={BpodEvent.Tup: "exit"},
            output_actions=[],
        )


    def after_trial(self):
        self.register_value("water", 0)

    def close(self):
        pass
