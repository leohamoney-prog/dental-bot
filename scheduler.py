import asyncio
import logging
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import ADMIN_CHAT_ID, REMINDER_HOUR
from firebase_db import (get_appointments_for_reminder,
                          mark_appointment_notified, get_patient_by_id)
from keyboards import attendance_kb
from utils import fmt_date, tomorrow_str, patient_full_name

logger = logging.getLogger(__name__)


async def send_reminders(bot: Bot):
    tomorrow = tomorrow_str()
    appointments = await get_appointments_for_reminder(tomorrow)
    logger.info(f"Напоминания на {tomorrow}: найдено {len(appointments)}")

    for appt in appointments:
        # Получаем пациента чтобы узнать telegramId
        patient = await get_patient_by_id(appt["patientId"])
        if not patient:
            continue

        tg_id = patient.get("telegramId")
        if not tg_id:
            logger.warning(f"Нет telegramId у пациента {patient.get('id')}")
            continue

        name = patient_full_name(patient)
        try:
            await bot.send_message(
                tg_id,
                f"🦷 <b>Напоминание о приёме!</b>\n\n"
                f"Завтра, <b>{fmt_date(appt['date'])}</b> в <b>{appt['time']}</b>\n"
                f"📋 {appt.get('service','')}\n\n"
                f"Вы придёте на приём?",
                parse_mode="HTML",
                reply_markup=attendance_kb(appt["id"])
            )
            await mark_appointment_notified(appt["id"])
            logger.info(f"Напоминание отправлено: {name}")
        except Exception as e:
            logger.error(f"Ошибка напоминания {appt['id']}: {e}")

        await asyncio.sleep(0.1)


async def start_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        send_reminders,
        trigger="cron",
        hour=REMINDER_HOUR,
        minute=0,
        args=[bot],
        id="reminders",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Планировщик запущен ✅ (напоминания в {REMINDER_HOUR}:00 МСК)")
