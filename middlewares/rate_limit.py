import time
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

logger = logging.getLogger(__name__)

# Foydalanuvchi oxirgi so'rov vaqtini saqlash
_last_request: Dict[int, float] = {}

# Minimum vaqt oralig'i (sekund) qo'shiq yuklab olish uchun
DOWNLOAD_COOLDOWN = 5.0


class RateLimitMiddleware(BaseMiddleware):
    """
    Foydalanuvchi juda tez-tez so'rov yuborishini cheklaydi.
    Asosan yuklab olish so'rovlari uchun foydali.
    """

    def __init__(self, cooldown: float = DOWNLOAD_COOLDOWN):
        self.cooldown = cooldown

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            user_id = event.from_user.id
            now = time.time()
            last = _last_request.get(user_id, 0)
            diff = now - last

            if diff < self.cooldown:
                wait = int(self.cooldown - diff) + 1
                await event.answer(
                    f"⏳ Biroz kuting — {wait} soniyadan so'ng so'rov yuboring.",
                )
                return

            _last_request[user_id] = now

        return await handler(event, data)

