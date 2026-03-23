from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from bot.repo import Repo
from bot.settings import FACULTIES

profile_router = Router()


class EditProfileFSM(StatesGroup):
    wait_text = State()
    wait_photo = State()


async def render_profile_menu(message_to_edit, tg_id: int, repo: Repo):
    profile = await repo.profile_get(tg_id)
    faculty_name = FACULTIES.get(profile["faculty_code"], "—")

    text = (
        f"<b>Имя:</b> {profile['display_name']}\n"
        f"<b>Пол:</b> {'Мужской' if profile['gender'] == 'male' else 'Женский'}\n"
        f"<b>Возраст:</b> {profile['age']}\n"
        f"<b>Описание:</b>\n{profile['about']}\n\n"
        f"<b>Интересы:</b> {', '.join(profile['interests'])}\n"
        f"<b>Вуз:</b> МГУ\n"
        f"<b>Факультет:</b> {faculty_name}\n\n"
        f"Что ты хочешь изменить?"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Аватар 📸", callback_data="p:edit:photo"),
            InlineKeyboardButton(text="Имя 🗣", callback_data="p:edit:name")
        ],
        [
            InlineKeyboardButton(text="Пол 👱", callback_data="p:edit:gender"),
            InlineKeyboardButton(text="Возраст 🧒", callback_data="p:edit:age")
        ],
        [
            InlineKeyboardButton(text="Описание ✏️", callback_data="p:edit:about"),
            InlineKeyboardButton(text="Интересы 🏄‍♂️", callback_data="p:edit:interests")
        ],
        [
            InlineKeyboardButton(text="Факультет 🏫", callback_data="p:edit:faculty")
        ],
        [InlineKeyboardButton(text="Назад ↩️", callback_data="menu:settings")]
    ])

    await message_to_edit.edit_text(text, reply_markup=kb)


@profile_router.callback_query(F.data == "profile:menu")
async def cb_profile_menu(call: CallbackQuery, repo: Repo, state: FSMContext):
    await state.clear()
    await call.message.delete()
    # Sending dummy text to be replaced by edit_text inside the function
    msg = await call.message.answer("Загрузка...")
    await render_profile_menu(msg, call.from_user.id, repo)
    await call.answer()


@profile_router.callback_query(F.data.startswith("p:edit:"))
async def cb_edit_field(call: CallbackQuery, state: FSMContext, repo: Repo):
    field = call.data.split(":")[2]

    if field == "gender":
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Парень", callback_data="p:save:gender:male"),
            InlineKeyboardButton(text="Девушка", callback_data="p:save:gender:female")
        ]])
        await call.message.edit_text("Укажи новый пол:", reply_markup=kb)
    elif field == "faculty":
        facs = [[InlineKeyboardButton(text=name, callback_data=f"p:save:faculty:{code}")] for code, name in
                FACULTIES.items()]
        await call.message.edit_text("Выбери новый факультет:", reply_markup=InlineKeyboardMarkup(inline_keyboard=facs))
    elif field == "photo":
        await call.message.edit_text("Отправь новое фото для анкеты:")
        await state.set_state(EditProfileFSM.wait_photo)
    else:
        prompts = {
            "name": "Введи новое имя:",
            "age": "Введи новый возраст (число):",
            "about": "Напиши новое описание о себе:",
            "interests": "Напиши новые интересы через запятую:"
        }
        await state.update_data(field=field, msg_id=call.message.message_id)
        await call.message.edit_text(prompts[field])
        await state.set_state(EditProfileFSM.wait_text)

    await call.answer()


@profile_router.callback_query(F.data.startswith("p:save:"))
async def cb_save_inline(call: CallbackQuery, repo: Repo):
    _, _, field, val = call.data.split(":")
    if field == "faculty":
        await repo.profile_update_field(call.from_user.id, "faculty_code", val)
    else:
        await repo.profile_update_field(call.from_user.id, field, val)

    await render_profile_menu(call.message, call.from_user.id, repo)
    await call.answer("Сохранено!", show_alert=True)


@profile_router.message(EditProfileFSM.wait_text)
async def on_edit_text(message: Message, state: FSMContext, repo: Repo):
    data = await state.get_data()
    field = data["field"]
    val = message.text

    if field == "age" and (not val.isdigit() or not (18 <= int(val) <= 35)):
        await message.answer("Ошибка! Введи возраст от 18 до 35.")
        return
    if field == "interests":
        val = [s.strip() for s in val.split(",") if s.strip()]

    await repo.profile_update_field(message.from_user.id, field, val)

    try:
        await message.bot.delete_message(message.chat.id, data["msg_id"])
    except:
        pass
    await message.delete()

    msg = await message.answer("Обновление...")
    await render_profile_menu(msg, message.from_user.id, repo)
    await state.clear()


@profile_router.message(EditProfileFSM.wait_photo, F.photo)
async def on_edit_photo(message: Message, state: FSMContext, repo: Repo):
    await repo.profile_update_field(message.from_user.id, "photo_file_id", message.photo[-1].file_id)
    await message.delete()

    msg = await message.answer("Обновление...")
    await render_profile_menu(msg, message.from_user.id, repo)
    await state.clear()