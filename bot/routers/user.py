from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from bot.repo import Repo
from bot.settings import FACULTIES
from bot.routers.menu import send_main_menu

user_router = Router()


class RegFSM(StatesGroup):
    name = State()
    gender = State()
    age = State()
    faculty = State()
    interests = State()
    about = State()
    photo = State()
    student_card = State()


@user_router.message(Command("start"))
async def cmd_start(message: Message, repo: Repo, state: FSMContext):
    await repo.upsert_user(message.from_user.id, message.from_user.username)
    status = await repo.user_status(message.from_user.id)

    if status == "VERIFIED":
        await send_main_menu(message, message.chat.id, message.from_user.id, repo)
    elif status == "PENDING":
        await message.answer("Твоя заявка на верификацию находится на рассмотрении ⏳")
    elif status == "REJECTED":
        await message.answer("Верификация отклонена. Пожалуйста, пришли новое четкое фото студенческого билета:")
        await state.set_state(RegFSM.student_card)
    else:
        await state.clear()
        await message.answer("Привет! Давай создадим анкету. Как тебя зовут?")
        await state.set_state(RegFSM.name)


@user_router.message(RegFSM.name)
async def reg_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text[:32])
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Парень", callback_data="reg:gender:male"),
        InlineKeyboardButton(text="Девушка", callback_data="reg:gender:female")
    ]])
    await message.answer("Отлично! Укажи свой пол:", reply_markup=kb)
    await state.set_state(RegFSM.gender)


@user_router.callback_query(RegFSM.gender, F.data.startswith("reg:gender:"))
async def reg_gender(call: CallbackQuery, state: FSMContext):
    gender = call.data.split(":")[2]
    await state.update_data(gender=gender)
    await call.message.edit_text("Сколько тебе лет? (напиши число от 18 до 35)")
    await state.set_state(RegFSM.age)
    await call.answer()


@user_router.message(RegFSM.age)
async def reg_age(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (18 <= int(message.text) <= 35):
        await message.answer("Возраст должен быть числом от 18 до 35. Попробуй еще раз:")
        return
    await state.update_data(age=int(message.text))

    facs = [[InlineKeyboardButton(text=name, callback_data=f"reg:fac:{code}")] for code, name in FACULTIES.items()]
    kb = InlineKeyboardMarkup(inline_keyboard=facs)
    await message.answer("Выбери свой факультет в МГУ:", reply_markup=kb)
    await state.set_state(RegFSM.faculty)


@user_router.callback_query(RegFSM.faculty, F.data.startswith("reg:fac:"))
async def reg_faculty(call: CallbackQuery, state: FSMContext):
    fac = call.data.split(":")[2]
    await state.update_data(faculty=fac)
    await call.message.edit_text("Напиши свои интересы через запятую (например: спорт, кино, прогулки):")
    await state.set_state(RegFSM.interests)
    await call.answer()


@user_router.message(RegFSM.interests)
async def reg_interests(message: Message, state: FSMContext):
    interests = [s.strip() for s in (message.text or "").split(",") if s.strip()]
    await state.update_data(interests=interests)
    await message.answer("Напиши пару слов о себе для анкеты:")
    await state.set_state(RegFSM.about)


@user_router.message(RegFSM.about)
async def reg_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text[:400])
    await message.answer("Супер! Теперь пришли свою фотографию для анкеты (просто отправь фото):")
    await state.set_state(RegFSM.photo)


@user_router.message(RegFSM.photo, F.photo)
async def reg_photo(message: Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer(
        "Анкета почти готова!\nДля доступа к знакомствам МГУ мы запрашиваем верификацию. "
        "Пожалуйста, пришли фото своего студенческого билета (он нигде не будет опубликован, только для модерации)."
    )
    await state.set_state(RegFSM.student_card)


@user_router.message(RegFSM.student_card, F.photo)
async def reg_student_card(message: Message, state: FSMContext, repo: Repo):
    data = await state.get_data()

    if "name" in data:  # Full registration flow
        await repo.profile_upsert(
            tg_id=message.from_user.id,
            display_name=data["name"],
            gender=data["gender"],
            age=data["age"],
            faculty_code=data["faculty"],
            interests=data["interests"],
            about=data["about"],
            photo_file_id=data["photo"],
        )

    file_id = message.photo[-1].file_id
    req_id = await repo.submit_verification(message.from_user.id, file_id)
    await state.clear()
    await message.answer(
        f"✅ Фото получено! Заявка #{req_id} отправлена на проверку. Мы напишем, когда модератор проверит её.")