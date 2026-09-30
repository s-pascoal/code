from village.custom_classes.task_base import BpodEvent, BpodOutput, TaskBase

class LickTeaching(TaskBase):

    def __init__(self):
        super().__init__()

        self.info = """
Lick Teaching Task
----------------------------------------------------------------
Description
"""

    def start(self):
        self.reward_drunk = 0

        self.valve_l_time = self.calibrations.water_calibration.get_valve_time(
            port = 1, volume = self.settings.water_volume
            )
        self.valve_r_time = self.calibrations.water_calibration.get_valve_time(
            port = 2, volume = self.settings.water_volume
            )
        self.number_of_switches = 0



    def create_trial(self):


        if ((self.current_trial - 1) // 3) % 2 == 0:

            self.bpod.add_state(
                state_name='left_load',
                state_timer=0,
                state_change_conditions={BpodEvent.Tup: 'left_choice'},
                output_actions=[BpodOutput.SoftCode2]
                )

            self.bpod.add_state(
                state_name='left_choice',
                state_timer=0,
                state_change_conditions={BpodEvent.Port1In: 'deliver_left_water'},
                output_actions=[(BpodOutput.PWM1, 255), BpodOutput.SoftCode5]
                )

            self.bpod.add_state(
                state_name='deliver_left_water',
                state_timer = self.valve_l_time,
                state_change_conditions={BpodEvent.Tup: 'reward'},
                output_actions=[BpodOutput.Valve1, BpodOutput.SoftCode6]
                )

            self.bpod.add_state(
                state_name='reward',
                state_timer = 3,
                state_change_conditions={BpodEvent.Tup: 'exit'},
                output_actions=[])

        else:
            self.bpod.add_state(
                state_name='right_choice',
                state_timer=0,
                state_change_conditions={BpodEvent.Port2In},
                output_actions=[(BpodOutput.PWM1, 255), [BpodOutput.SoftCode3]]
                )

            self.bpod.add_state(
                state_name='deliver_right_water',
                state_timer = self.valve_r_time,
                state_change_conditions={BpodEvent.Tup: 'reward'},
                output_actions=[BpodOutput.Valve2]
                )

            self.bpod.add_state(
                state_name='reward',
                state_timer = 3,
                state_change_conditions={BpodEvent.Tup: 'exit'},
                output_actions=[BpodOutput.SoftCode5])



    def after_trial(self):

        self.register_value('water', self.settings.water_volume)
        self.register_value('number_of_switches', self.number_of_switches)


    def close(self):
        pass
    