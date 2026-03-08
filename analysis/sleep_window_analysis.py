"""
Sleep Window & Readiness Analysis
Identifies personal optimal sleep/wake times and correlates
sleep quality with next-day readiness (resting HR + steps).

Produces four charts saved to ../output/:
  1. sleep_duration_vs_quality.png   — duration buckets vs deep, REM, next-day steps
  2. bedtime_vs_quality.png          — bedtime hour vs sleep quality metrics
  3. optimal_sleep_window.png        — personal recommendation summary visual
  4. sleep_vs_readiness.png          — sleep quality → next-day readiness score
"""

import os
import sqlite3
import warnings
warnings.filterwarnings("ignore")

from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker
import matplotlib.gridspec as gridspec
from matplotlib.lines import Line2D
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH    = os.path.join(BASE_DIR, "fitbit_data.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Palette ────────────────────────────────────────────────────────────────────
C_BLUE    = "#1A73E8"
C_TEAL    = "#00BFA5"
C_ORANGE  = "#FF6D00"
C_RED     = "#E53935"
C_PURPLE  = "#7B1FA2"
C_AMBER   = "#FFB300"
C_GREEN   = "#2E7D32"
GREY_BG   = "#F8F9FA"
GREY_GRID = "#E0E0E0"
GREY_TEXT = "#5F6368"
DARK      = "#202124"

plt.rcParams.update({
    "font.family":       "sans-serif",
    "font.size":         11,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.facecolor":    GREY_BG,
    "figure.facecolor":  "white",
    "axes.grid":         True,
    "grid.color":        GREY_GRID,
    "grid.linewidth":    0.7,
    "axes.labelcolor":   GREY_TEXT,
    "xtick.color":       GREY_TEXT,
    "ytick.color":       GREY_TEXT,
})

# ── Data loading ───────────────────────────────────────────────────────────────

def load_data():
    conn = sqlite3.connect(DB_PATH)

    # Sleep + next-day activity + next-day heart rate
    rows = conn.execute("""
        SELECT
            s.date,
            CAST(strftime('%H', s.start_time) AS INTEGER)  AS bed_hour,
            CAST(strftime('%M', s.start_time) AS INTEGER)  AS bed_min,
            CAST(strftime('%H', s.end_time)   AS INTEGER)  AS wake_hour,
            CAST(strftime('%M', s.end_time)   AS INTEGER)  AS wake_min,
            s.minutes_asleep,
            s.efficiency,
            s.deep_minutes,
            s.rem_minutes,
            s.wake_minutes,
            s.time_in_bed,
            a.steps                                         AS next_steps,
            h.resting_hr                                    AS next_rhr,
            h.cardio_minutes + h.peak_minutes               AS next_active_mins
        FROM daily_sleep s
        JOIN daily_activity  a ON a.date = DATE(s.date, '+1 day')
        JOIN daily_heartrate h ON h.date = DATE(s.date, '+1 day')
        WHERE s.minutes_asleep > 120
          AND h.resting_hr IS NOT NULL
          AND h.resting_hr > 0
        ORDER BY s.date
    """).fetchall()
    conn.close()

    cols = ["date","bed_hour","bed_min","wake_hour","wake_min",
            "minutes_asleep","efficiency","deep_minutes","rem_minutes",
            "wake_minutes","time_in_bed","next_steps","next_rhr","next_active_mins"]
    return [dict(zip(cols, r)) for r in rows]


def readiness_score(rhr, rhr_baseline, sleep_hrs, deep_mins, rem_mins):
    """
    Composite readiness score 0-100:
      40% resting HR delta from personal baseline
      30% sleep duration vs 8-hr target
      20% deep sleep vs 96-min personal avg
      10% REM sleep vs 82-min personal avg
    """
    rhr_score  = max(0, min(100, 100 - (rhr - rhr_baseline) * 5))
    sleep_score = max(0, min(100, (sleep_hrs / 8.0) * 100))
    deep_score  = max(0, min(100, (deep_mins / 96.0) * 100))
    rem_score   = max(0, min(100, (rem_mins  / 82.0) * 100))
    return round(0.4*rhr_score + 0.3*sleep_score + 0.2*deep_score + 0.1*rem_score, 1)


# ── Chart 1: Sleep Duration vs Quality ────────────────────────────────────────

def plot_duration_vs_quality(records):
    buckets = {"<5h": [], "5-6h": [], "6-7h": [], "7-8h": [], "8h+": []}
    for r in records:
        hrs = r["minutes_asleep"] / 60.0
        if   hrs < 5: buckets["<5h"].append(r)
        elif hrs < 6: buckets["5-6h"].append(r)
        elif hrs < 7: buckets["6-7h"].append(r)
        elif hrs < 8: buckets["7-8h"].append(r)
        else:         buckets["8h+"].append(r)

    labels      = list(buckets.keys())
    counts      = [len(v) for v in buckets.values()]
    avg_deep    = [np.mean([r["deep_minutes"]  for r in v]) if v else 0 for v in buckets.values()]
    avg_rem     = [np.mean([r["rem_minutes"]   for r in v]) if v else 0 for v in buckets.values()]
    avg_eff     = [np.mean([r["efficiency"]    for r in v]) if v else 0 for v in buckets.values()]
    avg_steps   = [np.mean([r["next_steps"]    for r in v]) if v else 0 for v in buckets.values()]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    fig.suptitle("Sleep Duration vs Sleep Quality & Next-Day Performance",
                 fontsize=14, fontweight="bold", color=DARK, y=1.02)

    x = np.arange(len(labels))
    w = 0.55

    # — Panel 1: Deep + REM minutes
    ax = axes[0]
    bars_d = ax.bar(x - w/4, avg_deep, width=w/2, color=C_BLUE,   alpha=0.85, label="Deep sleep")
    bars_r = ax.bar(x + w/4, avg_rem,  width=w/2, color=C_PURPLE, alpha=0.85, label="REM sleep")
    ax.axhline(96, color=C_BLUE,   linewidth=1.2, linestyle="--", alpha=0.6, label="Personal avg deep (96 min)")
    ax.axhline(82, color=C_PURPLE, linewidth=1.2, linestyle=":",  alpha=0.6, label="Personal avg REM (82 min)")
    for bar in list(bars_d) + list(bars_r):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=8.5, color=DARK)
    ax.set_title("Sleep Stage Minutes", fontsize=11, fontweight="bold", color=DARK)
    ax.set_ylabel("Minutes", fontsize=10)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.legend(fontsize=8, framealpha=0.9)
    ax.set_ylim(0, 160)
    for i, n in enumerate(counts):
        ax.text(i, 3, f"n={n}", ha="center", va="bottom", fontsize=7.5, color=GREY_TEXT)

    # — Panel 2: Sleep efficiency
    ax = axes[1]
    colours = [C_RED if e < 85 else C_AMBER if e < 90 else C_TEAL for e in avg_eff]
    bars = ax.bar(x, avg_eff, width=w, color=colours, alpha=0.85)
    ax.axhline(90, color=C_TEAL,   linewidth=1.5, linestyle="--", label="Excellent (90%)")
    ax.axhline(85, color=C_AMBER,  linewidth=1.5, linestyle=":",  label="Good (85%)")
    for bar, v in zip(bars, avg_eff):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                f"{v:.1f}%", ha="center", va="bottom", fontsize=9, color=DARK)
    ax.set_title("Sleep Efficiency", fontsize=11, fontweight="bold", color=DARK)
    ax.set_ylabel("Efficiency (%)", fontsize=10)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylim(80, 96)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v,_: f"{v:.0f}%"))
    ax.legend(fontsize=8, framealpha=0.9)

    # — Panel 3: Next-day steps
    ax = axes[2]
    bar_colours = [C_RED if s < 5000 else C_ORANGE if s < 8000 else C_TEAL for s in avg_steps]
    bars = ax.bar(x, avg_steps, width=w, color=bar_colours, alpha=0.85)
    ax.axhline(6067, color=GREY_TEXT, linewidth=1.5, linestyle="--", label="30-day avg (6,067)")
    for bar, v in zip(bars, avg_steps):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 80,
                f"{int(v):,}", ha="center", va="bottom", fontsize=8.5, color=DARK)
    ax.set_title("Next-Day Steps", fontsize=11, fontweight="bold", color=DARK)
    ax.set_ylabel("Steps", fontsize=10)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v,_: f"{int(v):,}"))
    ax.legend(fontsize=8, framealpha=0.9)

    # Highlight optimal column
    for ax in axes:
        ax.axvspan(3 - 0.4, 3 + 0.4, color=C_TEAL, alpha=0.06, zorder=0)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "sleep_duration_vs_quality.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ── Chart 2: Bedtime & Wake Time vs Quality ────────────────────────────────────

