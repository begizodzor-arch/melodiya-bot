import asyncio
import logging
import sys
import os
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
import database
from middlewares import UserTrackingMiddleware, RateLimitMiddleware
from handlers import (
    common_router,
    search_router,
    download_router,
    recognition_router,
    charts_router,
    favorites_router,
    admin_router,
    inline_router,
    media_router,
)

# ── Logging sozlamasi ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.DATA_DIR / "bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Bot ishga tushganda bajariladigan ishlar."""
    await database.init_db()
    await database.cleanup_old_sessions()

    me = await bot.get_me()
    logger.info(f"🎵 Melodiya Bot ishga tushdi! @{me.username} (ID: {me.id})")

    # Admin(lar)ga xabar yuborish
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "✅ <b>Melodiya Bot</b> muvaffaqiyatli ishga tushdi!\n\n"
                f"🤖 Bot: @{me.username}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Admin ({admin_id}) ga xabar yuborib bo'lmadi: {e}")


async def on_shutdown(bot: Bot):
    """Bot to'xtatilganda bajariladigan ishlar."""
    logger.info("🛑 Melodiya Bot to'xtatilmoqda...")

    # Vaqtinchalik yuklab olingan fayllarni tozalash
    downloads = Path(config.DOWNLOADS_DIR)
    removed = 0
    for pattern in ("*.mp3", "*.mp4", "*.m4a", "*.ogg", "*.jpg", "*.webp"):
        for f in downloads.glob(pattern):
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass
    if removed:
        logger.info(f"🗑 {removed} ta vaqtinchalik fayl o'chirildi.")


async def start_web_server():
    """Render.com yoki bulutli hostinglar uchun 24/7 Healthcheck Web Server."""
    port = int(os.getenv("PORT", "8080"))
    app = web.Application()

    async def healthcheck(request):
        return web.Response(text="🎵 Melodiya Bot 24/7 muvaffaqiyatli ishlab turibdi!", content_type="text/plain")

    app.router.add_get("/", healthcheck)
    app.router.add_get("/health", healthcheck)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Healthcheck Web server 0.0.0.0:{port} portida ishga tushdi (Render uchun).")


async def main():
    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ BOT_TOKEN sozlanmagan! .env faylini tekshiring.")
        sys.exit(1)

    # Render.com yoki PORT berilgan bulutli serverlarda web serverni fon rejimida yoqish
    if os.getenv("PORT"):
        try:
            await start_web_server()
        except Exception as e:
            logger.warning(f"Web serverni ishga tushirishda ogohlantirish: {e}")

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Middleware — barcha xabarlar uchun foydalanuvchini kuzatish
    dp.message.middleware(UserTrackingMiddleware())
    dp.callback_query.middleware(UserTrackingMiddleware())

    # Startup / Shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Routerlarni ulash (tartib muhim — umumiylar oxirida)
    dp.include_router(admin_router)
    dp.include_router(charts_router)
    dp.include_router(favorites_router)
    dp.include_router(media_router)       # Video, audio va effektlar
    dp.include_router(download_router)
    dp.include_router(recognition_router)
    dp.include_router(search_router)
    dp.include_router(inline_router)   # Inline mode (@bot chat ichida)
    dp.include_router(common_router)   # /start va fallback eng oxirida

    logger.info("⚡ Polling boshlandi...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot foydalanuvchi tomonidan to'xtatildi.")

