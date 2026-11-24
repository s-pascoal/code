import ast
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.transforms import blended_transform_factory

from village.custom_classes.session_plot_base import SessionPlotBase

GO_ONSET = 0.5  # s after stimulus onset (STIMULUS_DURATION in the tasks)
OUTCOME_COLORS = {"correct": "tab:green", "incorrect": "tab:red", "miss": "tab:gray"}
SIDE_COLORS = {"left": "tab:blue", "right": "tab:orange"}  # stimulus and licks
SWITCH_Y = {"off": 0, "on": 1}  # as in online_plot.py
WATER_STATES = ["STATE_deliver_water_START", "STATE_water_START"]  # valve states
RASTER_WINDOW = (0.0, 5.0)  # s from stimulus onset shown in the lick raster
RASTER_BIN = 0.1  # s, bin of the licks/s histogram
LICK_SIZE = 2.5  # lick marker size
EPOCH_ALPHA = 0.25  # transparency of the epoch bars (stimulus, RT, outcome)


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


def cell(df: pd.DataFrame, column: str, i: int):
    """df[column] of trial i, or nan if the session doesn't have that column."""
    return df[column].iloc[i] if column in df.columns else math.nan


def unavailable(ax, text: str) -> None:
    ax.text(0.5, 0.5, text, ha="center", va="center", transform=ax.transAxes)


def lick_raster(df: pd.DataFrame, axes_raster: dict, axes_rate: dict) -> None:
    """Trial-by-trial lick raster, aligned to stimulus onset, one column per
    rewarded side, with the licks/s of each port below.

    Each column numbers its own trials in order of appearance (no gaps for
    the other side's trials). Each trial is a row: stimulus (color of the
    rewarded side), RT (GO to the
    first lick, dark gray), then the outcome until the end of the trial (green
    correct, red error; a timeout has no first lick, so its RT runs to the end
    of the window). Dots: licks on the left / right port. Black tick: water.
    """
    start, end = RASTER_WINDOW
    bars = {
        side: {"stim": [], "rt": [], "correct": [], "incorrect": []}
        for side in SIDE_COLORS
    }
    licks = {side: {"left": [], "right": []} for side in SIDE_COLORS}  # (t, y)
    water = {side: [] for side in SIDE_COLORS}
    n_side = {side: 0 for side in SIDE_COLORS}

    for i in range(len(df)):
        side = str(cell(df, "rewarded_side", i))
        t_stim = first_timestamp(cell(df, "STATE_play_stim_START", i))
        if side not in SIDE_COLORS or math.isnan(t_stim):
            continue
        n_side[side] += 1
        y = n_side[side]  # this side's trials in order of appearance

        def rel(column):
            return first_timestamp(cell(df, column, i)) - t_stim

        stim_end = rel("STATE_play_stim_END")
        go = rel("STATE_choice_START")
        trial_end = min(rel("TRIAL_END"), end)
        bars[side]["stim"].append((y, 0.0, stim_end))
        trial_licks = {
            port: [t - t_stim for t in timestamps(cell(df, column, i))]
            for port, column in (("left", "Port1In"), ("right", "Port2In"))
        }
        after_go = sorted(t for ts in trial_licks.values() for t in ts if t >= go)
        outcome = str(cell(df, "outcome", i))
        if after_go and outcome in ("correct", "incorrect"):
            response = after_go[0]
            bars[side]["rt"].append((y, go, response))
            bars[side][outcome].append((y, response, trial_end))
        elif not math.isnan(go):
            bars[side]["rt"].append((y, go, end))  # no response in the window
        for port, ts in trial_licks.items():
            licks[side][port] += [(t, y) for t in ts if start <= t <= end]
        water_onset = next(
            (rel(c) for c in WATER_STATES if not math.isnan(rel(c))), math.nan
        )
        if not math.isnan(water_onset):
            water[side].append((water_onset, y))

    # Many trials -> thin rows: smaller dots and ticks, so they stay apart
    n_trials = max(len(df), 1)
    lick_size = min(LICK_SIZE, max(1.0, 300 / n_trials))
    colors = {
        "rt": "dimgray",
        "correct": OUTCOME_COLORS["correct"],
        "incorrect": OUTCOME_COLORS["incorrect"],
    }
    for side, ax in axes_raster.items():
        for kind, rows in bars[side].items():
            rows = [(y, a, b) for y, a, b in rows if not math.isnan(b - a)]
            if rows:
                ys, lefts, rights = zip(*rows, strict=False)
                ax.barh(
                    ys,
                    np.array(rights) - np.array(lefts),
                    left=lefts,
                    height=1.0,  # rows touch: no white gaps between trials
                    color=SIDE_COLORS[side] if kind == "stim" else colors[kind],
                    alpha=EPOCH_ALPHA,
                    antialiased=False,  # crisp row edges, no seams or gaps
                    linewidth=0,
                )
        for port, points in licks[side].items():
            if points:
                ts, ys = zip(*points, strict=False)
                ax.plot(
                    ts,
                    ys,
                    "o",
                    markersize=lick_size,
                    markeredgewidth=0,
                    color=SIDE_COLORS[port],
                )
        if water[side]:
            ts, ys = zip(*water[side], strict=False)
            ax.plot(ts, ys, "|", markersize=lick_size * 1.6, color="black")
        ax.set_title(f"{side.capitalize()} trials ({n_side[side]})")
        ax.set_ylim(0.5, max(n_side[side], 1) + 0.5)
        ax.set_xlim(start, end)

        # Licks/s of each port, over the trials of this side
        rate_ax = axes_rate[side]
        edges = np.arange(start, end + RASTER_BIN, RASTER_BIN)
        for port in SIDE_COLORS:
            ts = [t for t, _ in licks[side][port]]
            counts, _ = np.histogram(ts, bins=edges)
            rate = counts / max(n_side[side], 1) / RASTER_BIN
            rate_ax.stairs(
                rate, edges, color=SIDE_COLORS[port], label=f"{port.capitalize()} port"
            )
        rate_ax.set_xlabel("Time (s) from stimulus onset")


