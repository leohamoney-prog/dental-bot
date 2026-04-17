"""
Работа с Firebase Firestore.

Структура коллекций (совпадает с веб-приложением):
  patients/          — пациенты
    {id}/
      firstName, lastName, middleName
      phone, email, address
      allergies, notes
      birthDate
      telegramId      ← добавляем при первой регистрации через бота

  appointments/      — записи на приём
    {id}/
      patientId       — ссылка на patients/{id}
      date            — "YYYY-MM-DD"
      time            — "HH:MM"
      service         — вид работы
      cost, paid      — стоимость / оплачено
      status          — "scheduled" | "confirmed" | "cancelled" | "done"
      notes
      remindBefore    — за сколько напоминать
      notified        — bool, отправлено ли напоминание
      createdAt
"""

import logging
from datetime import datetime, date
from google.cloud.firestore_v1 import AsyncClient
import firebase_admin
from firebase_admin import credentials, firestore_async
from config import FIREBASE_CREDENTIALS

logger = logging.getLogger(__name__)

_db: AsyncClient | None = None


def get_db() -> AsyncClient:
    global _db
    if _db is None:
        raise RuntimeError("Firebase не инициализирован. Вызови init_firebase() сначала.")
    return _db


def init_firebase():
    global _db
    cred = credentials.Certificate(FIREBASE_CREDENTIALS)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    _db = firestore_async.client()
    logger.info("Firebase Firestore подключён ✅")


# ══════════════════════════════════════════════════════════════════
#  ПАЦИЕНТЫ
# ══════════════════════════════════════════════════════════════════

async def find_patient_by_telegram(telegram_id: int) -> dict | None:
    """Ищет пациента по telegramId."""
    db = get_db()
    docs = db.collection("patients").where("telegramId", "==", telegram_id).limit(1)
    async for doc in await docs.get():
        return {"id": doc.id, **doc.to_dict()}
    return None


async def find_patient_by_phone(phone: str) -> dict | None:
    """Ищет пациента по номеру телефона."""
    db = get_db()
    # Нормализуем телефон
    clean = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    docs = db.collection("patients").stream()
    async for doc in docs:
        data = doc.to_dict()
        stored = (data.get("phone", "") or "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if stored == clean:
            return {"id": doc.id, **data}
    return None


async def get_all_patients() -> list[dict]:
    db = get_db()
    result = []
    async for doc in db.collection("patients").stream():
        result.append({"id": doc.id, **doc.to_dict()})
    # Сортируем по фамилии
    result.sort(key=lambda p: p.get("lastName", ""))
    return result


async def link_telegram_to_patient(patient_id: str, telegram_id: int):
    """Привязывает Telegram ID к существующему пациенту."""
    db = get_db()
    await db.collection("patients").document(patient_id).update({
        "telegramId": telegram_id
    })


async def create_patient_from_bot(telegram_id: int, last_name: str,
                                   first_name: str, phone: str) -> dict:
    """Создаёт нового пациента через бота."""
    db = get_db()
    data = {
        "lastName":   last_name,
        "firstName":  first_name,
        "middleName": "",
        "phone":      phone,
        "email":      "",
        "address":    "",
        "allergies":  "",
        "notes":      "Зарегистрирован через Telegram-бот",
        "telegramId": telegram_id,
        "createdAt":  datetime.utcnow().isoformat(),
    }
    ref = await db.collection("patients").add(data)
    return {"id": ref[1].id, **data}


async def get_patient_by_id(patient_id: str) -> dict | None:
    db = get_db()
    doc = await db.collection("patients").document(patient_id).get()
    if doc.exists:
        return {"id": doc.id, **doc.to_dict()}
    return None


# ══════════════════════════════════════════════════════════════════
#  ЗАПИСИ НА ПРИЁМ
# ══════════════════════════════════════════════════════════════════

async def get_booked_slots(target_date: str) -> list[str]:
    """Возвращает список занятых времён на дату."""
    db = get_db()
    slots = []
    query = db.collection("appointments")\
              .where("date", "==", target_date)\
              .where("status", "in", ["scheduled", "confirmed"])
    async for doc in await query.get():
        t = doc.to_dict().get("time", "")
        if t:
            slots.append(t)
    return slots


async def create_appointment(patient_id: str, patient_name: str,
                              appt_date: str, appt_time: str,
                              service: str) -> str:
    """Создаёт запись в Firestore. Возвращает ID."""
    db = get_db()
    data = {
        "patientId":   patient_id,
        "patientName": patient_name,   # денормализованное имя для удобства
        "date":        appt_date,
        "time":        appt_time,
        "service":     service,
        "cost":        0,
        "paid":        0,
        "status":      "scheduled",
        "notes":       "Запись через Telegram-бот",
        "remindBefore": "1day",
        "notified":    False,
        "createdAt":   datetime.utcnow().isoformat(),
    }
    ref = await db.collection("appointments").add(data)
    return ref[1].id


async def get_patient_appointments(patient_id: str) -> list[dict]:
    """Активные записи пациента (будущие)."""
    db = get_db()
    today = date.today().isoformat()
    result = []
    query = db.collection("appointments")\
              .where("patientId", "==", patient_id)\
              .where("status", "in", ["scheduled", "confirmed"])
    async for doc in await query.get():
        d = doc.to_dict()
        if d.get("date", "") >= today:
            result.append({"id": doc.id, **d})
    result.sort(key=lambda a: (a.get("date",""), a.get("time","")))
    return result


async def get_appointment_by_id(appt_id: str) -> dict | None:
    db = get_db()
    doc = await db.collection("appointments").document(appt_id).get()
    if doc.exists:
        return {"id": doc.id, **doc.to_dict()}
    return None


async def update_appointment_status(appt_id: str, status: str):
    db = get_db()
    await db.collection("appointments").document(appt_id).update({
        "status": status
    })


async def get_appointments_for_reminder(tomorrow: str) -> list[dict]:
    """Записи на завтра, которым ещё не отправляли напоминание."""
    db = get_db()
    result = []
    query = db.collection("appointments")\
              .where("date", "==", tomorrow)\
              .where("status", "==", "scheduled")\
              .where("notified", "==", False)
    async for doc in await query.get():
        result.append({"id": doc.id, **doc.to_dict()})
    return result


async def mark_appointment_notified(appt_id: str):
    db = get_db()
    await db.collection("appointments").document(appt_id).update({
        "notified": True
    })


async def cancel_appointment(appt_id: str):
    await update_appointment_status(appt_id, "cancelled")


async def get_upcoming_appointments_admin() -> list[dict]:
    """Все предстоящие записи для врача (/schedule)."""
    db = get_db()
    today = date.today().isoformat()
    result = []
    query = db.collection("appointments")\
              .where("status", "in", ["scheduled", "confirmed"])
    async for doc in await query.get():
        d = doc.to_dict()
        if d.get("date", "") >= today:
            result.append({"id": doc.id, **d})
    result.sort(key=lambda a: (a.get("date",""), a.get("time","")))
    return result
