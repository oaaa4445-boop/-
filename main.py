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
import asyncpg

from config import BOT_TOKEN, ADMIN_ID, WEB_PORT, MANAGER_USERNAME
from admin import router as admin_router, setup_admin
from database import init_db, get_categories, get_products, get_products_by_ids, search_products, save_user

WEBAPP_DIR = Path(__file__).parent / "webapp"

# ✅ СЕКРЕТ ДЛЯ ЗАЩИТЫ MIGRATE ENDPOINT
# Меняй на любое своё слово — это защита от случайного вызова
MIGRATE_SECRET = "puffy2026migrate"

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

# ✅ ENDPOINT ДЛЯ ПЕРЕНОСА ДАННЫХ
async def handle_migrate(request):
    secret = request.query.get("secret", "")
    
    if secret != MIGRATE_SECRET:
        return web.Response(
            text="❌ Неверный секрет. Используй ?secret=puffy2026migrate",
            content_type="text/plain"
        )
    
    old_db_url = os.environ.get("OLD_DATABASE_URL")
    if not old_db_url:
        return web.Response(
            text="❌ Переменная OLD_DATABASE_URL не задана в Render Environment",
            content_type="text/plain"
        )
    
    new_db_url = os.environ.get("DATABASE_URL")
    if not new_db_url:
        return web.Response(
            text="❌ Переменная DATABASE_URL не задана",
            content_type="text/plain"
        )
    
    log = []
    log.append("🔄 Начинаем перенос данных...")
    
    # Читаем из старой базы
    try:
        log.append("📥 Подключаемся к СТАРОЙ базе...")
        old_conn = await asyncpg.connect(old_db_url)
        
        categories = await old_conn.fetch("SELECT * FROM categories")
        products = await old_conn.fetch("SELECT * FROM products")
        users = await old_conn.fetch("SELECT * FROM users")
        
        await old_conn.close()
        log.append(f"   Найдено: {len(categories)} категорий, {len(products)} товаров, {len(users)} пользователей.")
    except Exception as e:
        log.append(f"❌ Ошибка подключения к СТАРОЙ базе: {e}")
        log.append("💡 Возможно, старая база уже удалена Render или ссылка неверная.")
        return web.Response(
            text="\n".join(log),
            content_type="text/plain"
        )
    
    if not categories and not products and not users:
        log.append("⚠️ Старая база пуста. Переносить нечего.")
        return web.Response(text="\n".join(log), content_type="text/plain")
    
    # Загружаем в новую базу
    try:
        log.append("📤 Подключаемся к НОВОЙ базе (Neon)...")
        new_conn = await asyncpg.connect(new_db_url)
        
        # Создаём таблицы
        await new_conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY, name TEXT, image TEXT
            );
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY, category TEXT, name TEXT, 
                description TEXT, price REAL, image TEXT, flavors TEXT
            );
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY, username TEXT, 
                full_name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Перенос категорий
        if categories:
            await new_conn.execute("TRUNCATE TABLE categories")
            for cat in categories:
                await new_conn.execute(
                    "INSERT INTO categories (id, name, image) VALUES ($1, $2, $3)",
                    cat['id'], cat['name'], cat['image']
                )
            log.append(f"   ✅ Перенесено {len(categories)} категорий.")
        
        # Перенос товаров
        if products:
            await new_conn.execute("TRUNCATE TABLE products RESTART IDENTITY")
            for prod in products:
                await new_conn.execute(
                    "INSERT INTO products (category, name, description, price, image, flavors) VALUES ($1, $2, $3, $4, $5, $6)",
                    prod['category'], prod['name'], prod['description'], 
                    prod['price'], prod['image'], prod['flavors']
                )
            log.append(f"   ✅ Перенесено {len(products)} товаров.")
        
        # Перенос пользователей
        if users:
            for user in users:
                await new_conn.execute(
                    """INSERT INTO users (user_id, username, full_name) 
                       VALUES ($1, $2, $3) 
                       ON CONFLICT (user_id) DO NOTHING""",
                    user['user_id'], user['username'], user['full_name']
                )
            log.append(f"   ✅ Перенесено {len(users)} пользователей.")
        
        await new_conn.close()
        log.append("\n🎉 ПЕРЕНОС УСПЕШНО ЗАВЕРШЁН!")
        log.append("\n⚠️ ВАЖНО: Теперь удали переменную OLD_DATABASE_URL из Render Environment!")
        
    except Exception as e:
        log.append(f"❌ Ошибка при записи в новую базу: {e}")
    
    return web.Response(text="\n".join(log), content_type="text/plain")

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
        print(f"⚠️ Не удалось отправить пользователю: {e}")
    
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
    app.router.add_get("/migrate", handle_migrate)  # ✅ ENDPOINT ДЛЯ МИГРАЦИИ
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
    print(f"📩 /start от {message.from_user.id}")
    
    try:
        username = message.from_user.username or ""
        full_name = message.from_user.full_name or ""
        await save_user(message.from_user.id, username, full_name)
    except Exception as e:
        print(f"⚠️ Ошибка сохранения: {e}")
    
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
        order_text += f"📊 Позиций: {items_count}"
        
        try:
            await bot.send_message(ADMIN_ID, order_text, parse_mode="HTML")
            print(f"✅ Заказ отправлен менеджеру (fallback)")
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
        
        try:
            user_msg = (
                f"✅ <b>Заказ оформлен!</b>\n\n"
                f"Спасибо за покупку, {safe_name}! 🎉\n\n"
                f"📦 <b>Ваш заказ:</b>\n"
                f"• Позиций: {items_count}\n"
                f"• Сумма: <b>{total}₽</b>\n\n"
                f"⏳ <b>Ожидайте</b> — менеджер свяжется с вами в ближайшее время.\n\n"
                f"Вопросы? @{MANAGER_USERNAME}"
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
    print(f"🤖 Бот запущен | Admin ID: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
