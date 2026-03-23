from aiogram import BaseMiddleware
from typing import Any, Awaitable, Callable, Dict


class RepoMiddleware(BaseMiddleware):
    def __init__(self, repo) -> None:
        self.repo = repo

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        data["repo"] = self.repo
        return await handler(event, data)