class IntraSessionReport(SessionPlotBase):
    """Intra-session report: what happened within one session.

    1) Lick raster, aligned to stimulus onset, one column for left-rewarded
       and one for right-rewarded trials: each trial is a row with the
       stimulus, the RT (GO -> first lick) and the outcome (correct / error),
       the licks on each port and the water. Below: licks/s of each port.
    2) Switch: headport switch on / off against session time, as in the
       online plot. When does the animal enter the headport, and for how long?
    3) Response latency per trial: stimulus onset -> first lick, coloured by
       outcome. Below the GO line, the animal licked before the GO cue.
       Timeouts are marked at the top. Does the animal respond faster?
    4) Lickport distance per trial (motor 1 angle, higher = closer). Does the
       lickport retract in the expected steps?
    """

    def __init__(self) -> None:
        super().__init__()
        self.name = "Intra-session report"

    def create_plot(
        self,
        df: pd.DataFrame,
        weight: float = 0.0,
        width: float = 10,
        height: float = 9,
    ) -> Figure:
        fig = plt.figure(figsize=(width, height))
        grid = fig.add_gridspec(
            5, 2, height_ratios=[3, 0.9, 0.7, 1.3, 1.1], width_ratios=[1, 1]
        )
        ax_raster_l = fig.add_subplot(grid[0, 0])
        ax_raster_r = fig.add_subplot(grid[0, 1], sharex=ax_raster_l)
        ax_rate_l = fig.add_subplot(grid[1, 0], sharex=ax_raster_l)
        ax_rate_r = fig.add_subplot(grid[1, 1], sharex=ax_raster_l, sharey=ax_rate_l)
        ax_switch = fig.add_subplot(grid[2, :])
        ax_latency = fig.add_subplot(grid[3, :])
        ax_distance = fig.add_subplot(grid[4, :], sharex=ax_latency)
        axes = [
            ax_raster_l,
            ax_raster_r,
            ax_rate_l,
            ax_rate_r,
            ax_switch,
            ax_latency,
            ax_distance,
        ]
        for ax in (ax_raster_l, ax_raster_r, ax_latency):
            ax.tick_params(labelbottom=False)
        ax_rate_r.tick_params(labelleft=False)

        task = str(df["task"].iloc[0]) if "task" in df.columns and len(df) else ""
        n_trials = len(df)
        trial = list(range(1, n_trials + 1))
        total_water = (
            float(pd.to_numeric(df["water"], errors="coerce").sum())
            if "water" in df.columns
            else 0.0
        )
        fig.suptitle(
            f"Intra-session report: {task} -- {n_trials} trials, "
            f"{total_water:.2f} µL water, weight {weight:.1f} g"
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
        # PANEL 1: LICK RASTER (aligned to stimulus onset) + LICKS/S
        # ==================================================
        if {"STATE_play_stim_START", "rewarded_side"} <= set(df.columns):
            lick_raster(
                df,
                {"left": ax_raster_l, "right": ax_raster_r},
                {"left": ax_rate_l, "right": ax_rate_r},
            )
            ax_raster_r.legend(
                handles=[
                    Patch(
                        color=SIDE_COLORS["left"], alpha=EPOCH_ALPHA, label="Left stim."
                    ),
                    Patch(
                        color=SIDE_COLORS["right"],
                        alpha=EPOCH_ALPHA,
                        label="Right stim.",
                    ),
                    Patch(color="dimgray", alpha=EPOCH_ALPHA, label="RT"),
                    Patch(
                        color=OUTCOME_COLORS["correct"],
                        alpha=EPOCH_ALPHA,
                        label="Correct",
                    ),
                    Patch(
                        color=OUTCOME_COLORS["incorrect"],
                        alpha=EPOCH_ALPHA,
                        label="Error",
                    ),
                    Line2D(
                        [],
                        [],
                        ls="",
                        marker="o",
                        markersize=4,
                        color=SIDE_COLORS["left"],
                        label="Left licks",
                    ),
                    Line2D(
                        [],
                        [],
                        ls="",
                        marker="o",
                        markersize=4,
                        color=SIDE_COLORS["right"],
                        label="Right licks",
                    ),
                    Line2D(
                        [],
                        [],
                        ls="",
                        marker="|",
                        markersize=6,
                        color="black",
                        label="Water",
                    ),
                ],
                loc="upper left",
                bbox_to_anchor=(1.01, 1),
                fontsize="small",
            )
            ax_rate_r.legend(
                loc="upper left", bbox_to_anchor=(1.01, 1), fontsize="small"
            )
        else:
            unavailable(ax_raster_l, "Lick raster unavailable")
        ax_raster_l.set_ylabel("Trial (of that side)")
        ax_rate_l.set_ylabel("Licks/s")

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
        ax_switch.set_xlabel("Time since the first trial started (s)")
        ax_switch.set_xlim(0, max(t_end, 1))

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
        ax_distance.set_xlim(0.5, max(n_trials, 1) + 0.5)

        for ax in (ax_switch, ax_latency, ax_distance):
            ax.grid(alpha=0.3)

        fig.tight_layout(rect=[0, 0, 1, 0.96])
        # Histogram right under its raster, no gap: the raster is stretched
        # down to the top of its histogram (it gets the space of the gap)
        for raster, rate in ((ax_raster_l, ax_rate_l), (ax_raster_r, ax_rate_r)):
            box = raster.get_position()
            bottom = rate.get_position().y1
            raster.set_position([box.x0, bottom, box.width, box.y1 - bottom])
        return fig
