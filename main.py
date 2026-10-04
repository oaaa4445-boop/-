import asyncio
import json
import os
import html
from pathlib import Path
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
import traceback

from config import BOT_TOKEN, ADMIN_ID, WEB_PORT, MANAGER_USERNAME
from admin import router as admin_router, setup_admin
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

setup_admin(ADMIN_ID, bot)
dp.include_router(admin_router)

START_TEXT = """🛍 PUFFY — твой вейп-шоп в Екб

✅ Только оригинальная продукция
✅ Цены ниже, чем в офлайн-магазинах
✅ Скидки постоянным клиентам

⚠️ 18+"""

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    print(f"📩 Получен /start от пользователя {message.from_user.id}")
    
    try:
        username = message.from_user.username or ""
        full_name = message.from_user.full_name or ""
        await save_user(message.from_user.id, username, full_name)
    except Exception as e:
        print(f"⚠️ Ошибка сохранения: {e}")
    
    try:
        webapp_url = os.environ.get("RENDER_EXTERNAL_URL", f"http://localhost:{WEB_PORT}")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=" Открыть каталог", web_app=WebAppInfo(url=webapp_url))],
            [InlineKeyboardButton(text="📞 Связаться с менеджером", url=f"https://t.me/{MANAGER_USERNAME}")]
        ])
        await message.answer(START_TEXT, reply_markup=keyboard)
        print(f"✅ Приветствие отправлено пользователю {message.from_user.id}")
    except Exception as e:
        print(f"❌ Ошибка отправки приветствия: {e}")

# ✅ ИСПРАВЛЕННЫЙ обработчик заказов
@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    print(f" Получены данные из Web App от пользователя {message.from_user.id}")
    
    try:
        # Парсим данные
        raw_data = message.web_app_data.data
        print(f"📋 Сырые данные: {raw_data}")
        
        data = json.loads(raw_data)
        
        if data.get("type") != "order":
            print(f"⚠️ Неверный тип данных: {data.get('type')}")
            await message.answer("❌ Неверный формат данных")
            return
        
        user = message.from_user
        items = data.get("items", [])
        total = data.get("total", 0)
        user_id_from_app = data.get("user_id")
        
        print(f" Товаров в заказе: {len(items)}, Сумма: {total}")
        
        if not items:
            await message.answer(" Корзина пуста")
            return
        
        # ✅ ЭКРАНИРУЕМ все пользовательские данные для HTML
        user_name_safe = html.escape(user.full_name or "Пользователь")
        username_text = f"@{html.escape(user.username)}" if user.username else "Нет юзернейма"
        profile_link = f"tg://user?id={user.id}"
        
        # Формируем текст заказа
        order_lines = [
            f" <b>НОВЫЙ ЗАКАЗ</b>\n",
            f"👤 <b>{user_name_safe}</b>",
            f"🆔 ID: <code>{user.id}</code>",
            f"📱 TG: {username_text}",
            f"🔗 <a href='{profile_link}'>Написать пользователю</a>\n",
            f"📦 <b>Состав:</b>"
        ]
        
        for item in items:
            item_name = html.escape(str(item.get("name", "Товар")))
            item_price = item.get("price", 0)
            item_qty = item.get("quantity", 1)
            item_sum = item_price * item_qty
            order_lines.append(f"• {item_name} x{item_qty} = {int(item_sum)}₽")
        
        order_lines.append(f"\n💰 <b>Итого: {int(total)}₽</b>")
        
        order_text = "\n".join(order_lines)
        
        print(f"📝 Текст заказа:\n{order_text}")
        
        # ✅ Сначала отвечаем пользователю
        await message.answer("✅ Заказ принят! Менеджер свяжется с вами в ближайшее время.")
        
        # ✅ Потом отправляем админу (с обработкой ошибок)
        try:
            await bot.send_message(ADMIN_ID, order_text, parse_mode="HTML")
            print(f"✅ Заказ отправлен админу (ID: {ADMIN_ID})")
        except Exception as admin_err:
            print(f"❌ Ошибка отправки админу: {admin_err}")
            # Fallback: отправляем без HTML
            try:
                plain_text = order_text.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "").replace("<a href='", "").replace("'>", ": ").replace("</a>", "")
                await bot.send_message(ADMIN_ID, plain_text)
                print(f"✅ Заказ отправлен админу в текстовом формате")
            except Exception as plain_err:
                print(f"❌❌ Критическая ошибка отправки админу: {plain_err}")
                await message.answer("⚠️ Заказ сохранён, но произошла ошибка при уведомлении менеджера. Мы свяжемся с вами!")
        
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        await message.answer("❌ Ошибка обработки данных заказа")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        traceback.print_exc()
        await message.answer("❌ Произошла ошибка. Попробуйте ещё раз или свяжитесь с менеджером.")

async def main():
    await init_db()
    print("✅ База данных PostgreSQL готова")
    
    web_app = create_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    print(f"🌐 Веб-сервер запущен: http://0.0.0.0:{WEB_PORT}")
    
    print(f"🤖 Бот запущен... Admin ID: {ADMIN_ID} (тип: {type(ADMIN_ID).__name__})")
    print(f"📞 Manager username: @{MANAGER_USERNAME}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
