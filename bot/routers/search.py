from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.exceptions import TelegramBadRequest

from bot.repo import Repo
from bot.settings import FACULTIES

search_router = Router()


async def _safe_delete(msg: Message):
    try:
        await msg.delete()
    except TelegramBadRequest:
        pass
    except Exception:
        pass


def kb_search_card(target_tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👎 Пропустить", callback_data=f"s:skip:{target_tg_id}"),
        InlineKeyboardButton(text="Лайк ❤️", callback_data=f"s:like:{target_tg_id}")
    ], [
        InlineKeyboardButton(text="Меню 🏠", callback_data="menu:main")
    ]])


async def _show_next(message_or_call, repo: Repo, viewer_id: int):
    prefs = await repo.prefs_get(viewer_id)
    p = await repo.search_next(
        viewer_tg_id=viewer_id,  # <-- фикс имени аргумента
        looking_gender=prefs["looking_gender"],
        age_min=prefs["age_min"],
        age_max=prefs["age_max"],
        faculties=prefs["faculties"]
    )

    bot = message_or_call.bot if hasattr(message_or_call, "bot") else message_or_call
    chat_id = message_or_call.message.chat.id if hasattr(message_or_call, "message") else message_or_call.chat.id

    if not p:
        await bot.send_message(
            chat_id,
            "Анкеты подходящие под фильтры закончились 😔\n\n"
            "Можешь сбросить свайпы или поменять фильтры в меню!",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Меню 🏠", callback_data="menu:main")]]
            )
        )
        return

    # ВАЖНО: не mark_seen здесь.
    # Теперь seen только при like/skip.
    fac_name = FACULTIES.get(p["faculty_code"], "МГУ")
    caption = (
        f"<b>{p['display_name']}, {p['age']}</b>\n"
        f"🎓 МГУ, {fac_name}\n\n"
        f"<b>Интересы:</b> {', '.join(p['interests']) if p['interests'] else '—'}\n"
        f"<b>О себе:</b>\n{p['about']}"
    )
    await bot.send_photo(chat_id, photo=p["photo_file_id"], caption=caption, reply_markup=kb_search_card(p["tg_id"]))


@search_router.callback_query(F.data == "search:start")
async def start_search(call: CallbackQuery, repo: Repo):
    await _safe_delete(call.message)
    await _show_next(call, repo, call.from_user.id)
    await call.answer()


@search_router.callback_query(F.data == "search:reset")
async def reset_swipes(call: CallbackQuery, repo: Repo):
    await repo.reset_seen(call.from_user.id)
    await call.answer("История просмотров сброшена! ⚡", show_alert=True)


@search_router.callback_query(F.data.startswith("s:like:"))
async def like_cb(call: CallbackQuery, repo: Repo):
    target = int(call.data.split(":")[2])

    # карточка считается просмотренной только по действию
    await repo.mark_seen(call.from_user.id, target)
    await _safe_delete(call.message)

    is_match = await repo.like(call.from_user.id, target)

    if is_match:
        m_contact = await repo.contact_for(call.from_user.id)
        t_contact = await repo.contact_for(target)
        try:
            await call.bot.send_message(call.from_user.id, f"🎉 У вас мэтч!\nКонтакт: {t_contact or 'добавьте username'}")
        except Exception:
            pass
        try:
            await call.bot.send_message(target, f"🎉 У вас мэтч!\nКонтакт: {m_contact or 'добавьте username'}")
        except Exception:
            pass
    else:
        liker_profile = await repo.profile_get(call.from_user.id)
        if liker_profile:
            fac_name = FACULTIES.get(liker_profile["faculty_code"], "МГУ")
            caption = (
                f"🔔 <b>Твою анкету лайкнули!</b>\n\n"
                f"<b>{liker_profile['display_name']}, {liker_profile['age']}</b>\n"
                f"🎓 МГУ, {fac_name}\n\n"
                f"<b>Интересы:</b> {', '.join(liker_profile['interests']) if liker_profile['interests'] else '—'}\n"
                f"<b>О себе:</b>\n{liker_profile['about']}"
            )
            try:
                await call.bot.send_photo(
                    chat_id=target,
                    photo=liker_profile["photo_file_id"],
                    caption=caption,
                    reply_markup=kb_search_card(liker_profile["tg_id"])
                )
            except Exception:
                pass

    await _show_next(call, repo, call.from_user.id)
    await call.answer()


