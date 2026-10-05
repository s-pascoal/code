from village.custom_classes.task_base import BpodEvent, BpodOutput, TaskBase


class LickTeaching(TaskBase):

    def __init__(self):
        super().__init__()

        self.info = """
Lick Teaching Task
----------------------------------------------------------------
The lickport is at the closest position to the headport, no head fixation.
Left and right ports alternate in blocks of 3 trials. Each trial starts with a
side cue (broadband noise, 400 ms, from the rewarded side) followed by a GO tone
(3.5 kHz, 0.1 s, both speakers). Mice must lick the rewarded port to get water.
Wrong licks are ignored (correction is okay, no punishment).
The stage ends after 20 rewarded trials -> HeadportEntryTeaching.

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
        side = "left" if ((self.current_trial - 1) // 3) % 2 == 0 else "right"
        self.side = side

        port_in = BpodEvent.Port1In if side == "left" else BpodEvent.Port2In
        valve = BpodOutput.Valve1 if side == "left" else BpodOutput.Valve2
        led = (BpodOutput.PWM1, 255)
        load_softcode = BpodOutput.SoftCode2 if side == "left" else BpodOutput.SoftCode3
        play_softcode = BpodOutput.SoftCode5
        advance_softcode = BpodOutput.SoftCode8 # lickport motor advance towards headport


        if self.current_trial == 1:
            self.bpod.add_state(
                state_name="advance_motor",
                state_timer=1,
                state_change_conditions={BpodEvent.Tup: "load_stim"},
                output_actions=[advance_softcode],
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

        # I dont think this applies to lick teaching, but I will leave it here for now
        # side_led_on_start = self.trial_data.get("STATE_side_led_on_START")
        # if not side_led_on_start:
        #     # The center poke never happened -> side LED never turned on.
        #     self.register_value("rewarded_side", self.side)
        #     self.register_value("water", 0)
        #     self.register_value("outcome", "omission")
        #     self.register_value("response_side", "none")
        #     return

        # t_side_led_on = side_led_on_start[0]

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

    def close(self):
        pass

    def close(self):
        pass