import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))  # ✅ Преобразуем строку в число
WEB_PORT = int(os.environ.get("WEB_PORT", "8080"))

# Проверка при загрузке
if not BOT_TOKEN:
    raise ValueError(" BOT_TOKEN не задан в переменных окружения!")
if ADMIN_ID == 0:
    raise ValueError("❌ ADMIN_ID не задан в переменных окружения!")

print(f"✅ Конфиг загружен: ADMIN_ID={ADMIN_ID} (тип: {type(ADMIN_ID).__name__})")
