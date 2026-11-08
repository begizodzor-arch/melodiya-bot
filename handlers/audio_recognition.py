import logging
import os
import tempfile
from pathlib import Path

from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatAction

import database
import config
from services.shazam_service import recognize_song_from_file
from services.music_downloader import search_youtube
from keyboards.inline import build_search_results_keyboard
from utils.helpers import generate_session_id, format_duration, safe_remove_file

logger = logging.getLogger(__name__)
recognition_router = Router()


async def _download_telegram_voice(message: Message) -> str | None:
    """Telegram ovozli xabarini yuklab olish."""
    bot = message.bot
    file_obj = message.voice
    if not file_obj:
        return None

    file_info = await bot.get_file(file_obj.file_id)
    tmp_path = Path(tempfile.gettempdir()) / f"melodiya_voice_{file_obj.file_id}.ogg"
    await bot.download_file(file_info.file_path, destination=str(tmp_path))
    return str(tmp_path)


@recognition_router.message(F.voice)
async def handle_voice_recognition(message: Message):
    """
    Ovozli xabar yuborilganda Shazam orqali qo'shiqni aniqlash.
    """
    await database.update_user_activity(message.from_user.id)
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    tmp_path = await _download_telegram_voice(message)
    if not tmp_path:
        await message.answer("❌ Ovozli xabar yuklanmadi. Qaytadan urinib ko'ring.")
        return

    try:
        result = await recognize_song_from_file(tmp_path)
    finally:
        safe_remove_file(tmp_path)

    if not result:
        await message.answer(
            "😔 Ovozdan qo'shiq aniqlanmadi.\n\n"
            "Ovozni aniqroq yuboring yoki 🔍 qidiruvdan foydalaning."
        )
        return

    artist = result.get("artist", "")
    title = result.get("title", "")
    query = result.get("query", f"{artist} {title}".strip())

    results = await search_youtube(query, limit=config.RESULTS_PER_PAGE * 2)

    if not results:
        await message.answer(
            f"✅ Topildi: <b>{artist} — {title}</b>\n\n"
            "😔 Lekin yuklab olish uchun musiqa topilmadi.",
            parse_mode="HTML"
        )
        return

    session_id = generate_session_id()
    await database.save_search_session(session_id, query, results)

    page_results = results[:config.RESULTS_PER_PAGE]
    total_pages = max(1, (len(results) + config.RESULTS_PER_PAGE - 1) // config.RESULTS_PER_PAGE)

    lines = [
        f"✅ <b>Ovozdan aniqlandi:</b> {artist} — {title}\n",
        "📋 <b>Topilgan natijalar:</b>\n"
    ]
    for i, track in enumerate(page_results, 1):
        dur = track.get("duration_str") or format_duration(track.get("duration"))
        lines.append(
            f"<b>{i}.</b> {track.get('performer', '')} — {track.get('title', '')}  <i>[{dur}]</i>"
        )
    lines.append("\n📥 Yuklab olish uchun pastdagi raqamni bosing:")

    keyboard = build_search_results_keyboard(
        session_id=session_id,
        current_page=1,
        total_pages=total_pages,
        page_items_count=len(page_results),
        start_index=0
    )

    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)
