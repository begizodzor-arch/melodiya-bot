import logging
import os
import tempfile
from pathlib import Path

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ChatAction

import database
import config
from services.media_processor import (
    apply_audio_effect,
    make_ringtone,
    convert_to_video_note,
    extract_audio_from_video,
    EFFECT_NAMES,
)
from services.shazam_service import recognize_song_from_file
from services.music_downloader import search_youtube, download_track_as_mp3
from services.lyrics_service import get_song_lyrics
from keyboards.inline import (
    build_video_action_keyboard,
    build_audio_effects_keyboard,
    build_audio_action_keyboard,
    build_search_results_keyboard,
)
from utils.helpers import safe_remove_file, generate_session_id, format_duration

logger = logging.getLogger(__name__)
media_router = Router()


# ── Foydalanuvchi oddiy Audio yuborganida ────────────────────────────────────
@media_router.message(F.audio)
async def handle_incoming_audio(message: Message):
    """
    Foydalanuvchi MP3/Audio fayl yuborganida:
    Effektlar (8D, Bass, Konsert, Ringtone) menyusini ko'rsatish.
    """
    await database.update_user_activity(message.from_user.id)
    audio = message.audio
    performer = audio.performer or "Ijrochi"
    title = audio.title or audio.file_name or "Musiqa"

    # Telegram 64-bayt callback limiti uchun qisqa ID saqlaymiz
    short_id = await database.save_temp_media(audio.file_id, "audio")

    await message.answer(
        f"🎵 <b>{performer} — {title}</b>\n\n"
        "Qo'shiqqa effekt qo'shish yoki Ringtone yasash uchun tanlang:",
        parse_mode="HTML",
        reply_markup=build_audio_effects_keyboard(target_id=short_id)
    )


# ── Foydalanuvchi Video yuborganida (Avtomatik musiqa aniqlash + katalog) ──────
@media_router.message(F.video)
async def handle_incoming_video(message: Message):
    """
    Foydalanuvchi video yuborganida:
    1. Darhol undagi musiqani Shazam orqali aniqlash
    2. Dumaloq video (Teleskop), MP3 ajratish, 8D/Bass kataloglarini taklif qilish
    """
    await database.update_user_activity(message.from_user.id)
    video = message.video

    # Qisqa ID saqlaymiz (Telegram 64-bayt tugma limiti uchun)
    short_id = await database.save_temp_media(video.file_id, "video")

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    # Videoni yuklab olib, audiosini Shazam orqali tekshiramiz
    tmp_video = None
    audio_path = None
    result = None

    try:
        file_info = await message.bot.get_file(video.file_id)
        tmp_video = Path(tempfile.gettempdir()) / f"v_in_{short_id}.mp4"
        await message.bot.download_file(file_info.file_path, destination=str(tmp_video))

        audio_path = await extract_audio_from_video(str(tmp_video))
        if audio_path:
            result = await recognize_song_from_file(audio_path)
    except Exception as e:
        logger.error(f"Videodan musiqa qidirishda xatolik: {e}")
    finally:
        safe_remove_file(audio_path)
        safe_remove_file(tmp_video)

    # 1. Musiqa topilgan bo'lsa
    if result:
        artist = result.get("artist", "")
        title = result.get("title", "")
        query = result.get("query", f"{artist} {title}".strip())

        results = await search_youtube(query, limit=config.RESULTS_PER_PAGE * 2)
        if results:
            session_id = generate_session_id()
            await database.save_search_session(session_id, query, results)

            page_results = results[:config.RESULTS_PER_PAGE]
            lines = [
                f"✅ <b>Videodagi musiqa aniqlandi!</b>\n"
                f"🎤 <b>{artist} — {title}</b>\n\n"
                "📋 <b>Yuklab olish uchun namunalar:</b>\n"
            ]
            for i, track in enumerate(page_results, 1):
                dur = track.get("duration_str") or format_duration(track.get("duration"))
                lines.append(f"<b>{i}.</b> {track.get('performer', '')} — {track.get('title', '')}  <i>[{dur}]</i>")
            lines.append("\n📥 Yuklab olish uchun raqamni bosing:")

            keyboard = build_search_results_keyboard(
                session_id=session_id,
                current_page=1,
                total_pages=max(1, (len(results) + config.RESULTS_PER_PAGE - 1) // config.RESULTS_PER_PAGE),
                page_items_count=len(page_results),
                start_index=0
            )
            await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)

    # 2. Shuningdek videoni boshqa amallarini katalog sifatida ko'rsatamiz
    await message.answer(
        "🎬 <b>Video amallari:</b>\n"
        "Quyidagi tugmalar orqali videoni dumaloq video (Teleskop) qilish yoki MP3 ajratib olishingiz mumkin 👇",
        parse_mode="HTML",
        reply_markup=build_video_action_keyboard(temp_file_id=short_id)
    )


