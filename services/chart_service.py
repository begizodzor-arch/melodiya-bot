import logging
from typing import List, Dict, Any
from database.db import get_top_downloaded_tracks

logger = logging.getLogger(__name__)

POPULAR_CATEGORIES = {
    "uzbek": {
        "title": "🇺🇿 O'zbek xitlari",
        "query": "Eng yangi o'zbek xit qo'shiqlar 2026"
    },
    "global": {
        "title": "🌍 Jahon xitlari (Global Top)",
        "query": "Top Global Hits Billboard 2026"
    },
    "cis": {
        "title": "🔥 MDH / Trend treklari",
        "query": "Populyarnie treki novinki 2026"
    },
    "tiktok": {
        "title": "📱 TikTok trend musiqalar",
        "query": "TikTok trend music viral 2026"
    }
}

async def get_popular_charts() -> Dict[str, Any]:
    """Trenddagi toifalar va botning eng ko'p yuklangan qo'shiqlari."""
    top_cached = await get_top_downloaded_tracks(limit=10)
    return {
        "categories": POPULAR_CATEGORIES,
        "top_cached": top_cached
    }

