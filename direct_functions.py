from sound_functions import cue_generator, sound_device, whitenoise_generator

from village.custom_classes.direct_functions_base import DirectFunctionsBase
from village.devices.chip import motor_box1
from village.devices.head_fixed import head_fixed
from village.scripts.time_utils import time_utils

# Electromagnet holding power (%) used when the running task has no
# magnet_power setting, e.g. the GUI button with no task running. The firmware
# caps it at 40.
MAGNET_POWER = 40


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
        self._log_lickport(motor_box1.close_angle)

    def function8(self):
        """Advance lickport"""
        motor_box1.open()
        self._log_lickport(motor_box1.open_angle)

    def function9(self):
        """Move motor to the current lickport_distance (last value from the previous
        session at trial 1, or the newly stepped value mid-session)."""
        self._move_lickport(round(self.task.settings.lickport_distance))

    def function10(self):
        """Move motor to the initial position."""
        self._move_lickport(round(self.task.settings.lickport_start_distance))

    def _move_lickport(self, angle):
        motor_box1.move(angle)
        self._log_lickport(angle)

    def _log_lickport(self, angle):
        # Log (time, angle) for the online plot. lickport_log is defined in the
        # tasks' start(); a task without it is just not logged.
        lickport_log = getattr(self.task, "lickport_log", None)
        if lickport_log is not None:
            lickport_log.append((time_utils.now_timestamp(), angle))

    # Head clamp: the electromagnet of the head-fixed board (connected to the
    # Raspberry Pi by USB; USE_HEAD_FIXED_BOARD in SETTINGS -> HEAD FIXED
    # SETTINGS). Called from the Bpod via softcodes, or from the GUI buttons.
    # Direct functions take no arguments, so the power comes from the task's
    # settings (magnet_power) and is passed to _magnet_down.
    # The commands return immediately: the board does the 200 ms kick, and
    # switches the magnet off by itself after 10 minutes on. With the board OFF
    # or not connected, head_fixed is a NullHeadFixed that does nothing.

    def function11(self):
        """Magnet down (fix head)"""
        power = getattr(self.task.settings, "magnet_power", MAGNET_POWER)
        self._magnet_down(power)

    def function12(self):
        """Magnet up (release head)"""
        head_fixed.magnet_off()
        self.task.register_raspberry_event("MagnetUp", time_utils.now_timestamp())

    def _magnet_down(self, power):
        # Electromagnet on: a 200 ms kick to pull the headbar in, then held at
        # `power` % (0-100; capped at 40 by the firmware; 0 = off).
        head_fixed.magnet(power)
        self.task.register_raspberry_event("MagnetDown", time_utils.now_timestamp())