# ── Video Note (dumaloq video) yuborilganida ─────────────────────────────────
@media_router.message(F.video_note)
async def handle_incoming_video_note(message: Message):
    """Dumaloq video yuborilganda Shazam orqali musiqasini topish."""
    await database.update_user_activity(message.from_user.id)
    vnote = message.video_note

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    file_info = await message.bot.get_file(vnote.file_id)
    tmp_path = Path(tempfile.gettempdir()) / f"vn_{vnote.file_id[:10]}.mp4"
    await message.bot.download_file(file_info.file_path, destination=str(tmp_path))

    try:
        result = await recognize_song_from_file(str(tmp_path))
    finally:
        safe_remove_file(tmp_path)

    if not result:
        await message.answer("😔 Ushbu dumaloq videodan musiqani aniqlab bo'lmadi.")
        return

    artist = result.get("artist", "")
    title = result.get("title", "")
    query = result.get("query", f"{artist} {title}".strip())

    results = await search_youtube(query, limit=config.RESULTS_PER_PAGE * 2)
    if not results:
        await message.answer(f"✅ Aniqlandi: <b>{artist} — {title}</b>\nLekin yuklab bo'lmadi.", parse_mode="HTML")
        return

    session_id = generate_session_id()
    await database.save_search_session(session_id, query, results)

    page_results = results[:config.RESULTS_PER_PAGE]
    lines = [f"✅ <b>Dumaloq videodan aniqlandi:</b> {artist} — {title}\n", "📋 <b>Natijalar:</b>\n"]
    for i, track in enumerate(page_results, 1):
        dur = track.get("duration_str") or format_duration(track.get("duration"))
        lines.append(f"<b>{i}.</b> {track.get('performer', '')} — {track.get('title', '')}  <i>[{dur}]</i>")
    lines.append("\n📥 Yuklab olish uchun raqamni bosing:")

    keyboard = build_search_results_keyboard(
        session_id=session_id,
        current_page=1,
        total_pages=max(1, (len(results) + config.RESULTS_PER_PAGE - 1) // config.RESULTS_PER_PAGE),
        page_items_count=len(page_results),
        start_index=0
    )
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)


# ── Videodan musiqani aniqlash (Shazam tugmasi bosilganda) ──────────────────
@media_router.callback_query(F.data.startswith("v_shazam:"))
async def cb_video_shazam(callback: CallbackQuery):
    """Videodagi musiqani Shazam orqali aniqlash."""
    short_id = callback.data.split(":", 1)[1]
    video_file_id = await database.get_temp_media(short_id) or short_id

    await callback.answer("🔍 Musiqa aniqlanmoqda...")
    await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.TYPING)

    file_info = await callback.bot.get_file(video_file_id)
    tmp_video = Path(tempfile.gettempdir()) / f"v_shz_{short_id}.mp4"
    await callback.bot.download_file(file_info.file_path, destination=str(tmp_video))

    try:
        audio_path = await extract_audio_from_video(str(tmp_video))
        if not audio_path:
            await callback.message.answer("❌ Videodan audio ajratib bo'lmadi.")
            return

        result = await recognize_song_from_file(audio_path)
        safe_remove_file(audio_path)
    finally:
        safe_remove_file(tmp_video)

    if not result:
        await callback.message.answer("😔 Ushbu videodan musiqani aniqlab bo'lmadi.")
        return

    artist = result.get("artist", "")
    title = result.get("title", "")
    query = result.get("query", f"{artist} {title}".strip())

    results = await search_youtube(query, limit=config.RESULTS_PER_PAGE * 2)
    if not results:
        await callback.message.answer(f"✅ Aniqlandi: <b>{artist} — {title}</b>\nLekin yuklab bo'lmadi.", parse_mode="HTML")
        return

    session_id = generate_session_id()
    await database.save_search_session(session_id, query, results)

    page_results = results[:config.RESULTS_PER_PAGE]
    lines = [f"✅ <b>Videodan aniqlandi:</b> {artist} — {title}\n", "📋 <b>Natijalar:</b>\n"]
    for i, track in enumerate(page_results, 1):
        dur = track.get("duration_str") or format_duration(track.get("duration"))
        lines.append(f"<b>{i}.</b> {track.get('performer', '')} — {track.get('title', '')}  <i>[{dur}]</i>")
    lines.append("\n📥 Yuklab olish uchun raqamni bosing:")

    keyboard = build_search_results_keyboard(
        session_id=session_id,
        current_page=1,
        total_pages=max(1, (len(results) + config.RESULTS_PER_PAGE - 1) // config.RESULTS_PER_PAGE),
        page_items_count=len(page_results),
        start_index=0
    )
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)


