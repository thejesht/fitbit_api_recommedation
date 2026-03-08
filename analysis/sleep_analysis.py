"""
Sleep Analysis — Last 30 Days
Data Analyst view of daily_sleep from fitbit_data.db

Produces three charts saved to ../output/:
  1. time_in_bed.png        — nightly time in bed vs 8-hour target
  2. sleep_efficiency.png   — efficiency line with 7-day rolling average
  3. wake_minutes.png       — nightly wake minutes with severity bands
"""

import sqlite3
import os
import warnings
warnings.filterwarnings("ignore")

from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D

import numpy as np
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH    = os.path.join(BASE_DIR, "fitbit_data.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Style ──────────────────────────────────────────────────────────────────────
BRAND_BLUE    = "#1A73E8"
BRAND_TEAL    = "#00BFA5"
BRAND_ORANGE  = "#FF6D00"
BRAND_RED     = "#E53935"
BRAND_PURPLE  = "#7B1FA2"
GREY_BG       = "#F8F9FA"
GREY_GRID     = "#E0E0E0"
GREY_TEXT     = "#5F6368"
DARK_TEXT     = "#202124"

plt.rcParams.update({
    "font.family":       "sans-serif",
    "font.size":         11,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.facecolor":    GREY_BG,
    "figure.facecolor":  "white",
    "axes.grid":         True,
    "grid.color":        GREY_GRID,
    "grid.linewidth":    0.8,
    "axes.labelcolor":   GREY_TEXT,
    "xtick.color":       GREY_TEXT,
    "ytick.color":       GREY_TEXT,
})

# ── Data ───────────────────────────────────────────────────────────────────────

def load_sleep_data(days: int = 30) -> list[dict]:
    cutoff = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn   = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT date, time_in_bed, minutes_asleep, minutes_awake,
               efficiency, deep_minutes, rem_minutes, light_minutes, wake_minutes
        FROM daily_sleep
        WHERE date >= ?
        ORDER BY date
    """, (cutoff,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_full_date_range(records: list[dict], days: int = 30) -> tuple:
    """
    Build a complete 30-day date axis.
    Days where the watch wasn't worn are represented as NaN so line plots
    show gaps rather than false continuity.
    """
    today    = date.today()
    all_dates = [(today - timedelta(days=days - 1 - i)) for i in range(days)]
    lookup   = {r["date"]: r for r in records}

    dates, tib, efficiency, wake = [], [], [], []
    for d in all_dates:
        ds = d.strftime("%Y-%m-%d")
        dates.append(d)
        if ds in lookup:
            r = lookup[ds]
            tib.append(r["time_in_bed"] / 60.0)          # convert to hours
            efficiency.append(r["efficiency"])
            wake.append(r["wake_minutes"])
        else:
            tib.append(np.nan)
            efficiency.append(np.nan)
            wake.append(np.nan)

    return (
        dates,
        np.array(tib,        dtype=float),
        np.array(efficiency, dtype=float),
        np.array(wake,       dtype=float),
    )


def _add_stat_box(ax, lines: list[str], x=0.02, y=0.97):
    """Add a small stats annotation box inside the axes."""
    text = "\n".join(lines)
    ax.text(x, y, text, transform=ax.transAxes,
            fontsize=9.5, verticalalignment="top",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white",
                      edgecolor=GREY_GRID, alpha=0.9),
            color=DARK_TEXT, linespacing=1.6)


def _format_xaxis(ax, dates):
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.xaxis.set_minor_locator(mdates.DayLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha="center")


# ── Chart 1: Time in Bed ───────────────────────────────────────────────────────

def plot_time_in_bed(dates, tib):
    fig, ax = plt.subplots(figsize=(14, 5.5))
    fig.suptitle("Time Spent in Bed — Last 30 Days",
                 fontsize=15, fontweight="bold", color=DARK_TEXT, y=1.01)

    # Bar colours: green ≥7h, amber 5–7h, red <5h
    colours = []
    for v in tib:
        if np.isnan(v):   colours.append("none")
        elif v >= 7:      colours.append(BRAND_TEAL)
        elif v >= 5:      colours.append(BRAND_ORANGE)
        else:             colours.append(BRAND_RED)

    bars = ax.bar(dates, tib, color=colours, width=0.7, zorder=3, alpha=0.85)

    # 8-hour target line
    ax.axhline(8, color=BRAND_BLUE, linewidth=1.8, linestyle="--",
               label="8-hr target", zorder=4)
    # 7-hour minimum line
    ax.axhline(7, color=GREY_TEXT, linewidth=1.2, linestyle=":",
               label="7-hr minimum", zorder=4)
    # Rolling 7-day average
    valid   = np.where(~np.isnan(tib), tib, 0)
    weights = np.where(~np.isnan(tib), 1, 0)
    rolling = np.array([
        np.sum(valid[max(0, i-6):i+1]) / max(1, np.sum(weights[max(0, i-6):i+1]))
        for i in range(len(tib))
    ])
    rolling[np.array([np.sum(weights[max(0,i-6):i+1]) for i in range(len(tib))]) == 0] = np.nan
    ax.plot(dates, rolling, color=BRAND_PURPLE, linewidth=2,
            label="7-day avg", zorder=5)

    # Value labels on bars
    for d, v in zip(dates, tib):
        if not np.isnan(v):
            ax.text(d, v + 0.07, f"{v:.1f}h",
                    ha="center", va="bottom", fontsize=8, color=DARK_TEXT)

    valid_tib = tib[~np.isnan(tib)]
    _add_stat_box(ax, [
        f"Nights recorded : {int(np.sum(~np.isnan(tib)))} / 30",
        f"Average         : {np.nanmean(tib):.1f} hrs",
        f"Longest night   : {np.nanmax(tib):.1f} hrs",
        f"Shortest night  : {np.nanmin(tib):.1f} hrs",
        f"Nights >= 7 hrs : {int(np.sum(valid_tib >= 7))}",
        f"Nights < 5 hrs  : {int(np.sum(valid_tib < 5))}",
    ])

    ax.set_ylabel("Hours in Bed", fontsize=11)
    ax.set_ylim(0, max(np.nanmax(tib) + 1.2, 9.5))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:.0f}h"))
    _format_xaxis(ax, dates)

    legend_elements = [
        mpatches.Patch(color=BRAND_TEAL,   label=">=7 hrs (good)"),
        mpatches.Patch(color=BRAND_ORANGE, label="5–7 hrs (fair)"),
        mpatches.Patch(color=BRAND_RED,    label="<5 hrs (short)"),
        Line2D([0],[0], color=BRAND_BLUE,   linewidth=1.8, linestyle="--", label="8-hr target"),
        Line2D([0],[0], color=GREY_TEXT,    linewidth=1.2, linestyle=":",  label="7-hr minimum"),
        Line2D([0],[0], color=BRAND_PURPLE, linewidth=2,                   label="7-day rolling avg"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=9,
              framealpha=0.9, edgecolor=GREY_GRID)

    ax.set_xlabel("Date", fontsize=11)
    fig.tight_layout()
    out = os.path.join(OUTPUT_DIR, "time_in_bed.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ── Chart 2: Sleep Efficiency ──────────────────────────────────────────────────

def plot_sleep_efficiency(dates, efficiency):
    fig, ax = plt.subplots(figsize=(14, 5.5))
    fig.suptitle("Sleep Efficiency — Last 30 Days",
                 fontsize=15, fontweight="bold", color=DARK_TEXT, y=1.01)

    # Shaded background bands
    ax.axhspan(90, 101, color=BRAND_TEAL,   alpha=0.08, zorder=1)
    ax.axhspan(85,  90, color=BRAND_ORANGE, alpha=0.08, zorder=1)
    ax.axhspan(0,   85, color=BRAND_RED,    alpha=0.06, zorder=1)

    # Reference lines
    ax.axhline(90, color=BRAND_TEAL,   linewidth=1.2, linestyle="--", alpha=0.7, zorder=2)
    ax.axhline(85, color=BRAND_ORANGE, linewidth=1.2, linestyle="--", alpha=0.7, zorder=2)

    # Fill under the line (gradient feel)
    ax.fill_between(dates, efficiency, alpha=0.15, color=BRAND_BLUE,
                    where=~np.isnan(efficiency), zorder=2)

    # Main efficiency line
    ax.plot(dates, efficiency, color=BRAND_BLUE, linewidth=2.2,
            marker="o", markersize=5, markerfacecolor="white",
            markeredgecolor=BRAND_BLUE, markeredgewidth=1.5,
            zorder=4, label="Efficiency %")

    # 7-day rolling average
    valid   = np.where(~np.isnan(efficiency), efficiency, 0)
    weights = np.where(~np.isnan(efficiency), 1, 0)
    rolling = np.array([
        np.sum(valid[max(0,i-6):i+1]) / max(1, np.sum(weights[max(0,i-6):i+1]))
        for i in range(len(efficiency))
    ])
    rolling[np.array([np.sum(weights[max(0,i-6):i+1]) for i in range(len(efficiency))]) == 0] = np.nan
    ax.plot(dates, rolling, color=BRAND_PURPLE, linewidth=2,
            linestyle="-", zorder=5, label="7-day rolling avg")

    # Annotate low-efficiency nights
    for d, v in zip(dates, efficiency):
        if not np.isnan(v) and v < 82:
            ax.annotate(f"{v:.0f}%", xy=(d, v), xytext=(0, -18),
                        textcoords="offset points", ha="center",
                        fontsize=8.5, color=BRAND_RED,
                        arrowprops=dict(arrowstyle="-", color=BRAND_RED, lw=0.8))

    valid_eff = efficiency[~np.isnan(efficiency)]
    _add_stat_box(ax, [
        f"Nights recorded  : {len(valid_eff)} / 30",
        f"Average          : {np.nanmean(efficiency):.1f}%",
        f"Best night       : {np.nanmax(efficiency):.0f}%",
        f"Worst night      : {np.nanmin(efficiency):.0f}%",
        f"Nights >= 90%    : {int(np.sum(valid_eff >= 90))}",
        f"Nights < 85%     : {int(np.sum(valid_eff < 85))}",
    ])

    band_labels = [
        mpatches.Patch(color=BRAND_TEAL,   alpha=0.3, label="Excellent (>=90%)"),
        mpatches.Patch(color=BRAND_ORANGE, alpha=0.3, label="Good (85–90%)"),
        mpatches.Patch(color=BRAND_RED,    alpha=0.25, label="Poor (<85%)"),
        Line2D([0],[0], color=BRAND_BLUE,   linewidth=2.2, marker="o",
               markerfacecolor="white", markeredgecolor=BRAND_BLUE,
               markeredgewidth=1.5, label="Efficiency %"),
        Line2D([0],[0], color=BRAND_PURPLE, linewidth=2, label="7-day rolling avg"),
    ]
    ax.legend(handles=band_labels, loc="lower right", fontsize=9,
              framealpha=0.9, edgecolor=GREY_GRID)

    ax.set_ylabel("Efficiency (%)", fontsize=11)
    ax.set_ylim(60, 105)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    _format_xaxis(ax, dates)
    ax.set_xlabel("Date", fontsize=11)

    fig.tight_layout()
    out = os.path.join(OUTPUT_DIR, "sleep_efficiency.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ── Chart 3: Wake Minutes ──────────────────────────────────────────────────────

def plot_wake_minutes(dates, wake):
    fig, ax = plt.subplots(figsize=(14, 5.5))
    fig.suptitle("Wake Minutes During Sleep — Last 30 Days",
                 fontsize=15, fontweight="bold", color=DARK_TEXT, y=1.01)

    # Colour bars by severity
    colours = []
    for v in wake:
        if np.isnan(v):  colours.append("none")
        elif v <= 20:    colours.append(BRAND_TEAL)
        elif v <= 45:    colours.append(BRAND_ORANGE)
        else:            colours.append(BRAND_RED)

    ax.bar(dates, wake, color=colours, width=0.7, zorder=3, alpha=0.85)

    # Healthy threshold line (20 min = ~<5% of 8h)
    ax.axhline(20, color=BRAND_TEAL,   linewidth=1.5, linestyle="--",
               label="Healthy threshold (20 min)", zorder=4)
    ax.axhline(45, color=BRAND_ORANGE, linewidth=1.5, linestyle=":",
               label="Elevated threshold (45 min)", zorder=4)

    # Rolling 7-day avg
    valid   = np.where(~np.isnan(wake), wake, 0)
    weights = np.where(~np.isnan(wake), 1, 0)
    rolling = np.array([
        np.sum(valid[max(0,i-6):i+1]) / max(1, np.sum(weights[max(0,i-6):i+1]))
        for i in range(len(wake))
    ])
    rolling[np.array([np.sum(weights[max(0,i-6):i+1]) for i in range(len(wake))]) == 0] = np.nan
    ax.plot(dates, rolling, color=BRAND_PURPLE, linewidth=2,
            zorder=5, label="7-day rolling avg")

    # Value labels
    for d, v in zip(dates, wake):
        if not np.isnan(v) and v > 0:
            ax.text(d, v + 1.2, f"{v:.0f}",
                    ha="center", va="bottom", fontsize=8, color=DARK_TEXT)

    valid_wake = wake[~np.isnan(wake)]
    _add_stat_box(ax, [
        f"Nights recorded    : {int(np.sum(~np.isnan(wake)))} / 30",
        f"Average wake       : {np.nanmean(wake):.0f} min / night",
        f"Total wake time    : {int(np.nansum(wake))} min ({np.nansum(wake)/60:.1f} hrs)",
        f"Worst night        : {np.nanmax(wake):.0f} min",
        f"Nights <= 20 min   : {int(np.sum(valid_wake <= 20))}",
        f"Nights > 45 min    : {int(np.sum(valid_wake > 45))}",
    ])

    legend_elements = [
        mpatches.Patch(color=BRAND_TEAL,   label="<=20 min (healthy)"),
        mpatches.Patch(color=BRAND_ORANGE, label="20–45 min (elevated)"),
        mpatches.Patch(color=BRAND_RED,    label=">45 min (disrupted)"),
        Line2D([0],[0], color=BRAND_TEAL,   linewidth=1.5, linestyle="--",
               label="Healthy threshold (20 min)"),
        Line2D([0],[0], color=BRAND_ORANGE, linewidth=1.5, linestyle=":",
               label="Elevated threshold (45 min)"),
        Line2D([0],[0], color=BRAND_PURPLE, linewidth=2, label="7-day rolling avg"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=9,
              framealpha=0.9, edgecolor=GREY_GRID)

    ax.set_ylabel("Wake Minutes", fontsize=11)
    ax.set_ylim(0, max(np.nanmax(wake) + 15, 80))
    _format_xaxis(ax, dates)
    ax.set_xlabel("Date", fontsize=11)

    fig.tight_layout()
    out = os.path.join(OUTPUT_DIR, "wake_minutes.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Loading sleep data (last 30 days)...")
    records = load_sleep_data(days=30)
    print(f"  {len(records)} nights recorded out of 30 calendar days\n")

    dates, tib, efficiency, wake = build_full_date_range(records, days=30)

    print("Generating charts...")
    plot_time_in_bed(dates, tib)
    plot_sleep_efficiency(dates, efficiency)
    plot_wake_minutes(dates, wake)

    # ── Analyst summary ──────────────────────────────────────────────────────
    valid_tib  = tib[~np.isnan(tib)]
    valid_eff  = efficiency[~np.isnan(efficiency)]
    valid_wake = wake[~np.isnan(wake)]

    print()
    print("=" * 55)
    print("  SLEEP ANALYST SUMMARY — LAST 30 DAYS")
    print("=" * 55)

    print(f"\n  TIME IN BED")
    print(f"  Average           : {np.nanmean(tib):.1f} hrs/night")
    print(f"  vs 8-hr target    : {np.nanmean(tib) - 8:+.1f} hrs/night")
    print(f"  Nights >= 7 hrs   : {int(np.sum(valid_tib >= 7))} / {len(valid_tib)}"
          f"  ({int(np.sum(valid_tib >= 7))/len(valid_tib)*100:.0f}%)")
    print(f"  Nights < 5 hrs    : {int(np.sum(valid_tib < 5))} / {len(valid_tib)}"
          f"  ({int(np.sum(valid_tib < 5))/len(valid_tib)*100:.0f}%)")

    print(f"\n  SLEEP EFFICIENCY")
    print(f"  Average           : {np.nanmean(efficiency):.1f}%")
    print(f"  Nights >= 90%     : {int(np.sum(valid_eff >= 90))} / {len(valid_eff)}"
          f"  ({int(np.sum(valid_eff >= 90))/len(valid_eff)*100:.0f}%)")
    print(f"  Nights < 85%      : {int(np.sum(valid_eff < 85))} / {len(valid_eff)}"
          f"  ({int(np.sum(valid_eff < 85))/len(valid_eff)*100:.0f}%)")
    low_eff = [(d.strftime('%d %b'), f'{e:.0f}%')
               for d, e in zip(dates, efficiency)
               if not np.isnan(e) and e < 85]
    if low_eff:
        print(f"  Poor nights       : {', '.join([f'{d} ({e})' for d, e in low_eff])}")

    print(f"\n  WAKE MINUTES")
    print(f"  Average/night     : {np.nanmean(wake):.0f} min")
    print(f"  Total lost        : {int(np.nansum(wake))} min"
          f" = {np.nansum(wake)/60:.1f} hrs over 30 days")
    print(f"  Nights <= 20 min  : {int(np.sum(valid_wake <= 20))} / {len(valid_wake)}"
          f"  ({int(np.sum(valid_wake <= 20))/len(valid_wake)*100:.0f}%)")
    print(f"  Nights > 45 min   : {int(np.sum(valid_wake > 45))} / {len(valid_wake)}"
          f"  ({int(np.sum(valid_wake > 45))/len(valid_wake)*100:.0f}%)")

    print()
    print("  Charts saved to: output/")
    print("=" * 55)


if __name__ == "__main__":
    main()
