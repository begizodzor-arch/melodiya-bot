import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

import database
import config
from keyboards.inline import build_admin_keyboard

logger = logging.getLogger(__name__)
admin_router = Router()


class BroadcastState(StatesGroup):
    waiting_for_text = State()


def admin_only(handler):
    """Admin uchun dekorator."""
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id
        if user_id not in config.ADMIN_IDS:
            if hasattr(event, 'answer'):
                await event.answer("⛔️ Sizda ruxsat yo'q.")
            return
        return await handler(event, *args, **kwargs)
    return wrapper


@admin_router.message(F.text == "⚙️ Admin panel")
async def admin_panel(message: Message):
    """Admin panel bosh sahifasi."""
    if message.from_user.id not in config.ADMIN_IDS:
        return

    user_count = await database.get_user_count()
    top_tracks = await database.get_top_downloaded_tracks(limit=5)

    top_text = ""
    if top_tracks:
        top_text = "\n\n📊 <b>Top 5 qo'shiq:</b>\n"
        for i, t in enumerate(top_tracks, 1):
            top_text += f"  {i}. {t.get('performer', '')} — {t.get('title', '')} ({t.get('download_count', 0)}x)\n"

    await message.answer(
        f"⚙️ <b>Admin panel</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{user_count}</b>{top_text}",
        parse_mode="HTML",
        reply_markup=build_admin_keyboard()
    )


@admin_router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    """To'liq statistika."""
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return

    user_count = await database.get_user_count()
    top_tracks = await database.get_top_downloaded_tracks(limit=10)

    lines = [f"📊 <b>Bot statistikasi</b>\n", f"👥 Foydalanuvchilar: <b>{user_count}</b>\n"]

    if top_tracks:
        lines.append("🏆 <b>Top 10 qo'shiqlar:</b>")
        for i, t in enumerate(top_tracks, 1):
            lines.append(
                f"  {i}. {t.get('performer', '')} — {t.get('title', '')} "
                f"(<b>{t.get('download_count', 0)}</b>x)"
            )

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=build_admin_keyboard()
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Broadcast (ommaviy xabar) boshlash."""
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return

    await state.set_state(BroadcastState.waiting_for_text)
    await callback.message.answer(
        "📢 <b>Broadcast</b>\n\n"
        "Barcha foydalanuvchilarga yuboriladigan xabarni yozing:\n"
        "(Bekor qilish uchun /cancel yuboring)",
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.message(Command("cancel"))
@admin_router.message(F.text == "/cancel")
async def cmd_cancel(message: Message, state: FSMContext):
    """Joriy amaliyotni bekor qilish."""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("❌ Bekor qilindi.")


@admin_router.message(BroadcastState.waiting_for_text)
async def handle_broadcast_message(message: Message, state: FSMContext):
    """Broadcast xabarini yuborish."""
    if message.from_user.id not in config.ADMIN_IDS:
        await state.clear()
        return

    await state.clear()
    broadcast_text = message.html_text or message.text or ""

    if not broadcast_text.strip():
        await message.answer("⚠️ Xabar bo'sh bo'lmasin.")
        return

    all_users = await database.get_all_users()
    total = len(all_users)
    success = 0
    failed = 0

    status_msg = await message.answer(
        f"📢 Xabar yuborilmoqda...\n0/{total}"
    )

    for i, user_id in enumerate(all_users, 1):
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text=broadcast_text,
                parse_mode="HTML"
            )
            success += 1
        except Exception:
            failed += 1

        # Har 50 foydalanuvchida bir yangilash
        if i % 50 == 0:
            try:
                await status_msg.edit_text(
                    f"📢 Xabar yuborilmoqda...\n{i}/{total}"
                )
            except Exception:
                pass

    await status_msg.edit_text(
        f"✅ <b>Broadcast yakunlandi!</b>\n\n"
        f"👥 Jami: {total}\n"
        f"✅ Muvaffaqiyatli: {success}\n"
        f"❌ Muvaffaqiyatsiz: {failed}",
        parse_mode="HTML"
    )


@admin_router.callback_query(F.data == "admin_refresh")
async def cb_admin_refresh(callback: CallbackQuery):
    """Admin panel ma'lumotlarini yangilash."""
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return
    await callback.answer("🔄 Yangilandi!")
    await admin_panel(callback.message)

