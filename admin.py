from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite
import os
import uuid

router = Router()

# ========== СОСТОЯНИЯ FSM ==========
class AddProduct(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_photo = State()
    waiting_for_category = State()

class SendMessage(StatesGroup):
    waiting_for_text = State()

# ========== АДМИН-МЕНЮ ==========
def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text=" Список товаров")],
            [KeyboardButton(text="📦 Заказы"), KeyboardButton(text=" Статистика")],
            [KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="👥 Пользователи")],
            [KeyboardButton(text="❌ Закрыть админку")]
        ],
        resize_keyboard=True
    )

def close_admin_btn():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Закрыть админку")]],
        resize_keyboard=True
    )

# ========== ПРОВЕРКА АДМИНА ==========
def is_admin(user_id: int, admin_id: int) -> bool:
    return user_id == admin_id

def get_admin_id(router_obj):
    return getattr(router_obj, 'admin_id', None)

def get_bot(router_obj):
    return getattr(router_obj, 'bot', None)

# ========== ОБРАБОТЧИКИ ==========

@router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    admin_id = get_admin_id(router)
    
    if not is_admin(message.from_user.id, admin_id):
        await message.answer("⛔ У вас нет прав администратора")
        return
    
    await state.clear()
    await message.answer(
        "⚙️ <b>Панель администратора</b>\n\nВыберите действие:",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

@router.message(F.text == "❌ Закрыть админку")
async def close_admin(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Админ-панель закрыта",
        reply_markup=types.ReplyKeyboardRemove()
    )

# ========== ДОБАВЛЕНИЕ ТОВАРА ==========

@router.message(F.text == "➕ Добавить товар")
async def start_add_product(message: types.Message, state: FSMContext):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    
    await state.set_state(AddProduct.waiting_for_name)
    await message.answer(
        "➕ <b>Добавление товара</b>\n\n"
        "📝 Шаг 1/5: Введите название товара:",
        reply_markup=close_admin_btn(),
        parse_mode="HTML"
    )

@router.message(AddProduct.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProduct.waiting_for_description)
    await message.answer(
        "📝 Шаг 2/5: Введите описание товара:\n\n"
        "️ Отправьте /admin для отмены",
        reply_markup=close_admin_btn()
    )

@router.message(AddProduct.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddProduct.waiting_for_price)
    await message.answer(
        "💰 Шаг 3/5: Введите цену (только число, например: 1500):\n\n"
        "⚠️ Отправьте /admin для отмены",
        reply_markup=close_admin_btn()
    )

@router.message(AddProduct.waiting_for_price)
async def process_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
        await state.update_data(price=price)
        await state.set_state(AddProduct.waiting_for_photo)
        await message.answer(
            " Шаг 4/5: Отправьте <b>фотографию товара</b>\n\n"
            "Просто перешлите фото или загрузите из галереи.\n"
            "Можно отправить фото без подписи.\n\n"
            "️ Отправьте /admin для отмены",
            reply_markup=close_admin_btn(),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            " Неверная цена. Введите число (например: 1500):\n\n"
            "⚠️ Отправьте /admin для отмены",
            reply_markup=close_admin_btn()
        )

@router.message(AddProduct.waiting_for_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    """Обработчик загрузки фото товара"""
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    
    # Берём самое большое фото (последнее в списке)
    photo = message.photo[-1]
    
    # Генерируем уникальное имя файла
    file_extension = "jpg"
    unique_name = f"{uuid.uuid4().hex}.{file_extension}"
    
    # Путь для сохранения
    images_dir = "webapp/images"
    os.makedirs(images_dir, exist_ok=True)
    file_path = os.path.join(images_dir, unique_name)
    
    # Скачиваем фото
    bot = get_bot(router)
    file = await bot.get_file(photo.file_id)
    await bot.download_file(file.file_path, file_path)
    
    # Сохраняем путь в состояние (относительный для веб-сервера)
    web_path = f"/static/images/{unique_name}"
    await state.update_data(image=web_path)
    
    await state.set_state(AddProduct.waiting_for_category)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💨 Одноразки", callback_data="cat_Одноразки")],
        [InlineKeyboardButton(text="🔋 Под-системы", callback_data="cat_Под-системы")],
        [InlineKeyboardButton(text="💧 Жидкость", callback_data="cat_Жидкость")],
        [InlineKeyboardButton(text="⚙️ Расходники", callback_data="cat_Расходники")],
        [InlineKeyboardButton(text="🌿 Жевательный табак", callback_data="cat_Жевательный табак")],
        [InlineKeyboardButton(text="🪝 Кальяны", callback_data="cat_Кальяны")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add")]
    ])
    
    await message.answer(
        "✅ Фото получено!\n\n"
        "📂 Шаг 5/5: Выберите категорию:",
        reply_markup=keyboard
    )

@router.message(AddProduct.waiting_for_photo, ~F.photo)
async def process_photo_wrong(message: types.Message, state: FSMContext):
    """Если прислали не фото"""
    await message.answer(
        "❌ Это не фотография. Пожалуйста, отправьте <b>фото товара</b>:\n\n"
        "⚠️ Отправьте /admin для отмены",
        reply_markup=close_admin_btn(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("cat_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.replace("cat_", "")
    data = await state.get_data()
    
    # Если фото не было загружено — используем заглушку
    image_path = data.get("image", "/static/images/default.jpg")
    
    # Добавляем товар в БД
    async with aiosqlite.connect("cloudshop.db") as db:
        await db.execute(
            "INSERT INTO products (category, name, description, price, image, flavors) VALUES (?, ?, ?, ?, ?, ?)",
            (category, data["name"], data["description"], data["price"], image_path, "")
        )
        await db.commit()
    
    await state.clear()
    
    # Показываем превью товара с фото
    preview_text = (
        f"✅ <b>Товар добавлен!</b>\n\n"
        f"📦 Название: {data['name']}\n"
        f"📝 Описание: {data['description']}\n"
        f"💰 Цена: {data['price']} ₽\n"
        f"📂 Категория: {category}\n"
        f" Фото: загружено"
    )
    
    await callback.message.answer(preview_text, parse_mode="HTML", reply_markup=admin_menu())
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data == "cancel_add")
async def cancel_add(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Добавление отменено", reply_markup=admin_menu())
    await callback.answer()

# ========== СПИСОК ТОВАРОВ ==========

@router.message(F.text == "📋 Список товаров")
async def list_products(message: types.Message):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    
    async with aiosqlite.connect("cloudshop.db") as db:
        async with db.execute("SELECT id, name, price, category, image FROM products ORDER BY id DESC") as cursor:
            products = await cursor.fetchall()
    
    if not products:
        await message.answer("📋 Список товаров пуст", reply_markup=admin_menu())
        return
    
    text = "📋 <b>Список товаров:</b>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for p in products[:20]:
        text += f"ID: {p[0]} | {p[1]} — {p[2]}₽ ({p[3]})\n"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"🗑 {p[1][:20]}", callback_data=f"del_{p[0]}")
        ])
    
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_admin")])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("del_"))
async def delete_product(callback: types.CallbackQuery):
    product_id = int(callback.data.replace("del_", ""))
    
    async with aiosqlite.connect("cloudshop.db") as db:
        # Получаем путь к фото перед удалением
        async with db.execute("SELECT image FROM products WHERE id=?", (product_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0] and row[0] != "/static/images/default.jpg":
                # Удаляем файл фото
                file_path = "webapp" + row[0]
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        await db.execute("DELETE FROM products WHERE id=?", (product_id,))
        await db.commit()
    
    await callback.answer("✅ Товар удалён")
    await callback.message.edit_text("🗑 Товар удалён. Выберите действие:", reply_markup=admin_menu())

@router.callback_query(F.data == "back_admin")
async def back_to_admin(callback: types.CallbackQuery):
    await callback.message.edit_text("⚙️ Панель администратора", reply_markup=admin_menu())
    await callback.answer()

# ========== ЗАКАЗЫ ==========

@router.message(F.text == "📦 Заказы")
async def show_orders(message: types.Message):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    
    await message.answer(
        "📦 <b>Последние заказы</b>\n\n"
        "Заказы приходят вам в личные сообщения от бота.\n"
        "В следующей версии здесь будет список всех заказов.",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

# ========== СТАТИСТИКА ==========

@router.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    
    async with aiosqlite.connect("cloudshop.db") as db:
        async with db.execute("SELECT COUNT(*) FROM products") as cursor:
            products_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM categories") as cursor:
            categories_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            users_count = (await cursor.fetchone())[0]
    
    text = (
        "📊 <b>Статистика магазина</b>\n\n"
        f"📦 Товаров: {products_count}\n"
        f"📂 Категорий: {categories_count}\n"
        f"👥 Пользователей: {users_count}"
    )
    
    await message.answer(text, reply_markup=admin_menu(), parse_mode="HTML")

# ========== РАССЫЛКА ==========

@router.message(F.text == " Рассылка")
async def start_broadcast(message: types.Message, state: FSMContext):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    
    await state.set_state(SendMessage.waiting_for_text)
    await message.answer(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Введите текст сообщения для рассылки всем пользователям:\n\n"
        "⚠️ Отправьте /admin для отмены",
        reply_markup=close_admin_btn(),
        parse_mode="HTML"
    )

@router.message(SendMessage.waiting_for_text)
async def process_broadcast(message: types.Message, state: FSMContext):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    
    text = message.text
    await state.clear()
    
    async with aiosqlite.connect("cloudshop.db") as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            user_ids = [r[0] for r in rows]
    
    bot = get_bot(router)
    sent = 0
    failed = 0
    
    await message.answer(f"📢 Начинаю рассылку {len(user_ids)} пользователям...")
    
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception:
            failed += 1
    
    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=admin_menu()
    )

# ========== ПОЛЬЗОВАТЕЛИ ==========

@router.message(F.text == "👥 Пользователи")
async def show_users(message: types.Message):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    
    async with aiosqlite.connect("cloudshop.db") as db:
        async with db.execute("SELECT user_id, username, full_name FROM users ORDER BY created_at DESC LIMIT 20") as cursor:
            users = await cursor.fetchall()
    
    if not users:
        await message.answer("👥 Пользователей пока нет", reply_markup=admin_menu())
        return
    
    text = " <b>Последние пользователи:</b>\n\n"
    for u in users:
        username = f"@{u[1]}" if u[1] else "без username"
        text += f"• {u[2]} ({username}) — ID: {u[0]}\n"
    
    await message.answer(text, reply_markup=admin_menu(), parse_mode="HTML")
