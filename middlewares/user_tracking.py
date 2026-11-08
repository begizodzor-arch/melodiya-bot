from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
import database


class UserTrackingMiddleware(BaseMiddleware):
    """
    Har bir xabar/callback da foydalanuvchini avtomatik bazaga yozish
    va faolligini yangilash.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user and not user.is_bot:
            await database.add_user(
                user_id=user.id,
                username=user.username,
                full_name=user.full_name or user.first_name or "",
            )

        return await handler(event, data)

