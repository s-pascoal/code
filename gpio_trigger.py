from village.custom_classes.gpio_trigger_base import GpioTriggerBase


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
        """
        self.task.cam_box.write_text("Switch triggered")
        self.task.bpod.send_softcode_to_bpod(1)
        self.task.number_of_switches += 1  

    def trigger_off(self) -> None:
        """Called when the input pin goes from ON to OFF."""
        self.task.cam_box.write_text("")