import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
WEB_PORT = int(os.environ.get("WEB_PORT", "8080"))

# Username менеджера (без @) - для кнопки "Связаться с менеджером"
MANAGER_USERNAME = os.environ.get("MANAGER_USERNAME")

# ✅ Числовой ID менеджера - туда будут приходить заказы
# Узнать через @userinfobot в Telegram
MANAGER_ID = int(os.environ.get("MANAGER_ID", "0"))

# Проверка при загрузке
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан в переменных окружения!")
if ADMIN_ID == 0:
    raise ValueError("❌ ADMIN_ID не задан в переменных окружения!")

print(f"✅ Конфиг загружен:")
print(f"   ADMIN_ID = {ADMIN_ID}")
print(f"   MANAGER_USERNAME = @{MANAGER_USERNAME}")
print(f"   MANAGER_ID = {MANAGER_ID if MANAGER_ID else 'не задан (заказы пойдут админу)'}")
