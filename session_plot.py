import ast
import math

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.transforms import blended_transform_factory

from village.custom_classes.session_plot_base import SessionPlotBase

GO_ONSET = 0.5  # s after stimulus onset (STIMULUS_DURATION in the tasks)
OUTCOME_COLORS = {"correct": "tab:green", "incorrect": "tab:red", "miss": "tab:gray"}
SWITCH_Y = {"off": 0, "on": 1}  # as in online_plot.py


def timestamps(cell) -> list[float]:
    """The timestamps in one cell of the session CSV: a list such as
    "[1762851204.12, 1762851206.88]" (read back from the CSV as text), a single
    number, or empty / nan (no event in that trial)."""
    if isinstance(cell, (list, tuple)):
        values = list(cell)
    elif isinstance(cell, str):
        text = cell.strip().strip("[]")
        values = text.split(",") if text else []
    elif isinstance(cell, (int, float)):
        values = [cell]
    else:
        return []
    result = []
    for value in values:
        try:
            t = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isnan(t):
            result.append(t)
    return result


def switch_changes(df: pd.DataFrame) -> list[tuple[float, str]]:
    """Every switch change of the session, (timestamp, "on" / "off"), sorted.

    From the "switch_changes" column that the tasks register in after_trial
    (it includes the changes between trials). Older sessions don't have it:
    then from the SwitchOn / SwitchOff events, which miss the changes between
    trials."""
    changes = []
    if "switch_changes" in df.columns:
        for cell in df["switch_changes"]:
            if isinstance(cell, str):
                try:
                    cell = ast.literal_eval(cell)
                except (ValueError, SyntaxError):
                    continue
            if isinstance(cell, (list, tuple)):
                changes += [(float(t), str(v)) for t, v in cell]
    else:
        for column, value in (("SwitchOn", "on"), ("SwitchOff", "off")):
            if column in df.columns:
                for cell in df[column]:
                    changes += [(t, value) for t in timestamps(cell)]
    return sorted(changes)


def first_timestamp(cell) -> float:
    """First timestamp of a cell, or nan (state not visited)."""
    values = timestamps(cell)
    return values[0] if values else math.nan


def unavailable(ax, text: str) -> None:
    ax.text(0.5, 0.5, text, ha="center", va="center", transform=ax.transAxes)