# ── Videoni Teleskop / Dumaloq video qilish ──────────────────────────────────
@media_router.callback_query(F.data.startswith("v_note:"))
async def cb_video_to_note(callback: CallbackQuery):
    """Videoni Telegram dumaloq video (Video Note) formatiga aylantirish."""
    short_id = callback.data.split(":", 1)[1]
    video_file_id = await database.get_temp_media(short_id) or short_id

    await callback.answer("⭕️ Dumaloq video tayyorlanmoqda...", show_alert=False)
    await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.RECORD_VIDEO_NOTE)

    file_info = await callback.bot.get_file(video_file_id)
    tmp_video = Path(tempfile.gettempdir()) / f"v_in_{short_id}.mp4"
    await callback.bot.download_file(file_info.file_path, destination=str(tmp_video))

    try:
        note_path = await convert_to_video_note(str(tmp_video))
        if not note_path:
            await callback.message.answer("❌ Dumaloq video tayyorlashda xatolik yuz berdi.")
            return

        await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_VIDEO_NOTE)
        await callback.message.answer_video_note(
            video_note=FSInputFile(note_path)
        )
        safe_remove_file(note_path)
    finally:
        safe_remove_file(tmp_video)


# ── Videodan MP3 ajratib olish ───────────────────────────────────────────────
@media_router.callback_query(F.data.startswith("v_mp3:"))
async def cb_video_extract_mp3(callback: CallbackQuery):
    """Videodan MP3 musiqani ajratib yuborish."""
    short_id = callback.data.split(":", 1)[1]
    video_file_id = await database.get_temp_media(short_id) or short_id

    await callback.answer("🎧 MP3 ajratib olinmoqda...", show_alert=False)
    await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.RECORD_VOICE)

    file_info = await callback.bot.get_file(video_file_id)
    tmp_video = Path(tempfile.gettempdir()) / f"v_mp3_{short_id}.mp4"
    await callback.bot.download_file(file_info.file_path, destination=str(tmp_video))

    try:
        audio_path = await extract_audio_from_video(str(tmp_video))
        if not audio_path:
            await callback.message.answer("❌ Videodan audio ajratib bo'lmadi.")
            return

        await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_VOICE)
        sent = await callback.message.answer_audio(
            audio=FSInputFile(audio_path, filename="video_audio.mp3"),
            caption="🎵 <b>Videodan ajratib olingan audio</b>",
            parse_mode="HTML"
        )
        # Shu yangi audio uchun ham qisqa ID olamiz
        new_short_id = await database.save_temp_media(sent.audio.file_id, "audio")
        await callback.message.answer(
            "🎛 Ushbu musiqaga effekt (8D, Bass) yoki ✂️ Ringtone bermoqchimisiz?",
            reply_markup=build_audio_effects_keyboard(new_short_id)
        )
        safe_remove_file(audio_path)
    finally:
        safe_remove_file(tmp_video)


