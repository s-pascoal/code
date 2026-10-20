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

        Every task defines scale_weight, state_weight, weight_log and state_log
        in its start().
        """
        self.task.scale_weight = weight
        self.task.weight_log.append((timestamp, weight))

        if weight > 30 and self.task.state_weight != "Heavy":
            self.task.state_weight = "Heavy"
            self.task.register_raspberry_event("Heavy", timestamp)
            self.task.state_log.append((timestamp, "Heavy"))
            self.task.bpod.send_softcode_to_bpod(2)
        elif weight < 5 and self.task.state_weight != "Jumping":
            self.task.state_weight = "Jumping"
            self.task.register_raspberry_event("Jumping", timestamp)
            self.task.state_log.append((timestamp, "Jumping"))
            self.task.bpod.send_softcode_to_bpod(3)
        elif 5 <= weight <= 30 and self.task.state_weight != "Normal":
            self.task.state_weight = "Normal"
            self.task.register_raspberry_event("Normal", timestamp)
            self.task.state_log.append((timestamp, "Normal"))
            self.task.bpod.send_softcode_to_bpod(4)
