from village.custom_classes.task_base import BpodEvent, BpodOutput, TaskBase


# Motor movement variables - lickport
step = 3.0
max_distance = 14.0
correct_to_step = 20


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
2 = load left cue, 3 = load right cue, 5 = play loaded cue

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

        self.correct_count = 0 # correct trials at current lickport distance
        self.move_motor_pensing = False

    def create_trial(self):
        # Define the rewarded side for this trial, each 3 trials switch side. 
        # Starts always Left.
        side = "left" if ((self.current_trial - 1) // 3) % 2 == 0 else "right"
        self.side = side

        # LICK TEACHING
        # Events and outputs needed from BPod
        port_in = BpodEvent.Port1In if side == "left" else BpodEvent.Port2In
        valve = BpodOutput.Valve1 if side == "left" else BpodOutput.Valve2
        led = (BpodOutput.PWM1, 255)

        # Events and outputs needed from Pi-->BPod - SoftCode established in direct_functions
        load_softcode = BpodOutput.SoftCode2 if side == "left" else BpodOutput.SoftCode3
        play_softcode = BpodOutput.SoftCode5
        
        # HEADPORT ENTRY TEACHING 
        # Events and outputs needed from Pi-->BPod - SoftCode established in direct_functions
        last_position_softcode = BpodOutput.SoftCode9 # lickport motor goes towards last position
    

        if self.current_trial == 1 or self.move_motor_pending:
            self.bpod.add_state(
                state_name="last_position_motor",
                state_timer=1,
                state_change_conditions={BpodEvent.Tup: "load_stim"},
                output_actions=[last_position_softcode],
            )
            self.move_motor_pending = False
  

        self.bpod.add_state(
            state_name="load_stim",
            state_timer=0,
            state_change_conditions={BpodEvent.Tup: "play_stim"},
            output_actions=[load_softcode],
        )

        self.bpod.add_state(
            state_name="play_stim",
            state_timer=0.5,
            state_change_conditions={BpodEvent.Tup: "choice"},
            output_actions=[play_softcode],
        )

        self.bpod.add_state(
            state_name="choice",
            state_timer=0,
            state_change_conditions={port_in: "deliver_water"},
            output_actions=[led],
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

        correct_key, wrong_key = (
            ("Port1In", "Port2In") if self.side == "left" else ("Port2In", "Port1In")
        )
        correct_licks = [
            t for t in self.trial_data.get(correct_key, [])
        ]
        wrong_licks = [
            t for t in self.trial_data.get(wrong_key, [])
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

        # water depends on whether the valve state was actually reached
        rewarded = len(self.trial_data.get("STATE_deliver_water_START", [])) > 0
        water = self.settings.water_volume if rewarded else 0

        self.register_value("rewarded_side", self.side)
        self.register_value("water", water)
        self.register_value("outcome", outcome)
        self.register_value("response_side", response_side)

        distance_during_trial = float(self.settings.lickport_distance)

        if outcome == "correct":           # first lick on the rewarded side
            self.correct_count += 1
        
        if self.correct_count >= correct_to_step and distance_during_trial < max_distance:
            self.settings.lickport_distance = min(distance_during_trial + step, max_distance) # min (x, cap), can never go above cap
            self.correct_count = 0
            self.move_motor_pending = True  # motor moves at the start of the next trial
        
        self.register_value("lickport_distance", distance_during_trial) # the actual value of this trial
        self.register_value("lickport_distance_next", float(self.settings.lickport_distance)) # next trial value


    def close(self):
        pass
