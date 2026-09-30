import asyncio
import json
import os
from pathlib import Path
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
import aiosqlite

from config import BOT_TOKEN, ADMIN_ID, WEB_PORT, DB_PATH
from admin import router as admin_router

WEBAPP_DIR = Path(__file__).parent / "webapp"

# ========== БАЗА ДАННЫХ ==========
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT,
                image TEXT
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                name TEXT,
                description TEXT,
                price REAL,
                image TEXT,
                flavors TEXT
            );
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            INSERT OR IGNORE INTO categories (id, name, image) VALUES 
            (1, 'Одноразки', '/static/images/disposables.jpg'),
            (2, 'Под-системы', '/static/images/pods.jpg'),
            (3, 'Жидкость', '/static/images/liquid.jpg'),
            (4, 'Расходники', '/static/images/consumables.jpg'),
            (5, 'Жевательный табак', '/static/images/snus.jpg'),
            (6, 'Кальяны', '/static/images/hookahs.jpg');
            INSERT OR IGNORE INTO products (category, name, description, price, image, flavors) VALUES
            ('Одноразки', 'ELFBAR 30.000', 'Регулировка никотина', 1350, '/static/images/elfbar.jpg', 'Манго, Арбуз'),
            ('Одноразки', 'Gang Arctic 20.000', 'Крепкие', 1600, '/static/images/gang.jpg', 'Лёд, Мята'),
            ('Одноразки', 'Waka 8000 Slim', 'Компактный', 1200, '/static/images/waka.jpg', 'Персик, Дыня');
        """)
        await db.commit()

async def get_categories():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM categories") as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1], "image": r[2]} for r in rows]

async def get_products(category):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM products WHERE category=?", (category,)) as cursor:
            rows = await cursor.fetchall()
            return [{
                "id": r[0], "category": r[1], "name": r[2],
                "description": r[3], "price": r[4], "image": r[5],
                "flavors": r[6]
            } for r in rows]

async def save_user(user_id, username, full_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username, full_name)
        )
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]
# =================================

# ========== ВЕБ-СЕРВЕР ==========
async def handle_index(request):
    with open(WEBAPP_DIR / "index.html", "r", encoding="utf-8") as f:
        return web.Response(text=f.read(), content_type="text/html")

async def handle_static(request):
    file_path = WEBAPP_DIR / request.match_info["filename"]
    if file_path.exists():
        return web.FileResponse(file_path)
    return web.Response(status=404)

async def api_categories(request):
    return web.json_response(await get_categories())

async def api_products(request):
    return web.json_response(await get_products(request.match_info["category"]))

def create_web_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/static/{filename}", handle_static)
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/products/{category}", api_products)
    return app
# ================================

# ========== TELEGRAM БОТ ==========
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Передаём ADMIN_ID и bot в роутер админки через данные
admin_router_instance = admin_router
admin_router_instance.admin_id = ADMIN_ID
admin_router_instance.bot = bot

dp.include_router(admin_router_instance)

START_TEXT = """🔥 Поехали без лирики:
— Стартовые наборы? Есть.
— Вкусы, от которых взлетаешь? Есть.
— Быстрая доставка по Екб? Ага.
Ты в Cloud Shop. — и за 2 минуты подберём то, что зацепит.

Что бы посмотреть наш ассортимент просто нажми кнопку «Открыть приложение»"""

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await save_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )
    
    webapp_url = os.environ.get("RENDER_EXTERNAL_URL", f"http://localhost:{WEB_PORT}")
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Открыть приложение", web_app=WebAppInfo(url=webapp_url))],
            [KeyboardButton(text="📞 Связаться с менеджером", url="https://t.me/your_manager")]
        ],
        resize_keyboard=True
    )
    await message.answer(START_TEXT, reply_markup=keyboard)

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        if data.get("type") == "order":
            order_text = f"🛒 НОВЫЙ ЗАКАЗ\n\n👤 {message.from_user.full_name}\n📱 @{message.from_user.username}\n\n📦 Состав:\n"
            total = 0
            for item in data["items"]:
                item_sum = item["price"] * item["quantity"]
                total += item_sum
                order_text += f"• {item['name']} x{item['quantity']} = {item_sum}₽\n"
            order_text += f"\n💰 Итого: {total}₽"
            await message.answer("✅ Заказ принят! Менеджер свяжется с вами.")
            await bot.send_message(ADMIN_ID, order_text)
    except Exception as e:
        print(f"Ошибка обработки заказа: {e}")
# ================================

# ========== ЗАПУСК ==========
async def main():
    await init_db()
    print("✅ База данных готова")
    
    web_app = create_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    print(f" Веб-сервер запущен: http://0.0.0.0:{WEB_PORT}")
    
    print("🤖 Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
