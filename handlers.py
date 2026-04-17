from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_CHAT_ID
from firebase_db import (
    find_patient_by_telegram, find_patient_by_phone,
    create_patient_from_bot, link_telegram_to_patient,
    get_all_patients, get_patient_by_id,
    get_booked_slots, create_appointment,
    get_patient_appointments, get_appointment_by_id,
    update_appointment_status, cancel_appointment,
    get_upcoming_appointments_admin,
)
from keyboards import (main_menu_kb, dates_kb, times_kb, services_kb,
                        confirm_kb, cancel_list_kb, patients_kb)
from utils import free_slots, fmt_date, patient_full_name

patient_router = Router()
admin_router   = Router()


# ══════════════════════════════════════════════════════════════════
#  FSM
# ══════════════════════════════════════════════════════════════════

class LinkFSM(StatesGroup):
    search_phone = State()   # поиск по телефону или выбор из списка
    new_lastname  = State()
    new_firstname = State()
    new_phone     = State()

class BookingFSM(StatesGroup):
    date    = State()
    time    = State()
    service = State()
    confirm = State()


# ══════════════════════════════════════════════════════════════════
#  СТАРТ — привязка к базе пациентов
# ══════════════════════════════════════════════════════════════════

@patient_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    patient = await find_patient_by_telegram(message.from_user.id)

    if patient:
        name = patient_full_name(patient)
        await message.answer(
            f"👋 С возвращением, <b>{name}</b>!\n"
            "Выберите действие 👇",
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )
        return

    # Пациент не найден — предлагаем связать аккаунт
    await message.answer(
        "👋 Добро пожаловать в <b>Стоматологический кабинет</b>!\n\n"
        "📱 Введите ваш <b>номер телефона</b>, который вы указывали при регистрации,\n"
        "чтобы связать Telegram с вашей картой пациента:",
        parse_mode="HTML"
    )
    await state.set_state(LinkFSM.search_phone)


@patient_router.message(LinkFSM.search_phone)
async def link_by_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    patient = await find_patient_by_phone(phone)

    if patient:
        # Нашли — привязываем Telegram ID
        await link_telegram_to_patient(patient["id"], message.from_user.id)
        await state.clear()
        name = patient_full_name(patient)
        await message.answer(
            f"✅ Аккаунт привязан!\n\n"
            f"👤 Ваша карта: <b>{name}</b>\n"
            f"📱 Телефон: {patient.get('phone','')}\n\n"
            "Теперь вы можете записаться на приём 👇",
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )
    else:
        # Не нашли — предлагаем выбрать из списка или создать нового
        await message.answer(
            "🔍 Пациент с таким номером не найден.\n\n"
            "Выберите своё имя из списка или создайте новую карту:"
        )
        patients = await get_all_patients()
        await message.answer(
            "Выберите себя в списке:",
            reply_markup=patients_kb(patients)
        )


@patient_router.callback_query(F.data.startswith("link:"))
async def link_existing(call: CallbackQuery, state: FSMContext):
    patient_id = call.data.split(":")[1]
    await link_telegram_to_patient(patient_id, call.from_user.id)
    patient = await get_patient_by_id(patient_id)
    await state.clear()
    await call.message.edit_text(
        f"✅ Аккаунт привязан к карте: <b>{patient_full_name(patient)}</b>",
        parse_mode="HTML"
    )
    await call.message.answer("Главное меню:", reply_markup=main_menu_kb())


@patient_router.callback_query(F.data == "new_patient")
async def new_patient_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("📝 Введите вашу <b>Фамилию</b>:", parse_mode="HTML")
    await state.set_state(LinkFSM.new_lastname)


@patient_router.message(LinkFSM.new_lastname)
async def new_patient_lastname(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text.strip())
    await message.answer("📝 Введите ваше <b>Имя</b>:", parse_mode="HTML")
    await state.set_state(LinkFSM.new_firstname)


