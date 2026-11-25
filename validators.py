import re
from datetime import datetime
from typing import List

CATEGORIES = [
    "Plain Water",
    "Electrolyte / Sports",
    "Herbal Tea",
    "Infused Water",
    "Sparkling Water",
]
MIN_VOLUME_ML = 10
MAX_VOLUME_ML = 3000


def get_valid_int(prompt: str, min_val: int, max_val: int) -> int:
    while True:
        raw = input(prompt).strip()
        if not raw:
            print("\033[91m[Validation Error] Input cannot be blank.\033[0m")
            continue
        try:
            value = int(raw)
            if not (min_val <= value <= max_val):
                print(f"\033[91m[Range Error] Enter a value between {min_val} and {max_val}.\033[0m")
                continue
            return value
        except ValueError:
            print(f"\033[91m[Type Error] '{raw}' is not a valid whole number.\033[0m")


def get_valid_date(prompt: str, allow_today_default: bool = True) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    while True:
        raw = input(prompt).strip()
        if not raw and allow_today_default:
            return today
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
            print(f"\033[91m[Format Error] Expected YYYY-MM-DD (e.g., {today}).\033[0m")
            continue
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            return raw
        except ValueError:
            print("\033[91m[Date Error] Invalid calendar date.\033[0m")


def get_valid_time(prompt: str, allow_now_default: bool = True) -> str:
    now_str = datetime.now().strftime("%H:%M")
    while True:
        raw = input(prompt).strip()
        if not raw and allow_now_default:
            return now_str
        if not re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", raw):
            print(f"\033[91m[Format Error] Expected 24-hour HH:MM (e.g., {now_str}).\033[0m")
            continue
        return raw


def get_valid_category(prompt: str, categories: List[str] = CATEGORIES) -> str:
    print("\nAvailable Categories:")
    for idx, cat in enumerate(categories, start=1):
        print(f"  {idx}. {cat}")
    choice = get_valid_int(prompt, 1, len(categories))
    return categories[choice - 1]