# ── Videodan effektli MP3 olish (v_fx:effect:short_id) ───────────────────────
@media_router.callback_query(F.data.startswith("v_fx:"))
async def cb_video_fx(callback: CallbackQuery):
    """Videodan audioni ajratib, effekt (8D, Bass, Konsert) berib yuborish."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return

    effect = parts[1]
    short_id = parts[2]
    video_file_id = await database.get_temp_media(short_id) or short_id
    effect_label = EFFECT_NAMES.get(effect, effect)

    await callback.answer(f"🎛 {effect_label} qo'shilmoqda...", show_alert=False)
    await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.RECORD_VOICE)

    file_info = await callback.bot.get_file(video_file_id)
    tmp_video = Path(tempfile.gettempdir()) / f"v_fx_{short_id}.mp4"
    await callback.bot.download_file(file_info.file_path, destination=str(tmp_video))

    try:
        raw_audio = await extract_audio_from_video(str(tmp_video))
        if not raw_audio:
            await callback.message.answer("❌ Audio ajratib bo'lmadi.")
            return

        effect_audio = await apply_audio_effect(raw_audio, effect)
        safe_remove_file(raw_audio)

        if not effect_audio:
            await callback.message.answer("❌ Effekt qo'shishda xatolik yuz berdi.")
            return

        await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_VOICE)
        await callback.message.answer_audio(
            audio=FSInputFile(effect_audio, filename=f"video_{effect}.mp3"),
            caption=f"🎛 <b>{effect_label}</b> versiyasi",
            parse_mode="HTML"
        )
        safe_remove_file(effect_audio)
    finally:
        safe_remove_file(tmp_video)


# ── Musiqa ostidagi 'Effektlar' tugmasi bosilganda ──────────────────────────
@media_router.callback_query(F.data.startswith("eff_menu:"))
async def cb_open_effects_menu(callback: CallbackQuery):
    """Musiqa ostidagi 'Effektlar' menyusini ochish."""
    video_id = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(
        reply_markup=build_audio_effects_keyboard(target_id=video_id)
    )
    await callback.answer()


# ── Effektlar menyusidan 'Orqaga' bosilganda ────────────────────────────────
@media_router.callback_query(F.data.startswith("back_to_track:"))
async def cb_back_to_track(callback: CallbackQuery):
    """Effektlar menyusidan orqaga qaytish."""
    target_id = callback.data.split(":", 1)[1]
    is_fav = await database.is_favorite(callback.from_user.id, target_id)
    await callback.message.edit_reply_markup(
        reply_markup=build_audio_action_keyboard(video_id=target_id, is_fav=is_fav)
    )
    await callback.answer()


# ── Audio effekt qo'llash (fx:effect:target_id) ─────────────────────────────
@media_router.callback_query(F.data.startswith("fx:"))
async def cb_apply_fx(callback: CallbackQuery):
    """Audioni yuklab / olib, effekt (8D, Bass, Konsert, Alvin, Robot) qo'llash."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return

    effect = parts[1]
    target_id = parts[2]
    # Qisqa ID bo'lsa asl file_id ni olamiz
    resolved_id = await database.get_temp_media(target_id) or target_id
    effect_label = EFFECT_NAMES.get(effect, effect)

    await callback.answer(f"🎛 {effect_label} tayyorlanmoqda...", show_alert=False)
    await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.RECORD_VOICE)

    source_path = None
    is_temp_source = False
    title = "Musiqa"
    performer = "Melodiya"

    # 1) Telegram audio file_id bo'lsa
    if len(resolved_id) > 20:
        file_info = await callback.bot.get_file(resolved_id)
        source_path = str(Path(tempfile.gettempdir()) / f"src_{target_id}.mp3")
        await callback.bot.download_file(file_info.file_path, destination=source_path)
        is_temp_source = True
    else:
        # 2) YouTube video_id bo'lsa
        cached = await database.get_cached_track(resolved_id)
        if cached:
            title = cached.get("title", "Musiqa")
            performer = cached.get("performer", "Ijrochi")
            file_info = await callback.bot.get_file(cached["file_id"])
            source_path = str(Path(tempfile.gettempdir()) / f"src_{target_id}.mp3")
            await callback.bot.download_file(file_info.file_path, destination=source_path)
            is_temp_source = True
        else:
            track_info = await download_track_as_mp3(resolved_id)
            if track_info:
                source_path = str(track_info["file_path"])
                title = track_info.get("title", "Musiqa")
                performer = track_info.get("performer", "Ijrochi")
                is_temp_source = True

    if not source_path or not Path(source_path).exists():
        await callback.message.answer("❌ Musiqa fayli topilmadi.")
        return

    try:
        effect_path = await apply_audio_effect(source_path, effect)
        if not effect_path or not Path(effect_path).exists():
            await callback.message.answer("❌ Effekt qo'llashda xatolik yuz berdi.")
            return

        await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_VOICE)
        await callback.message.answer_audio(
            audio=FSInputFile(effect_path, filename=f"{performer} - {title} ({effect}).mp3"),
            caption=f"🎛 <b>{performer} — {title}</b>\n<i>{effect_label}</i>",
            parse_mode="HTML",
            performer=performer,
            title=f"{title} ({effect.upper()})"
        )
        safe_remove_file(effect_path)
    finally:
        if is_temp_source:
            safe_remove_file(source_path)


