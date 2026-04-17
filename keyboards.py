from aiogram.types import (InlineKeyboardMarkup, InlineKeyboardButton,
                            ReplyKeyboardMarkup, KeyboardButton)
from config import SERVICES
from utils import get_available_dates, fmt_date


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Записаться на приём")],
            [KeyboardButton(text="📋 Мои записи")],
            [KeyboardButton(text="❌ Отменить запись")],
            [KeyboardButton(text="👤 Мои данные")],
        ],
        resize_keyboard=True
    )


def dates_kb() -> InlineKeyboardMarkup:
    buttons = []
    for d in get_available_dates():
        ds = d.strftime("%Y-%m-%d")
        buttons.append([InlineKeyboardButton(text=fmt_date(ds), callback_data=f"date:{ds}")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def times_kb(free: list[str]) -> InlineKeyboardMarkup:
    rows, row = [], []
    for i, slot in enumerate(free):
        row.append(InlineKeyboardButton(text=slot, callback_data=f"time:{slot}"))
        if len(row) == 4:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_date"),
                 InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def services_kb() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=s, callback_data=f"svc:{s}")] for s in SERVICES]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_time"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm"),
         InlineKeyboardButton(text="◀️ Изменить", callback_data="back_service")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])


def attendance_kb(appt_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, приду!", callback_data=f"attend:yes:{appt_id}"),
         InlineKeyboardButton(text="❌ Не приду",   callback_data=f"attend:no:{appt_id}")]
    ])


def cancel_list_kb(appointments: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for a in appointments:
        label = f"{fmt_date(a['date'])} {a['time']} — {a.get('service','')[:20]}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"do_cancel:{a['id']}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def patients_kb(patients: list[dict]) -> InlineKeyboardMarkup:
    """Список пациентов для связки аккаунта."""
    from utils import patient_full_name
    buttons = []
    for p in patients[:20]:   # максимум 20 вариантов
        name = patient_full_name(p)
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"link:{p['id']}")])
    buttons.append([InlineKeyboardButton(text="➕ Создать нового пациента", callback_data="new_patient")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
