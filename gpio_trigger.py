from village.custom_classes.gpio_trigger_base import GpioTriggerBase
from village.scripts.time_utils import time_utils


class GpioTrigger(GpioTriggerBase):

    def __init__(self) -> None:
        super().__init__()

    def trigger_on(self) -> None:
        """Called when the input pin goes from OFF to ON.

        Available via self.task:
        - self.task.cam_box      — box camera (write_text, areas, position, …)
        - self.task.bpod         — Bpod controller (send_softcode_to_bpod, …)
        - self.task.gpio         — set_on()/set_off() for the output pin
        - any attribute defined in the task class

        Every task defines number_of_switches, switch_on and switch_log in its
        start().
        """
        timestamp = time_utils.now_timestamp()
        self.task.register_raspberry_event("SwitchOn", timestamp)
        self.task.bpod.send_softcode_to_bpod(1)
        self.task.number_of_switches += 1
        self.task.switch_on = True
        self.task.switch_log.append((timestamp, "on"))

    def trigger_off(self) -> None:
        """Called when the input pin goes from ON to OFF."""
        timestamp = time_utils.now_timestamp()
        self.task.register_raspberry_event("SwitchOff", timestamp)
        self.task.switch_on = False
        self.task.switch_log.append((timestamp, "off"))
