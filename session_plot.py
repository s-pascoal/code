import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from village.custom_classes.session_plot_base import SessionPlotBase


class SessionPlot(SessionPlotBase):
    ''' 
    Panel	
        1) Left/right licking - Does the animal consistently prefer one port, independently of the rewarded side?
        2) Response latency	- Does the animal begin licking more readily after the auditory cue?
        3) Lickport progression	- Does the lickport retract in the expected steps? When does the switch turn ON?
     
    '''

    def __init__(self) -> None:
        super().__init__()

    def create_plot(
        self,
        df: pd.DataFrame,
        weight: float = 0.0,
        width: float = 10,
        height: float = 9,
    ) -> Figure:

        fig, axes = plt.subplots(3, 1, figsize=(width, height))

        task = str(df["task"].iloc[0]) if "task" in df.columns and len(df) else ""
        n_trials = len(df)

        total_water = (
            float(pd.to_numeric(df["water"], errors="coerce").sum())
            if "water" in df.columns else 0.0
        )

        fig.suptitle(
            f"{task} -- {n_trials} trials, "
            f"{total_water:.2f} µL water, "
            f"weight {weight:.1f} g"
        )

        trial = range(1, n_trials + 1)

        # ==================================================
        # PANEL 1: LEFT / RIGHT LICKING BEHAVIOUR
        # ==================================================

        ax = axes[0]

        if (
            "choice_left_licks" in df.columns
            and "choice_right_licks" in df.columns
            and n_trials
        ):

            left = pd.to_numeric(
                df["choice_left_licks"], errors="coerce"
            )

            right = pd.to_numeric(
                df["choice_right_licks"], errors="coerce"
            )

            ax.plot(
                trial,
                left,
                marker="o",
                markersize=3,
                label="Left licks"
            )

            ax.plot(
                trial,
                right,
                marker="o",
                markersize=3,
                label="Right licks"
            )

            ax.legend()

        else:
            ax.text(
                0.5, 0.5,
                "Licking data unavailable",
                ha="center",
                va="center",
                transform=ax.transAxes
            )

        ax.set_xlabel("Trial")
        ax.set_ylabel("Number of licks")
        ax.set_title("Left / Right licking during choice")
        ax.grid(alpha=0.3)

        # ==================================================
        # PANEL 2: RESPONSE LATENCY
        # ==================================================

        ax = axes[1]

        if "response_latency" in df.columns and n_trials:

            latency = pd.to_numeric(
                df["response_latency"], errors="coerce"
            )

            ax.plot(
                trial,
                latency,
                marker="o",
                linestyle="none",
                markersize=4,
                label="First lick latency"
            )

            ax.legend()

        else:
            ax.text(
                0.5, 0.5,
                "Response latency unavailable",
                ha="center",
                va="center",
                transform=ax.transAxes
            )

        ax.set_xlabel("Trial")
        ax.set_ylabel("Latency (s)")
        ax.set_title("Response latency")
        ax.grid(alpha=0.3)

        # ==================================================
        # PANEL 3: LICKPORT DISTANCE + SWITCH STATUS
        # ==================================================

        ax = axes[2]

        if "lickport_distance" in df.columns and n_trials:

            distance = pd.to_numeric(
                df["lickport_distance"], errors="coerce"
            )

            ax.step(
                trial,
                distance,
                where="post",
                marker=".",
                label="Lickport distance"
            )

            ax.set_ylabel("Lickport distance (degrees)")
            ax.legend(loc="upper left")

        else:
            ax.text(
                0.5, 0.5,
                "Lickport distance unavailable",
                ha="center",
                va="center",
                transform=ax.transAxes
            )

        # Secondary axis: switch ON / OFF

        if "switch_on" in df.columns and n_trials:

            switch = df["switch_on"].map(
                lambda x: (
                    1 if str(x).strip().lower() in ("true", "1")
                    else 0 if str(x).strip().lower() in ("false", "0")
                    else float("nan")
                )
            )

            ax2 = ax.twinx()

            ax2.step(
                trial,
                switch,
                where="post",
                linestyle="--",
                label="Switch ON/OFF"
            )

            ax2.set_ylabel("Switch status")
            ax2.set_yticks([0, 1])
            ax2.set_yticklabels(["OFF", "ON"])

            ax2.legend(loc="upper right")

        ax.set_xlabel("Trial")
        ax.set_title("Lickport progression and switch status")
        ax.grid(alpha=0.3)

        # ==================================================

        fig.tight_layout(rect=[0, 0, 1, 0.96])

        return fig