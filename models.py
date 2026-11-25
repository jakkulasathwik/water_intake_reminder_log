from dataclasses import dataclass, asdict


@dataclass
class WaterEntry:
    entry_id: str
    date: str          # YYYY-MM-DD
    time: str          # HH:MM
    amount_ml: int
    category: str
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DailySummary:
    date: str
    total_ml: int
    target_ml: int
    completion_pct: float
    entry_count: int
    status: str
