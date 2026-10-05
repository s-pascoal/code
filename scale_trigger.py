from village.custom_classes.scale_trigger_base import ScaleTriggerBase


class ScaleTrigger(ScaleTriggerBase):

    def __init__(self) -> None:
        super().__init__()
        self.period = 0.1  # seconds between readings

    def on_weight(self, weight: float, timestamp: float) -> None:
        """Called after every reading of the box scale.

        Available via self.task:
        - self.task.cam_box      — box camera (write_text, areas, position, …)
        - self.task.bpod         — Bpod controller (send_softcode_to_bpod, …)
        - self.task.gpio         — set_on()/set_off() for the output pin
        - any attribute defined in the task class
        """
        pass
        # if weight > 30:
        #     self.task.register_raspberry_event("Heavy", timestamp)
        #     self.task.cam_box.write_text("Heavy")
        #     self.task.bpod.send_softcode_to_bpod(2)
        # elif weight < 5:
        #     self.task.register_raspberry_event("Jumping", timestamp)
        #     self.task.cam_box.write_text("Jumping")
        # else:
        #     self.task.cam_box.write_text("")
            