# ── Ringtone (30s) qirqib olish ──────────────────────────────────────────────
@media_router.callback_query(F.data.startswith("make_ring:"))
async def cb_make_ringtone(callback: CallbackQuery):
    """Musiqadan 30 soniyalik silliq Ringtone (Gudok) yasash."""
    target_id = callback.data.split(":", 1)[1]
    resolved_id = await database.get_temp_media(target_id) or target_id

    await callback.answer("✂️ 30 soniyalik Ringtone tayyorlanmoqda...", show_alert=False)
    await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.RECORD_VOICE)

    source_path = None
    is_temp_source = False
    title = "Ringtone"
    performer = "Melodiya"

    if len(resolved_id) > 20:
        file_info = await callback.bot.get_file(resolved_id)
        source_path = str(Path(tempfile.gettempdir()) / f"ring_src_{target_id}.mp3")
        await callback.bot.download_file(file_info.file_path, destination=source_path)
        is_temp_source = True
    else:
        cached = await database.get_cached_track(resolved_id)
        if cached:
            title = cached.get("title", "Ringtone")
            performer = cached.get("performer", "Ijrochi")
            file_info = await callback.bot.get_file(cached["file_id"])
            source_path = str(Path(tempfile.gettempdir()) / f"ring_src_{target_id}.mp3")
            await callback.bot.download_file(file_info.file_path, destination=source_path)
            is_temp_source = True
        else:
            track_info = await download_track_as_mp3(resolved_id)
            if track_info:
                source_path = str(track_info["file_path"])
                title = track_info.get("title", "Ringtone")
                performer = track_info.get("performer", "Ijrochi")
                is_temp_source = True

    if not source_path or not Path(source_path).exists():
        await callback.message.answer("❌ Musiqa fayli topilmadi.")
        return

    try:
        ringtone_path = await make_ringtone(source_path, start_sec=25, duration=30)
        if not ringtone_path or not Path(ringtone_path).exists():
            await callback.message.answer("❌ Ringtone kesishda xatolik.")
            return

        await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_VOICE)
        await callback.message.answer_audio(
            audio=FSInputFile(ringtone_path, filename=f"{performer} - {title} (Ringtone).mp3"),
            caption=f"✂️ <b>{performer} — {title}</b>\n🔔 <i>Telefon uchun Ringtone (30s)</i>",
            parse_mode="HTML",
            performer=performer,
            title=f"{title} (Ringtone)",
            duration=30
        )
        safe_remove_file(ringtone_path)
    finally:
        if is_temp_source:
            safe_remove_file(source_path)


# ── Qo'shiq matni (Lyrics) ───────────────────────────────────────────────────
@media_router.callback_query(F.data.startswith("lyrics:"))
async def cb_get_lyrics(callback: CallbackQuery):
    """Qo'shiq matnini topib berish."""
    video_id = callback.data.split(":", 1)[1]
    await callback.answer("📜 Matn izlanmoqda...", show_alert=False)

    cached = await database.get_cached_track(video_id)
    if cached:
        performer = cached.get("performer", "")
        title = cached.get("title", "")
    else:
        performer = "Noma'lum"
        title = "Musiqa"

    lyrics = await get_song_lyrics(performer, title, video_id=video_id)

    if not lyrics:
        await callback.message.answer(
            f"😔 <b>«{performer} — {title}»</b> uchun matn topilmadi.",
            parse_mode="HTML"
        )
        return

    max_len = 3900
    if len(lyrics) > max_len:
        lyrics = lyrics[:max_len] + "...\n<i>(Matn qisqartirildi)</i>"

    await callback.message.answer(
        f"📜 <b>{performer} — {title}</b> matni:\n\n"
        f"<i>{lyrics}</i>",
        parse_mode="HTML"
    )
