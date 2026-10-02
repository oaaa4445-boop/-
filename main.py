import asyncio
import json
import os
from pathlib import Path
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
import traceback

from config import BOT_TOKEN, ADMIN_ID, WEB_PORT
from admin import router as admin_router
from database import init_db, get_categories, get_products, get_products_by_ids, search_products, save_user

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

async def api_products_by_ids(request):
    ids_str = request.query.get("ids", "")
    if not ids_str:
        return web.json_response([])
    try:
        ids = [int(x.strip()) for x in ids_str.split(",") if x.strip()]
        products = await get_products_by_ids(ids)
        return web.json_response(products)
    except (ValueError, TypeError):
        return web.json_response([])

async def api_search(request):
    query = request.query.get("q", "").strip()
    if not query or len(query) < 2:
        return web.json_response([])
    products = await search_products(query)
    return web.json_response(products)

def create_web_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/static/{filename}", handle_static)
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/products/{category}", api_products)
    app.router.add_get("/api/products-by-ids", api_products_by_ids)
    app.router.add_get("/api/search", api_search)
    return app

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

admin_router_instance = admin_router
admin_router_instance.admin_id = ADMIN_ID
admin_router_instance.bot = bot

dp.include_router(admin_router_instance)

# ⚠️ БЕЗОПАСНОЕ ПРИВЕТСТВИЕ С ПРЕДУПРЕЖДЕНИЕМ 18+
START_TEXT = """⚠️ Внимание! Контент 18+

PUFFY — каталог продукции для совершеннолетних.
Быстрая доставка по Екб.

Открывая приложение, вы подтверждаете, что вам есть 18 лет 👇"""

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик /start с защитой от ошибок"""
    print(f"📩 Получен /start от пользователя {message.from_user.id}")
    
    # 1. Сохраняем пользователя (не блокируем работу при ошибке)
    try:
        username = message.from_user.username or ""
        full_name = message.from_user.full_name or ""
        await save_user(message.from_user.id, username, full_name)
        print(f"✅ Пользователь {message.from_user.id} сохранён в БД")
    except Exception as e:
        print(f"⚠️ Ошибка сохранения пользователя: {e}")
        traceback.print_exc()
    
    # 2. Формируем клавиатуру
    try:
        webapp_url = os.environ.get("RENDER_EXTERNAL_URL", f"http://localhost:{WEB_PORT}")
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=" Открыть каталог", web_app=WebAppInfo(url=webapp_url))],
                [KeyboardButton(text="📞 Связаться с менеджером", url="https://t.me/ghjkIz")]
            ],
            resize_keyboard=True
        )
        
        # 3. Отправляем приветствие с предупреждением
        await message.answer(START_TEXT, reply_markup=keyboard)
        print(f"✅ Приветствие отправлено пользователю {message.from_user.id}")
        
    except Exception as e:
        print(f"❌ Ошибка отправки приветствия: {e}")
        traceback.print_exc()
        # Пробуем отправить хотя бы текст без клавиатуры
        try:
            await message.answer(START_TEXT)
        except Exception as e2:
            print(f"❌❌ Критическая ошибка: {e2}")

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
        traceback.print_exc()

async def main():
    await init_db()
    print("✅ База данных PostgreSQL готова")
    
    web_app = create_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    print(f"🌐 Веб-сервер запущен: http://0.0.0.0:{WEB_PORT}")
    
    print("🤖 Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
