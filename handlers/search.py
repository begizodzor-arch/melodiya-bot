import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database
import config
from services.music_downloader import search_youtube
from keyboards.inline import build_search_results_keyboard
from utils.helpers import generate_session_id, is_subscribed_to_sponsors, format_duration

logger = logging.getLogger(__name__)
search_router = Router()

class SearchState(StatesGroup):
    waiting_for_query = State()


@search_router.message(F.text == "🔍 Qo'shiq qidirish")
async def ask_for_query(message: Message, state: FSMContext):
    """Qidiruv tugmasi bosilganda foydalanuvchidan so'z so'rash."""
    await database.update_user_activity(message.from_user.id)
    await state.set_state(SearchState.waiting_for_query)
    await message.answer("🔍 Qo'shiq nomi yoki ijrochisini yozing:", parse_mode="HTML")


@search_router.message(SearchState.waiting_for_query)
async def handle_search_query(message: Message, state: FSMContext):
    """Foydalanuvchi kiritgan so'z bo'yicha qidiruv (qidirilmoqda xabarisiz)."""
    query = (message.text or "").strip()
    if not query:
        await message.answer("⚠️ Iltimos, qo'shiq nomi yoki ijrochisini yozing.")
        return

    await state.clear()

    # Majburiy obuna tekshirish
    subscribed, unsubscribed = await is_subscribed_to_sponsors(message.bot, message.from_user.id)
    if not subscribed:
        from keyboards.inline import build_sponsor_keyboard
        await message.answer(
            "⚠️ Botdan foydalanish uchun kanallarga a'zo bo'ling:",
            reply_markup=build_sponsor_keyboard(unsubscribed)
        )
        return

    # Chat action: foydalanuvchiga 'yozmoqda...' ko'rsatish
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    try:
        results = await search_youtube(query, limit=config.RESULTS_PER_PAGE * 3)
    except Exception as e:
        logger.error(f"Qidiruvda xatolik: {e}")
        await message.answer("❌ Qidiruvda xatolik yuz berdi. Keyinroq urinib ko'ring.")
        return

    # Agar birinchi natija musiqa bilan bog'liq ko'rinmasa, faqat audio filtr qo'llanadi
    # Bu holda natijalar allaqachon music_downloader ichida filtrlangan

    if not results:
        await message.answer(
            f"😕 <b>«{query}»</b> bo'yicha hech narsa topilmadi.\n\nBoshqa so'z bilan qidiring.",
            parse_mode="HTML"
        )
        return

    # Sessiyani saqlash
    session_id = generate_session_id()
    await database.save_search_session(session_id, query, results)

    # Natijalarni to'g'ridan-to'g'ri yuborish
    total_pages = max(1, (len(results) + config.RESULTS_PER_PAGE - 1) // config.RESULTS_PER_PAGE)
    page_results = results[:config.RESULTS_PER_PAGE]

    lines = [f"🎵 <b>Qidiruv natijalari:</b> «{query}»\n"]
    for i, track in enumerate(page_results, start=1):
        dur = track.get("duration_str") or format_duration(track.get("duration"))
        performer = track.get("performer", "")
        title = track.get("title", track.get("raw_title", ""))
        lines.append(f"<b>{i}.</b> {performer} — {title}  <i>[{dur}]</i>")
    lines.append("\n📥 Yuklab olish uchun pastdagi raqamni bosing:")

    text = "\n".join(lines)
    keyboard = build_search_results_keyboard(
        session_id=session_id,
        current_page=1,
        total_pages=total_pages,
        page_items_count=len(page_results),
        start_index=0
    )

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


async def _show_search_page(msg_or_callback, session_id: str, query: str, results: list, page: int, is_edit: bool = False):
    """Qidiruv natijalari sahifasini ko'rsatish/almashtirish."""
    per_page = config.RESULTS_PER_PAGE
    total_pages = max(1, (len(results) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * per_page
    page_results = results[start_idx: start_idx + per_page]

    lines = [f"🎵 <b>Qidiruv natijalari:</b> «{query}»\n"]
    for i, track in enumerate(page_results, start=start_idx + 1):
        dur = track.get("duration_str") or format_duration(track.get("duration"))
        performer = track.get("performer", "")
        title = track.get("title", track.get("raw_title", ""))
        lines.append(f"<b>{i}.</b> {performer} — {title}  <i>[{dur}]</i>")
    lines.append("\n📥 Yuklab olish uchun pastdagi raqamni bosing:")

    text = "\n".join(lines)
    keyboard = build_search_results_keyboard(
        session_id=session_id,
        current_page=page,
        total_pages=total_pages,
        page_items_count=len(page_results),
        start_index=start_idx
    )

    if is_edit:
        await msg_or_callback.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await msg_or_callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
