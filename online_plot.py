import matplotlib.pyplot as plt
import pandas as pd

from village.custom_classes.online_plot_base import OnlinePlotBase
from village.scripts.time_utils import time_utils

# Height in the plot of each value written by the triggers (gpio_trigger.py,
# scale_trigger.py)
SWITCH_Y = {"off": 0, "on": 1}
STATE_Y = {"Jumping": 0, "Normal": 1, "Heavy": 2}


class OnlinePlot(OnlinePlotBase):
    """Live view of the switch, the box scale and the lickport, against the
    time since the task started (x axis, growing):

    - the switch, off or on;
    - every reading of the scale, in grams (points);
    - the weight state, Jumping, Normal or Heavy;
    - the lickport position (motor 1 angle, higher = closer).

    The data are collected in the task by gpio_trigger.py and scale_trigger.py
    (switch_log, weight_log, state_log) and by the lickport functions of
    direct_functions.py (lickport_log). The trials can be long, so the plot is
    redrawn every refresh_period seconds, not only when a trial finishes.
    """

    def __init__(self) -> None:
        super().__init__()
        self.refresh_period = 1  # seconds between redraws

    def create_figure_and_axes(self) -> None:
        (
            self.fig,
            (self.ax_switch, self.ax_weight, self.ax_state, self.ax_lickport),
        ) = plt.subplots(4, 1, figsize=(10, 9), sharex=True)

        (self.switch_line,) = self.ax_switch.plot([], [], drawstyle="steps-post")
        self.ax_switch.set_ylim(-0.1, 1.1)
        self.ax_switch.set_yticks(list(SWITCH_Y.values()), list(SWITCH_Y))
        self.ax_switch.set_ylabel("Switch")

        (self.weight_points,) = self.ax_weight.plot([], [], ".", markersize=3)
        self.ax_weight.set_ylabel("Weight (g)")

        (self.state_line,) = self.ax_state.plot([], [], drawstyle="steps-post")
        self.ax_state.set_ylim(-0.2, 2.2)
        self.ax_state.set_yticks(list(STATE_Y.values()), list(STATE_Y))
        self.ax_state.set_ylabel("Weight state")

        (self.lickport_line,) = self.ax_lickport.plot(
            [], [], drawstyle="steps-post", marker="."
        )
        self.ax_lickport.set_ylabel("Lickport (°)\nhigher = closer")
        self.ax_lickport.set_xlabel("Time since the task started (s)")

        self.fig.tight_layout()

    def update_plot(self, df: pd.DataFrame) -> None:
        # Imported here: this file is imported while the manager is being built
        from village.manager import manager

        task = manager.task
        # The lists keep timestamps: the x axis is the seconds since the task
        # started (start_timestamp, set in the task's start()). Nothing to draw
        # before start() has run.
        start = getattr(task, "start_timestamp", None)
        if start is None:
            return
        now = time_utils.now_timestamp() - start

        def logged(name: str) -> list:
            # A copy, as the triggers keep appending from their own threads.
            # Empty if the task doesn't define it: village hides errors in the
            # online plot, so a missing list must not stop the whole plot.
            return list(getattr(task, name, []))

        # (seconds, height) for the step lines: each text becomes its height
        switch_log = [(t - start, SWITCH_Y[v]) for t, v in logged("switch_log")]
        weight_log = [(t - start, w) for t, w in logged("weight_log")]
        state_log = [(t - start, STATE_Y[v]) for t, v in logged("state_log")]
        lickport_log = [(t - start, a) for t, a in logged("lickport_log")]

        # The switch starts off and the weight state Normal (see start())
        self.switch_line.set_data(
            *self.steps(switch_log, now, start_value=SWITCH_Y["off"])
        )
        self.state_line.set_data(
            *self.steps(state_log, now, start_value=STATE_Y["Normal"])
        )

        if weight_log:
            times, weights = zip(*weight_log)
            self.weight_points.set_data(times, weights)
            low, high = min(weights), max(weights)
            margin = max(1.0, 0.1 * (high - low))
            self.ax_weight.set_ylim(low - margin, high + margin)
        else:
            self.weight_points.set_data([], [])

        # Lickport: unknown until the first move of the session (trial 1)
        self.lickport_line.set_data(*self.steps(lickport_log, now))
        if lickport_log:
            angles = [a for _, a in lickport_log]
            self.ax_lickport.set_ylim(min(angles) - 5, max(angles) + 5)

        self.ax_lickport.set_xlim(0, max(now, 10))  # shared by the 4 axes

    @staticmethod
    def steps(
        log: list[tuple[float, int]], now: float, start_value: int | None = None
    ) -> tuple[list[float], list[int]]:
        """(time, value) changes -> the points of a step line that lasts until
        now. With start_value, the line starts at time 0 with that value."""
        times = [t for t, _ in log]
        values = [v for _, v in log]
        if start_value is not None:
            times.insert(0, 0.0)
            values.insert(0, start_value)
        if values:
            times.append(now)
            values.append(values[-1])
        return times, values
