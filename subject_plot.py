import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from village.custom_classes.subject_plot_base import SubjectPlotBase

from headfixation_teaching import FINAL_FIXATION
from lick_headport_teaching import FINAL_ANGLE, START_ANGLE

STAGES = [  # pre-training stages, in order (y axis of the stage panel)
    "Habituation",
    "LickHeadportTeaching",
    "HeadFixationTeaching",
]


def per_session(df: pd.DataFrame) -> pd.DataFrame:
    """One row per session, from the subject's trials (df, with the "session"
    column village adds when it joins the session files). Columns a session
    doesn't have (e.g. fixation in LickHeadportTeaching) stay nan."""

    def column(name: str) -> pd.Series:
        if name in df.columns:
            return df[name]
        return pd.Series(float("nan"), index=df.index)

    def number(name: str) -> pd.Series:
        return pd.to_numeric(column(name), errors="coerce")

    trials = pd.DataFrame(
        {
            "session": df["session"],
            "task": column("task").astype(str),
            # date = start of the session, "YYYY-MM-DD HH:MM:SS"
            "day": pd.to_datetime(column("date").astype(str).str[:10], errors="coerce"),
            "distance": number("lickport_distance"),
            "distance_next": number("lickport_distance_next"),
            "fixation": number("fixation_duration"),
            "fixation_next": number("fixation_duration_next"),
        }
    )
    grouped = trials.groupby("session", sort=True)
    sessions = pd.DataFrame(
        {
            "task": grouped["task"].first(),
            "day": grouped["day"].first(),
            # Start = value in the first trial, end = value after the last trial
            "start_angle": grouped["distance"].first(),
            "end_angle": grouped["distance_next"].last(),
            "start_fixation": grouped["fixation"].first(),
            "end_fixation": grouped["fixation_next"].last(),
        }
    )
    # Day number since the first session (D1 = first day; a skipped day shows)
    sessions["day_number"] = (sessions["day"] - sessions["day"].min()).dt.days + 1
    return sessions


def start_end(ax, x, start, end, color: str) -> None:
    """Value at the start (open circle) and end (filled) of each session,
    joined by a line."""
    for xi, s, e in zip(x, start, end, strict=False):
        ax.plot([xi, xi], [s, e], color=color)
    ax.plot(x, start, "o", markerfacecolor="white", color=color, label="start")
    ax.plot(x, end, "o", color=color, label="end")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))


def unavailable(ax, text: str) -> None:
    ax.text(0.5, 0.5, text, ha="center", va="center", transform=ax.transAxes)


class SubjectPlot(SubjectPlotBase):
    """Progress of one subject across sessions. x axis: session number, with
    the day under it (D1 = first day) and a faint line where a new day starts.

    1) Stage: which pre-training task each session was.
    2) Lickport distance (motor 1 angle, higher = closer) at the start and end
       of each session, between START_ANGLE and FINAL_ANGLE.
    3) Head-fixation duration at the start and end of each session, up to
       FINAL_FIXATION (end of pre-training).

    The rest of the data (e.g. outcome and rewarded_side, for side biases) is
    in the subject's CSV for later analysis.
    """

    def __init__(self) -> None:
        super().__init__()

    def create_plot(
        self,
        df: pd.DataFrame,
        summary_df: pd.DataFrame,
        width: float = 10,
        height: float = 8,
    ) -> Figure:
        fig, axes = plt.subplots(3, 1, figsize=(width, height), sharex=True)
        ax_stage, ax_distance, ax_fixation = axes

        subject = (
            str(df["subject"].iloc[0]) if "subject" in df.columns and len(df) else ""
        )
        fig.suptitle(subject)

        if "session" not in df.columns or not len(df):
            for ax in axes:
                unavailable(ax, "No sessions")
            fig.tight_layout(rect=[0, 0, 1, 0.96])
            return fig

        sessions = per_session(df)
        x = list(sessions.index)

        # ==================================================
        # PANEL 1: STAGE
        # ==================================================
        # Known stages in order; any other task goes above them
        stages = STAGES + [t for t in sessions["task"].unique() if t not in STAGES]
        level = [stages.index(task) for task in sessions["task"]]
        ax_stage.plot(x, level, "o-", drawstyle="steps-mid", color="tab:green")
        ax_stage.set_yticks(list(range(len(stages))), stages)
        ax_stage.set_ylim(-0.5, len(stages) - 0.5)
        ax_stage.set_title("Stage")

        # ==================================================
        # PANEL 2: LICKPORT DISTANCE
        # ==================================================
        if sessions["start_angle"].notna().any():
            start_end(
                ax_distance,
                x,
                sessions["start_angle"],
                sessions["end_angle"],
                "tab:blue",
            )
            ax_distance.axhline(START_ANGLE, color="gray", linestyle="--", linewidth=1)
            ax_distance.axhline(
                FINAL_ANGLE, color="tab:red", linestyle="--", linewidth=1
            )
        else:
            unavailable(ax_distance, "No lickport data")
        ax_distance.set_ylabel("Angle (°)\nhigher = closer")
        ax_distance.set_title(
            f"Lickport distance (start {START_ANGLE:g}°, final {FINAL_ANGLE:g}°)"
        )

        # ==================================================
        # PANEL 3: HEAD-FIXATION DURATION
        # ==================================================
        if sessions["start_fixation"].notna().any():
            start_end(
                ax_fixation,
                x,
                sessions["start_fixation"],
                sessions["end_fixation"],
                "tab:purple",
            )
            ax_fixation.axhline(
                FINAL_FIXATION, color="tab:red", linestyle="--", linewidth=1
            )
        else:
            unavailable(ax_fixation, "No head-fixation data")
        ax_fixation.set_ylabel("Fixation (s)")
        ax_fixation.set_title(f"Head-fixation duration (final {FINAL_FIXATION} s)")

        # x axis: session number and day; a faint line where a new day starts
        days = list(sessions["day_number"])
        labels = [
            f"{s}\nD{int(d)}" if pd.notna(d) else str(s)
            for s, d in zip(x, days, strict=False)
        ]
        ax_fixation.set_xticks(x, labels)
        ax_fixation.set_xlabel("Session (D = day)")
        for previous, current, xi in zip(days, days[1:], x[1:], strict=False):
            if previous != current:
                for ax in axes:
                    ax.axvline(xi - 0.5, color="gray", alpha=0.3)
        for ax in axes:
            ax.grid(alpha=0.3, axis="y")

        fig.tight_layout(rect=[0, 0, 1, 0.96])
        return fig
