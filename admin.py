from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from database import add_product, delete_product, get_product_count, get_user_count, get_db

router = Router()

class AddProduct(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_image = State()
    waiting_for_category = State()

class SendMessage(StatesGroup):
    waiting_for_text = State()

def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="📋 Список товаров")],
            [KeyboardButton(text="📦 Заказы"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text=" Рассылка"), KeyboardButton(text="👥 Пользователи")],
            [KeyboardButton(text="❌ Закрыть админку")]
        ],
        resize_keyboard=True
    )

def close_admin_btn():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Закрыть админку")]],
        resize_keyboard=True
    )

def is_admin(user_id: int, admin_id: int) -> bool:
    return user_id == admin_id

def get_admin_id(router_obj):
    return getattr(router_obj, 'admin_id', None)

def get_bot(router_obj):
    return getattr(router_obj, 'bot', None)

@router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        await message.answer("⛔ У вас нет прав администратора")
        return
    await state.clear()
    await message.answer("⚙️ <b>Панель администратора</b>\n\nВыберите действие:", reply_markup=admin_menu(), parse_mode="HTML")

@router.message(F.text == "❌ Закрыть админку")
async def close_admin(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(" Админ-панель закрыта", reply_markup=types.ReplyKeyboardRemove())

@router.message(F.text == "➕ Добавить товар")
async def start_add_product(message: types.Message, state: FSMContext):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    await state.set_state(AddProduct.waiting_for_name)
    await message.answer(" <b>Добавление товара</b>\n\n📝 Шаг 1/5: Введите название товара:", reply_markup=close_admin_btn(), parse_mode="HTML")

@router.message(AddProduct.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProduct.waiting_for_description)
    await message.answer("📝 Шаг 2/5: Введите описание товара:\n\n⚠️ /admin для отмены", reply_markup=close_admin_btn())

@router.message(AddProduct.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddProduct.waiting_for_price)
    await message.answer("💰 Шаг 3/5: Введите цену (только число, например: 1500):\n\n⚠️ /admin для отмены", reply_markup=close_admin_btn())

@router.message(AddProduct.waiting_for_price)
async def process_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
        await state.update_data(price=price)
        await state.set_state(AddProduct.waiting_for_image)
        await message.answer(
            "📸 Шаг 4/5: Отправьте <b>ссылку на фото товара</b>\n\n"
            "Например: https://example.com/photo.jpg\n\n"
            "Или отправьте /skip чтобы пропустить фото\n\n"
            "⚠️ /admin для отмены",
            reply_markup=close_admin_btn(),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверная цена. Введите число (например: 1500):\n\n⚠️ /admin для отмены", reply_markup=close_admin_btn())

@router.message(AddProduct.waiting_for_image, F.text == "/skip")
async def skip_image(message: types.Message, state: FSMContext):
    await state.update_data(image="")
    await state.set_state(AddProduct.waiting_for_category)
    await show_category_buttons(message)

@router.message(AddProduct.waiting_for_image)
async def process_image(message: types.Message, state: FSMContext):
    image_url = message.text.strip()
    if image_url.startswith("http"):
        await state.update_data(image=image_url)
        await state.set_state(AddProduct.waiting_for_category)
        await show_category_buttons(message)
    else:
        await message.answer("❌ Это не ссылка. Введите URL картинки (начинается с http) или отправьте /skip")

async def show_category_buttons(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💨 Одноразки", callback_data="cat_Одноразки")],
        [InlineKeyboardButton(text="🔋 Под-системы", callback_data="cat_Под-системы")],
        [InlineKeyboardButton(text="💧 Жидкость", callback_data="cat_Жидкость")],
        [InlineKeyboardButton(text="⚙️ Расходники", callback_data="cat_Расходники")],
        [InlineKeyboardButton(text="🌿 Жевательный табак", callback_data="cat_Жевательный табак")],
        [InlineKeyboardButton(text="🪝 Кальяны", callback_data="cat_Кальяны")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add")]
    ])
    await message.answer("📂 Шаг 5/5: Выберите категорию:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("cat_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.replace("cat_", "")
    data = await state.get_data()
    
    product_id = await add_product(
        category, data["name"], data["description"], data["price"], data.get("image", ""), ""
    )
    
    await state.clear()
    
    preview_text = (
        f"✅ <b>Товар добавлен!</b>\n\n"
        f"🆔 ID: {product_id}\n"
        f"📦 Название: {data['name']}\n"
        f"📝 Описание: {data['description']}\n"
        f"💰 Цена: {data['price']} ₽\n"
        f" Категория: {category}\n"
        f"📸 Фото: {'добавлено' if data.get('image') else 'не добавлено'}"
    )
    
    if data.get("image"):
        await callback.message.answer_photo(
            photo=data["image"],
            caption=preview_text,
            parse_mode="HTML",
            reply_markup=admin_menu()
        )
    else:
        await callback.message.answer(preview_text, parse_mode="HTML", reply_markup=admin_menu())
    
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data == "cancel_add")
async def cancel_add(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Добавление отменено", reply_markup=admin_menu())
    await callback.answer()

@router.message(F.text == "📋 Список товаров")
async def list_products(message: types.Message):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    
    conn = await get_db()
    try:
        products = await conn.fetch("SELECT id, name, price, category FROM products ORDER BY id DESC LIMIT 20")
    finally:
        await conn.close()
    
    if not products:
        await message.answer("📋 Список товаров пуст", reply_markup=admin_menu())
        return
    
    text = "📋 <b>Список товаров:</b>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for p in products:
        text += f"ID: {p['id']} | {p['name']} — {p['price']}₽ ({p['category']})\n"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"🗑 {p['name'][:20]}", callback_data=f"del_{p['id']}")
        ])
    
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_admin")])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("del_"))
async def delete_product_handler(callback: types.CallbackQuery):
    product_id = int(callback.data.replace("del_", ""))
    await delete_product(product_id)
    await callback.answer("✅ Товар удалён")
    await callback.message.edit_text("🗑 Товар удалён. Выберите действие:", reply_markup=admin_menu())

