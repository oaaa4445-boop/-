from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import get_user_count, get_product_count

router = Router()

# Глобальные переменные
_admin_id = None
_bot = None

def setup_admin(admin_id, bot_instance):
    """Устанавливает ID админа и экземпляр бота"""
    global _admin_id, _bot
    # ✅ Принудительно преобразуем в int
    _admin_id = int(admin_id) if admin_id else None
    _bot = bot_instance
    print(f"✅ Админ ID установлен: {_admin_id} (тип: {type(_admin_id).__name__})")

def get_admin_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📦 Управление товарами", callback_data="admin_products_placeholder")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast_placeholder")],
        [InlineKeyboardButton(text="🔙 Закрыть панель", callback_data="admin_close")]
    ])

def get_admin_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=" Назад в меню", callback_data="admin_menu")]
    ])

def is_admin(user_id) -> bool:
    """Проверка, является ли пользователь админом (с приведением типов)"""
    if _admin_id is None:
        return False
    return int(user_id) == int(_admin_id)

@router.message(Command("admin"))
async def admin_command(message: types.Message):
    user_id = message.from_user.id
    print(f"🔍 Попытка доступа к /admin от пользователя {user_id} (тип: {type(user_id).__name__})")
    print(f"   Ожидаемый admin_id: {_admin_id} (тип: {type(_admin_id).__name__})")
    
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    await message.answer(
        "🛠 **Панель администратора PUFFY**\n\nВыберите действие:",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_menu")
async def admin_menu(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🛠 **Панель администратора PUFFY**\n\nВыберите действие:",
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
            f" Всего пользователей: `{users}`\n"
            f"📦 Всего товаров в каталоге: `{products}`\n\n"
            "Данные актуальны на текущий момент."
        )
        await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="Markdown")
    except Exception as e:
        await callback.answer(f"Ошибка получения данных: {e}", show_alert=True)
    await callback.answer()

@router.callback_query(F.data == "admin_close")
async def admin_close(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(" Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text("✅ Панель администратора закрыта.")
    await callback.answer()

@router.callback_query(F.data.in_(["admin_products_placeholder", "admin_broadcast_placeholder"]))
async def admin_placeholder(callback: types.CallbackQuery):
    await callback.answer("⚙️ Этот раздел в разработке", show_alert=True)
