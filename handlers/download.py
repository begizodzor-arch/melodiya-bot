import logging
import re
from pathlib import Path
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.enums import ChatAction

import database
import config
from services.music_downloader import download_track_as_mp3
from keyboards.inline import build_audio_action_keyboard
from utils.helpers import safe_remove_file, is_subscribed_to_sponsors, format_duration

logger = logging.getLogger(__name__)
download_router = Router()

# YouTube URL pattern
_YT_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})"
)


async def _download_and_send(
    callback_or_message,
    video_id: str,
    user_id: int,
    is_callback: bool = True
):
    """Musiqa yuklab yuborish — asosiy logika."""
    bot = callback_or_message.bot
    chat_id = callback_or_message.message.chat.id if is_callback else callback_or_message.chat.id

    # Majburiy obuna tekshirish
    subscribed, unsubscribed = await is_subscribed_to_sponsors(bot, user_id)
    if not subscribed:
        from keyboards.inline import build_sponsor_keyboard
        text = "⚠️ Botdan foydalanish uchun kanallarga a'zo bo'ling:"
        kb = build_sponsor_keyboard(unsubscribed)
        if is_callback:
            await callback_or_message.message.answer(text, reply_markup=kb)
            await callback_or_message.answer()
        else:
            await callback_or_message.answer(text, reply_markup=kb)
        return

    # Telegram keshida mavjudmi tekshirish
    cached = await database.get_cached_track(video_id)
    if cached:
        await database.increment_download_count(video_id)
        is_fav = await database.is_favorite(user_id, video_id)
        caption = (
            f"🎵 <b>{cached['performer']} — {cached['title']}</b>\n"
            f"⏱ <i>{format_duration(cached.get('duration'))}</i>"
        )
        keyboard = build_audio_action_keyboard(
            video_id=video_id,
            is_fav=is_fav,
            share_query=cached.get("title", "")
        )

        if is_callback:
            await callback_or_message.answer("⚡️ Keshdan yuborilmoqda...")
            await callback_or_message.message.answer_audio(
                audio=cached["file_id"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await callback_or_message.answer_audio(
                audio=cached["file_id"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        return

    # Yuklab olish kerak
    if is_callback:
        await callback_or_message.answer("⏳ Qo'shiq yuklanmoqda...", show_alert=False)

    # Chat action: 'audio yuklanmoqda...' ko'rsatish
    await bot.send_chat_action(chat_id, ChatAction.RECORD_VOICE)

    track_info = await download_track_as_mp3(video_id)

    if not track_info:
        msg_target = callback_or_message.message if is_callback else callback_or_message
        await msg_target.answer("❌ Yuklab olishda xatolik yuz berdi. Keyinroq urinib ko'ring.")
        return

    file_path: Path = track_info["file_path"]

    try:
        is_fav = await database.is_favorite(user_id, video_id)
        caption = (
            f"🎵 <b>{track_info['performer']} — {track_info['title']}</b>\n"
            f"⏱ <i>{format_duration(track_info.get('duration'))}</i>"
        )
        keyboard = build_audio_action_keyboard(
            video_id=video_id,
            is_fav=is_fav,
            share_query=track_info.get("title", "")
        )

        audio_input = FSInputFile(file_path, filename=f"{track_info['performer']} - {track_info['title']}.mp3")

        await bot.send_chat_action(chat_id, ChatAction.UPLOAD_VOICE)

        msg_target = callback_or_message.message if is_callback else callback_or_message
        sent = await msg_target.answer_audio(
            audio=audio_input,
            caption=caption,
            parse_mode="HTML",
            performer=track_info["performer"],
            title=track_info["title"],
            duration=track_info.get("duration"),
            reply_markup=keyboard
        )

        # Telegram file_id ni keshga saqlash
        file_id = sent.audio.file_id
        await database.save_cached_track(
            video_id=video_id,
            file_id=file_id,
            title=track_info["title"],
            performer=track_info["performer"],
            duration=track_info.get("duration", 0)
        )

    except Exception as e:
        logger.error(f"Audio yuborishda xatolik: {e}")
        msg_target = callback_or_message.message if is_callback else callback_or_message
        await msg_target.answer("❌ Musiqa yuborishda xatolik yuz berdi.")
    finally:
        safe_remove_file(file_path)


@download_router.callback_query(F.data.startswith("dl:"))
async def cb_download_from_search(callback: CallbackQuery):
    """Qidiruv natijalaridan qo'shiqni yuklab olish."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("❌ Noto'g'ri so'rov", show_alert=True)
        return

    session_id = parts[1]
    try:
        track_index = int(parts[2])
    except ValueError:
        await callback.answer("❌ Noto'g'ri indeks", show_alert=True)
        return

    session = await database.get_search_session(session_id)
    if not session:
        await callback.answer("⚠️ Qidiruv sessiyasi eskirib qoldi. Qaytadan qidiring.", show_alert=True)
        return

    results = session.get("results", [])
    if track_index < 0 or track_index >= len(results):
        await callback.answer("⚠️ Noto'g'ri tanlandi", show_alert=True)
        return

    track = results[track_index]
    video_id = track["video_id"]
    await _download_and_send(callback, video_id, callback.from_user.id, is_callback=True)


@download_router.callback_query(F.data.startswith("dl_id:"))
async def cb_download_by_id(callback: CallbackQuery):
    """Video ID orqali to'g'ridan-to'g'ri yuklab olish (sevimlilar va chartlardan)."""
    video_id = callback.data.split(":", 1)[1]
    if not video_id:
        await callback.answer("❌ Xatolik", show_alert=True)
        return
    await _download_and_send(callback, video_id, callback.from_user.id, is_callback=True)


@download_router.callback_query(F.data.startswith("pg:"))
async def cb_paginate_search(callback: CallbackQuery):
    """Qidiruv natijalarida sahifalash."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return

    session_id = parts[1]
    try:
        page = int(parts[2])
    except ValueError:
        await callback.answer()
        return

    session = await database.get_search_session(session_id)
    if not session:
        await callback.answer("⚠️ Sessiya eskirdi. Qaytadan qidiring.", show_alert=True)
        return

    results = session.get("results", [])
    query = session.get("query", "")

    from handlers.search import _show_search_page
    await _show_search_page(callback, session_id, query, results, page=page, is_edit=False)
    await callback.answer()


@download_router.callback_query(F.data == "close_search")
async def cb_close_search(callback: CallbackQuery):
    """Qidiruv natijalarini yopish."""
    await callback.message.delete()
    await callback.answer()


@download_router.message(F.text.regexp(r"(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/"))
async def handle_youtube_url(message: Message):
    """
    Foydalanuvchi YouTube havolasini yuborganda — to'g'ridan MP3 yuklab olish.
    Misol: https://youtu.be/4EfM6rPmxow
    """
    text = message.text or ""
    match = _YT_URL_RE.search(text)
    if not match:
        await message.answer("⚠️ YouTube havolasi noto'g'ri. Misol: https://youtu.be/4EfM6rPmxow")
        return

    video_id = match.group(1)
    await _download_and_send(message, video_id, message.from_user.id, is_callback=False)


# TikTok va Instagram havolalari uchun regex
_SOCIAL_URL_RE = re.compile(
    r"https?://(?:www\.|vm\.|vt\.)?(?:tiktok\.com|instagram\.com)/(?:@[^/]+/video/\d+|[\w-]+/?|reel/[\w-]+|p/[\w-]+)"
)

@download_router.message(F.text.regexp(r"https?://(?:www\.|vm\.|vt\.)?(?:tiktok\.com|instagram\.com)"))
async def handle_social_media_url(message: Message):
    """
    TikTok yoki Instagram Reels havolasidan MP3 musiqani ajratib olish.
    """
    text = (message.text or "").strip()
    match = _SOCIAL_URL_RE.search(text)
    url = match.group(0) if match else text

    await message.bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)

    from services.social_service import download_social_audio
    track_info = await download_social_audio(url)

    if not track_info:
        await message.answer("❌ Ushbu TikTok/Instagram havolasidan musiqani yuklab bo'lmadi.")
        return

    file_path = track_info["file_path"]
    try:
        title = track_info["title"]
        performer = track_info["performer"]
        dur = track_info.get("duration")

        await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VOICE)
        sent = await message.answer_audio(
            audio=FSInputFile(file_path, filename=f"{performer} - {title}.mp3"),
            caption=f"🎵 <b>{performer} — {title}</b>\n📱 <i>TikTok / Instagram Reels musiqasi</i>",
            parse_mode="HTML",
            performer=performer,
            title=title,
            duration=dur
        )
        # Shu yangi qo'shiq uchun ham effektlar taklif qilish
        from keyboards.inline import build_audio_effects_keyboard
        await message.answer(
            "🎛 Ushbu musiqaga effekt (8D, Bass) yoki ✂️ Ringtone yasamoqchimisiz?",
            reply_markup=build_audio_effects_keyboard(sent.audio.file_id)
        )
    finally:
        safe_remove_file(file_path)

