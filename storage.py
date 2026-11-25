import csv
import json
import os
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from models import WaterEntry
from validators import CATEGORIES, MIN_VOLUME_ML, MAX_VOLUME_ML

DATA_DIR = "data"
JSON_PATH = os.path.join(DATA_DIR, "water_logs.json")
CSV_PATH = os.path.join(DATA_DIR, "water_logs.csv")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
SAMPLE_IMPORT_PATH = os.path.join(DATA_DIR, "legacy_import_sample.csv")
DEFAULT_TARGET_ML = 2500


def next_entry_id(entries: List[WaterEntry], prefix: str = "WTR") -> str:
    """Return a unique ID even after entries have been deleted."""
    existing = {e.entry_id for e in entries}
    highest = 1000
    for e in entries:
        tail = e.entry_id.rsplit("-", 1)[-1]
        if tail.isdigit():
            highest = max(highest, int(tail))
    candidate = highest + 1
    while f"{prefix}-{candidate}" in existing:
        candidate += 1
    return f"{prefix}-{candidate}"


def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def load_config(config_path: str = CONFIG_PATH) -> Dict:
    os.makedirs(os.path.dirname(config_path) or ".", exist_ok=True)
    if not os.path.exists(config_path):
        cfg = {"daily_target_ml": DEFAULT_TARGET_ML, "reminder_interval_mins": 90}
        save_config(cfg, config_path)
        return cfg
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if not isinstance(cfg.get("daily_target_ml"), int):
                raise ValueError("Invalid target type")
            return cfg
    except (json.JSONDecodeError, ValueError, OSError):
        print("\033[93m[Recovery] Corrupted config file reset to 2500 ml default.\033[0m")
        cfg = {"daily_target_ml": DEFAULT_TARGET_ML, "reminder_interval_mins": 90}
        save_config(cfg, config_path)
        return cfg


def save_config(cfg: Dict, config_path: str = CONFIG_PATH) -> None:
    os.makedirs(os.path.dirname(config_path) or ".", exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def seed_realistic_data(count: int = 42) -> List[WaterEntry]:
    entries: List[WaterEntry] = []
    base = datetime.now()
    volumes = [200, 250, 300, 350, 500, 750, 1000]
    notes = [
        "Morning wake-up glass",
        "Between lectures refill",
        "Post-gym hydration",
        "Lunchtime water",
        "Library study session",
        "Evening walk bottle",
    ]
    rng = random.Random(42)

    for i in range(1, count + 1):
        dt = base - timedelta(days=i % 8)
        hr = 7 + (i * 2) % 15
        mn = (i * 11) % 60
        entries.append(
            WaterEntry(
                entry_id=f"WTR-{1000 + i}",
                date=dt.strftime("%Y-%m-%d"),
                time=f"{hr:02d}:{mn:02d}",
                amount_ml=rng.choice(volumes),
                category=rng.choice(CATEGORIES),
                note=rng.choice(notes),
            )
        )
    entries.sort(key=lambda e: (e.date, e.time))
    return entries


def create_sample_import_csv(path: str = SAMPLE_IMPORT_PATH) -> None:
    ensure_data_dir()
    if os.path.exists(path):
        return
    today = datetime.now().strftime("%Y-%m-%d")
    rows = [
        ["date", "time", "amount_ml", "category", "note"],
        [today, "08:30", "400", "Plain Water", "Valid morning import"],
        [today, "11:15", "350", "Herbal Tea", "Valid mid-day import"],
        ["invalid-date", "12:00", "250", "Plain Water", "Bad date test case"],
        [today, "14:00", "9500", "Plain Water", "Out of bounds volume test"],
        [today, "16:00", "abc", "Electrolyte", "Non-numeric volume test"],
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def save_entries(entries: List[WaterEntry], json_path: str = JSON_PATH, csv_path: str = CSV_PATH) -> None:
    os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([e.to_dict() for e in entries], f, indent=2)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["entry_id", "date", "time", "amount_ml", "category", "note"])
        for e in entries:
            writer.writerow([e.entry_id, e.date, e.time, e.amount_ml, e.category, e.note])


def load_entries(json_path: str = JSON_PATH, csv_path: str = CSV_PATH) -> List[WaterEntry]:
    ensure_data_dir()
    create_sample_import_csv()
    if not os.path.exists(json_path):
        seeded = seed_realistic_data(42)
        save_entries(seeded, json_path, csv_path)
        return seeded
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
            if not isinstance(raw, list):
                raise ValueError("Invalid JSON root")
            return [
                WaterEntry(
                    entry_id=str(item["entry_id"]),
                    date=str(item["date"]),
                    time=str(item["time"]),
                    amount_ml=int(item["amount_ml"]),
                    category=str(item["category"]),
                    note=str(item.get("note", "")),
                )
                for item in raw
            ]
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        backup = f"{json_path}.corrupt_{datetime.now().strftime('%H%M%S')}.bak"
        os.rename(json_path, backup)
        print(f"\033[91m[Recovery] Corrupted JSON backed up to '{backup}'. Re-seeded clean dataset.\033[0m")
        seeded = seed_realistic_data(42)
        save_entries(seeded, json_path, csv_path)
        return seeded


def bulk_import_csv(
    filepath: str,
    existing: List[WaterEntry],
    json_path: str = JSON_PATH,
    csv_path: str = CSV_PATH,
) -> Tuple[int, List[str]]:
    if not os.path.exists(filepath):
        return 0, [f"File not found: {filepath}"]
    imported = 0
    errors: List[str] = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, start=2):
            try:
                d = (row.get("date") or "").strip()
                datetime.strptime(d, "%Y-%m-%d")
                t = (row.get("time") or "12:00").strip() or "12:00"
                datetime.strptime(t, "%H:%M")
                amt = int((row.get("amount_ml") or "").strip())
                if not (MIN_VOLUME_ML <= amt <= MAX_VOLUME_ML):
                    raise ValueError(f"amount_ml {amt} out of range ({MIN_VOLUME_ML}-{MAX_VOLUME_ML})")
                cat = (row.get("category") or "Plain Water").strip() or "Plain Water"
                note = (row.get("note") or "Bulk import").strip()
                existing.append(
                    WaterEntry(
                        entry_id=f"IMP-{1000 + len(existing) + imported}",
                        date=d,
                        time=t,
                        amount_ml=amt,
                        category=cat,
                        note=note,
                    )
                )
                imported += 1
            except Exception as exc:
                errors.append(f"Row {row_idx}: {exc}")
    if imported:
        save_entries(existing, json_path, csv_path)
    return imported, errors
