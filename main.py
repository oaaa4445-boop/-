import asyncio
import json
import os
from pathlib import Path
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
import traceback
import html as html_module

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
✅ Доставка за 60 минут по городу
✅ Скидки постоянным клиентам

⚠️ 18+"""

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    print(f" /start от {message.from_user.id}")
    
    try:
        username = message.from_user.username or ""
        full_name = message.from_user.full_name or ""
        await save_user(message.from_user.id, username, full_name)
    except Exception as e:
        print(f"⚠️ Ошибка сохранения: {e}")
    
    webapp_url = os.environ.get("RENDER_EXTERNAL_URL", f"http://localhost:{WEB_PORT}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=" Открыть каталог", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton(text="📞 Связаться с менеджером", url=f"https://t.me/{MANAGER_USERNAME}")]
    ])
    
    await message.answer(START_TEXT, reply_markup=keyboard)

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    print("\n" + "=" * 70)
    print("🛒 ШАГ 1: ПОЛУЧЕНЫ ДАННЫЕ ИЗ WEB APP")
    print(f"   Пользователь: {message.from_user.id}")
    print(f"   Имя: {message.from_user.full_name}")
    print(f"   Username: @{message.from_user.username or 'нет'}")
    print("=" * 70)
    
    try:
        raw_data = message.web_app_data.data
        print(f"\n🛒 ШАГ 2: Сырые данные ({len(raw_data)} символов):")
        print(f"   {raw_data[:300]}...")
        
        data = json.loads(raw_data)
        print(f"   ✅ JSON распарсен успешно")
    except json.JSONDecodeError as e:
        print(f"   ❌ ОШИБКА ПАРСИНГА JSON: {e}")
        await message.answer("❌ Ошибка обработки заказа. Попробуйте ещё раз.")
        return
    except Exception as e:
        print(f"   ❌ НЕИЗВЕСТНАЯ ОШИБКА: {e}")
        await message.answer("❌ Произошла ошибка.")
        return
    
    if data.get("type") != "order":
        print(f"   ⚠️ Неверный тип: {data.get('type')}")
        return
    
    print(f"\n🛒 ШАГ 3: Тип заказа подтверждён")
    print(f"   Позиций: {len(data.get('items', []))}")
    print(f"   Сумма: {data.get('total')}₽")
    
    user = message.from_user
    user_id = user.id
    username_text = f"@{user.username}" if user.username else "❌ Нет username"
    profile_link = f"tg://user?id={user_id}"
    safe_name = html_module.escape(user.full_name or "Пользователь")
    
    order_text = f"🛒 <b>НОВЫЙ ЗАКАЗ</b>\n\n"
    order_text += f" <b>{safe_name}</b>\n"
    order_text += f"🆔 ID: <code>{user_id}</code>\n"
    order_text += f"📱 TG: {username_text}\n"
    order_text += f" <a href='{profile_link}'>Написать пользователю</a>\n\n"
    order_text += f"📦 <b>Состав заказа:</b>\n"
    order_text += "━━━━━━━━━━━━━━━━━━━━\n"
    
    total = 0
    items_count = 0
    for i, item in enumerate(data.get("items", []), 1):
        item_name = html_module.escape(item.get("name", "Товар"))
        item_price = item.get("price", 0)
        item_qty = item.get("quantity", 1)
        item_sum = item_price * item_qty
        total += item_sum
        items_count += 1
        
        order_text += f"{i}. {item_name}\n"
        order_text += f"   {item_qty} шт × {item_price}₽ = <b>{item_sum}₽</b>\n\n"
    
    order_text += "━━━━━━━━━━━━━━━━━━━━\n"
    order_text += f"\n💰 <b>ИТОГО: {total}₽</b>\n"
    order_text += f"📊 Позиций: {items_count}\n"
    order_text += f"🕐 Время: {data.get('timestamp', 'неизвестно')[:19]}"
    
    print(f"\n🛒 ШАГ 5: Сообщение сформировано ({len(order_text)} символов)")
    
    print(f"\n🛒 ШАГ 6: Отправка менеджеру (ADMIN_ID={ADMIN_ID})")
    
    try:
        await bot.send_message(ADMIN_ID, order_text, parse_mode="HTML")
        print(f"   ✅ Заказ УСПЕШНО отправлен менеджеру!")
    except Exception as e:
        print(f"   ❌ ОШИБКА отправки менеджеру: {e}")
        
        try:
            plain_text = order_text.replace("<b>", "").replace("</b>", "") \
                .replace("<code>", "").replace("</code>", "") \
                .replace(f"<a href='{profile_link}'>", " ") \
                .replace("</a>", "")
            await bot.send_message(ADMIN_ID, plain_text)
            print(f"   ✅ Заказ отправлен в текстовом формате (fallback)")
        except Exception as e2:
            print(f"   ❌ КРИТИЧЕСКАЯ ОШИБКА fallback: {e2}")
    
    print(f"\n🛒 ШАГ 7: Ответ пользователю")
    try:
        await message.answer(
            "✅ <b>Заказ принят!</b>\n\n"
            "Менеджер свяжется с вами в ближайшее время.\n"
            "Спасибо за покупку! ",
            parse_mode="HTML"
        )
        print(f"   ✅ Ответ пользователю отправлен")
    except Exception as e:
        print(f"   ⚠️ Не удалось ответить пользователю: {e}")
    
    print("=" * 70)
    print("🛒 ЗАКАЗ ОБРАБОТАН\n")

async def main():
    await init_db()
    print("✅ База данных PostgreSQL готова")
    
    web_app = create_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    print(f"🌐 Веб-сервер: http://0.0.0.0:{WEB_PORT}")
    print(f"🤖 Бот запущен | Admin ID: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Бот остановлен")
