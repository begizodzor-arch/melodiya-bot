import logging
from typing import Optional, Dict, Any
from shazamio import Shazam

logger = logging.getLogger(__name__)

async def recognize_song_from_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Ovozli xabar yoki video fayldan qo'shiqni aniqlash (Shazam).
    Foydalanuvchi audio yoki ovozli xabar yuborganda ishlaydi.
    """
    try:
        shazam = Shazam()
        out = await shazam.recognize(file_path)
        track = out.get('track')
        if not track:
            return None
        
        title = track.get('title', 'Unknown')
        artist = track.get('subtitle', 'Unknown')
        
        images = track.get('images', {})
        cover = images.get('coverarthq') or images.get('coverart')
        
        return {
            "title": title,
            "artist": artist,
            "query": f"{artist} {title}".strip(),
            "cover_url": cover,
        }
    except Exception as e:
        logger.error(f"Shazam orqali musiqani aniqlashda xatolik: {e}")
        return None

