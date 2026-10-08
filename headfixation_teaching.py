import math

from sound_functions import whitenoise_generator

from village.custom_classes.task_base import BpodEvent, BpodOutput, TaskBase, TaskError
from village.devices.sound_device import sound_device
from village.scripts.time_utils import time_utils

# Head entry / fixation
CLAMP_TRAVEL_TIME = None  # BLANK: seconds the clamp servo needs to close/open
START_FIXATION = 1  # first fixation duration (same as default_training_settings)
FIXATION_STEP = 2  # seconds added to the fixation duration
TIME_UPS_TO_STEP = 20  # time-up releases needed for each step
FINAL_FIXATION = 30  # fixation duration that ends this stage

# Trial structure
SIDE_SOUND_DURATION = 0.5  # or 0.4s?
SIDE_SOUND_DB = 70  # same as LickHeadportTeaching (diagram legend says 72 dB)
TRIALS_PER_SIDE = 3  # trials before switching side (as in LickHeadportTeaching)

# Softcodes, Raspberry Pi -> Bpod (events the state machine listens to)
HEAD_ENTRY_SOFTCODE = BpodEvent.SoftCode1  # sent by gpio_trigger.py (headport switch)
STRUGGLE_SOFTCODE = BpodEvent.SoftCode2  # BLANK: no detector sends this yet

# Softcodes, Bpod -> Raspberry Pi (direct_functions.py)
PLAY_SOFTCODE = BpodOutput.SoftCode5  # function5: play loaded sound
CLAMP_CLOSE_SOFTCODE = BpodOutput.SoftCode11  # BLANK: function11 not written yet
CLAMP_OPEN_SOFTCODE = BpodOutput.SoftCode12  # BLANK: function12 not written yet

# GO cue
GO_LED = None  # BLANK: which LED is GO, e.g. (BpodOutput.PWM1, 255)?