@patient_router.message(LinkFSM.new_firstname)
async def new_patient_firstname(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text.strip())
    await message.answer("📱 Введите ваш <b>номер телефона</b>:", parse_mode="HTML")
    await state.set_state(LinkFSM.new_phone)


@patient_router.message(LinkFSM.new_phone)
async def new_patient_phone(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    patient = await create_patient_from_bot(
        message.from_user.id,
        data["last_name"],
        data["first_name"],
        message.text.strip()
    )
    await state.clear()
    name = patient_full_name(patient)
    await message.answer(
        f"🎉 Карта пациента создана!\n\n"
        f"👤 {name}\n"
        f"📱 {patient.get('phone','')}\n\n"
        "Теперь вы можете записаться на приём 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )
    # Уведомление врачу
    await bot.send_message(
        ADMIN_CHAT_ID,
        f"🆕 <b>Новый пациент зарегистрировался через бота!</b>\n\n"
        f"👤 {name}\n"
        f"📱 {patient.get('phone','')}",
        parse_mode="HTML"
    )


# ══════════════════════════════════════════════════════════════════
#  ЗАПИСЬ НА ПРИЁМ
# ══════════════════════════════════════════════════════════════════

@patient_router.message(F.text == "📅 Записаться на приём")
async def book_start(message: Message, state: FSMContext):
    patient = await find_patient_by_telegram(message.from_user.id)
    if not patient:
        await message.answer("⚠️ Сначала зарегистрируйтесь. Введите /start")
        return
    await state.clear()
    await message.answer("📅 Выберите удобный день:", reply_markup=dates_kb())
    await state.set_state(BookingFSM.date)


@patient_router.callback_query(BookingFSM.date, F.data.startswith("date:"))
async def book_date(call: CallbackQuery, state: FSMContext):
    appt_date = call.data.split(":")[1]
    booked = await get_booked_slots(appt_date)
    slots  = free_slots(booked)
    if not slots:
        await call.answer("😔 На этот день нет свободных слотов", show_alert=True)
        return
    await state.update_data(date=appt_date)
    await call.message.edit_text(
        f"📅 <b>{fmt_date(appt_date)}</b>\n\n⏰ Выберите время:",
        parse_mode="HTML",
        reply_markup=times_kb(slots)
    )
    await state.set_state(BookingFSM.time)


@patient_router.callback_query(BookingFSM.time, F.data.startswith("time:"))
async def book_time(call: CallbackQuery, state: FSMContext):
    t = call.data.split(":")[1]
    await state.update_data(time=t)
    data = await state.get_data()
    await call.message.edit_text(
        f"📅 {fmt_date(data['date'])}  🕐 {t}\n\n🦷 Выберите вид работы:",
        parse_mode="HTML",
        reply_markup=services_kb()
    )
    await state.set_state(BookingFSM.service)


@patient_router.callback_query(BookingFSM.service, F.data.startswith("svc:"))
async def book_service(call: CallbackQuery, state: FSMContext):
    service = call.data[4:]
    await state.update_data(service=service)
    data    = await state.get_data()
    patient = await find_patient_by_telegram(call.from_user.id)
    await call.message.edit_text(
        f"📋 <b>Подтвердите запись:</b>\n\n"
        f"👤 {patient_full_name(patient)}\n"
        f"📅 {fmt_date(data['date'])}\n"
        f"🕐 {data['time']}\n"
        f"🦷 {service}",
        parse_mode="HTML",
        reply_markup=confirm_kb()
    )
    await state.set_state(BookingFSM.confirm)


@patient_router.callback_query(BookingFSM.confirm, F.data == "confirm")
async def book_confirm(call: CallbackQuery, state: FSMContext, bot: Bot):
    data    = await state.get_data()
    patient = await find_patient_by_telegram(call.from_user.id)
    await state.clear()

    name    = patient_full_name(patient)
    appt_id = await create_appointment(
        patient["id"], name,
        data["date"], data["time"], data["service"]
    )

    await call.message.edit_text(
        f"✅ <b>Запись подтверждена!</b>\n\n"
        f"📅 {fmt_date(data['date'])}\n"
        f"🕐 {data['time']}\n"
        f"🦷 {data['service']}\n\n"
        f"Напомним за сутки до приёма 🔔",
        parse_mode="HTML"
    )
    await call.message.answer("Главное меню:", reply_markup=main_menu_kb())

    # Уведомление врачу
    await bot.send_message(
        ADMIN_CHAT_ID,
        f"🆕 <b>Новая запись!</b>\n\n"
        f"👤 {name}\n"
        f"📱 {patient.get('phone','')}\n"
        f"📅 {fmt_date(data['date'])}\n"
        f"🕐 {data['time']}\n"
        f"🦷 {data['service']}",
        parse_mode="HTML"
    )


# ── Навигация назад ───────────────────────────────────────────────

@patient_router.callback_query(F.data == "back_date")
async def back_date(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("📅 Выберите удобный день:", reply_markup=dates_kb())
    await state.set_state(BookingFSM.date)

@patient_router.callback_query(F.data == "back_time")
async def back_time(call: CallbackQuery, state: FSMContext):
    data   = await state.get_data()
    booked = await get_booked_slots(data.get("date",""))
    slots  = free_slots(booked)
    await call.message.edit_text(
        f"📅 {fmt_date(data['date'])}\n\n⏰ Выберите время:",
        parse_mode="HTML",
        reply_markup=times_kb(slots)
    )
    await state.set_state(BookingFSM.time)

@patient_router.callback_query(F.data == "back_service")
async def back_service(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await call.message.edit_text(
        f"📅 {fmt_date(data['date'])}  🕐 {data['time']}\n\n🦷 Выберите вид работы:",
        parse_mode="HTML",
        reply_markup=services_kb()
    )
    await state.set_state(BookingFSM.service)

@patient_router.callback_query(F.data == "cancel")
async def cancel_cb(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Действие отменено.")
    await call.message.answer("Главное меню:", reply_markup=main_menu_kb())


# ══════════════════════════════════════════════════════════════════
#  МОИ ЗАПИСИ
# ══════════════════════════════════════════════════════════════════

@patient_router.message(F.text == "📋 Мои записи")
async def my_appointments(message: Message):
    patient = await find_patient_by_telegram(message.from_user.id)
    if not patient:
        await message.answer("⚠️ Введите /start для регистрации")
        return
    apts = await get_patient_appointments(patient["id"])
    if not apts:
        await message.answer("У вас нет активных записей.", reply_markup=main_menu_kb())
        return
    text = "📋 <b>Ваши записи:</b>\n\n"
    for a in apts:
        icon = "✅" if a["status"] == "confirmed" else "🕐"
        text += f"{icon} <b>{fmt_date(a['date'])}</b> в {a['time']}\n   🦷 {a.get('service','')}\n\n"
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())


# ══════════════════════════════════════════════════════════════════
#  ОТМЕНА ЗАПИСИ
# ══════════════════════════════════════════════════════════════════

@patient_router.message(F.text == "❌ Отменить запись")
async def cancel_start(message: Message):
    patient = await find_patient_by_telegram(message.from_user.id)
    if not patient:
        await message.answer("⚠️ Введите /start для регистрации")
        return
    apts = await get_patient_appointments(patient["id"])
    if not apts:
        await message.answer("У вас нет активных записей.", reply_markup=main_menu_kb())
        return
    await message.answer("Выберите запись для отмены:", reply_markup=cancel_list_kb(apts))


@patient_router.callback_query(F.data.startswith("do_cancel:"))
async def do_cancel(call: CallbackQuery, bot: Bot):
    appt_id = call.data.split(":")[1]
    appt    = await get_appointment_by_id(appt_id)
    await cancel_appointment(appt_id)
    await call.message.edit_text(
        f"✅ Запись на <b>{fmt_date(appt['date'])}</b> в {appt['time']} отменена.",
        parse_mode="HTML"
    )
    await call.message.answer("Главное меню:", reply_markup=main_menu_kb())

    patient = await find_patient_by_telegram(call.from_user.id)
    await bot.send_message(
        ADMIN_CHAT_ID,
        f"⚠️ <b>Пациент отменил запись</b>\n\n"
        f"👤 {patient_full_name(patient)}\n"
        f"📱 {patient.get('phone','')}\n"
        f"📅 {fmt_date(appt['date'])} в {appt['time']}\n"
        f"🦷 {appt.get('service','')}",
        parse_mode="HTML"
    )


# ══════════════════════════════════════════════════════════════════
#  МОИ ДАННЫЕ
# ══════════════════════════════════════════════════════════════════

@patient_router.message(F.text == "👤 Мои данные")
async def my_data(message: Message):
    patient = await find_patient_by_telegram(message.from_user.id)
    if not patient:
        await message.answer("⚠️ Введите /start")
        return
    await message.answer(
        f"👤 <b>Ваша карта пациента:</b>\n\n"
        f"Имя: {patient_full_name(patient)}\n"
        f"📱 Телефон: {patient.get('phone','—')}\n"
        f"🎂 Дата рождения: {patient.get('birthDate','—')}\n"
        f"⚠️ Аллергии: {patient.get('allergies','—')}",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


# ══════════════════════════════════════════════════════════════════
#  ОТВЕТ НА НАПОМИНАНИЕ (приду / не приду)
# ══════════════════════════════════════════════════════════════════

@patient_router.callback_query(F.data.startswith("attend:"))
async def attend_response(call: CallbackQuery, bot: Bot):
    _, answer, appt_id = call.data.split(":", 2)
    appt = await get_appointment_by_id(appt_id)
    patient = await find_patient_by_telegram(call.from_user.id)
    name = patient_full_name(patient) if patient else "Пациент"

    if answer == "yes":
        await update_appointment_status(appt_id, "confirmed")
        await call.message.edit_text(
            f"✅ Отлично! Ждём вас <b>{fmt_date(appt['date'])}</b> в <b>{appt['time']}</b>.\n"
            f"🦷 {appt.get('service','')}",
            parse_mode="HTML"
        )
        admin_msg = (f"✅ <b>Пациент подтвердил визит</b>\n\n"
                     f"👤 {name}\n📱 {patient.get('phone','') if patient else ''}\n"
                     f"📅 {fmt_date(appt['date'])} в {appt['time']}\n🦷 {appt.get('service','')}")
    else:
        await update_appointment_status(appt_id, "cancelled")
        await call.message.edit_text(
            "❌ Понял, запись отменена.\n"
            "Для новой записи нажмите /start"
        )
        admin_msg = (f"❌ <b>Пациент НЕ придёт!</b>\n\n"
                     f"👤 {name}\n📱 {patient.get('phone','') if patient else ''}\n"
                     f"📅 {fmt_date(appt['date'])} в {appt['time']}\n🦷 {appt.get('service','')}")

    await bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="HTML")
    await call.answer()


# ══════════════════════════════════════════════════════════════════
#  ADMIN
# ══════════════════════════════════════════════════════════════════

@admin_router.message(Command("schedule"))
async def admin_schedule(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    apts = await get_upcoming_appointments_admin()
    if not apts:
        await message.answer("Нет предстоящих записей.")
        return
    text, prev_date = "📅 <b>Предстоящие записи:</b>\n", None
    for a in apts:
        if a["date"] != prev_date:
            text += f"\n📆 <b>{fmt_date(a['date'])}</b>\n"
            prev_date = a["date"]
        icon = {"scheduled":"🕐","confirmed":"✅","cancelled":"❌"}.get(a["status"],"🕐")
        text += f"  {icon} {a['time']} — {a.get('patientName','?')} — {a.get('service','')}\n"
    await message.answer(text, parse_mode="HTML")


@admin_router.message(Command("help"))
async def admin_help(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    await message.answer(
        "🔧 <b>Команды врача:</b>\n\n"
        "/schedule — все предстоящие записи\n"
        "/help — справка",
        parse_mode="HTML"
    )
