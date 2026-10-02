from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import (
    get_user_count, get_product_count, get_categories, get_category_by_id,
    get_products, add_product, delete_product, add_category, delete_category
)

router = Router()

_admin_id = None
_bot = None

# Состояния для добавления товара
class AddProduct(StatesGroup):
    category = State()
    name = State()
    description = State()
    price = State()
    image = State()
    flavors = State()

# Состояния для добавления категории
class AddCategory(StatesGroup):
    name = State()
    image = State()

def setup_admin(admin_id, bot_instance):
    global _admin_id, _bot
    _admin_id = int(admin_id) if admin_id else None
    _bot = bot_instance
    print(f"✅ Админ ID установлен: {_admin_id}")

def is_admin(user_id) -> bool:
    if _admin_id is None:
        return False
    return int(user_id) == int(_admin_id)

# ========== КЛАВИАТУРЫ ==========

def get_admin_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📦 Управление товарами", callback_data="admin_products")],
        [InlineKeyboardButton(text="📂 Управление категориями", callback_data="admin_categories")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast_placeholder")],
        [InlineKeyboardButton(text="🔙 Закрыть панель", callback_data="admin_close")]
    ])

def get_admin_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="admin_menu")]
    ])

def get_products_keyboard(categories):
    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(
            text=f" {cat['name']}",
            callback_data=f"admin_view_cat_{cat['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_products_list_keyboard(products, category_name):
    buttons = []
    for p in products[:20]:
        name_short = p['name'][:25] + "..." if len(p['name']) > 25 else p['name']
        buttons.append([InlineKeyboardButton(
            text=f"🗑 {name_short} — {int(p['price'])}₽",
            callback_data=f"admin_del_prod_{p['id']}"  # ✅ Изменён префикс
        )])
    buttons.append([InlineKeyboardButton(text=f" К категориям", callback_data="admin_products")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_categories_manage_keyboard(categories):
    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(
            text=f" {cat['name']}",
            callback_data=f"admin_remove_cat_{cat['id']}"  # ✅ Изменён префикс
        )])
    buttons.append([InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin_add_category")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_category_select_keyboard(categories):
    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(
            text=cat['name'],
            callback_data=f"admin_sel_cat_{cat['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_menu")]
    ])

# ========== ОБРАБОТЧИКИ ГЛАВНОГО МЕНЮ ==========

