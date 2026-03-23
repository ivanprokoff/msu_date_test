from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from bot.repo import Repo
from bot.settings import FACULTIES

menu_router = Router()


async def _safe_delete(msg: Message):
    try:
        await msg.delete()
    except TelegramBadRequest:
        pass
    except Exception:
        pass


async def send_main_menu(message_or_bot, chat_id: int, tg_id: int, repo: Repo):
    profile = await repo.profile_get(tg_id)
    if not profile:
        return

    faculty_name = FACULTIES.get(profile["faculty_code"], "—")
    caption = (
        f"<b>{profile['display_name']}, {profile['age']}</b>\n\n"
        f"🎓: МГУ, {faculty_name}\n\n"
        f"<b>О себе:</b>\n{profile['about']}\n\n"
        f"<b>Интересы:</b> {', '.join(profile['interests']) if profile['interests'] else '—'}\n"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Смотреть анкеты 🔥", callback_data="search:start")],
        [InlineKeyboardButton(text="Сброс свайпов ⚡", callback_data="search:reset")],
        [InlineKeyboardButton(text="Настройки ⚙️", callback_data="menu:settings")],
    ])

    if hasattr(message_or_bot, "answer_photo"):
        await message_or_bot.answer_photo(photo=profile["photo_file_id"], caption=caption, reply_markup=kb)
    else:
        await message_or_bot.send_photo(chat_id=chat_id, photo=profile["photo_file_id"], caption=caption, reply_markup=kb)


@menu_router.message(Command("menu"))
async def cmd_menu(message: Message, repo: Repo):
    status = await repo.user_status(message.from_user.id)
    if status == "VERIFIED":
        await send_main_menu(message, message.chat.id, message.from_user.id, repo)
    else:
        await message.answer("Сначала пройди регистрацию и верификацию: /start")


@menu_router.callback_query(F.data == "menu:main")
async def cb_main_menu(call: CallbackQuery, repo: Repo):
    await _safe_delete(call.message)
    await send_main_menu(call.bot, call.message.chat.id, call.from_user.id, repo)
    await call.answer()


@menu_router.callback_query(F.data == "menu:settings")
async def cb_settings(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Анкету 💃", callback_data="profile:menu"),
            InlineKeyboardButton(text="Фильтры поиска 🔍", callback_data="search:filters:menu")
        ],
        [InlineKeyboardButton(text="Назад ↩️", callback_data="menu:main")]
    ])

    await _safe_delete(call.message)
    await call.message.answer("<b>Настройки ⚙️</b>\n\nЧто ты хочешь изменить?", reply_markup=kb)
    await call.answer()