from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite
import json

router = Router()

# ========== СОСТОЯНИЯ FSM ==========
class AddProduct(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_category = State()

class SendMessage(StatesGroup):
    waiting_for_text = State()

# ========== АДМИН-МЕНЮ ==========
def admin_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="📋 Список товаров")],
            [KeyboardButton(text="📦 Заказы"), KeyboardButton(text=" Статистика")],
            [KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="👥 Пользователи")],
            [KeyboardButton(text="❌ Закрыть админку")]
        ],
        resize_keyboard=True
    )
    return keyboard

def close_admin_btn():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Закрыть админку")]],
        resize_keyboard=True
    )

# ========== ПРОВЕРКА АДМИНА ==========
def is_admin(user_id: int, admin_id: int) -> bool:
    return user_id == admin_id

# ========== ОБРАБОТЧИКИ ==========

@router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    """Открыть админ-панель"""
    from main import ADMIN_ID  # импортируем из main
    
    if not is_admin(message.from_user.id, ADMIN_ID):
        await message.answer("⛔ У вас нет прав администратора")
        return
    
    await state.clear()
    await message.answer(
        "⚙️ <b>Панель администратора</b>\n\n"
        "Выберите действие:",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

@router.message(F.text == "❌ Закрыть админку")
async def close_admin(message: types.Message, state: FSMContext):
    """Закрыть админку"""
    await state.clear()
    await message.answer(
        "👋 Админ-панель закрыта",
        reply_markup=types.ReplyKeyboardRemove()
    )

# ========== ДОБАВЛЕНИЕ ТОВАРА ==========

@router.message(F.text == "➕ Добавить товар")
async def start_add_product(message: types.Message, state: FSMContext):
    from main import ADMIN_ID
    
    if not is_admin(message.from_user.id, ADMIN_ID):
        return
    
    await state.set_state(AddProduct.waiting_for_name)
    await message.answer(
        "➕ <b>Добавление товара</b>\n\n"
        "Введите название товара:",
        reply_markup=close_admin_btn(),
        parse_mode="HTML"
    )

@router.message(AddProduct.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProduct.waiting_for_description)
    await message.answer("📝 Введите описание товара:")

@router.message(AddProduct.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddProduct.waiting_for_price)
    await message.answer("💰 Введите цену (только число, например: 1500):")

@router.message(AddProduct.waiting_for_price)
async def process_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
        await state.update_data(price=price)
        await state.set_state(AddProduct.waiting_for_category)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Одноразки", callback_data="cat_Одноразки")],
            [InlineKeyboardButton(text="Под-системы", callback_data="cat_Под-системы")],
            [InlineKeyboardButton(text="Жидкость", callback_data="cat_Жидкость")],
            [InlineKeyboardButton(text="Расходники", callback_data="cat_Расходники")],
            [InlineKeyboardButton(text="Жевательный табак", callback_data="cat_Жевательный табак")],
            [InlineKeyboardButton(text="Кальяны", callback_data="cat_Кальяны")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add")]
        ])
        
        await message.answer("📂 Выберите категорию:", reply_markup=keyboard)
    except ValueError:
        await message.answer("❌ Неверная цена. Введите число (например: 1500):")

