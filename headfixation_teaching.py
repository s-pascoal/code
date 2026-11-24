import math

from sound_functions import whitenoise_generator

from village.custom_classes.task_base import BpodEvent, BpodOutput, TaskBase
from village.devices.sound_device import sound_device
from village.scripts.time_utils import time_utils

# Head clamp: the electromagnet of the head-fixed board, switched by the Pi
# (direct functions 11/12). Off = a spring releases the headbar.
MAGNET_KICK_TIME = 0.2  # s: the board's kick that pulls the headbar in

# Fixation duration
START_FIXATION = 1  # first fixation duration (same as default_training_settings)
FIXATION_STEP = 2  # seconds added to the fixation duration
TIME_UPS_TO_STEP = 20  # time-up releases needed for each step
FINAL_FIXATION = 30  # fixation duration that ends this stage

# Trial structure
STIMULUS_DURATION = 0.5  # white noise from the rewarded side. BLANK: 0.4 s?
STIMULUS_DB = 70
TRIALS_PER_SIDE = 3  # trials before switching side (as in LickHeadportTeaching)

# Softcodes, Raspberry Pi -> Bpod (events the state machine listens to)
HEAD_ENTRY_SOFTCODE = BpodEvent.SoftCode1  # sent by gpio_trigger.py (headport switch)
STRUGGLE_SOFTCODE = BpodEvent.SoftCode2  # scale_trigger.py "Heavy"; BLANK: verify

# Softcodes, Bpod -> Raspberry Pi (direct_functions.py)
PLAY_SOFTCODE = BpodOutput.SoftCode5  # function5: play loaded sound
MAGNET_DOWN_SOFTCODE = BpodOutput.SoftCode11  # function11: magnet on (magnet_power)
MAGNET_UP_SOFTCODE = BpodOutput.SoftCode12  # function12: magnet off

# GO cue: LED on until the response. Both outputs, so it works on either port
GO_LED = [(BpodOutput.PWM1, 255), (BpodOutput.PWM2, 255)]


