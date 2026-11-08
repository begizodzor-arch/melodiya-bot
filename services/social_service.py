import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
import yt_dlp

import config
from utils.helpers import clean_music_metadata

logger = logging.getLogger(__name__)


def _sync_download_social_audio(url: str) -> Optional[Dict[str, Any]]:
    """TikTok yoki Instagram Reels havolasidan MP3 musiqani yuklab olish."""
    out_id = uuid.uuid4().hex[:8]
    outtmpl = str(config.DOWNLOADS_DIR / f"social_{out_id}.%(ext)s")
    expected_mp3 = config.DOWNLOADS_DIR / f"social_{out_id}.mp3"

    ydl_opts = {
        'format': 'ba/b',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'ffmpeg_location': config.FFMPEG_PATH,
        'outtmpl': outtmpl,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'socket_timeout': 20,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            raw_title = info.get('title') or "TikTok / Reels Musiqa"
            uploader = info.get('uploader') or "ijtimoiy tarmoq"
            duration = info.get('duration') or 0

            performer, title = clean_music_metadata(raw_title, uploader)

            if expected_mp3.exists():
                return {
                    "file_path": expected_mp3,
                    "title": title[:60],
                    "performer": performer[:60],
                    "duration": duration,
                }
    except Exception as e:
        logger.error(f"TikTok/Instagram yuklashda xatolik: {e}")
        if expected_mp3.exists():
            expected_mp3.unlink(missing_ok=True)

    return None


async def download_social_audio(url: str) -> Optional[Dict[str, Any]]:
    """TikTok yoki Instagram Reels dan MP3 yuklab olish (asinxron)."""
    return await asyncio.to_thread(_sync_download_social_audio, url)