@search_router.callback_query(F.data.startswith("s:skip:"))
async def skip_cb(call: CallbackQuery, repo: Repo):
    target = int(call.data.split(":")[2])

    await repo.mark_seen(call.from_user.id, target)
    await _safe_delete(call.message)

    await _show_next(call, repo, call.from_user.id)
    await call.answer()


# === Ниже логика меню Фильтров ===

async def render_filters_menu(msg, tg_id: int, repo: Repo):
    prefs = await repo.prefs_get(tg_id)
    g_label = {"any": "🙋 любого пола", "male": "👱 парней", "female": "👧 девушек"}[prefs["looking_gender"]]
    fac_labels = [FACULTIES[f] for f in prefs["faculties"] if f in FACULTIES] if prefs["faculties"] else ["любого факультета"]

    text = (
        f"<b>Настройки фильтров поиска 🔍</b>\n\n"
        f"Сейчас ты ищешь {g_label} "
        f"от {prefs['age_min']} до {prefs['age_max']} лет "
        f"из: <b>{', '.join(fac_labels)}</b>\n\n"
        f"Что ты хочешь изменить?"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Фильтр по полу 🙋‍♀️", callback_data="sf:toggle:gender")],
        [InlineKeyboardButton(text="Фильтр по возрасту 🧒", callback_data="sf:toggle:age")],
        [InlineKeyboardButton(text="Фильтр по факультету 🏫", callback_data="sf:fac:menu")],
        [InlineKeyboardButton(text="Назад ↩️", callback_data="menu:settings")]
    ])
    await msg.edit_text(text, reply_markup=kb)


@search_router.callback_query(F.data == "search:filters:menu")
async def cb_filters_menu(call: CallbackQuery, repo: Repo):
    await _safe_delete(call.message)
    msg = await call.message.answer("Загрузка...")
    await render_filters_menu(msg, call.from_user.id, repo)
    await call.answer()


@search_router.callback_query(F.data.startswith("sf:toggle:"))
async def toggle_simple_filter(call: CallbackQuery, repo: Repo):
    field = call.data.split(":")[2]
    prefs = await repo.prefs_get(call.from_user.id)

    if field == "gender":
        n = {"any": "male", "male": "female", "female": "any"}[prefs["looking_gender"]]
        await repo.prefs_set(call.from_user.id, n, prefs["age_min"], prefs["age_max"], prefs["faculties"])
        await render_filters_menu(call.message, call.from_user.id, repo)

    await call.answer()


@search_router.callback_query(F.data == "sf:fac:menu")
async def fac_filter_menu(call: CallbackQuery, repo: Repo):
    prefs = await repo.prefs_get(call.from_user.id)
    rows = [[InlineKeyboardButton(text="✅ Любые", callback_data="sf:fac:toggle:any")]]

    for code, name in FACULTIES.items():
        m = "✅ " if code in prefs["faculties"] else ""
        rows.append([InlineKeyboardButton(text=f"{m}{name}", callback_data=f"sf:fac:toggle:{code}")])

    rows.append([InlineKeyboardButton(text="Готово ↩️", callback_data="search:filters:menu")])
    await call.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@search_router.callback_query(F.data.startswith("sf:fac:toggle:"))
async def fac_toggle(call: CallbackQuery, repo: Repo):
    code = call.data.split(":")[3]
    prefs = await repo.prefs_get(call.from_user.id)
    sel = set(prefs["faculties"])

    if code == "any":
        sel.clear()
    else:
        if code in sel:
            sel.remove(code)
        else:
            sel.add(code)

    await repo.prefs_set(call.from_user.id, prefs["looking_gender"], prefs["age_min"], prefs["age_max"], list(sel))
    await fac_filter_menu(call, repo)