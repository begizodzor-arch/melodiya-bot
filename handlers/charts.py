import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

import database
import config
from services.chart_service import get_popular_charts
from services.music_downloader import search_youtube
from keyboards.inline import build_charts_keyboard, build_search_results_keyboard
from utils.helpers import generate_session_id, format_duration

logger = logging.getLogger(__name__)
charts_router = Router()


@charts_router.message(F.text == "🔥 Trend musiqalar")
async def show_charts_menu(message: Message):
    """Trend musiqalar menyusini ko'rsatish."""
    await database.update_user_activity(message.from_user.id)
    charts_data = await get_popular_charts()

    keyboard = build_charts_keyboard(
        categories=charts_data["categories"],
        top_cached=charts_data["top_cached"]
    )

    await message.answer(
        "🔥 <b>Trend musiqalar</b>\n\n"
        "Quyidagi toifalardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@charts_router.callback_query(F.data.startswith("chart:"))
async def cb_chart_category(callback: CallbackQuery):
    """Chart toifasiga bosilganda natijalarni qidirish va ko'rsatish."""
    category_key = callback.data.split(":", 1)[1]

    # Bot ichidagi top yuklashlar
    if category_key == "top_downloads":
        charts_data = await get_popular_charts()
        top_tracks = charts_data.get("top_cached", [])

        if not top_tracks:
            await callback.answer("😔 Hali yetarli ma'lumot yo'q.", show_alert=True)
            return

        lines = ["🏆 <b>Eng ko'p yuklangan qo'shiqlar:</b>\n"]
        for i, track in enumerate(top_tracks, 1):
            dur = format_duration(track.get("duration"))
            count = track.get("download_count", 0)
            lines.append(
                f"<b>{i}.</b> {track.get('performer', '')} — {track.get('title', '')}  "
                f"<i>[{dur}]</i>  📥{count}"
            )
        lines.append("\n📥 Yuklab olish uchun raqamni bosing (ID bilan):")

        # top_downloads uchun inline keyboard bilan ID orqali yuklash
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        rows = []
        for i, track in enumerate(top_tracks, 1):
            video_id = track.get("video_id", "")
            title = (track.get("title") or "Musiqa")[:25]
            rows.append([
                InlineKeyboardButton(text=f"▶️ {i}. {title}", callback_data=f"dl_id:{video_id}")
            ])
        rows.append([InlineKeyboardButton(text="❌ Yopish", callback_data="close_search")])

        await callback.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
        )
        await callback.answer()
        return

    # YouTube-dan qidirish
    from services.chart_service import POPULAR_CATEGORIES
    category = POPULAR_CATEGORIES.get(category_key)
    if not category:
        await callback.answer("⚠️ Toifa topilmadi", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        f"{category['title']}\n\n⏳ <i>Qidirilmoqda...</i>",
        parse_mode="HTML"
    )

    query = category["query"]
    results = await search_youtube(query, limit=config.RESULTS_PER_PAGE * 2)

    if not results:
        await callback.message.edit_text("😔 Hech narsa topilmadi. Keyinroq urinib ko'ring.")
        return

    session_id = generate_session_id()
    await database.save_search_session(session_id, query, results)

    total_pages = max(1, (len(results) + config.RESULTS_PER_PAGE - 1) // config.RESULTS_PER_PAGE)
    page_results = results[:config.RESULTS_PER_PAGE]

    lines = [f"{category['title']}\n", "📋 <b>Natijalar:</b>\n"]
    for i, track in enumerate(page_results, 1):
        dur = track.get("duration_str") or format_duration(track.get("duration"))
        lines.append(
            f"<b>{i}.</b> {track.get('performer', '')} — {track.get('title', '')}  <i>[{dur}]</i>"
        )
    lines.append("\n📥 Yuklab olish uchun raqamni bosing:")

    keyboard = build_search_results_keyboard(
        session_id=session_id,
        current_page=1,
        total_pages=total_pages,
        page_items_count=len(page_results),
        start_index=0
    )
    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)

