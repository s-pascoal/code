from village.custom_classes.task_base import BpodEvent, BpodOutput, TaskBase
from village.scripts.time_utils import time_utils
from sound_functions import sound_device, whitenoise_generator
import math

# Lickport variables
START_ANGLE = 100.0    # motor 1 angle closest to the headport; 
STEP_ANGLE = 21.0      # PLACEHOLDER: degrees that equal 3 mm - 1mm = 7 degrees, 3mm = 21 degrees
FINAL_ANGLE = 50.0     # PLACEHOLDER: degrees that equal 14 mm from the headport
CORRECT_TO_STEP = 20   # how many correct licks 1st attempt to retract lickport
NO_LICK_TIMEOUT = 90   # after how many seconds no lick the motor retracts to previous stage

# GO cue: the LED although only 1 side, this way it doesnt matter to which board its connected
GO_LED = [(BpodOutput.PWM1, 255), (BpodOutput.PWM2, 255)]


class LickHeadportTeaching(TaskBase):

    def __init__(self):
        super().__init__()

        self.info = """
Lick and Headport Teaching Task
----------------------------------------------------------------
The lickport is at the closest position to the headport, no head fixation.
Left and right ports alternate in blocks of 3 trials. Each trial starts with a
side cue (broadband noise, 400 ms, from the rewarded side) followed by a GO cue
(LED). Mice must lick the rewarded port to get water.
Wrong licks are ignored (correction is okay, no punishment), but they restart
the 30 s no-lick timeout.

After 20 rewarded trials, lickport retracts 3mm, until it reached 14mm.

When at 14mm, if the animal gets >30 switch triggers, it moves to the next stage (HeadFixationTeaching).

Softcodes (direct_functions):
5 = play loaded cue
- Sound load comes directly from sound_functions, calibrated in start, and loaded in every trial depending on side

"""

    def start(self):
        self.valve_time = {
            "left": self.calibrations.water_calibration.get_valve_time(
                port=1, volume=self.settings.water_volume
            ),
            "right": self.calibrations.water_calibration.get_valve_time(
                port=2, volume=self.settings.water_volume
            ),
        }

        cal = self.calibrations.sound_calibration
        # BLANK: 0.4 s? 72 dB?
        self.cue = {
            "left": whitenoise_generator(0.5, cal.get_sound_gain(0, 70, "whitenoise")),
            "right": whitenoise_generator(0.5, cal.get_sound_gain(1, 70, "whitenoise")),
        }

        self.correct_count = 0 # correct trials at current lickport distance
        self.move_motor_pending = False
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
        # Define the rewarded side for this trial, each 3 trials switch side.
        # Starts always Left.
        side = "left" if ((self.current_trial - 1) // 3) % 2 == 0 else "right"
        self.side = side

        # LICK TEACHING
        # Events and outputs needed from BPod
        port_in = BpodEvent.Port1In if side == "left" else BpodEvent.Port2In
        wrong_port_in = BpodEvent.Port2In if side == "left" else BpodEvent.Port1In
        valve = BpodOutput.Valve1 if side == "left" else BpodOutput.Valve2

        # Events and outputs needed from Pi-->BPod - SoftCode established in direct_functions
        play_softcode = BpodOutput.SoftCode5
        if side == "left":
            sound_device.load(left=self.cue["left"], right=None)
        else:
            sound_device.load(left=None, right=self.cue["right"])

                # HEADPORT ENTRY TEACHING
        # Events and outputs needed from Pi-->BPod - SoftCode established in direct_functions
        last_position_softcode = BpodOutput.SoftCode9 # lickport motor goes towards last position


        if self.current_trial == 1 or self.move_motor_pending:
            self.bpod.add_state(
                state_name="last_position_motor",
                state_timer=1,
                state_change_conditions={BpodEvent.Tup: "play_stim"},
                output_actions=[last_position_softcode],
            )
            self.move_motor_pending = False

        self.bpod.add_state(
            state_name="play_stim",
            state_timer=0.5,
            state_change_conditions={BpodEvent.Tup: "choice"},
            output_actions=[play_softcode],
        )

        self.bpod.add_state(
            state_name="choice",
            state_timer=NO_LICK_TIMEOUT,
            state_change_conditions={
                port_in: "deliver_water",        # correct port: reward
                wrong_port_in: "wrong_lick",     # wrong port: restart the 30 s clock
                BpodEvent.Tup: "no_lick_timeout" # silence on both ports
            },
            output_actions=GO_LED,
        )

        # A state pointing to itself does not restart its timer in Bpod (it is
        # not a transition), so the wrong lick goes through this 0 s state and
        # back to "choice", which is entered again with a new 30 s timer.
        self.bpod.add_state(
            state_name="wrong_lick",
            state_timer=0,
            state_change_conditions={BpodEvent.Tup: "choice"},
            output_actions=GO_LED,
        )

        self.bpod.add_state(
            state_name="no_lick_timeout",
            state_timer=0,
            state_change_conditions={BpodEvent.Tup: "exit"},
            output_actions=[],
        )

        self.bpod.add_state(
            state_name="deliver_water",
            state_timer=self.valve_time[side],
            state_change_conditions={BpodEvent.Tup: "reward"},
            output_actions=[valve],
        )

        self.bpod.add_state(
            state_name="reward",
            state_timer=3,
            state_change_conditions={BpodEvent.Tup: "exit"},
            output_actions=[],
        )

    def after_trial(self):
        """Register trial outcomes, licking behaviour, response latency
        and lickport progression.
        """

        def get_timestamps(key):
            """Return valid timestamps from a Bpod trial-data field."""
            values = self.trial_data.get(key, [])

            if values is None:
                return []

            if not isinstance(values, (list, tuple)):
                values = [values]

            return [
                float(t) for t in values
                if t is not None and not math.isnan(float(t))
            ]

        def visited(state):
            return bool(get_timestamps(f"STATE_{state}_START"))

        # --------------------------------------------------
        # 1. Auditory cue and lick events
        # --------------------------------------------------

        play_stim_times = get_timestamps("STATE_play_stim_START")
        t_play_stim = play_stim_times[0] if play_stim_times else math.nan

        left_licks = get_timestamps("Port1In")
        right_licks = get_timestamps("Port2In")

        correct_licks = (
            left_licks if self.side == "left" else right_licks
        )
        wrong_licks = (
            right_licks if self.side == "left" else left_licks
        )

        # Only consider licks after auditory cue onset for outcome
        if not math.isnan(t_play_stim):

            correct_licks_after_cue = [
                t for t in correct_licks if t >= t_play_stim
            ]

            wrong_licks_after_cue = [
                t for t in wrong_licks if t >= t_play_stim
            ]

            all_licks_after_cue = sorted(
                correct_licks_after_cue + wrong_licks_after_cue
            )

        else:
            correct_licks_after_cue = []
            wrong_licks_after_cue = []
            all_licks_after_cue = []

        # --------------------------------------------------
        # 2. First lick and outcome
        # --------------------------------------------------

        if correct_licks_after_cue and (
            not wrong_licks_after_cue
            or correct_licks_after_cue[0] <= wrong_licks_after_cue[0]
        ):
            outcome = "correct"
            response_side = self.side

        elif wrong_licks_after_cue:
            outcome = "incorrect"
            response_side = "right" if self.side == "left" else "left"

        else:
            outcome = "miss"
            response_side = "none"

        # --------------------------------------------------
        # 3. Response latency
        # --------------------------------------------------

        response_latency = (
            all_licks_after_cue[0] - t_play_stim
            if all_licks_after_cue
            else math.nan
        )

        # --------------------------------------------------
        # 4. Count left and right licks during choice
        # --------------------------------------------------

        choice_starts = get_timestamps("STATE_choice_START")
        choice_ends = get_timestamps("STATE_choice_END")

        # Each choice entry should have a corresponding exit.
        choice_intervals = list(zip(choice_starts, choice_ends))

        def count_choice_licks(licks):
            return sum(
                1 for lick in licks
                if any(start <= lick <= end
                    for start, end in choice_intervals)
            )

        choice_left_licks = count_choice_licks(left_licks)
        choice_right_licks = count_choice_licks(right_licks)

        # --------------------------------------------------
        # 5. Water delivery
        # --------------------------------------------------

        rewarded = visited("deliver_water")

        water = self.settings.water_volume if rewarded else 0

        # --------------------------------------------------
        # 6. Register trial variables
        # --------------------------------------------------

        self.register_value("rewarded_side", self.side)
        self.register_value("water", water)
        self.register_value("outcome", outcome)
        self.register_value("response_side", response_side)

        self.register_value("response_latency", response_latency)

        self.register_value("choice_left_licks", choice_left_licks)
        self.register_value("choice_right_licks", choice_right_licks)

        # --------------------------------------------------
        # 7. Lickport progression
        # --------------------------------------------------

        distance_during_trial = float(self.settings.lickport_distance)

        timed_out = visited("no_lick_timeout")

        if timed_out:

            # No lick for 90 seconds: move closer to the headport
            if distance_during_trial < START_ANGLE:

                self.settings.lickport_distance = min(
                    distance_during_trial + STEP_ANGLE,
                    START_ANGLE
                )

                self.move_motor_pending = True

            # self.correct_count = 0 # reset correct count after a timeout, so the animal has to get 20 correct trials again to retract the lickport

        elif rewarded:

            # Advance after 20 rewarded trials
            self.correct_count += 1

            if (
                self.correct_count >= CORRECT_TO_STEP
                and distance_during_trial > FINAL_ANGLE
            ):

                self.settings.lickport_distance = max(
                    distance_during_trial - STEP_ANGLE,
                    FINAL_ANGLE
                )

                self.move_motor_pending = True
                self.correct_count = 0

        # --------------------------------------------------
        # 8. Register lickport and switch information
        # --------------------------------------------------

        self.register_value(
            "lickport_distance",
            distance_during_trial
        )

        self.register_value(
            "lickport_distance_next",
            float(self.settings.lickport_distance)
        )

        self.register_value(
            "number_of_switches",
            self.number_of_switches
        )

        self.register_value(
            "switch_on",
            bool(self.switch_on)
        )

    def close(self):
        pass
