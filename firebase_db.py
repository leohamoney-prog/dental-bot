import os, json, logging
from datetime import datetime, date
import firebase_admin
from firebase_admin import credentials, firestore_async
from google.cloud.firestore_v1 import AsyncClient

logger = logging.getLogger(__name__)
_db: AsyncClient | None = None

def get_db() -> AsyncClient:
    global _db
    if _db is None:
        raise RuntimeError("Firebase не инициализирован")
    return _db

def init_firebase():
    global _db
    cred_json = os.getenv("GOOGLE_CREDENTIALS")
    if cred_json:
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
    else:
        cred = credentials.Certificate("serviceAccountKey.json")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    _db = firestore_async.client()
    logger.info("Firebase Firestore подключён ✅")
