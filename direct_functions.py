from sound_functions import cue_generator, sound_device, whitenoise_generator

from village.custom_classes.direct_functions_base import DirectFunctionsBase
from village.devices.chip import motor_box1
from village.scripts.time_utils import time_utils


class DirectFunctions(DirectFunctionsBase):

    # Sound-related functions, called from the Bpod via softcodes (or from the
    # GUI buttons).

    # playing sound from both speakers with constant gain (not calibrated)
    # useful to use from the GUI buttons
    def function1(self):
        """Play Manual Sound"""
        sound = whitenoise_generator(2, 0.05)
        sound_device.load(left=sound, right=sound)
        sound_device.play()

    def function2(self):
        """Load left sound"""
        left_calibration = self.task.calibrations.sound_calibration.get_sound_gain(
            0, 70, "whitenoise"  # BLANK: 72 dB? 0.4 s?
        )
        left_sound = whitenoise_generator(0.5, left_calibration)
        sound_device.load(left=left_sound, right=None)

    def function3(self):
        """Load right sound"""
        right_calibration = self.task.calibrations.sound_calibration.get_sound_gain(
            1, 70, "whitenoise"  # BLANK: 72 dB? 0.4 s?
        )
        right_sound = whitenoise_generator(0.5, right_calibration)
        sound_device.load(left=None, right=right_sound)

    def function4(self):
        """Load go sound"""
        left_calibration = self.task.calibrations.sound_calibration.get_sound_gain(
            0, 70, "tone_3500"
        )
        right_calibration = self.task.calibrations.sound_calibration.get_sound_gain(
            1, 70, "tone_3500"
        )
        left_sound, right_sound = cue_generator((left_calibration, right_calibration))
        sound_device.load(left=left_sound, right=right_sound)

    def function5(self):
        """Play loaded sound"""
        sound_device.play()

    def function6(self):
        """Stop sound"""
        sound_device.stop()

    # Functions to control the lickport motor (box motor 1: ports towards/away
    # from the animal), called from the Bpod via softcodes. motor_box1 must be
    # enabled (MOTOR1_BOX in SETTINGS -> BOX SETTINGS) and calibrated
    # (MONITOR -> BOX -> MOTOR1 VALUES): open() and close() go to its calibrated
    # angles, move() to any angle. The moves return immediately and run in the
    # background.
    # self.task.settings are the settings of the running task (the subject's
    # training protocol values); lickport_distance is the value the subject
    # had at the end of its previous session, or the new one set mid-session.

    def function7(self):
        """Retract lickport"""
        motor_box1.close()

    def function8(self):
        """Advance lickport"""
        motor_box1.open()

    def function9(self):
        """Move motor to the current lickport_distance (last value from the previous
        session at trial 1, or the newly stepped value mid-session)."""
        self._move_lickport(round(self.task.settings.lickport_distance))

    def function10(self):
        """Move motor to the initial position."""
        self._move_lickport(round(self.task.settings.lickport_start_distance))

    def _move_lickport(self, angle):
        # Move, and log (time, angle) for the online plot. lickport_log is
        # defined in the tasks' start(); a task without it is just not logged.
        motor_box1.move(angle)
        lickport_log = getattr(self.task, "lickport_log", None)
        if lickport_log is not None:
            lickport_log.append((time_utils.now_timestamp(), angle))

    # The head clamp is an electromagnet board, not a servo, so there are no
    # clamp functions here. BLANK: how the board is controlled.
