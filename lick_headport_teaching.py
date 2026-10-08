from village.custom_classes.task_base import BpodEvent, BpodOutput, TaskBase
from sound_functions import sound_device, whitenoise_generator
import math

# Lickport variables
START_ANGLE = 60.0     # open angle = closest to the headport (training start)
STEP_ANGLE = 5.0       # PLACEHOLDER: degrees that equal 3 mm 
FINAL_ANGLE = 20.0     # PLACEHOLDER: degrees that equal 14 mm from the headport
CORRECT_TO_STEP = 20   # how many correct licks 1st attempt to retract lickport
NO_LICK_TIMEOUT = 30   # after how many seconds no lick the motor retracts to previous stage


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
Wrong licks are ignored (correction is okay, no punishment).

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
        self.cue = {
            "left": whitenoise_generator(0.5, cal.get_sound_gain(0, 70, "whitenoise")),
            "right": whitenoise_generator(0.5, cal.get_sound_gain(1, 70, "whitenoise")),
        }

        self.correct_count = 0 # correct trials at current lickport distance
        self.move_motor_pending = False

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
        led = (BpodOutput.PWM1, 255)

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
                wrong_port_in: "choice",         # wrong port: restart the 30 s clock
                BpodEvent.Tup: "no_lick_timeout" # silence on both ports
            },
            output_actions=[led],
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
        """Work out response_side and outcome for this trial.
        Whichever side the animal poked first (if any) after the side sound
        turned on determines the outcome
        """
        play_stim_start = self.trial_data.get("STATE_play_stim_START")
        t_play_stim = play_stim_start[0]
        
        correct_key, wrong_key = (
            ("Port1In", "Port2In") if self.side == "left" else ("Port2In", "Port1In")
        )
        correct_licks = [
            t for t in self.trial_data.get(correct_key, []) if t >= t_play_stim
        ]
        wrong_licks = [
            t for t in self.trial_data.get(wrong_key, []) if t >= t_play_stim
        ]

        # outcome stays based on the FIRST lick (this is what drives the 20-correct counter)
        if correct_licks and (not wrong_licks or correct_licks[0] <= wrong_licks[0]):
            outcome = "correct"
            response_side = self.side
        elif wrong_licks:
            outcome = "incorrect"
            response_side = "right" if self.side == "left" else "left"
        else:
            outcome = "miss"
            response_side = "none"

        def visited(state):
            # With Bpod, a state that was not visited in this trial is still in
            # trial_data, as [nan] -- so check the time, not just the key.
            return not math.isnan(
                self.trial_data.get(f"STATE_{state}_START", [math.nan])[0]
            )
        # water depends on whether the valve state was actually reached
        rewarded = visited("deliver_water")
        water = self.settings.water_volume if rewarded else 0

        self.register_value("rewarded_side", self.side)
        self.register_value("water", water)
        self.register_value("outcome", outcome)
        self.register_value("response_side", response_side)

        distance_during_trial = float(self.settings.lickport_distance)
        timed_out = visited("no_lick_timeout")
        
        if timed_out:
            # no lick for 30 s: make it easier, advance toward the window
            if distance_during_trial < START_ANGLE:
                self.settings.lickport_distance = min(distance_during_trial + STEP_ANGLE, START_ANGLE)
                self.move_motor_pending = True
            self.correct_count = 0

        
        # HERE CHOOSE WHICH CONDITION IS BEST!
        
        elif rewarded:            # After every rewarded trial independent of 1st licking
            self.correct_count += 1
            if self.correct_count >= CORRECT_TO_STEP and distance_during_trial > FINAL_ANGLE:
                self.settings.lickport_distance = max(distance_during_trial - STEP_ANGLE, FINAL_ANGLE)
                self.move_motor_pending = True
                self.correct_count = 0
        
        '''
       
        elif outcome == "correct": # After every 20 correct 1st licks 
            self.correct_count += 1
            if self.correct_count >= CORRECT_TO_STEP and distance_during_trial > FINAL_ANGLE:
                # 20 correct: make it harder, retract away from the window
                self.settings.lickport_distance = max(distance_during_trial - STEP_ANGLE, FINAL_ANGLE)
                self.move_motor_pending = True
                self.correct_count = 0

        '''
        
        self.register_value("lickport_distance", distance_during_trial)
        self.register_value("lickport_distance_next", float(self.settings.lickport_distance))

    def close(self):
        pass
