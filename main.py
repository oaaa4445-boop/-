import asyncio
import json
import os
from pathlib import Path
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_ID, WEB_PORT
from admin import router as admin_router
from database import init_db, get_categories, get_products, save_user

WEBAPP_DIR = Path(__file__).parent / "webapp"

async def handle_index(request):
    with open(WEBAPP_DIR / "index.html", "r", encoding="utf-8") as f:
        return web.Response(text=f.read(), content_type="text/html")

async def handle_static(request):
    filename = request.match_info["filename"]
    file_path = WEBAPP_DIR / filename
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

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

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
            [KeyboardButton(text="📞 Связаться с менеджером", url="https://t.me/ghjkIz")]
        ],
        resize_keyboard=True
    )
    await message.answer(START_TEXT, reply_markup=keyboard)

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        if data.get("type") == "order":
            order_text = f"🛒 НОВЫЙ ЗАКАЗ\n\n👤 {message.from_user.full_name}\n📱 @{message.from_user.username}\n\n Состав:\n"
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

async def main():
    await init_db()
    print("✅ База данных PostgreSQL готова")
    
    web_app = create_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    print(f"🌐 Веб-сервер запущен: http://0.0.0.0:{WEB_PORT}")
    
    print(" Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
