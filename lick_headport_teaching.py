from village.custom_classes.task_base import BpodEvent, BpodOutput, TaskBase


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



        if self.current_trial == 1:
            self.bpod.add_state(
                state_name="last_position_motor",
                state_timer=1,
                state_change_conditions={BpodEvent.Tup: "load_stim"},
                output_actions=[last_position_softcode],
            )
  

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

        if correct_licks and (not wrong_licks or correct_licks[0] <= wrong_licks[0]):
            outcome = "correct"
            response_side = self.side
            water = self.settings.water_volume
        elif wrong_licks:
            outcome = "incorrect"
            response_side = "right" if self.side == "left" else "left"
            water = 0
        
        else:
            outcome = "miss" # here miss would only be possible 1 time (if the animal never licked at all)
            response_side = "none"
            water = 0

        self.register_value("rewarded_side", self.side)
        self.register_value("water", water)
        self.register_value("outcome", outcome)
        self.register_value("response_side", response_side)

           
        # Filters exclusively on this session - Is there such column? And is this dataset created on the go or only after the session?
        df_lht = self.df[self.df["task"] == "LickPortTeaching"]
        df_lht_session = df_lht.iloc[-1]
        correct_trials = df_lht_session[df_lht_session["outcome"] == "correct"]
        # Uses multiples of 20 to advance lickport every 20 correct, only until reaching 15mm
        if (len(correct_trials) % 20 == 0 and self.settings.lickport_distance >= 15):
            # Picks last value of lickport distance from the last session and subtracts 3mm for the next session
            previous_lickport_distance = df_lht_session["lickport_distance"] if len(df_lht_session) > 0 else 0.0
            new_lickport_distance = previous_lickport_distance - 3.0
            self.settings.lickport_distance = new_lickport_distance
            self.task.motor_box3.set_position(new_lickport_distance)


    def close(self):
        pass