class HeadFixationTeaching(TaskBase):
    """Stage 3 of pre-training 

    One Bpod trial = at most one reward, like LickHeadportTeaching. A fixation
    lasts several trials: the clamp stays closed between them and the fixation
    time is tracked in Python (self.fixed, self.fixation_start).

    First trial of a fixation:
        wait_head_entry --SoftCode1 (head entry event)--> fix (clamp closes;
        the fixation time starts once it has finished closing)
        -> play_stim -> choice -> water -> exit
    Next trials, while still fixed:
        play_stim -> choice -> water -> exit
    As in LickHeadportTeaching, the side cue is built once in start() and
    loaded into the sound device in create_trial, before the trial runs; the
    Bpod only sends the play softcode.
    In every trial, Global Timer 1 is set to the time left in the fixation:
    when it ends -> time_up_release; a struggle -> self_release. Both open the
    clamp and end the fixation.

    Precision: the fixation clock keeps running in the short gaps between
    trials (after_trial + create_trial + sending the next state machine, a few
    tens of ms), and licks in those gaps are not detected. So a fixation can
    last slightly longer than fixation_duration. 
    """

    def __init__(self):
        super().__init__()

        self.info = """
        Head-Fixation Teaching Task
        ----------------------------------------------------------------
        The mouse enters the headport (switch -> SoftCode1) and its head is
        fixed. While fixed: side cue (white noise from the rewarded side) and GO
        cue (LED), then a lick on the rewarded port gives water. Left and right
        alternate every 3 trials. Wrong licks are ignored (correction
        is okay, no punishment).

        Release:
        - Time-up release: fixation_duration has elapsed (starts at 1 s).
        - Self release: the mouse struggles (SoftCode2 from the Pi).

        Every 20 time-up releases, fixation_duration increases by 2 s.
        When fixation_duration > 30 s -> task training.

        Softcodes (direct_functions):
        5 = play loaded cue, 11 = close clamp, 12 = open clamp
        - Sound load comes directly from sound_functions, calibrated in start,
          and loaded in every trial depending on side
        """

    def start(self):
        """Look up valve times, step the fixation back for warm-up, and reset
        the session variables.

        Required settings (defined in training_protocol.py):
        - self.settings.water_volume: reward volume per correct lick
        - self.settings.fixation_duration: seconds the head stays fixed
          (starts at 1, +2 s every 20 time-ups, -2 s at each session start)
        """

        blanks = {
            "CLAMP_TRAVEL_TIME": CLAMP_TRAVEL_TIME,
            "GO_LED": GO_LED,
        }
        missing = [name for name, value in blanks.items() if value is None]
        if missing:
            raise TaskError(
                "HeadFixationTeaching draft: fill in " + ", ".join(missing)
            )

        self.valve_time = {
            "left": self.calibrations.water_calibration.get_valve_time(
                port=1, volume=self.settings.water_volume
            ),
            "right": self.calibrations.water_calibration.get_valve_time(
                port=2, volume=self.settings.water_volume
            ),
        }

        # Side cues, built once per session (calibrated white noise, one side)
        cal = self.calibrations.sound_calibration
        self.cue = {
            "left": whitenoise_generator(
                duration=SIDE_SOUND_DURATION,
                gain=cal.get_sound_gain(
                    speaker=0, dB=SIDE_SOUND_DB, sound_name="whitenoise"
                ),
            ),
            "right": whitenoise_generator(
                duration=SIDE_SOUND_DURATION,
                gain=cal.get_sound_gain(
                    speaker=1, dB=SIDE_SOUND_DB, sound_name="whitenoise"
                ),
            ),
        }

        # Warm-up: each session starts one step below where the last one ended,
        # never below the first duration.
        self.settings.fixation_duration = max(
            float(self.settings.fixation_duration) - FIXATION_STEP, START_FIXATION
        )

        # Session-only variables (reset every session)
        self.fixed = False  # True while the clamp is closed (across trials)
        self.fixation_start = 0.0  # Raspberry time the clamp closed
        self.time_up_count = 0  # time-up releases since the last +2 s step
        self.number_of_switches = 0  # incremented by gpio_trigger.py

    def create_trial(self):
        # Rewarded side starts always left, switches every 3 trials
        block = (self.current_trial - 1) // TRIALS_PER_SIDE
        self.side = "left" if block % 2 == 0 else "right"
        port_in = BpodEvent.Port1In if self.side == "left" else BpodEvent.Port2In
        valve = BpodOutput.Valve1 if self.side == "left" else BpodOutput.Valve2

        fixation = float(self.settings.fixation_duration)
        if self.fixed:
            # Time left in this fixation. `elapsed` includes the pause between trials
            elapsed = time_utils.now_timestamp() - self.fixation_start
            remaining = fixation - elapsed
        else:
            remaining = fixation

        # The fixation already ran out during the gap: just release.
        if self.fixed and remaining <= 0:
            self.bpod.add_state(
                state_name="release_now",
                state_timer=0,
                state_change_conditions={BpodEvent.Tup: "time_up_release"},
                output_actions=[],
            )
            self.add_release_states()
            return

        # Load this trial's side cue now, before the trial runs; play_stim only
        # sends the play softcode.
        if self.side == "left":
            sound_device.load(left=self.cue["left"], right=None)
        else:
            sound_device.load(left=None, right=self.cue["right"])

        # Ways out of a fixation, valid in every state while the head is fixed.
        release = {
            BpodEvent.GlobalTimer1End: "time_up_release",
            STRUGGLE_SOFTCODE: "self_release",
        }

        # Global Timer 1 = time left in the fixation. Configured here, started
        # by GlobalTimer1Trig in "play_stim": right after "fix" (once the clamp
        # has finished closing) or as the first state of an ongoing fixation.
        self.bpod.set_global_timer(timer_id=1, timer_duration=remaining)

        if not self.fixed:
            # Wait as long as it takes for the head entry (no Tup)
            self.bpod.add_state(
                state_name="wait_head_entry",
                state_timer=0,
                state_change_conditions={HEAD_ENTRY_SOFTCODE: "fix"},
                output_actions=[],
            )

            # Close the clamp and wait for it to finish closing. The fixation
            # time only starts after this (GlobalTimer1Trig is in play_stim).
            self.bpod.add_state(
                state_name="fix",
                state_timer=CLAMP_TRAVEL_TIME,
                state_change_conditions={BpodEvent.Tup: "play_stim", **release},
                output_actions=[CLAMP_CLOSE_SOFTCODE],
            )

        self.bpod.add_state(
            state_name="play_stim",
            state_timer=SIDE_SOUND_DURATION,
            state_change_conditions={BpodEvent.Tup: "choice", **release},
            output_actions=[PLAY_SOFTCODE, BpodOutput.GlobalTimer1Trig],
        )

        # No Tup: Global Timer 1 (or a struggle) bounds this wait. Wrong-port
        # licks are not listed, so they are ignored (correction is okay).
        self.bpod.add_state(
            state_name="choice",
            state_timer=0,
            state_change_conditions={port_in: "water", **release},
            output_actions=[GO_LED],
        )

        # Still fixed after the water: the trial ends here and the next one
        # continues the same fixation.
        self.bpod.add_state(
            state_name="water",
            state_timer=self.valve_time[self.side],
            state_change_conditions={BpodEvent.Tup: "exit", **release},
            output_actions=[valve],
        )

        self.add_release_states()

    def add_release_states(self):
        """Open the clamp and give it time to travel, then end the trial."""

        self.bpod.add_state(
            state_name="time_up_release",
            state_timer=CLAMP_TRAVEL_TIME,
            state_change_conditions={BpodEvent.Tup: "exit"},
            output_actions=[CLAMP_OPEN_SOFTCODE],
        )

        self.bpod.add_state(
            state_name="self_release",
            state_timer=CLAMP_TRAVEL_TIME,
            state_change_conditions={BpodEvent.Tup: "exit"},
            output_actions=[CLAMP_OPEN_SOFTCODE],
        )

    def after_trial(self):
        """Work out whether this trial was rewarded and whether the fixation
        ended, and update fixation_duration."""

        def visited(state):
            # With Bpod, a state that was not visited in this trial is still in
            # trial_data, as [nan] -- so check the time, not just the key.
            return not math.isnan(
                self.trial_data.get(f"STATE_{state}_START", [math.nan])[0]
            )

        rewarded = visited("water")

        # A new fixation started in this trial: remember when the clamp had
        # finished closing (end of "fix"), the moment Global Timer 1 started.
        if visited("fix"):
            self.fixed = True
            self.fixation_start = self.trial_data["STATE_fix_END"][0]

        fixation_during_trial = float(self.settings.fixation_duration)

        if visited("time_up_release"):
            release = "time_up"
            self.fixed = False
            self.time_up_count += 1
            if self.time_up_count >= TIME_UPS_TO_STEP:
                self.settings.fixation_duration = fixation_during_trial + FIXATION_STEP
                self.time_up_count = 0
        elif visited("self_release"):
            release = "self_release"
            self.fixed = False
        else:
            release = "none"  # still fixed, the next trial continues

        self.register_value("rewarded_side", self.side)
        self.register_value("water", self.settings.water_volume if rewarded else 0)
        self.register_value("rewarded", rewarded)
        self.register_value("release", release)
        self.register_value("fixation_duration", fixation_during_trial)
        self.register_value(
            "fixation_duration_next", float(self.settings.fixation_duration)
        )
        self.register_value("time_up_count", self.time_up_count)
        self.register_value("number_of_switches", self.number_of_switches)

    def close(self):
        # BLANK: always open the clamp at the end, even if the session is cut off
        # mid-fixation. Needs the clamp motor, e.g.
        # from village.devices.chip import motor_box4  (which motor index?)
        # motor_box4.open()
        pass


# To add to direct_functions.py once the clamp motor is known (BLANK):
#
# from village.devices.chip import motor_box4  # BLANK: clamp motor index
#
#     def function11(self):
#         """Close head clamp"""
#         motor_box4.close(hold=True)
#
#     def function12(self):
#         """Open head clamp"""
#         motor_box4.open()
#
# And in training_protocol.py:
# - update_training_settings: LickHeadportTeaching -> HeadFixationTeaching
#   (lickport at FINAL_ANGLE and >30 switches), and HeadFixationTeaching ->
#   BLANK task name when fixation_duration > FINAL_FIXATION.
