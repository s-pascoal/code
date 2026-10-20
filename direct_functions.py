from sound_functions import cue_generator, sound_device, whitenoise_generator

from village.custom_classes.direct_functions_base import DirectFunctionsBase
from village.devices.chip import motor_box1, motor_box3


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
            0, 70, "whitenoise"
        )
        left_sound = whitenoise_generator(0.5, left_calibration)
        sound_device.load(left=left_sound, right=None)

    def function3(self):
        """Load right sound"""
        right_calibration = self.task.calibrations.sound_calibration.get_sound_gain(
            1, 70, "whitenoise"
        )
        right_sound = whitenoise_generator(0.5, right_calibration)
        sound_device.load(left=None, right=right_sound)

    def function4(self):
        """Load cue sound"""
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

    # Functions to control the lickport motor (box motor 3), called from the Bpod
    # via softcodes. motor_box3 must be enabled (MOTOR3_BOX in SETTINGS -> BOX
    # SETTINGS) and calibrated (MONITOR -> BOX -> MOTOR3 VALUES): open() and
    # close() go to its calibrated angles, move() to any angle. The moves return
    # immediately and run in the background.
    # self.task.settings are the settings of the running task (the subject's
    # training protocol values); lickport_distance is the value the subject
    # had at the end of its previous session, or the new one set mid-session.

    def function7(self):
        """Retract motor3"""
        motor_box3.close()

    def function8(self):
        """Advance motor3"""
        motor_box3.open()

    def function9(self):
        """Move motor to the current lickport_distance (last value from the previous
        session at trial 1, or the newly stepped value mid-session)."""
        motor_box3.move(round(self.task.settings.lickport_distance))

    def function10(self):
        """Move motor to the initial position."""
        motor_box3.move(round(self.task.settings.lickport_start_distance))

    # Head clamp: motor 1 of the box drives the pistons that fix the head.
    # Called from HeadFixationTeaching via softcodes 11 (fix) and 12 (release).
    # Angles and travel times are calibrated in MONITOR -> BOX -> MOTOR1 VALUES.

    def function11(self):
        """Close head clamp"""
        # hold=True: keep holding torque so the mouse can't push the clamp open
        motor_box1.close(hold=True)

    def function12(self):
        """Open head clamp"""
        motor_box1.open()
