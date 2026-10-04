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

async def handle_order(request):
    print("\n" + "=" * 70)
    print("🛒 HTTP ЗАКАЗ: получены данные")
    
    try:
        data = await request.json()
        print(f"📦 Данные: {json.dumps(data, ensure_ascii=False)[:500]}")
    except Exception as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        return web.json_response({"success": False, "error": "Неверный формат данных"}, status=400)
    
    if data.get("type") != "order":
        print(f"⚠️ Неверный тип: {data.get('type')}")
        return web.json_response({"success": False, "error": "Неверный тип"}, status=400)
    
    user_info = data.get("user", {})
    user_id = user_info.get("id", "неизвестно")
    user_name = user_info.get("name", "Пользователь")
    user_username = user_info.get("username", "нет")
    
    print(f"👤 Пользователь: {user_id} ({user_name})")
    print(f"📱 Username: @{user_username}")
    
    profile_link = f"tg://user?id={user_id}"
    safe_name = html_module.escape(user_name)
    
    order_text = f"🛒 <b>НОВЫЙ ЗАКАЗ</b>\n\n"
    order_text += f"👤 <b>{safe_name}</b>\n"
    order_text += f"🆔 ID: <code>{user_id}</code>\n"
    order_text += f"📱 TG: @{user_username}\n"
    order_text += f"🔗 <a href='{profile_link}'>Написать пользователю</a>\n\n"
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
    
    print(f"\n📤 Отправка менеджеру (ADMIN_ID={ADMIN_ID})")
    
    order_sent = False
    error = None
    
    try:
        await bot.send_message(ADMIN_ID, order_text, parse_mode="HTML")
        print(f"✅ Заказ УСПЕШНО отправлен менеджеру!")
        order_sent = True
    except Exception as e:
        print(f"❌ ОШИБКА отправки менеджеру: {e}")
        try:
            plain_text = order_text.replace("<b>", "").replace("</b>", "") \
                .replace("<code>", "").replace("</code>", "") \
                .replace(f"<a href='{profile_link}'>", "👉 ") \
                .replace("</a>", "")
            await bot.send_message(ADMIN_ID, plain_text)
            print(f"✅ Заказ отправлен в текстовом формате")
            order_sent = True
        except Exception as e2:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e2}")
            error = str(e2)
    
    print(f"\n📤 Отправка подтверждения пользователю (ID: {user_id})")
    
    user_message = (
        f"✅ <b>Заказ оформлен!</b>\n\n"
        f"Спасибо за покупку, {html_module.escape(user_name)}! 🎉\n\n"
        f"📦 <b>Ваш заказ:</b>\n"
        f"• Позиций: {items_count}\n"
        f"• Сумма: <b>{total}₽</b>\n\n"
        f"⏳ <b>Ожидайте</b> — менеджер свяжется с вами в ближайшее время для подтверждения и уточнения деталей доставки.\n\n"
        f"Если у вас есть вопросы, напишите нам: @{MANAGER_USERNAME}"
    )
    
    try:
        await bot.send_message(user_id, user_message, parse_mode="HTML")
        print(f"✅ Подтверждение отправлено пользователю!")
    except Exception as e:
        print(f"️ Не удалось отправить пользователю: {e}")
        print(f"💡 Возможно, пользователь не начал диалог с ботом")
    
    print("=" * 70)
    
    return web.json_response({
        "success": order_sent,
        "error": error,
        "total": total,
        "items": items_count
    })

def create_web_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/static/{filename}", handle_static)
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/products/{category}", api_products)
    app.router.add_get("/api/products-by-ids", api_products_by_ids)
    app.router.add_get("/api/search", api_search)
    app.router.add_post("/api/order", handle_order)
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

️ 18+"""

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    print(f"📩 /start от {message.from_user.id}")
    
    try:
        username = message.from_user.username or ""
        full_name = message.from_user.full_name or ""
        await save_user(message.from_user.id, username, full_name)
    except Exception as e:
        print(f"️ Ошибка сохранения: {e}")
    
    webapp_url = os.environ.get("RENDER_EXTERNAL_URL", f"http://localhost:{WEB_PORT}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Открыть каталог", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton(text="📞 Связаться с менеджером", url=f"https://t.me/{MANAGER_USERNAME}")]
    ])
    
    await message.answer(START_TEXT, reply_markup=keyboard)

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    print("\n" + "=" * 70)
    print("🛒 FALLBACK: получены данные через web_app_data")
    
    try:
        raw_data = message.web_app_data.data
        data = json.loads(raw_data)
        
        if data.get("type") != "order":
            return
        
        user = message.from_user
        user_id = user.id
        user_name = user.full_name or "Пользователь"
        user_username = user.username or "нет"
        profile_link = f"tg://user?id={user_id}"
        safe_name = html_module.escape(user_name)
        
        order_text = f"🛒 <b>НОВЫЙ ЗАКАЗ</b>\n\n"
        order_text += f"👤 <b>{safe_name}</b>\n"
        order_text += f"🆔 ID: <code>{user_id}</code>\n"
        order_text += f" TG: @{user_username}\n"
        order_text += f"🔗 <a href='{profile_link}'>Написать пользователю</a>\n\n"
        order_text += f" <b>Состав заказа:</b>\n"
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
        order_text += f"📊 Позиций: {items_count}"
        
        try:
            await bot.send_message(ADMIN_ID, order_text, parse_mode="HTML")
            print(f"✅ Заказ отправлен менеджеру (fallback)")
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
        
        try:
            user_msg = (
                f"✅ <b>Заказ оформлен!</b>\n\n"
                f"Спасибо за покупку, {safe_name}! \n\n"
                f" <b>Ваш заказ:</b>\n"
                f"• Позиций: {items_count}\n"
                f"• Сумма: <b>{total}₽</b>\n\n"
                f"⏳ <b>Ожидайте</b> — менеджер свяжется с вами в ближайшее время.\n\n"
            )
            await message.answer(user_msg, parse_mode="HTML")
            print(f"✅ Подтверждение отправлено пользователю (fallback)")
        except Exception as e:
            print(f"⚠️ Не удалось ответить пользователю: {e}")
        
    except Exception as e:
        print(f"❌ Ошибка fallback: {e}")
    
    print("=" * 70)

async def main():
    await init_db()
    print("✅ База данных PostgreSQL готова")
    
    web_app = create_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    print(f"🌐 Веб-сервер: http://0.0.0.0:{WEB_PORT}")
    print(f" Бот запущен | Admin ID: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
