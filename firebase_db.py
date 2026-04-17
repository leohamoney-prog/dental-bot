import os, json, logging
from datetime import datetime, date
import firebase_admin
from firebase_admin import credentials, firestore_async
from google.cloud.firestore_v1 import AsyncClient

logger = logging.getLogger(__name__)
_db = None

def get_db():
    global _db
    if _db is None:
        raise RuntimeError("Firebase не инициализирован")
    return _db

def init_firebase():
    global _db
    cred_json = os.getenv("GOOGLE_CREDENTIALS")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
    else:
        cred = credentials.Certificate("serviceAccountKey.json")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    _db = firestore_async.client()
    logger.info("Firebase Firestore подключён ✅")

async def find_patient_by_telegram(telegram_id):
    db = get_db()
    async for doc in db.collection("patients").where("telegramId","==",telegram_id).limit(1).stream():
        return {"id": doc.id, **doc.to_dict()}
    return None

async def find_patient_by_phone(phone):
    db = get_db()
    clean = phone.replace(" ","").replace("-","").replace("(","").replace(")","")
    async for doc in db.collection("patients").stream():
        data = doc.to_dict()
        stored = (data.get("phone","") or "").replace(" ","").replace("-","").replace("(","").replace(")","")
        if stored == clean:
            return {"id": doc.id, **data}
    return None

async def get_all_patients():
    db = get_db()
    result = []
    async for doc in db.collection("patients").stream():
        result.append({"id": doc.id, **doc.to_dict()})
    result.sort(key=lambda p: p.get("lastName",""))
    return result

async def link_telegram_to_patient(patient_id, telegram_id):
    await get_db().collection("patients").document(patient_id).update({"telegramId": telegram_id})

async def create_patient_from_bot(telegram_id, last_name, first_name, phone):
    db = get_db()
    data = {"lastName": last_name, "firstName": first_name, "middleName": "",
            "phone": phone, "email": "", "address": "", "allergies": "",
            "notes": "Telegram-бот", "telegramId": telegram_id,
            "createdAt": datetime.utcnow().isoformat()}
    ref = await db.collection("patients").add(data)
    return {"id": ref[1].id, **data}

async def get_patient_by_id(patient_id):
    doc = await get_db().collection("patients").document(patient_id).get()
    return {"id": doc.id, **doc.to_dict()} if doc.exists else None

async def get_booked_slots(target_date):
    db = get_db()
    slots = []
    async for doc in db.collection("appointments").where("date","==",target_date).stream():
        d = doc.to_dict()
        if d.get("status") in ["scheduled","confirmed"] and d.get("time"):
            slots.append(d["time"])
    return slots

async def create_appointment(patient_id, patient_name, appt_date, appt_time, service):
    db = get_db()
    data = {"patientId": patient_id, "patientName": patient_name,
            "date": appt_date, "time": appt_time, "service": service,
            "cost": 0, "paid": 0, "status": "scheduled",
            "notes": "Telegram-бот", "remindBefore": "1day",
            "notified": False, "createdAt": datetime.utcnow().isoformat()}
    ref = await db.collection("appointments").add(data)
    return ref[1].id

async def get_patient_appointments(patient_id):
    db = get_db()
    today = date.today().isoformat()
    result = []
    async for doc in db.collection("appointments").where("patientId","==",patient_id).stream():
        d = doc.to_dict()
        if d.get("status") in ["scheduled","confirmed"] and d.get("date","") >= today:
            result.append({"id": doc.id, **d})
    result.sort(key=lambda a: (a.get("date",""), a.get("time","")))
    return result

async def get_appointment_by_id(appt_id):
    doc = await get_db().collection("appointments").document(appt_id).get()
    return {"id": doc.id, **doc.to_dict()} if doc.exists else None

async def update_appointment_status(appt_id, status):
    await get_db().collection("appointments").document(appt_id).update({"status": status})

async def cancel_appointment(appt_id):
    await update_appointment_status(appt_id, "cancelled")

async def get_appointments_for_reminder(tomorrow):
    db = get_db()
    result = []
    async for doc in db.collection("appointments").where("date","==",tomorrow).stream():
        d = doc.to_dict()
        if d.get("status") == "scheduled" and not d.get("notified"):
            result.append({"id": doc.id, **d})
    return result

async def mark_appointment_notified(appt_id):
    await get_db().collection("appointments").document(appt_id).update({"notified": True})

async def get_upcoming_appointments_admin():
    db = get_db()
    today = date.today().isoformat()
    result = []
    async for doc in db.collection("appointments").stream():
        d = doc.to_dict()
        if d.get("status") in ["scheduled","confirmed"] and d.get("date","") >= today:
            result.append({"id": doc.id, **d})
    result.sort(key=lambda a: (a.get("date",""), a.get("time","")))
    return result