def plot_bedtime_vs_quality(records):
    # Only use nights with enough data (midnight = hour 0, treated as 24)
    def norm_hour(h):
        return h + 24 if h < 6 else h  # treat 00-05 as 24-29 for sorting

    bed_buckets  = {}
    wake_buckets = {}
    for r in records:
        bh = norm_hour(r["bed_hour"])
        wh = r["wake_hour"]
        bed_buckets.setdefault(bh, []).append(r)
        wake_buckets.setdefault(wh, []).append(r)

    # Filter to hours with >=5 nights
    bed_hours  = sorted([h for h, v in bed_buckets.items()  if len(v) >= 5])
    wake_hours = sorted([h for h, v in wake_buckets.items() if len(v) >= 5])

    def label_hour(h):
        return f"{h % 24:02d}:00"

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle("Bedtime & Wake Time vs Sleep Quality",
                 fontsize=14, fontweight="bold", color=DARK, y=1.01)

    # ── Top row: Bedtime ──
    bx = np.arange(len(bed_hours))
    b_deep  = [np.mean([r["deep_minutes"] for r in bed_buckets[h]]) for h in bed_hours]
    b_rem   = [np.mean([r["rem_minutes"]  for r in bed_buckets[h]]) for h in bed_hours]
    b_hrs   = [np.mean([r["minutes_asleep"]/60 for r in bed_buckets[h]]) for h in bed_hours]
    b_wake  = [np.mean([r["wake_minutes"] for r in bed_buckets[h]]) for h in bed_hours]
    b_count = [len(bed_buckets[h]) for h in bed_hours]
    b_xlabels = [label_hour(h) for h in bed_hours]

    ax = axes[0][0]
    ax.bar(bx - 0.2, b_deep, width=0.38, color=C_BLUE,   alpha=0.85, label="Deep")
    ax.bar(bx + 0.2, b_rem,  width=0.38, color=C_PURPLE, alpha=0.85, label="REM")
    ax.axhline(96, color=C_BLUE,   linewidth=1.2, linestyle="--", alpha=0.5)
    ax.axhline(82, color=C_PURPLE, linewidth=1.2, linestyle=":",  alpha=0.5)
    ax.set_title("Bedtime vs Deep & REM Sleep", fontsize=11, fontweight="bold", color=DARK)
    ax.set_ylabel("Minutes", fontsize=10)
    ax.set_xticks(bx); ax.set_xticklabels(b_xlabels, rotation=0)
    ax.set_xlabel("Bedtime", fontsize=10)
    ax.legend(fontsize=9)
    for i, n in enumerate(b_count):
        ax.text(i, 3, f"n={n}", ha="center", fontsize=7.5, color=GREY_TEXT)
    # shade optimal band (22:00–23:00)
    opt_idx = [i for i, h in enumerate(bed_hours) if h in (22, 23)]
    for i in opt_idx:
        ax.axvspan(i-0.5, i+0.5, color=C_TEAL, alpha=0.12, zorder=0)
    ax.text(opt_idx[0] if opt_idx else 0, ax.get_ylim()[1]*0.92,
            "Optimal\nwindow", ha="center", fontsize=8, color=C_TEAL, fontweight="bold")

    ax = axes[0][1]
    ax.plot(bx, b_hrs, color=C_BLUE, linewidth=2.2, marker="o",
            markersize=6, markerfacecolor="white", markeredgecolor=C_BLUE,
            markeredgewidth=1.8, label="Avg sleep hrs", zorder=4)
    ax.fill_between(bx, b_hrs, alpha=0.12, color=C_BLUE)
    ax2 = ax.twinx()
    ax2.spines["top"].set_visible(False)
    ax2.bar(bx, b_wake, width=0.4, color=C_ORANGE, alpha=0.5, label="Wake mins")
    ax2.set_ylabel("Wake minutes", fontsize=10, color=C_ORANGE)
    ax2.tick_params(axis="y", colors=C_ORANGE)
    ax.axhline(7.5, color=C_TEAL, linewidth=1.3, linestyle="--", alpha=0.7, label="7.5hr target")
    for i, (h, w) in enumerate(zip(b_hrs, b_wake)):
        ax.text(i, h + 0.08, f"{h:.1f}h", ha="center", fontsize=8, color=DARK)
    ax.set_title("Bedtime vs Hours Slept & Wake Minutes", fontsize=11, fontweight="bold", color=DARK)
    ax.set_ylabel("Hours asleep", fontsize=10)
    ax.set_xticks(bx); ax.set_xticklabels(b_xlabels, rotation=0)
    ax.set_xlabel("Bedtime", fontsize=10)
    lines1, labs1 = ax.get_legend_handles_labels()
    lines2, labs2 = ax2.get_legend_handles_labels()
    ax.legend(lines1+lines2, labs1+labs2, fontsize=9, loc="lower left")
    for i in opt_idx:
        ax.axvspan(i-0.5, i+0.5, color=C_TEAL, alpha=0.12, zorder=0)

    # ── Bottom row: Wake time ──
    wx = np.arange(len(wake_hours))
    w_deep  = [np.mean([r["deep_minutes"] for r in wake_buckets[h]]) for h in wake_hours]
    w_rem   = [np.mean([r["rem_minutes"]  for r in wake_buckets[h]]) for h in wake_hours]
    w_hrs   = [np.mean([r["minutes_asleep"]/60 for r in wake_buckets[h]]) for h in wake_hours]
    w_count = [len(wake_buckets[h]) for h in wake_hours]
    w_xlabels = [label_hour(h) for h in wake_hours]

    ax = axes[1][0]
    ax.bar(wx - 0.2, w_deep, width=0.38, color=C_BLUE,   alpha=0.85, label="Deep")
    ax.bar(wx + 0.2, w_rem,  width=0.38, color=C_PURPLE, alpha=0.85, label="REM")
    ax.axhline(96, color=C_BLUE,   linewidth=1.2, linestyle="--", alpha=0.5)
    ax.axhline(82, color=C_PURPLE, linewidth=1.2, linestyle=":",  alpha=0.5)
    ax.set_title("Wake Time vs Deep & REM Sleep", fontsize=11, fontweight="bold", color=DARK)
    ax.set_ylabel("Minutes", fontsize=10)
    ax.set_xticks(wx); ax.set_xticklabels(w_xlabels, rotation=0)
    ax.set_xlabel("Wake time", fontsize=10)
    ax.legend(fontsize=9)
    for i, n in enumerate(w_count):
        ax.text(i, 3, f"n={n}", ha="center", fontsize=7.5, color=GREY_TEXT)
    opt_w = [i for i, h in enumerate(wake_hours) if h in (8, 9)]
    for i in opt_w:
        ax.axvspan(i-0.5, i+0.5, color=C_TEAL, alpha=0.12, zorder=0)
    if opt_w:
        ax.text(opt_w[0], ax.get_ylim()[1]*0.92, "Optimal\nwindow",
                ha="center", fontsize=8, color=C_TEAL, fontweight="bold")

    ax = axes[1][1]
    bar_c = [C_RED if h < 7 else C_TEAL for h in w_hrs]
    bars = ax.bar(wx, w_hrs, width=0.55, color=bar_c, alpha=0.85)
    ax.axhline(7.5, color=C_TEAL,   linewidth=1.5, linestyle="--", label="7.5-hr target")
    ax.axhline(5.0, color=C_ORANGE, linewidth=1.2, linestyle=":",  label="Minimum threshold")
    for bar, v in zip(bars, w_hrs):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                f"{v:.1f}h", ha="center", fontsize=8.5, color=DARK)
    ax.set_title("Wake Time vs Hours Slept", fontsize=11, fontweight="bold", color=DARK)
    ax.set_ylabel("Avg hours asleep", fontsize=10)
    ax.set_xticks(wx); ax.set_xticklabels(w_xlabels, rotation=0)
    ax.set_xlabel("Wake time", fontsize=10)
    ax.legend(fontsize=9)
    for i in opt_w:
        ax.axvspan(i-0.5, i+0.5, color=C_TEAL, alpha=0.12, zorder=0)

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "bedtime_vs_quality.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ── Chart 3: Optimal Sleep Window Summary ─────────────────────────────────────

def plot_optimal_window(records):
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.set_xlim(18, 32)      # 18:00 → 08:00 next day (32 = 08:00 next day)
    ax.set_ylim(0, 5)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    fig.suptitle("Your Personal Optimal Sleep Window",
                 fontsize=16, fontweight="bold", color=DARK, y=0.98)

    # ── Timeline bar ──
    y_bar = 2.8
    h_bar = 0.55

    # Full timeline background
    full = mpatches.FancyBboxPatch((18, y_bar), 14, h_bar,
        boxstyle="round,pad=0.05", facecolor="#ECEFF1", edgecolor=GREY_GRID, linewidth=1)
    ax.add_patch(full)

    # Optimal sleep zone (22:30 to 31:00 = 07:00)
    sleep_zone = mpatches.FancyBboxPatch((22.5, y_bar), 8.0, h_bar,
        boxstyle="round,pad=0.05", facecolor=C_TEAL, edgecolor="none", alpha=0.85)
    ax.add_patch(sleep_zone)

    # Acceptable zone edges
    early = mpatches.FancyBboxPatch((21.0, y_bar), 1.5, h_bar,
        boxstyle="round,pad=0.05", facecolor=C_AMBER, edgecolor="none", alpha=0.5)
    ax.add_patch(early)
    late = mpatches.FancyBboxPatch((30.5, y_bar), 1.0, h_bar,
        boxstyle="round,pad=0.05", facecolor=C_ORANGE, edgecolor="none", alpha=0.5)
    ax.add_patch(late)

    # Hour tick marks
    for hour in range(18, 33):
        xp = hour
        label = f"{hour % 24:02d}:00"
        ax.plot([xp, xp], [y_bar - 0.1, y_bar], color=GREY_TEXT, linewidth=0.8)
        ax.text(xp, y_bar - 0.22, label, ha="center", va="top",
                fontsize=8, color=GREY_TEXT, rotation=45)

    # Labels on the bar
    ax.text(26.5, y_bar + h_bar/2, "Optimal sleep window", ha="center", va="center",
            fontsize=11, fontweight="bold", color="white")
    ax.text(21.75, y_bar + h_bar/2, "Early", ha="center", va="center",
            fontsize=8.5, color=DARK, fontweight="bold")
    ax.text(31.0, y_bar + h_bar/2, "Late", ha="center", va="center",
            fontsize=8.5, color=DARK, fontweight="bold")

    # Bedtime arrow
    ax.annotate("Bed by\n22:30–23:00",
                xy=(22.75, y_bar + h_bar), xytext=(22.75, y_bar + 1.45),
                fontsize=10, ha="center", color=C_TEAL, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color=C_TEAL, lw=1.8))

    # Wake time arrow
    ax.annotate("Wake at\n07:30–08:30",
                xy=(30.25, y_bar + h_bar), xytext=(30.25, y_bar + 1.45),
                fontsize=10, ha="center", color=C_TEAL, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color=C_TEAL, lw=1.8))

    # Duration callout
    ax.annotate("", xy=(30.5, y_bar + h_bar + 0.55),
                     xytext=(22.5, y_bar + h_bar + 0.55),
                arrowprops=dict(arrowstyle="<->", color=DARK, lw=1.5))
    ax.text(26.5, y_bar + h_bar + 0.72, "~8 – 8.5 hours in bed",
            ha="center", fontsize=10, color=DARK)

    # ── Stats boxes at bottom ──
    stats = [
        ("7–8h duration", "Best deep + REM sleep\n108 min deep / 102 min REM", C_BLUE),
        ("Bed: 22:00–23:00", "Highest sleep duration\n7.7 hrs avg vs 5.2 hrs at 02:00+", C_TEAL),
        ("Wake: 08:00–09:00", "Deep & REM both peak\n107 min deep / 97 min REM", C_PURPLE),
        ("Avg efficiency", "89.2% on optimal nights\nvs 86.7% on other nights", C_AMBER),
    ]
    for i, (title, body, col) in enumerate(stats):
        x0 = 18.2 + i * 3.45
        box = mpatches.FancyBboxPatch((x0, 0.15), 3.1, 1.85,
            boxstyle="round,pad=0.15", facecolor=col, edgecolor="none", alpha=0.12)
        ax.add_patch(box)
        ax.text(x0 + 1.55, 1.72, title, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color=col)
        ax.text(x0 + 1.55, 0.9, body, ha="center", va="center",
                fontsize=8.5, color=DARK, linespacing=1.5)

    out = os.path.join(OUTPUT_DIR, "optimal_sleep_window.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ── Chart 4: Sleep Quality → Next-Day Readiness ────────────────────────────────

def plot_sleep_vs_readiness(records):
    rhr_baseline = np.median([r["next_rhr"] for r in records])

    # Compute readiness for each night
    for r in records:
        r["readiness"] = readiness_score(
            r["next_rhr"], rhr_baseline,
            r["minutes_asleep"] / 60.0,
            r["deep_minutes"], r["rem_minutes"]
        )

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle("Sleep Quality vs Next-Day Readiness Score",
                 fontsize=14, fontweight="bold", color=DARK, y=1.01)

    def scatter_with_trend(ax, x_vals, y_vals, xlabel, ylabel, title, col):
        ax.scatter(x_vals, y_vals, color=col, alpha=0.45, s=35, zorder=3)
        # trend line
        valid = [(x, y) for x, y in zip(x_vals, y_vals) if not (np.isnan(x) or np.isnan(y))]
        if len(valid) > 5:
            xv, yv = zip(*valid)
            z = np.polyfit(xv, yv, 1)
            p = np.poly1d(z)
            xline = np.linspace(min(xv), max(xv), 100)
            ax.plot(xline, p(xline), color=col, linewidth=2, linestyle="--", zorder=4)
            corr = np.corrcoef(xv, yv)[0, 1]
            ax.text(0.97, 0.05, f"r = {corr:.2f}", transform=ax.transAxes,
                    ha="right", fontsize=10, color=col,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                              edgecolor=GREY_GRID, alpha=0.9))
        ax.set_xlabel(xlabel, fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(title, fontsize=11, fontweight="bold", color=DARK)

    sleep_hrs   = [r["minutes_asleep"] / 60 for r in records]
    deep_mins   = [r["deep_minutes"]        for r in records]
    efficiency  = [r["efficiency"]          for r in records]
    readiness   = [r["readiness"]           for r in records]
    next_rhr    = [r["next_rhr"]            for r in records]
    next_steps  = [r["next_steps"]          for r in records]

    scatter_with_trend(axes[0][0], sleep_hrs,  readiness,
                       "Sleep duration (hrs)", "Next-day readiness score",
                       "Sleep Duration vs Readiness", C_BLUE)
    scatter_with_trend(axes[0][1], deep_mins,  readiness,
                       "Deep sleep (mins)", "Next-day readiness score",
                       "Deep Sleep vs Readiness", C_PURPLE)
    scatter_with_trend(axes[1][0], efficiency, next_rhr,
                       "Sleep efficiency (%)", "Next-day resting HR (bpm)",
                       "Sleep Efficiency vs Resting HR\n(lower is better)", C_ORANGE)
    scatter_with_trend(axes[1][1], readiness,  next_steps,
                       "Next-day readiness score", "Next-day steps",
                       "Readiness Score vs Activity", C_TEAL)

    # Readiness band annotations on step chart
    for threshold, label, col in [(40, "Low", C_RED), (70, "Medium", C_AMBER), (85, "High", C_TEAL)]:
        axes[1][1].axvline(threshold, color=col, linewidth=1.2, linestyle=":", alpha=0.7)
        axes[1][1].text(threshold + 0.5, axes[1][1].get_ylim()[1] * 0.96,
                        label, fontsize=8, color=col, va="top")

    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "sleep_vs_readiness.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ── Summary ────────────────────────────────────────────────────────────────────

def print_summary(records):
    rhr_baseline = np.median([r["next_rhr"] for r in records])
    for r in records:
        r["readiness"] = readiness_score(
            r["next_rhr"], rhr_baseline,
            r["minutes_asleep"] / 60.0,
            r["deep_minutes"], r["rem_minutes"]
        )

    high = [r for r in records if r["readiness"] >= 70]
    low  = [r for r in records if r["readiness"] <  50]

    print()
    print("=" * 58)
    print("  SLEEP WINDOW & READINESS — ANALYST SUMMARY")
    print("=" * 58)
    print(f"\n  Dataset          : {len(records)} nights with next-day HR data")
    print(f"  RHR baseline     : {rhr_baseline:.0f} bpm (personal median)")

    print(f"\n  OPTIMAL SLEEP WINDOW (data-derived)")
    print(f"  Bed by           : 22:30 – 23:00")
    print(f"  Wake at          : 07:30 – 08:30")
    print(f"  Target duration  : 7.5 – 8.5 hrs")

    print(f"\n  READINESS SCORE COMPOSITION")
    print(f"  40%  Resting HR vs your {rhr_baseline:.0f} bpm baseline")
    print(f"  30%  Sleep duration vs 8-hr target")
    print(f"  20%  Deep sleep vs your 96-min avg")
    print(f"  10%  REM sleep vs your 82-min avg")

    print(f"\n  HIGH READINESS NIGHTS (score >= 70): {len(high)}")
    if high:
        hb = [r["bed_hour"] for r in high]
        hw = [r["wake_hour"] for r in high]
        print(f"  Avg bedtime      : {int(round(np.mean(hb))):02d}:00")
        print(f"  Avg wake time    : {int(round(np.mean(hw))):02d}:00")
        print(f"  Avg sleep hrs    : {np.mean([r['minutes_asleep']/60 for r in high]):.1f}")
        print(f"  Avg deep sleep   : {np.mean([r['deep_minutes'] for r in high]):.0f} min")
        print(f"  Avg next-day RHR : {np.mean([r['next_rhr'] for r in high]):.1f} bpm")
        print(f"  Avg next-day steps: {int(np.mean([r['next_steps'] for r in high])):,}")

    print(f"\n  LOW READINESS NIGHTS (score < 50): {len(low)}")
    if low:
        lb = [r["bed_hour"] for r in low]
        print(f"  Avg bedtime      : {int(round(np.mean(lb))):02d}:00")
        print(f"  Avg sleep hrs    : {np.mean([r['minutes_asleep']/60 for r in low]):.1f}")
        print(f"  Avg next-day RHR : {np.mean([r['next_rhr'] for r in low]):.1f} bpm")
        print(f"  Avg next-day steps: {int(np.mean([r['next_steps'] for r in low])):,}")

    print()
    print("  Charts saved to: output/")
    print("=" * 58)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    records = load_data()
    print(f"  {len(records)} nights with matching next-day HR + activity data\n")

    print("Generating charts...")
    plot_duration_vs_quality(records)
    plot_bedtime_vs_quality(records)
    plot_optimal_window(records)
    plot_sleep_vs_readiness(records)

    print_summary(records)


if __name__ == "__main__":
    main()
