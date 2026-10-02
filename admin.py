from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import get_user_count, get_product_count

router = Router()

# Эти переменные будут заполнены из main.py
admin_id = None
bot = None

def get_admin_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📦 Управление товарами", callback_data="admin_products_placeholder")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast_placeholder")],
        [InlineKeyboardButton(text="🔙 Закрыть панель", callback_data="admin_close")]
    ])

def get_admin_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="admin_menu")]
    ])

# ✅ ОБРАБОТЧИК КОМАНДЫ /admin
@router.message(Command("admin"))
async def admin_command(message: types.Message):
    if message.from_user.id != admin_id:
        await message.answer(" Доступ запрещен")
        return
    
    await message.answer(
        "🛠 **Панель администратора PUFFY**\n\nВыберите действие:",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_menu")
async def admin_menu(callback: types.CallbackQuery):
    if callback.from_user.id != admin_id:
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
    if callback.from_user.id != admin_id:
        await callback.answer(" Доступ запрещен", show_alert=True)
        return
    
    try:
        users = await get_user_count()
        products = await get_product_count()
        
        text = (
            "📊 **Статистика магазина**\n\n"
            f"👥 Всего пользователей: `{users}`\n"
            f"📦 Всего товаров в каталоге: `{products}`\n\n"
            "Данные актуальны на текущий момент."
        )
        await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="Markdown")
    except Exception as e:
        await callback.answer(f"Ошибка получения данных: {e}", show_alert=True)
    await callback.answer()

@router.callback_query(F.data == "admin_close")
async def admin_close(callback: types.CallbackQuery):
    if callback.from_user.id != admin_id:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text("✅ Панель администратора закрыта.")
    await callback.answer()

@router.callback_query(F.data.in_(["admin_products_placeholder", "admin_broadcast_placeholder"]))
async def admin_placeholder(callback: types.CallbackQuery):
    await callback.answer("⚙️ Этот раздел в разработке", show_alert=True)
