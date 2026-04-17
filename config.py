import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────
BOT_TOKEN     = os.getenv("BOT_TOKEN",     "СЮДА_ТОКЕН_БОТА")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))  # твой Telegram ID

# ── Firebase ──────────────────────────────────────────────────────
# Путь к файлу serviceAccountKey.json (скачивается из Firebase Console)
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS", "serviceAccountKey.json")

# ── Расписание ────────────────────────────────────────────────────
WORK_START        = 9    # начало рабочего дня
WORK_END          = 18   # конец рабочего дня
BOOKING_DAYS_AHEAD = 14  # на сколько дней вперёд можно записаться
REMINDER_HOUR     = 10   # во сколько отправлять напоминания (по МСК)

# ── Виды работ (берём из твоего приложения) ───────────────────────
SERVICES = [
    "🦷 Лечение кариеса",
    "🪥 Профессиональная чистка",
    "🔧 Установка пломбы",
    "👑 Установка коронки",
    "🦷 Удаление зуба",
    "✨ Отбеливание",
    "🔬 Диагностика / Консультация",
    "🩺 Другое",
]
