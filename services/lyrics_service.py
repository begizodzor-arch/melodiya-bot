import logging
import re
from typing import Optional
import aiohttp
import yt_dlp
import asyncio

import database

logger = logging.getLogger(__name__)


def _sync_get_yt_lyrics(video_id: str) -> Optional[str]:
    """YouTube video tavsifidan qo'shiq matnini ajratish."""
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': False,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            desc = info.get("description", "")
            if not desc:
                return None

            # Matn belgilari bo'lsa (Lyrics, Текст песни, Qo'shiq matni)
            keywords = ["lyrics:", "tekst:", "matni:", "текст песни:", "слова песни:"]
            desc_lower = desc.lower()
            for kw in keywords:
                if kw in desc_lower:
                    idx = desc_lower.index(kw)
                    return desc[idx + len(kw):].strip()[:3500]

            # Agar 10 qatordan ko'p matn bo'lsa
            lines = desc.split("\n")
            if len(lines) > 8:
                return desc[:3500].strip()
    except Exception as e:
        logger.error(f"YouTube lyrics xatosi: {e}")
    return None


async def get_song_lyrics(performer: str, title: str, video_id: Optional[str] = None) -> Optional[str]:
    """
    Qo'shiq matnini olish (Cache -> Lyrics API -> YouTube tavsifi).
    """
    clean_p = re.sub(r'feat\..*|ft\..*', '', performer, flags=re.IGNORECASE).strip()
    clean_t = re.sub(r'\(.*?\)|\[.*?\]', '', title).strip()
    cache_key = f"{clean_p} - {clean_t}"

    # 1. Keshdan tekshirish
    cached = await database.get_cached_lyrics(cache_key)
    if cached:
        return cached

    # 2. lyrics.ovh ochiq API
    try:
        url = f"https://api.lyrics.ovh/v1/{clean_p}/{clean_t}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    lyrics = data.get("lyrics", "").strip()
                    if lyrics and len(lyrics) > 30:
                        await database.save_cached_lyrics(cache_key, lyrics)
                        return lyrics
    except Exception:
        pass

    # 3. YouTube tavsifidan izlash
    if video_id:
        yt_lyrics = await asyncio.to_thread(_sync_get_yt_lyrics, video_id)
        if yt_lyrics and len(yt_lyrics) > 40:
            await database.save_cached_lyrics(cache_key, yt_lyrics)
            return yt_lyrics

    return None