@router.message(Command("admin"))
async def admin_command(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    await message.answer(
        " **Панель администратора PUFFY**\n\nВыберите действие:",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_menu")
async def admin_menu(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        " **Панель администратора PUFFY**\n\nВыберите действие:",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    try:
        users = await get_user_count()
        products = await get_product_count()
        text = (
            "📊 **Статистика магазина**\n\n"
            f"👥 Всего пользователей: `{users}`\n"
            f" Всего товаров в каталоге: `{products}`\n\n"
            "Данные актуальны на текущий момент."
        )
        await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="Markdown")
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)
    await callback.answer()

# ========== УПРАВЛЕНИЕ ТОВАРАМИ ==========

@router.callback_query(F.data == "admin_products")
async def admin_products(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    try:
        categories = await get_categories()
        if not categories:
            await callback.message.edit_text(
                "📂 Категории не найдены. Сначала создайте категорию.",
                reply_markup=get_admin_back_keyboard()
            )
        else:
            text = "📦 **Управление товарами**\n\nВыберите категорию для просмотра или добавьте новый товар:"
            await callback.message.edit_text(
                text,
                reply_markup=get_products_keyboard(categories),
                parse_mode="Markdown"
            )
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_view_cat_"))
async def admin_view_category(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    try:
        cat_id = int(callback.data.split("_")[-1])
        category = await get_category_by_id(cat_id)
        if not category:
            await callback.answer("Категория не найдена", show_alert=True)
            return
        
        products = await get_products(category['name'])
        if not products:
            text = f"📂 **{category['name']}**\n\nТоваров в категории пока нет."
        else:
            text = f"📂 **{category['name']}**\n\nНайдено товаров: {len(products)}\n\nНажмите на товар, чтобы удалить его:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_products_list_keyboard(products, category['name']),
            parse_mode="Markdown"
        )
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_del_prod_"))  # ✅ Изменён префикс
async def admin_delete_product(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(" Доступ запрещен", show_alert=True)
        return
    try:
        product_id = int(callback.data.split("_")[-1])
        await delete_product(product_id)
        await callback.message.edit_text(
            f"✅ Товар ID {product_id} удалён из базы данных.",
            reply_markup=get_admin_back_keyboard()
        )
    except Exception as e:
        await callback.answer(f"Ошибка удаления: {e}", show_alert=True)
    await callback.answer()

# ========== ДОБАВЛЕНИЕ ТОВАРА ==========

@router.callback_query(F.data == "admin_add_product")
async def admin_add_product_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(" Доступ запрещен", show_alert=True)
        return
    categories = await get_categories()
    if not categories:
        await callback.message.edit_text(
            "❌ Сначала создайте хотя бы одну категорию!",
            reply_markup=get_admin_back_keyboard()
        )
        await callback.answer()
        return
    
    await state.set_state(AddProduct.category)
    await callback.message.edit_text(
        "➕ **Добавление товара**\n\nШаг 1/6: Выберите категорию:",
        reply_markup=get_category_select_keyboard(categories),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(AddProduct.category, F.data.startswith("admin_sel_cat_"))
async def process_category_select(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    cat_id = int(callback.data.split("_")[-1])
    category = await get_category_by_id(cat_id)
    if not category:
        await callback.answer("Категория не найдена", show_alert=True)
        return
    
    await state.update_data(category=category['name'])
    await state.set_state(AddProduct.name)
    await callback.message.edit_text(
        f"✅ Категория: **{category['name']}**\n\n📝 Шаг 2/6: Введите **название товара**:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.message(AddProduct.name)
async def process_name(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddProduct.description)
    await message.answer(
        "📝 Шаг 3/6: Введите **описание товара**:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

@router.message(AddProduct.description)
async def process_description(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(description=message.text.strip())
    await state.set_state(AddProduct.price)
    await message.answer(
        "💰 Шаг 4/6: Введите **цену** (только число, например 1500):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

@router.message(AddProduct.price)
async def process_price(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        price = float(message.text.strip().replace(",", "."))
        await state.update_data(price=price)
        await state.set_state(AddProduct.image)
        await message.answer(
            "🖼 Шаг 5/6: Отправьте **фото товара** (или напишите 'нет', чтобы пропустить):",
            reply_markup=get_cancel_keyboard(),
            parse_mode="Markdown"
        )
    except ValueError:
        await message.answer("❌ Неверный формат цены. Введите число, например 1500")

@router.message(AddProduct.image, F.photo)
async def process_image_photo(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    photo = message.photo[-1]
    file = await _bot.get_file(photo.file_id)
    file_url = f"https://api.telegram.org/file/bot{_bot.token}/{file.file_path}"
    await state.update_data(image=file_url)
    await state.set_state(AddProduct.flavors)
    await message.answer(
        "🎨 Шаг 6/6: Введите **вкусы/варианты** (через запятую) или напишите 'нет':",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

@router.message(AddProduct.image)
async def process_image_text(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip().lower()
    if text in ("нет", "no", "-"):
        await state.update_data(image="")
    else:
        await state.update_data(image=message.text.strip())
    await state.set_state(AddProduct.flavors)
    await message.answer(
        "🎨 Шаг 6/6: Введите **вкусы/варианты** (через запятую) или напишите 'нет':",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

@router.message(AddProduct.flavors)
async def process_flavors(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    flavors = "" if text.lower() in ("нет", "no", "-") else text
    
    data = await state.get_data()
    try:
        product_id = await add_product(
            category=data['category'],
            name=data['name'],
            description=data['description'],
            price=data['price'],
            image=data.get('image', ''),
            flavors=flavors
        )
        await message.answer(
            f"✅ **Товар добавлен!**\n\n"
            f"📂 Категория: {data['category']}\n"
            f" Название: {data['name']}\n"
            f"💰 Цена: {int(data['price'])}₽\n"
            f" ID товара: {product_id}",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка добавления: {e}")
    await state.clear()

# ========== УПРАВЛЕНИЕ КАТЕГОРИЯМИ ==========

@router.callback_query(F.data == "admin_categories")
async def admin_categories(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    try:
        categories = await get_categories()
        if not categories:
            text = "📂 **Управление категориями**\n\nКатегорий пока нет. Создайте первую!"
        else:
            text = "📂 **Управление категориями**\n\nНажмите на категорию, чтобы удалить её (если в ней нет товаров):"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_categories_manage_keyboard(categories),
            parse_mode="Markdown"
        )
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_remove_cat_"))  # ✅ Изменён префикс
async def admin_delete_category(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    try:
        cat_id = int(callback.data.split("_")[-1])
        category = await get_category_by_id(cat_id)
        if not category:
            await callback.answer("Категория не найдена", show_alert=True)
            return
        
        success, product_count = await delete_category(cat_id)
        
        if not success:
            await callback.message.edit_text(
                f"❌ Нельзя удалить категорию **{category['name']}**!\n\n"
                f"В ней ещё {product_count} товар(ов). Сначала удалите товары.",
                reply_markup=get_admin_back_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                f"✅ Категория **{category['name']}** удалена.",
                reply_markup=get_admin_back_keyboard(),
                parse_mode="Markdown"
            )
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)
    await callback.answer()

# ========== ДОБАВЛЕНИЕ КАТЕГОРИИ ==========

@router.callback_query(F.data == "admin_add_category")
async def admin_add_category_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await state.set_state(AddCategory.name)
    await callback.message.edit_text(
        "➕ **Добавление категории**\n\nШаг 1/2: Введите **название категории** (например: Одноразки):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.message(AddCategory.name)
async def process_category_name(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    
    # Проверяем, нет ли уже такой категории
    from database import get_category_by_name
    existing = await get_category_by_name(name)
    if existing:
        await message.answer(f"❌ Категория '{name}' уже существует!")
        return
    
    await state.update_data(name=name)
    await state.set_state(AddCategory.image)
    await message.answer(
        f"✅ Название: **{name}**\n\n🖼 Шаг 2/2: Отправьте **фото категории** (или напишите 'нет', чтобы пропустить):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

@router.message(AddCategory.image, F.photo)
async def process_category_image_photo(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    photo = message.photo[-1]
    file = await _bot.get_file(photo.file_id)
    file_url = f"https://api.telegram.org/file/bot{_bot.token}/{file.file_path}"
    await state.update_data(image=file_url)
    
    data = await state.get_data()
    try:
        cat_id = await add_category(data['name'], file_url)
        await message.answer(
            f"✅ **Категория добавлена!**\n\n"
            f"📂 Название: {data['name']}\n"
            f"🆔 ID: {cat_id}\n\n"
            f"Теперь можно добавлять товары в эту категорию.",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()

@router.message(AddCategory.image)
async def process_category_image_text(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip().lower()
    image_url = "" if text in ("нет", "no", "-") else message.text.strip()
    
    data = await state.get_data()
    try:
        cat_id = await add_category(data['name'], image_url)
        await message.answer(
            f"✅ **Категория добавлена!**\n\n"
            f"📂 Название: {data['name']}\n"
            f"🆔 ID: {cat_id}\n\n"
            f"Теперь можно добавлять товары в эту категорию.",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()

# ========== ЗАКРЫТИЕ И ЗАГЛУШКИ ==========

@router.callback_query(F.data == "admin_close")
async def admin_close(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(" Доступ запрещен", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text("✅ Панель администратора закрыта.")
    await callback.answer()

@router.callback_query(F.data == "admin_broadcast_placeholder")
async def admin_placeholder(callback: types.CallbackQuery):
    await callback.answer("⚙️ Этот раздел в разработке", show_alert=True)
