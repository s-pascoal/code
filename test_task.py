from village.custom_classes.task_base import BpodEvent, BpodOutput, TaskBase


class test_task(TaskBase):

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
2 = load left cue, 3 = load right cue, 4 = play loaded cue
"""

    def start(self):
        pass

    def create_trial(self):

        self.bpod.add_state(
            state_name="stay",
            state_timer=10,
            state_change_conditions={BpodEvent.Tup: "exit"},
            output_actions=[],
        )


    def after_trial(self):
        pass

    def close(self):
        pass