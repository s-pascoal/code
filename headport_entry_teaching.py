import math

from village.custom_classes.task_base import BpodEvent, BpodOutput, TaskBase
from village.scripts.time_utils import time_utils


class HeadPortEntryTeaching(TaskBase):

    def __init__(self):
        super().__init__()

        self.info = """
Headport Entry Teaching
----------------------------------------------------------------
Left and right ports alternate in blocks of 3 trials. Each trial loads the
side sound (white noise from the rewarded side), then plays it while the LED
is on and waits for a lick on the rewarded port, which delivers the water.

Softcodes (direct_functions):
2 = load left sound, 3 = load right sound, 5 = play loaded sound,
6 = stop sound
"""

    def start(self):
        self.valve_l_time = self.calibrations.water_calibration.get_valve_time(
            port=1, volume=self.settings.water_volume
        )
        self.valve_r_time = self.calibrations.water_calibration.get_valve_time(
            port=2, volume=self.settings.water_volume
        )
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
        if ((self.current_trial - 1) // 3) % 2 == 0:
            self.bpod.add_state(
                state_name="left_load",
                state_timer=0,
                state_change_conditions={BpodEvent.Tup: "left_choice"},
                output_actions=[BpodOutput.SoftCode2],
            )

            self.bpod.add_state(
                state_name="left_choice",
                state_timer=0,
                state_change_conditions={BpodEvent.Port1In: "deliver_left_water"},
                output_actions=[(BpodOutput.PWM1, 255), BpodOutput.SoftCode5],
            )

            self.bpod.add_state(
                state_name="deliver_left_water",
                state_timer=self.valve_l_time,
                state_change_conditions={BpodEvent.Tup: "reward"},
                output_actions=[BpodOutput.Valve1, BpodOutput.SoftCode6],
            )

        else:
            self.bpod.add_state(
                state_name="right_load",
                state_timer=0,
                state_change_conditions={BpodEvent.Tup: "right_choice"},
                output_actions=[BpodOutput.SoftCode3],
            )

            self.bpod.add_state(
                state_name="right_choice",
                state_timer=0,
                state_change_conditions={BpodEvent.Port2In: "deliver_right_water"},
                output_actions=[(BpodOutput.PWM1, 255), BpodOutput.SoftCode5],
            )

            self.bpod.add_state(
                state_name="deliver_right_water",
                state_timer=self.valve_r_time,
                state_change_conditions={BpodEvent.Tup: "reward"},
                output_actions=[BpodOutput.Valve2, BpodOutput.SoftCode6],
            )

        self.bpod.add_state(
            state_name="reward",
            state_timer=3,
            state_change_conditions={BpodEvent.Tup: "exit"},
            output_actions=[],
        )

    def after_trial(self):
        # With Bpod, a state that was not visited in this trial is still in
        # trial_data, as [nan] -- so check the time, not just the key.
        rewarded = not math.isnan(
            self.trial_data.get("STATE_reward_START", [math.nan])[0]
        )
        water = self.settings.water_volume if rewarded else 0

        self.register_value("water", water)
        self.register_value("number_of_switches", self.number_of_switches)

    def close(self):
        pass
