import logging
import hashlib
from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultCachedAudio,
    InputTextMessageContent,
)

import database
from services.music_downloader import search_youtube
from utils.helpers import format_duration

logger = logging.getLogger(__name__)
inline_router = Router()


@inline_router.inline_query()
async def handle_inline_query(inline_query: InlineQuery):
    """
    @melodiyauz_bot song_name — boshqa chatlarda qidirish va yuborish.
    Agar qo'shiq keshda bo'lsa to'g'ridan-to'g'ri Audio yuboradi!
    """
    query = inline_query.query.strip()
    me = await inline_query.bot.get_me()
    bot_username = me.username

    if not query or len(query) < 2:
        await inline_query.answer(
            results=[],
            switch_pm_text="🔍 Qo'shiq nomini yozing...",
            switch_pm_parameter="start",
            cache_time=5,
            is_personal=True,
        )
        return

    try:
        results = await search_youtube(query, limit=10)
    except Exception as e:
        logger.error(f"Inline qidiruvda xatolik: {e}")
        results = []

    if not results:
        await inline_query.answer(
            results=[],
            switch_pm_text=f"😕 '{query}' topilmadi",
            switch_pm_parameter="start",
            cache_time=10,
            is_personal=True,
        )
        return

    query_results = []
    for track in results[:10]:
        video_id = track.get("video_id", "")
        performer = track.get("performer", "")
        title = track.get("title", "")
        dur = track.get("duration_str") or format_duration(track.get("duration"))

        result_id = hashlib.md5(video_id.encode()).hexdigest()[:10]

        # Keshda mavjud bo'lsa — to'g'ridan Audio yuborish
        cached = await database.get_cached_track(video_id)
        if cached and cached.get("file_id"):
            query_results.append(
                InlineQueryResultCachedAudio(
                    id=result_id,
                    audio_file_id=cached["file_id"],
                    caption=f"🎵 <b>{cached['performer']} — {cached['title']}</b>\nvia @{bot_username}",
                    parse_mode="HTML"
                )
            )
        else:
            # Keshda bo'lmasa — botga yo'naltirish havolasi
            deep_link = f"https://t.me/{bot_username}?start=dl_{video_id}"
            query_results.append(
                InlineQueryResultArticle(
                    id=result_id,
                    title=f"🎵 {performer} — {title}",
                    description=f"⏱ {dur} | Yuklab olish",
                    input_message_content=InputTextMessageContent(
                        message_text=(
                            f"🎵 <b>{performer} — {title}</b>\n"
                            f"⏱ {dur}\n\n"
                            f"📥 <a href='{deep_link}'>Qo'shiqni yuklab olish</a> | @{bot_username}"
                        ),
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    ),
                    thumbnail_url=f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                )
            )

    await inline_query.answer(
        results=query_results,
        cache_time=30,
        is_personal=False,
    )
