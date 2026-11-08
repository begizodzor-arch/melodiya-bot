import logging
import math

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

import database
import config
from keyboards.inline import build_favorites_keyboard
from utils.helpers import format_duration

logger = logging.getLogger(__name__)
favorites_router = Router()

FAVS_PER_PAGE = 10


@favorites_router.message(F.text == "⭐️ Sevimlilar")
async def show_favorites(message: Message):
    """Foydalanuvchi sevimlilarini ko'rsatish."""
    await database.update_user_activity(message.from_user.id)
    user_id = message.from_user.id

    await _send_favorites_page(message, user_id, page=1, is_reply=True)


async def _send_favorites_page(msg_or_callback, user_id: int, page: int, is_reply: bool = False):
    """Sevimlilar sahifasini yuborish yoki tahrirlash."""
    offset = (page - 1) * FAVS_PER_PAGE
    favorites = await database.get_favorites(user_id, limit=FAVS_PER_PAGE, offset=offset)

    # Jami sonini hisoblash
    all_favs = await database.get_favorites(user_id, limit=9999, offset=0)
    total = len(all_favs)
    total_pages = max(1, math.ceil(total / FAVS_PER_PAGE))

    if not favorites:
        text = (
            "⭐️ <b>Sevimlilar</b>\n\n"
            "Sizda hali saqlangan qo'shiqlar yo'q.\n\n"
            "💡 Musiqa yuborilganda <b>❤️ Saqlash</b> tugmasini bosing!"
        )
        if is_reply:
            await msg_or_callback.answer(text, parse_mode="HTML")
        else:
            await msg_or_callback.message.edit_text(text, parse_mode="HTML")
        return

    lines = [f"⭐️ <b>Sevimlilar</b> ({total} ta)\n"]
    for i, fav in enumerate(favorites, start=offset + 1):
        dur = format_duration(fav.get("duration"))
        lines.append(
            f"<b>{i}.</b> {fav.get('performer', '')} — {fav.get('title', '')}  <i>[{dur}]</i>"
        )
    lines.append("\n▶️ Tinglamoq uchun bosing:")

    keyboard = build_favorites_keyboard(favorites=favorites, page=page, total_pages=total_pages)

    if is_reply:
        await msg_or_callback.answer("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)
    else:
        await msg_or_callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)


@favorites_router.callback_query(F.data.startswith("fav:"))
async def cb_toggle_favorite(callback: CallbackQuery):
    """Sevimlilarni qo'shish / o'chirish."""
    video_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    already_fav = await database.is_favorite(user_id, video_id)

    if already_fav:
        await database.remove_favorite(user_id, video_id)
        await callback.answer("💔 Sevimlilardan o'chirildi", show_alert=False)
        new_fav_state = False
    else:
        # Ma'lumotlarni keshdan olish
        cached = await database.get_cached_track(video_id)
        if cached:
            await database.add_favorite(
                user_id=user_id,
                video_id=video_id,
                title=cached.get("title", ""),
                performer=cached.get("performer", ""),
                duration=cached.get("duration", 0)
            )
            await callback.answer("❤️ Sevimlilarga saqlandi!", show_alert=False)
        else:
            await callback.answer("⚠️ Ma'lumot topilmadi", show_alert=True)
            return
        new_fav_state = True

    # Tugmani yangilash
    from keyboards.inline import build_audio_action_keyboard
    cached_info = await database.get_cached_track(video_id)
    share_q = cached_info.get("title", "") if cached_info else ""
    new_keyboard = build_audio_action_keyboard(
        video_id=video_id,
        is_fav=new_fav_state,
        share_query=share_q
    )
    try:
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    except Exception:
        pass


@favorites_router.callback_query(F.data.startswith("favpage:"))
async def cb_favorites_page(callback: CallbackQuery):
    """Sevimlilar sahifasi o'zgarganda."""
    page = int(callback.data.split(":", 1)[1])
    await _send_favorites_page(callback, callback.from_user.id, page=page, is_reply=False)
    await callback.answer()

