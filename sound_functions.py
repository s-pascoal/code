import numpy as np

from village.devices.sound_device import sound_device


# generators of sounds, must return numpy arrays
def tone_generator(
    duration: float,
    gain: float,
    frequency: int,
) -> np.ndarray:
    """
    Generate a single tone
    Args:
        duration (float): Duration (seconds)
        gain (float): Tone amplitude
        frequency (int): Tone frequency
    Returns:
        np.ndarray: Generated sound
    """

    samplerate = sound_device.samplerate

    time = np.linspace(0, duration, int(samplerate * duration))
    # If no frequency specified, return zero array
    if frequency == 0:
        return np.zeros_like(time)
    # Generate tone
    tone = gain * np.sin(2 * np.pi * frequency * time)
    return tone


def whitenoise_generator(
    duration: float,
    gain: float,
) -> np.ndarray:
    """
    Generate white noise
    Args:
        duration (float): Duration (seconds)
        gain (float): Noise amplitude
    Returns:
        np.ndarray: Generated sound
    """

    samplerate = sound_device.samplerate

    time = np.linspace(0, duration, int(samplerate * duration))
    # Generate noise
    noise = gain * np.random.uniform(-1, 1, int(samplerate * duration))
    return noise


# calibration sounds, the only arguments are duration and gain
def whitenoise(duration: float, gain: float) -> np.ndarray:
    return whitenoise_generator(duration=duration, gain=gain)


def tone_600(duration: float, gain: float) -> np.ndarray:
    return tone_generator(duration=duration, gain=gain, frequency=600)


def tone_1000(duration: float, gain: float) -> np.ndarray:
    return tone_generator(duration=duration, gain=gain, frequency=1000)


def tone_3500(duration: float, gain: float) -> np.ndarray:
    return tone_generator(duration=duration, gain=gain, frequency=3500)


def tone_5000(duration: float, gain: float) -> np.ndarray:
    return tone_generator(duration=duration, gain=gain, frequency=5000)


def tone_10000(duration: float, gain: float) -> np.ndarray:
    return tone_generator(duration=duration, gain=gain, frequency=10000)


def tone_20000(duration: float, gain: float) -> np.ndarray:
    return tone_generator(duration=duration, gain=gain, frequency=20000)

def ramp(x, ms=5):
    n = int(sound_device.samplerate * ms / 1000)
    w = np.ones_like(x)
    w[:n] = 0.5 * (1 - np.cos(np.pi * np.arange(n) / n))
    w[-n:] = w[:n][::-1]
    return x * w

def side_generator(side, gain_noise):
    # gain_noise: (left, right) calibrated gains; noise only on the cued side
    noise = ramp(whitenoise_generator(0.4, 1))
    silence = np.zeros_like(noise)
    if side == "left":
        return gain_noise[0] * noise, silence
    return silence, gain_noise[1] * noise


def cue_generator(gain_tone):
    tone = ramp(tone_generator(0.1, 1, 3500))
    return gain_tone[0] * tone, gain_tone[1] * tone


sound_calibration_functions = [
    whitenoise,
    tone_600,
    tone_1000,
    tone_3500,
    tone_5000,
    tone_10000,
    tone_20000,
]











    









