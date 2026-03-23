from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.settings import settings
from bot.repo import Repo

admin_router = Router()


async def _safe_delete(msg: Message) -> None:
    try:
        await msg.delete()
    except TelegramBadRequest:
        pass
    except Exception:
        pass


@admin_router.message(Command("pending"))
async def pending(message: Message, repo: Repo):
    if message.from_user.id not in settings.admin_ids:
        return

    item = await repo.admin_pending()
    if not item:
        await message.answer("Очередь пустая. 🎉")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Принять", callback_data=f"v:ok:{item['request_id']}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"v:no:{item['request_id']}"),
    ]])

    username = f"@{item['username']}" if item.get("username") else "—"
    caption = (
        f"📝 <b>Заявка #{item['request_id']}</b>\n"
        f"User: {username}\n\n"
        f"<b>Анкета:</b>\n"
        f"Имя: {item.get('display_name') or '—'}\n"
        f"Пол: {item.get('gender') or '—'}, Возраст: {item.get('age') or '—'}\n"
        f"Факультет: {item.get('faculty_code') or '—'}\n"
        f"О себе: {item.get('about') or '—'}\n\n"
        f"👇 Фото студенческого:"
    )
    await message.answer_photo(photo=item["student_card_file_id"], caption=caption, reply_markup=kb)


@admin_router.callback_query(F.data.startswith("v:"))
async def callbacks(call: CallbackQuery, repo: Repo):
    if call.from_user.id not in settings.admin_ids:
        await call.answer("Недостаточно прав", show_alert=True)
        return

    _, decision, req_id_str = call.data.split(":", 2)
    req_id = int(req_id_str)

    try:
        user_tg_id = await repo.admin_decide(
            req_id,
            call.from_user.id,
            "APPROVED" if decision == "ok" else "REJECTED"
        )
        if not user_tg_id:
            raise ValueError
    except Exception:
        await call.answer("Уже обработано", show_alert=True)
        return

    await _safe_delete(call.message)

    if decision == "ok":
        await call.message.answer(f"✅ Заявка #{req_id} одобрена.")
        try:
            await call.bot.send_message(
                user_tg_id,
                "🎉 Твоя анкета подтверждена!\nЖми /menu, чтобы начать искать пару!"
            )
        except Exception:
            pass
    else:
        await call.message.answer(f"❌ Заявка #{req_id} отклонена.")
        try:
            await call.bot.send_message(
                user_tg_id,
                "К сожалению, мы не смогли верифицировать анкету.\nОтправь /start, чтобы податься снова."
            )
        except Exception:
            pass

    await call.answer()