@router.callback_query(F.data == "back_admin")
async def back_to_admin(callback: types.CallbackQuery):
    await callback.message.edit_text("⚙️ Панель администратора", reply_markup=admin_menu())
    await callback.answer()

@router.message(F.text == "📦 Заказы")
async def show_orders(message: types.Message):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    await message.answer("📦 Заказы приходят вам в личные сообщения от бота.", reply_markup=admin_menu())

@router.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    
    products_count = await get_product_count()
    users_count = await get_user_count()
    
    text = (
        "📊 <b>Статистика магазина</b>\n\n"
        f"📦 Товаров: {products_count}\n"
        f"👥 Пользователей: {users_count}"
    )
    await message.answer(text, reply_markup=admin_menu(), parse_mode="HTML")

@router.message(F.text == "📢 Рассылка")
async def start_broadcast(message: types.Message, state: FSMContext):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    await state.set_state(SendMessage.waiting_for_text)
    await message.answer("📢 Введите текст рассылки:\n\n⚠️ /admin для отмены", reply_markup=close_admin_btn())

@router.message(SendMessage.waiting_for_text)
async def process_broadcast(message: types.Message, state: FSMContext):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    
    text = message.text
    await state.clear()
    
    user_ids = await get_all_users()
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
    
    await message.answer(f"✅ Рассылка завершена!\n\n📤 Отправлено: {sent}\n❌ Ошибок: {failed}", reply_markup=admin_menu())

@router.message(F.text == "👥 Пользователи")
async def show_users(message: types.Message):
    admin_id = get_admin_id(router)
    if not is_admin(message.from_user.id, admin_id):
        return
    
    conn = await get_db()
    try:
        users = await conn.fetch("SELECT user_id, username, full_name FROM users ORDER BY created_at DESC LIMIT 20")
    finally:
        await conn.close()
    
    if not users:
        await message.answer("👥 Пользователей пока нет", reply_markup=admin_menu())
        return
    
    text = " <b>Последние пользователи:</b>\n\n"
    for u in users:
        username = f"@{u['username']}" if u['username'] else "без username"
        text += f"• {u['full_name']} ({username}) — ID: {u['user_id']}\n"
    
    await message.answer(text, reply_markup=admin_menu(), parse_mode="HTML")
