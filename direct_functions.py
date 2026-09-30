from sound_functions import sound_device, whitenoise_generator, cue_generator
from village.custom_classes.direct_functions_base import DirectFunctionsBase


class DirectFunctions(DirectFunctionsBase):

    _cue_cache = {}

    def _load_cue(self, side):
        if side not in self._cue_cache:
            cal = self.task.calibrations.sound_calibration
            gain_noise = [cal.get_sound_gain(ch, 72, "whitenoise") for ch in (0, 1)]
            gain_tone = [cal.get_sound_gain(ch, 72, "tone_3500") for ch in (0, 1)]
            self._cue_cache[side] = cue_generator(side, gain_noise, gain_tone)
        left, right = self._cue_cache[side]
        sound_device.load(left=left, right=right)

    def function1(self):
        """Play Manual Sound"""
        sound = whitenoise_generator(2, 0.05)
        sound_device.load(left=sound, right=sound)
        sound_device.play()

    def function2(self):
        """Load left cue (SIDE + GO)"""
        self._load_cue("left")

    def function3(self):
        """Load right cue (SIDE + GO)"""
        self._load_cue("right")

    def function4(self):
        """Play loaded sound"""
        sound_device.play()

    def function5(self):
        """Stop sound"""
        sound_device.stop()

    def function6(self):
        """Retract motor"""
        # write here the code

    def function7(self):
        """Advance motor"""
        # write here the code