@router.callback_query(F.data.startswith("cat_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.replace("cat_", "")
    data = await state.get_data()
    
    # Добавляем товар в БД
    async with aiosqlite.connect("cloudshop.db") as db:
        await db.execute(
            "INSERT INTO products (category, name, description, price, image, flavors) VALUES (?, ?, ?, ?, ?, ?)",
            (category, data["name"], data["description"], data["price"], "/static/images/default.jpg", "")
        )
        await db.commit()
    
    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Товар добавлен!</b>\n\n"
        f"📦 Название: {data['name']}\n"
        f" Описание: {data['description']}\n"
        f"💰 Цена: {data['price']} ₽\n"
        f" Категория: {category}",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "cancel_add")
async def cancel_add(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Добавление отменено", reply_markup=admin_menu())
    await callback.answer()

# ========== СПИСОК ТОВАРОВ ==========

@router.message(F.text == "📋 Список товаров")
async def list_products(message: types.Message):
    from main import ADMIN_ID
    
    if not is_admin(message.from_user.id, ADMIN_ID):
        return
    
    async with aiosqlite.connect("cloudshop.db") as db:
        async with db.execute("SELECT id, name, price, category FROM products ORDER BY id DESC") as cursor:
            products = await cursor.fetchall()
    
    if not products:
        await message.answer("📋 Список товаров пуст", reply_markup=admin_menu())
        return
    
    text = "📋 <b>Список товаров:</b>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for p in products[:20]:  # показываем последние 20
        text += f"ID: {p[0]} | {p[1]} — {p[2]}₽ ({p[3]})\n"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"🗑 {p[1]}", callback_data=f"del_{p[0]}")
        ])
    
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_admin")])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("del_"))
async def delete_product(callback: types.CallbackQuery):
    product_id = int(callback.data.replace("del_", ""))
    
    async with aiosqlite.connect("cloudshop.db") as db:
        await db.execute("DELETE FROM products WHERE id=?", (product_id,))
        await db.commit()
    
    await callback.answer("✅ Товар удалён")
    await callback.message.edit_text("🗑 Товар удалён. Выберите действие:", reply_markup=admin_menu())

@router.callback_query(F.data == "back_admin")
async def back_to_admin(callback: types.CallbackQuery):
    await callback.message.edit_text("️ Панель администратора", reply_markup=admin_menu())
    await callback.answer()

# ========== ЗАКАЗЫ ==========

@router.message(F.text == "📦 Заказы")
async def show_orders(message: types.Message):
    from main import ADMIN_ID
    
    if not is_admin(message.from_user.id, ADMIN_ID):
        return
    
    # Пока просто заглушка - заказы приходят в личку
    await message.answer(
        " <b>Последние заказы</b>\n\n"
        "Заказы приходят вам в личные сообщения от бота.\n"
        "В следующей версии здесь будет список всех заказов.",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

# ========== СТАТИСТИКА ==========

@router.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    from main import ADMIN_ID
    
    if not is_admin(message.from_user.id, ADMIN_ID):
        return
    
    async with aiosqlite.connect("cloudshop.db") as db:
        async with db.execute("SELECT COUNT(*) FROM products") as cursor:
            products_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM categories") as cursor:
            categories_count = (await cursor.fetchone())[0]
    
    text = (
        "📊 <b>Статистика магазина</b>\n\n"
        f" Товаров: {products_count}\n"
        f"📂 Категорий: {categories_count}\n"
        f"👥 Пользователей: (в разработке)\n"
        f"🛒 Заказов: (в разработке)"
    )
    
    await message.answer(text, reply_markup=admin_menu(), parse_mode="HTML")

# ========== РАССЫЛКА ==========

@router.message(F.text == "📢 Рассылка")
async def start_broadcast(message: types.Message, state: FSMContext):
    from main import ADMIN_ID
    
    if not is_admin(message.from_user.id, ADMIN_ID):
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
    from main import ADMIN_ID, bot
    
    await state.clear()
    
    # Пока заглушка - в реальной версии нужно хранить список пользователей в БД
    await message.answer(
        "📢 <b>Рассылка</b>\n\n"
        "Функция в разработке. Нужно добавить таблицу пользователей в БД.\n"
        "Сообщение сохранено для отправки позже.",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

# ========== ПОЛЬЗОВАТЕЛИ ==========

@router.message(F.text == "👥 Пользователи")
async def show_users(message: types.Message):
    from main import ADMIN_ID
    
    if not is_admin(message.from_user.id, ADMIN_ID):
        return
    
    await message.answer(
        "👥 <b>Пользователи</b>\n\n"
        "Функция в разработке. Нужно добавить таблицу users в БД.",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )
