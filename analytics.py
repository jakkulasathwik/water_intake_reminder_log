import os
from datetime import datetime
from typing import List, Dict
from models import WaterEntry, DailySummary

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

EXPORT_DIR = "exports"


def build_daily_summaries(entries: List[WaterEntry], target_ml: int) -> List[DailySummary]:
    grouped: Dict[str, List[WaterEntry]] = {}
    for e in entries:
        grouped.setdefault(e.date, []).append(e)

    summaries: List[DailySummary] = []
    for date_str in sorted(grouped.keys()):
        day_entries = grouped[date_str]
        total = sum(x.amount_ml for x in day_entries)
        pct = (total / target_ml) * 100 if target_ml > 0 else 0.0
        if total > 5000:
            status = "CRITICAL: Over-Hydration (>5000ml)"
        elif total >= target_ml:
            status = "Target Met"
        elif pct >= 50:
            status = "In Progress"
        else:
            status = "WARNING: Dehydration Risk (<50%)"
        summaries.append(DailySummary(date_str, total, target_ml, pct, len(day_entries), status))
    return summaries


def calculate_streak(summaries: List[DailySummary]) -> int:
    """Consecutive days (ending today or yesterday) on which the target was met."""
    from datetime import timedelta
    met = {s.date for s in summaries if s.total_ml >= s.target_ml}
    day = datetime.now().date()
    if day.strftime("%Y-%m-%d") not in met:
        day -= timedelta(days=1)  # today is still in progress
    streak = 0
    while day.strftime("%Y-%m-%d") in met:
        streak += 1
        day -= timedelta(days=1)
    return streak


def check_reminder_status(entries: List[WaterEntry], interval_mins: int = 90) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    today_entries = [e for e in entries if e.date == today]
    if not today_entries:
        return "REMINDER: No water logged today yet!"
    latest = max(today_entries, key=lambda e: e.time)
    try:
        last_dt = datetime.strptime(f"{latest.date} {latest.time}", "%Y-%m-%d %H:%M")
        elapsed = int((datetime.now() - last_dt).total_seconds() // 60)
        if elapsed >= interval_mins:
            return f"OVERDUE REMINDER: {elapsed} mins since last drink ({latest.time})!"
        return f"On Track: Last logged {max(0, elapsed)} mins ago at {latest.time}."
    except ValueError:
        return f"Last logged today at {latest.time}."


def plot_hydration_trends(summaries: List[DailySummary], show_plot: bool = True) -> str:
    if not MATPLOTLIB_AVAILABLE:
        return "Matplotlib not installed. Run 'pip install matplotlib' to generate charts."
    if not summaries:
        return "No summary data available to plot."

    os.makedirs(EXPORT_DIR, exist_ok=True)
    dates = [s.date for s in summaries]
    totals = [s.total_ml for s in summaries]
    target = summaries[0].target_ml

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))
    colors = ["#10b981" if t >= target else "#3b82f6" for t in totals]
    ax1.bar(dates, totals, color=colors, width=0.55)
    ax1.axhline(target, color="#ef4444", linestyle="--", linewidth=2, label=f"Target ({target} ml)")
    ax1.set_title("Daily Water Intake vs. Target")
    ax1.set_ylabel("Volume (ml)")
    ax1.tick_params(axis="x", rotation=30)
    ax1.legend()

    ax2.plot(dates, [s.completion_pct for s in summaries], marker="o", color="#0ea5e9", linewidth=2)
    ax2.axhline(100, color="#10b981", linestyle=":", linewidth=1.5, label="100% Goal")
    ax2.set_title("Daily Target Completion (%)")
    ax2.set_ylabel("Completion (%)")
    ax2.tick_params(axis="x", rotation=30)
    ax2.legend()

    plt.tight_layout()
    out_path = os.path.join(EXPORT_DIR, "hydration_analytics.png")
    plt.savefig(out_path, dpi=150)
    if show_plot:
        try:
            plt.show()
        except Exception:
            pass
    plt.close(fig)
    return f"Chart saved to '{out_path}'."


def export_reports(entries: List[WaterEntry], summaries: List[DailySummary]) -> str:
    os.makedirs(EXPORT_DIR, exist_ok=True)
    md_path = os.path.join(EXPORT_DIR, "executive_summary.md")
    txt_path = os.path.join(EXPORT_DIR, "audit_log.txt")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Water Intake Reminder Log – Executive Summary\n\n")
        f.write("| Date | Intake (ml) | Target (ml) | Completion | Status |\n")
        f.write("| :--- | :---: | :---: | :---: | :--- |\n")
        for s in summaries:
            f.write(f"| {s.date} | {s.total_ml} | {s.target_ml} | {s.completion_pct:.1f}% | {s.status} |\n")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"WATER INTAKE AUDIT LOG - {datetime.now().isoformat()}\n")
        f.write("=" * 65 + "\n")
        for e in entries:
            f.write(f"[{e.date} {e.time}] {e.entry_id} | {e.amount_ml}ml | {e.category} | {e.note}\n")

    return f"Exported '{md_path}' and '{txt_path}'."
