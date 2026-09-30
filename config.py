import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

if not BOT_TOKEN or not ADMIN_ID:
    raise ValueError("Ошибка: Не указаны BOT_TOKEN или ADMIN_ID в переменных окружения!")

WEB_PORT = int(os.environ.get("PORT", 8080))
DB_PATH = "cloudshop.db"
