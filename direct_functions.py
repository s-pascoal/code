from sound_functions import sound_device, whitenoise_generator, cue_generator
from village.custom_classes.direct_functions_base import DirectFunctionsBase


class DirectFunctions(DirectFunctionsBase):

    def _load_cue(self, side):
        if side not in self._cue_cache:
            cal = self.task.calibrations.sound_calibration
            gain_noise = [cal.get_sound_gain(ch, 72, "whitenoise") for ch in (0, 1)]
            gain_tone = [cal.get_sound_gain(ch, 72, "tone_3500") for ch in (0, 1)]
            self._cue_cache[side] = cue_generator(side, gain_noise, gain_tone)
        left, right = self._cue_cache[side]
        sound_device.load(left=left, right=right)

    # playing sound from both speakers with constant gain (not calibrated)
    # useful to use from the GUI buttons
    def function1(self):
        """Play Manual Sound"""
        sound = whitenoise_generator(2, 0.05)
        sound_device.load(left=sound, right= sound)
        sound_device.play()


    def function2(self):
        """Load left sound"""
        left_calibration = self.task.calibrations.sound_calibration.get_sound_gain(
            0, 70, "whitenoise") 
        left_sound = whitenoise_generator(0.5, left_calibration)
        sound_device.load(left=left_sound, right=None)

    def function3(self):
        """Load right sound"""
        right_calibration = self.task.calibrations.sound_calibration.get_sound_gain(
            1, 70, "whitenoise")
        right_sound = whitenoise_generator(0.5, right_calibration)
        sound_device.load(left=None, right=right_sound)

    def function4(self):
        """Load cue sound"""
        left_calibration = self.task.calibrations.sound_calibration.get_sound_gain(
                    0, 70, "tone_3500")
        right_calibration = self.task.calibrations.sound_calibration.get_sound_gain(
                    1, 70, "tone_3500")
        left_sound = cue_generator(left_calibration)
        right_sound = cue_generator(right_calibration)
        sound_device.load(left=left_sound, right=right_sound)


    def function5(self):
        """Play loaded sound"""
        sound_device.play()

    def function6(self):
        """Stop sound"""
        sound_device.stop()

    def function7(self):
        """Retract motor3"""
        self.task.motor_box3.close()

    def function8(self):
        """Advance motor3"""
        self.task.motor_box3.open()

    def function9(self):
        """Move motor"""
        self.task.motor_box3.set_position(self.task.settings.motor_position)




