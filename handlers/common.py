import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database
import config
from keyboards.reply import get_main_menu_keyboard
from keyboards.inline import build_sponsor_keyboard
from utils.helpers import is_subscribed_to_sponsors

logger = logging.getLogger(__name__)
common_router = Router()

class SearchState(StatesGroup):
    """Qidiruv FSM holatlari."""
    waiting_for_query = State()
    waiting_for_broadcast = State()

@common_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    """Botni boshlash. Deep link orqali kelsa (start=dl_ID yoki ref_ID)."""
    user = message.from_user
    deep_arg = command.args or ""
    referrer_id = None

    if deep_arg.startswith("ref_"):
        ref_str = deep_arg[4:]
        if ref_str.isdigit():
            referrer_id = int(ref_str)

    await database.add_user(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name or user.first_name or "",
        referred_by=referrer_id
    )
    await state.clear()

    # Agar do'sti taklif qilgan bo'lsa, taklif qilganga xabar yuborish
    if referrer_id and referrer_id != user.id:
        try:
            ref_count = await database.get_referral_count(referrer_id)
            await message.bot.send_message(
                chat_id=referrer_id,
                text=(
                    f"🎉 <b>Yangi do'st qo'shildi!</b>\n\n"
                    f"Sizning havolangiz orqali <b>{user.full_name}</b> botga kirdi.\n"
                    f"📊 Jami takliflaringiz: <b>{ref_count}</b> ta! ⭐️"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    # ── Deep link: inline modedan /start?dl_VIDEO_ID ─────────────────────────
    if deep_arg.startswith("dl_"):
        video_id = deep_arg[3:]
        if video_id:
            from handlers.download import _download_and_send
            subscribed, unsubscribed = await is_subscribed_to_sponsors(message.bot, user.id)
            if not subscribed:
                await message.answer(
                    "⚠️ Botdan foydalanish uchun kanallarga a'zo bo'ling:",
                    reply_markup=build_sponsor_keyboard(unsubscribed)
                )
                return
            is_admin = user.id in config.ADMIN_IDS
            await message.answer(
                "🎵 Pastdagi menyudan foydalaning 👇",
                reply_markup=get_main_menu_keyboard(is_admin=is_admin)
            )
            await _download_and_send(message, video_id, user.id, is_callback=False)
            return

    is_admin = user.id in config.ADMIN_IDS

    # Majburiy obuna tekshirish
    subscribed, unsubscribed = await is_subscribed_to_sponsors(message.bot, user.id)
    if not subscribed:
        keyboard = build_sponsor_keyboard(unsubscribed)
        await message.answer(
            "🎵 <b>Melodiya Bot</b>ga xush kelibsiz!\n\n"
            "Botdan foydalanish uchun quyidagi kanallarga a'zo bo'lishingiz kerak:",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return

    name = user.first_name or "Do'st"
    await message.answer(
        f"🎵 <b>Melodiya Bot</b>ga xush kelibsiz, <b>{name}</b>!\n\n"
        "Men orqali:\n"
        "🔍 Qo'shiq qidirish va yuklab olish\n"
        "🔥 Trenddagi musiqalarni ko'rish\n"
        "⭐️ Sevimli qo'shiqlarni saqlash\n"
        "🎙 Ovozli xabar yuborib qo'shiq aniqlash mumkin!\n\n"
        "Pastdagi menyudan foydalaning 👇",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(is_admin=is_admin)
    )

@common_router.message(F.text == "👥 Do'stlarni taklif qilish")
async def show_referral_program(message: Message):
    """Do'stlarni taklif qilish va shaxsiy referral havola."""
    await database.update_user_activity(message.from_user.id)
    user_id = message.from_user.id
    ref_count = await database.get_referral_count(user_id)
    me = await message.bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref_{user_id}"

    text = (
        "👥 <b>Do'stlarni taklif qilish</b>\n\n"
        "O'z havolangiz orqali do'stlaringizni taklif qiling va bot rivojiga hissa qo'shing!\n\n"
        f"🔗 <b>Sizning taklif havolangiz:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"📊 Siz taklif qilgan do'stlar: <b>{ref_count}</b> ta\n\n"
        "<i>Pastdagi tugma orqali havolani bitta bosishda do'stlaringizga yuborishingiz mumkin 👇</i>"
    )
    from keyboards.inline import build_referral_keyboard
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=build_referral_keyboard(me.username, user_id)
    )


@common_router.message(F.text == "ℹ️ Bot haqida / Yordam")
async def cmd_help(message: Message):
    """Yordam xabari."""
    await database.update_user_activity(message.from_user.id)
    me = await message.bot.get_me()
    await message.answer(
        f"🎵 <b>Melodiya Bot — Yordam</b>\n\n"
        "🔍 <b>Qidirish:</b>\n"
        "   Qo'shiq nomini yozing — 10 ta namuna chiqadi\n\n"
        "🎬 <b>Video yuborish:</b>\n"
        "   Videoni yuboring — bot undagi musiqani topadi, "
        "dumaloq video (Teleskop) qiladi yoki MP3 ga aylantiradi\n\n"
        "🎛 <b>Audio effektlar:</b>\n"
        "   Musiqa yuboring yoki yuklang — <b>8D Audio</b>, <b>Bass Boost</b>, "
        "<b>Konsert</b>, <b>Slowed</b> effektlarini qo'shing\n\n"
        "🎙 <b>Ovozli xabar:</b>\n"
        "   Ovoz yuboring — Shazam orqali qo'shiqni aniqlaydi\n\n"
        "🔗 <b>YouTube havolasi:</b>\n"
        "   Link yuboring — to'g'ridan MP3 qilib beradi\n\n"
        "🔥 <b>Trend musiqalar:</b>\n"
        "   Eng xit qo'shiqlarni ko'ring\n\n"
        "⭐️ <b>Sevimlilar:</b>\n"
        "   Yoqtirgan qo'shiqlaringizni saqlang\n\n"
        "📣 <b>Boshqa chatlarda:</b>\n"
        f"   <code>@{me.username} qo'shiq nomi</code> yozing\n\n"
        f"🤖 <b>Bot:</b> @{me.username}",
        parse_mode="HTML"
    )

@common_router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(callback: CallbackQuery):
    """Majburiy obunani tekshirish tugmasi."""
    subscribed, unsubscribed = await is_subscribed_to_sponsors(callback.bot, callback.from_user.id)
    
    if subscribed:
        is_admin = callback.from_user.id in config.ADMIN_IDS
        await callback.message.edit_text(
            "✅ Obuna tasdiqlandi! Botdan foydalanishingiz mumkin.",
        )
        await callback.message.answer(
            "🎵 Pastdagi menyudan foydalaning 👇",
            reply_markup=get_main_menu_keyboard(is_admin=is_admin)
        )
    else:
        await callback.answer("❌ Hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)

@common_router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    """Bo'sh tugmalar uchun."""
    await callback.answer()


# ── Fallback: foydalanuvchi to'g'ridan qo'shiq nomi yozsa ──────────────────
@common_router.message(F.text & ~F.text.startswith("/"))
async def fallback_text_search(message: Message, state: FSMContext):
    """
    Foydalanuvchi har qanday matn yuborganda (menyu tugmasi emas)
    avtomatik qidiruv boshlash.
    """
    # Agar avvalgi biror holat bo'lsa uni bekor qilamiz
    await state.clear()

    query = (message.text or "").strip()
    # Menyu tugmalarini o'tkazib yuborish
    menu_buttons = {
        "🔍 Qo'shiq qidirish", "🔥 Trend musiqalar",
        "⭐️ Sevimlilar", "ℹ️ Bot haqida / Yordam", "⚙️ Admin panel",
        "👥 Do'stlarni taklif qilish"
    }
    if query in menu_buttons or not query:
        return

    subscribed, unsubscribed = await is_subscribed_to_sponsors(message.bot, message.from_user.id)
    if not subscribed:
        keyboard = build_sponsor_keyboard(unsubscribed)
        await message.answer("⚠️ Botdan foydalanish uchun kanallarga a'zo bo'ling:", reply_markup=keyboard)
        return

    # Qidiruvni to'g'ridan ishga tushirish
    from services.music_downloader import search_youtube
    from keyboards.inline import build_search_results_keyboard
    from utils.helpers import generate_session_id, format_duration
    from aiogram.enums import ChatAction
    import config

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    try:
        results = await search_youtube(query, limit=config.RESULTS_PER_PAGE * 3)
    except Exception as e:
        logger.error(f"Fallback qidiruvda xatolik: {e}")
        await message.answer("❌ Qidiruvda xatolik. Keyinroq urinib ko'ring.")
        return

    if not results:
        await message.answer(
            f"😕 <b>«{query}»</b> bo'yicha hech narsa topilmadi.\n\nBoshqa so'z bilan qidiring.",
            parse_mode="HTML"
        )
        return

    session_id = generate_session_id()
    await database.save_search_session(session_id, query, results)

    total_pages = max(1, (len(results) + config.RESULTS_PER_PAGE - 1) // config.RESULTS_PER_PAGE)
    page_results = results[:config.RESULTS_PER_PAGE]

    lines = [f"🎵 <b>Qidiruv natijalari:</b> «{query}»\n"]
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
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)