class HeadFixationTeaching(TaskBase):
    """Stage 3 of pre-training

    One Bpod trial = at most one reward, like LickHeadportTeaching. A fixation
    lasts several trials: the head stays fixed between them and the fixation
    time is tracked in Python (self.fixed, self.fixation_start).

    First trial of a fixation:
        wait_head_entry --SoftCode1 (head entry event)--> fix (SoftCode11:
        the Pi switches the magnet on; the fixation time starts after the
        board's 200 ms kick)
        -> play_stim (stimulus) -> choice (GO cue) -> water -> exit
    Next trials, while still fixed:
        play_stim -> choice -> water -> exit
    As in LickHeadportTeaching, the stimulus is built once per side in
    start() and loaded into the sound device in create_trial, before the
    trial runs; the Bpod only sends the play softcode.
    In every trial, Global Timer 1 is set to the time left in the fixation:
    when it ends -> time_up_release; a struggle -> self_release. Both switch
    the magnet off (SoftCode12) and end the fixation. A new fixation needs a
    new press of the switches (a new SoftCode1), so a mouse that keeps its
    headbar on them after a release is not fixed again.

    The magnet is also switched off in close() and by TaskBase at the end of
    every session, so a session cut off mid-fixation releases the mouse.

    Precision: the fixation clock keeps running in the short gaps between
    trials (after_trial + create_trial + sending the next state machine, a few
    tens of ms), and licks in those gaps are not detected. So a fixation can
    last slightly longer than fixation_duration.

    Board limit: the firmware never keeps the magnet on more than 10 minutes,
    and an off-on less than 5 s apart does not restart that count. If a mouse
    re-enters within 5 s again and again, the board switches the magnet off
    after 10 min in total and refuses to switch it on for 30 s (TIMEOUT and
    ERR LOCKOUT in the events log); this task would not notice.
    """

    def __init__(self):
        super().__init__()

        self.info = """
        Head-Fixation Teaching Task
        ----------------------------------------------------------------
        The mouse presses its headbar against the two switches (-> SoftCode1)
        and the electromagnet of the head-fixed board fixes its head. While fixed: stimulus (white
        noise from the rewarded side), then GO cue (LED, on until the
        response), then a lick on the rewarded port gives water. Left and right alternate every 3 trials.
        Wrong licks are ignored (correction is okay, no punishment).

        Release:
        - Time-up release: fixation_duration has elapsed (starts at 1 s).
        - Self release: the mouse struggles (SoftCode2 from the Pi).

        Every 20 time-up releases, fixation_duration increases by 2 s.
        When fixation_duration > 30 s -> task training.

        Softcodes (direct_functions):
        5 = play loaded sound (stimulus)
        11 = magnet down (power = magnet_power), 12 = magnet up
        - The trial sound is built once per side in start (calibrated), and
          loaded in every trial depending on side
        """

    def start(self):
        """Look up valve times, step the fixation back for warm-up, and reset
        the session variables.

        Required settings (defined in training_protocol.py):
        - self.settings.water_volume: reward volume per correct lick
        - self.settings.fixation_duration: seconds the head stays fixed
          (starts at 1, +2 s every 20 time-ups, -2 s at each session start)
        - self.settings.magnet_power: electromagnet holding power in %
          (read by direct_functions.function11)
        """

        self.valve_time = {
            "left": self.calibrations.water_calibration.get_valve_time(
                port=1, volume=self.settings.water_volume
            ),
            "right": self.calibrations.water_calibration.get_valve_time(
                port=2, volume=self.settings.water_volume
            ),
        }

        # Stimuli, built once per session (calibrated white noise, one side)
        cal = self.calibrations.sound_calibration
        self.stimulus = {
            "left": whitenoise_generator(
                duration=STIMULUS_DURATION,
                gain=cal.get_sound_gain(
                    speaker=0, dB=STIMULUS_DB, sound_name="whitenoise"
                ),
            ),
            "right": whitenoise_generator(
                duration=STIMULUS_DURATION,
                gain=cal.get_sound_gain(
                    speaker=1, dB=STIMULUS_DB, sound_name="whitenoise"
                ),
            ),
        }

        # Warm-up: each session starts one step below where the last one ended,
        # never below the first duration.
        self.settings.fixation_duration = max(
            float(self.settings.fixation_duration) - FIXATION_STEP, START_FIXATION
        )

        # Session-only variables (reset every session)
        self.fixed = False  # True while the head is fixed (across trials)
        self.fixation_start = 0.0  # Raspberry time the magnet kick ended
        self.time_up_count = 0  # time-up releases since the last +2 s step

        # Used by gpio_trigger.py, scale_trigger.py and online_plot.py
        self.start_timestamp = time_utils.now_timestamp()
        self.number_of_switches = 0
        self.switch_on = False
        self.state_weight = "Normal"
        self.scale_weight = 0.0
        self.switch_log = []  # (timestamp, "on" / "off")
        self.switch_log_saved = 0  # switch_log entries already registered
        self.weight_log = []  # (timestamp, weight in g)
        self.state_log = []  # (timestamp, "Jumping" / "Normal" / "Heavy")
        self.lickport_log = []  # (timestamp, motor 1 angle), direct_functions.py

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

        # Load this trial's stimulus now, before the trial runs; play_stim only
        # sends the play softcode.
        if self.side == "left":
            sound_device.load(left=self.stimulus["left"], right=None)
        else:
            sound_device.load(left=None, right=self.stimulus["right"])

        # Ways out of a fixation, valid in every state while the head is fixed.
        release = {
            BpodEvent.GlobalTimer1End: "time_up_release",
            STRUGGLE_SOFTCODE: "self_release",
        }

        # Global Timer 1 = time left in the fixation. Configured here, started
        # by GlobalTimer1Trig in "play_stim": right after "fix" (once the
        # magnet holds) or as the first state of an ongoing fixation.
        self.bpod.set_global_timer(timer_id=1, timer_duration=remaining)

        if not self.fixed:
            # Wait as long as it takes for the head entry (no Tup)
            self.bpod.add_state(
                state_name="wait_head_entry",
                state_timer=0,
                state_change_conditions={HEAD_ENTRY_SOFTCODE: "fix"},
                output_actions=[],
            )

            # The Pi switches the magnet on (function11); wait for the kick
            # that pulls the headbar in.
            self.bpod.add_state(
                state_name="fix",
                state_timer=MAGNET_KICK_TIME,
                state_change_conditions={BpodEvent.Tup: "play_stim", **release},
                output_actions=[MAGNET_DOWN_SOFTCODE],
            )

        # Start global time, play the stimulus; "choice" (GO LED) starts when
        # it ends.
        self.bpod.add_state(
            state_name="play_stim",
            state_timer=STIMULUS_DURATION,
            state_change_conditions={BpodEvent.Tup: "choice", **release},
            output_actions=[PLAY_SOFTCODE, BpodOutput.GlobalTimer1Trig],
        )

        # No Tup: Global Timer 1 (or a struggle) bounds this wait. Wrong-port
        # licks are not listed, so they are ignored (correction is okay).
        self.bpod.add_state(
            state_name="choice",
            state_timer=0,
            state_change_conditions={port_in: "water", **release},
            output_actions=GO_LED,
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
        """Switch the magnet off (function12) and end the trial. No need to
        wait for the spring: the next fixation needs a new head entry."""

        self.bpod.add_state(
            state_name="time_up_release",
            state_timer=0,
            state_change_conditions={BpodEvent.Tup: "exit"},
            output_actions=[MAGNET_UP_SOFTCODE],
        )

        self.bpod.add_state(
            state_name="self_release",
            state_timer=0,
            state_change_conditions={BpodEvent.Tup: "exit"},
            output_actions=[MAGNET_UP_SOFTCODE],
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

        # A new fixation started in this trial: remember when the magnet held
        # the headbar (end of "fix"), the moment Global Timer 1 started.
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

        # Switch changes since the previous trial, for the session plot
        new_changes = self.switch_log[self.switch_log_saved :]
        self.switch_log_saved += len(new_changes)
        self.register_value("switch_changes", new_changes)

    def close(self):
        # Release the mouse even if the session was cut off mid-fixation (no
        # release state ran). TaskBase does it too after close(), as a backup.
        self.head_fixed.magnet_off()