class SessionPlot(SessionPlotBase):
    """Session summary. The top two panels share a time axis (seconds since
    the first trial started), the bottom two a trial axis:

    1) Licks: every lick as a dot, one row for the left port and one for the
       right one. Does the animal prefer one port?
    2) Switch: headport switch on / off, as in the online plot. When does the
       animal enter the headport, and for how long?
    3) Response latency per trial: stimulus onset -> first lick, coloured by
       outcome. Below the GO line, the animal licked before the GO cue.
       Timeouts are marked at the top. Does the animal respond faster?
    4) Lickport distance per trial (motor 1 angle, higher = closer). Does the
       lickport retract in the expected steps?
    """

    def __init__(self) -> None:
        super().__init__()

    def create_plot(
        self,
        df: pd.DataFrame,
        weight: float = 0.0,
        width: float = 10,
        height: float = 9,
    ) -> Figure:
        fig, axes = plt.subplots(
            4,
            1,
            figsize=(width, height),
            gridspec_kw={"height_ratios": [1, 1, 2, 1.5]},
        )
        ax_licks, ax_switch, ax_latency, ax_distance = axes
        # Time axis for licks + switch, trial axis for latency + distance
        ax_switch.sharex(ax_licks)
        ax_distance.sharex(ax_latency)
        ax_licks.tick_params(labelbottom=False)
        ax_latency.tick_params(labelbottom=False)

        task = str(df["task"].iloc[0]) if "task" in df.columns and len(df) else ""
        n_trials = len(df)
        trial = list(range(1, n_trials + 1))
        total_water = (
            float(pd.to_numeric(df["water"], errors="coerce").sum())
            if "water" in df.columns
            else 0.0
        )
        fig.suptitle(
            f"{task} -- {n_trials} trials, {total_water:.2f} µL water, "
            f"weight {weight:.1f} g"
        )

        # Time zero: start of the first trial. All timestamps (licks, states,
        # switch) are Raspberry times, so they share this zero.
        trial_starts = (
            [first_timestamp(c) for c in df["TRIAL_START"]]
            if "TRIAL_START" in df.columns
            else []
        )
        trial_ends = (
            [first_timestamp(c) for c in df["TRIAL_END"]]
            if "TRIAL_END" in df.columns
            else []
        )
        valid_starts = [t for t in trial_starts if not math.isnan(t)]
        valid_ends = [t for t in trial_ends if not math.isnan(t)]
        if not valid_starts:
            for ax in axes:
                unavailable(ax, "No trial times")
            fig.tight_layout(rect=[0, 0, 1, 0.96])
            return fig
        t0 = min(valid_starts)
        t_end = max(valid_ends + valid_starts) - t0

        # ==================================================
        # PANEL 1: LICKS (one row per port)
        # ==================================================
        rows = []
        for column, label in (("Port1In", "L"), ("Port2In", "R")):
            if column in df.columns:
                licks = [t - t0 for cell in df[column] for t in timestamps(cell)]
                rows.append((label, licks))
        if rows:
            for y, ((_, licks), color) in enumerate(
                zip(rows, ["tab:blue", "tab:orange"], strict=False)
            ):
                ax_licks.plot(
                    licks, [y] * len(licks), ".", markersize=4, color=color
                )
            ax_licks.set_yticks(list(range(len(rows))), [label for label, _ in rows])
            ax_licks.set_ylim(-0.6, len(rows) - 0.4)
        else:
            unavailable(ax_licks, "Licking data unavailable")
        ax_licks.set_ylabel("Licks")
        ax_licks.set_title("Licks (left / right port)")

        # ==================================================
        # PANEL 2: SWITCH ON / OFF
        # ==================================================
        changes = switch_changes(df)
        if changes:
            # Starts off (as in start()) and lasts until the end of the session
            times = [0.0] + [t - t0 for t, _ in changes] + [t_end]
            values = [SWITCH_Y["off"]] + [SWITCH_Y[v] for _, v in changes]
            values.append(values[-1])
            ax_switch.step(times, values, where="post", color="tab:purple")
            ax_switch.fill_between(
                times, values, step="post", alpha=0.3, color="tab:purple"
            )
        elif "switch_changes" in df.columns or "SwitchOn" in df.columns:
            ax_switch.step([0, t_end], [0, 0], where="post", color="tab:purple")
        else:
            unavailable(ax_switch, "Switch data unavailable")
        ax_switch.set_ylim(-0.1, 1.1)
        ax_switch.set_yticks(list(SWITCH_Y.values()), list(SWITCH_Y))
        ax_switch.set_ylabel("Switch")
        ax_switch.set_title("Headport switch")

        # ==================================================
        # PANEL 3: RESPONSE LATENCY
        # ==================================================
        if "response_latency" in df.columns:
            latency = pd.to_numeric(df["response_latency"], errors="coerce")
            x = trial
            outcome = (
                df["outcome"].astype(str)
                if "outcome" in df.columns
                else pd.Series(["miss"] * n_trials)
            )
            for name, color in OUTCOME_COLORS.items():
                mask = (outcome == name).to_numpy()
                ax_latency.scatter(
                    [xi for xi, m in zip(x, mask, strict=False) if m],
                    latency[mask],
                    s=12,
                    color=color,
                    label=name,
                )
            ax_latency.axhline(
                GO_ONSET, color="black", linestyle="--", linewidth=1, label="GO"
            )
            # Timeouts: a mark at the top of the panel, at the trial
            if "STATE_no_lick_timeout_START" in df.columns:
                timeouts = [
                    xi
                    for xi, c in zip(x, df["STATE_no_lick_timeout_START"], strict=False)
                    if not math.isnan(first_timestamp(c))
                ]
                top = blended_transform_factory(
                    ax_latency.transData, ax_latency.transAxes
                )
                ax_latency.plot(
                    timeouts,
                    [0.95] * len(timeouts),
                    "v",
                    color="black",
                    transform=top,
                    label="timeout",
                )
            ax_latency.set_ylim(bottom=0)
            # Outside the panel, so it never hides points or timeout marks
            ax_latency.legend(
                loc="upper left", bbox_to_anchor=(1.01, 1), fontsize="small"
            )
        else:
            unavailable(ax_latency, "Response latency unavailable")
        ax_latency.set_ylabel("Latency (s)")
        ax_latency.set_title("Response latency (stimulus onset -> first lick)")

        # ==================================================
        # PANEL 4: LICKPORT DISTANCE
        # ==================================================
        if "lickport_distance" in df.columns:
            distance = pd.to_numeric(df["lickport_distance"], errors="coerce")
            ax_distance.step(trial, distance, where="mid", marker=".")
        else:
            unavailable(ax_distance, "Lickport distance unavailable")
        ax_distance.set_ylabel("Angle (°)\nhigher = closer")
        ax_distance.set_title("Lickport distance (motor 1)")
        ax_distance.set_xlabel("Trial")
        ax_switch.set_xlabel("Time since the first trial started (s)")

        for ax in axes:
            ax.grid(alpha=0.3)
        ax_switch.set_xlim(0, max(t_end, 1))
        ax_distance.set_xlim(0.5, max(n_trials, 1) + 0.5)

        fig.tight_layout(rect=[0, 0, 1, 0.96])
        return fig
