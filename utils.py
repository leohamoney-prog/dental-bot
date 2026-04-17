from datetime import datetime, timedelta, date
from config import WORK_START, WORK_END, BOOKING_DAYS_AHEAD

MONTHS_RU = ["января","февраля","марта","апреля","мая","июня",
             "июля","августа","сентября","октября","ноября","декабря"]
DAYS_RU   = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]


def generate_time_slots() -> list[str]:
    slots, cur = [], datetime.strptime(f"{WORK_START:02d}:00", "%H:%M")
    end = datetime.strptime(f"{WORK_END:02d}:00", "%H:%M")
    while cur < end:
        slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=30)
    return slots


def free_slots(booked: list[str]) -> list[str]:
    return [s for s in generate_time_slots() if s not in booked]


def get_available_dates() -> list[date]:
    result, today = [], date.today()
    for i in range(1, BOOKING_DAYS_AHEAD + 1):
        d = today + timedelta(days=i)
        if d.weekday() < 6:          # пн–сб
            result.append(d)
    return result


def fmt_date(date_str: str) -> str:
    """YYYY-MM-DD → 'Пн, 5 января'"""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return f"{DAYS_RU[d.weekday()]}, {d.day} {MONTHS_RU[d.month-1]}"


def tomorrow_str() -> str:
    return (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")


def patient_full_name(p: dict) -> str:
    parts = [p.get("lastName",""), p.get("firstName",""), p.get("middleName","")]
    return " ".join(x for x in parts if x).strip() or "Без имени"
