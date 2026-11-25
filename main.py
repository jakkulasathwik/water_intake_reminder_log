import sys
from datetime import datetime
from models import WaterEntry
from validators import (
    CATEGORIES,
    MIN_VOLUME_ML,
    MAX_VOLUME_ML,
    get_valid_int,
    get_valid_date,
    get_valid_time,
    get_valid_category,
)
from storage import load_config, save_config, load_entries, save_entries, bulk_import_csv, SAMPLE_IMPORT_PATH
from analytics import build_daily_summaries, check_reminder_status, plot_hydration_trends, export_reports


def render_bar(current: int, target: int, width: int = 26) -> str:
    ratio = min(current / target, 1.0) if target > 0 else 0
    filled = int(width * ratio)
    bar = "█" * filled + "░" * (width - filled)
    color = "\033[92m" if current >= target else ("\033[93m" if ratio >= 0.5 else "\033[91m")
    return f"{color}[{bar}]\033[0m {current}/{target} ml ({(current/target)*100:.1f}%)"


def main() -> None:
    if "--gui" in sys.argv:
        from gui import launch_gui
        launch_gui()
        return
    cfg = load_config()
    entries = load_entries()

    while True:
        today = datetime.now().strftime("%Y-%m-%d")
        today_total = sum(e.amount_ml for e in entries if e.date == today)
        target = cfg["daily_target_ml"]
        reminder_msg = check_reminder_status(entries, cfg.get("reminder_interval_mins", 90))

        print("\n\033[1m\033[96m╔══════════════════════════════════════════════════════════════╗")
        print("║        CAMPUSSOLVE #31: WATER INTAKE REMINDER LOG            ║")
        print("╚══════════════════════════════════════════════════════════════╝\033[0m")
        print(f"  Today ({today}): {render_bar(today_total, target)}")
        print(f"  Status Alert     : \033[93m{reminder_msg}\033[0m")
        print("-" * 64)
        print("  1. Record Water Intake")
        print("  2. Update Daily Hydration Target")
        print("  3. Query & Search Records (Date / Category / Keyword)")
        print("  4. View All Entries (Paginated Table)")
        print("  5. Executive Summary & Threshold Warnings")
        print("  6. Generate Visual Trend Charts (Matplotlib)")
        print("  7. Export Multi-Format Reports (Markdown & Audit Log)")
        print("  8. Bulk Import Legacy CSV Dataset")
        print("  9. Launch Modern Desktop GUI (HydroTrack)")
        print(" 10. Save & Exit")
        print("-" * 64)

        choice = get_valid_int("Select Option (1-10): ", 1, 10)

        if choice == 1:
            d = get_valid_date("Date (YYYY-MM-DD) [Enter for Today]: ")
            t = get_valid_time("Time (HH:MM) [Enter for Now]: ")
            amt = get_valid_int(f"Volume in ml ({MIN_VOLUME_ML}-{MAX_VOLUME_ML}): ", MIN_VOLUME_ML, MAX_VOLUME_ML)
            cat = get_valid_category("Select Category #: ", CATEGORIES)
            note = input("Optional Note: ").strip() or "Routine intake"
            new_entry = WaterEntry(f"WTR-{1001 + len(entries)}", d, t, amt, cat, note)
            entries.append(new_entry)
            save_entries(entries)
            print(f"\033[92m✓ Logged {amt} ml ({cat}) on {d} at {t}.\033[0m")

        elif choice == 2:
            new_t = get_valid_int("Enter New Daily Target (500-6000 ml): ", 500, 6000)
            cfg["daily_target_ml"] = new_t
            save_config(cfg)
            print(f"\033[92m✓ Target updated to {new_t} ml.\033[0m")

        elif choice == 3:
            print("\n1. By Date  2. By Category  3. By Keyword")
            mode = get_valid_int("Filter Mode (1-3): ", 1, 3)
            if mode == 1:
                qd = get_valid_date("Enter Date (YYYY-MM-DD): ", allow_today_default=False)
                res = [e for e in entries if e.date == qd]
            elif mode == 2:
                qc = get_valid_category("Select Category #: ")
                res = [e for e in entries if e.category == qc]
            else:
                kw = input("Keyword: ").strip().lower()
                res = [e for e in entries if kw in e.note.lower() or kw in e.category.lower()]
            print(f"\nFound {len(res)} record(s):")
            for r in res:
                print(f"  {r.entry_id} | {r.date} {r.time} | {r.amount_ml:>4} ml | {r.category:<20} | {r.note}")

        elif choice == 4:
            print("-" * 84)
            print(f"{'ID':<9} | {'Date':<10} | {'Time':<5} | {'Volume':<8} | {'Category':<20} | {'Note'}")
            print("-" * 84)
            for idx, r in enumerate(entries, start=1):
                print(f"{r.entry_id:<9} | {r.date:<10} | {r.time:<5} | {r.amount_ml:>5} ml | {r.category:<20} | {r.note}")
                if idx % 15 == 0 and idx < len(entries):
                    if input("-- Press Enter for next page ('q' to stop) -- ").strip().lower() == "q":
                        break

        elif choice == 5:
            summaries = build_daily_summaries(entries, target)
            avg = sum(s.total_ml for s in summaries) / len(summaries) if summaries else 0
            print(f"\n\033[1mEXECUTIVE SUMMARY (Daily Average: {avg:.1f} ml | Target: {target} ml)\033[0m")
            print("-" * 82)
            for s in summaries:
                print(f"{s.date} | {s.total_ml:>5} ml ({s.completion_pct:>5.1f}%) | {s.entry_count} entries | {s.status}")
            print("-" * 82)

        elif choice == 6:
            summaries = build_daily_summaries(entries, target)
            print(plot_hydration_trends(summaries))

        elif choice == 7:
            summaries = build_daily_summaries(entries, target)
            print(f"\033[92m✓ {export_reports(entries, summaries)}\033[0m")

        elif choice == 8:
            path = input(f"CSV Path [Enter for '{SAMPLE_IMPORT_PATH}']: ").strip() or SAMPLE_IMPORT_PATH
            ok, errs = bulk_import_csv(path, entries)
            print(f"\033[92m✓ Imported {ok} valid rows.\033[0m")
            for err in errs[:10]:
                print(f"  \033[91m- {err}\033[0m")

        elif choice == 9:
            try:
                from gui import launch_gui
                print("\033[96mLaunching HydroTrack Desktop GUI... Close the GUI window to return to terminal.\033[0m")
                launch_gui()
                entries = load_entries()
                cfg = load_config()
            except Exception as exc:
                print(f"\033[91m[GUI Fallback] Unable to open GUI window ({exc}). Continuing in terminal mode.\033[0m")

        elif choice == 10:
            save_entries(entries)
            save_config(cfg)
            print("\033[92mAll data persisted safely. Goodbye!\033[0m")
            break


if __name__ == "__main__":
    main()
