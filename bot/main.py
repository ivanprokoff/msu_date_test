import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from bot.settings import settings
from bot.repo import Repo
from bot.middlewares.repo import RepoMiddleware

from bot.routers.menu import menu_router
from bot.routers.user import user_router
from bot.routers.admin import admin_router
from bot.routers.profile import profile_router
from bot.routers.search import search_router

async def main():
    session = AiohttpSession(proxy=settings.proxy_url) if settings.proxy_url else AiohttpSession()

    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    repo = Repo(settings.db_path)
    await repo.init()

    dp.update.middleware(RepoMiddleware(repo))

    # user_router должен идти раньше, т.к. ловит все состояния RegistrationFSM
    dp.include_router(user_router)
    dp.include_router(menu_router)
    dp.include_router(profile_router)
    dp.include_router(search_router)
    dp.include_router(admin_router)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
