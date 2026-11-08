import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import yt_dlp

import config
from utils.helpers import clean_music_metadata, format_duration

logger = logging.getLogger(__name__)


def _sync_search_youtube(query: str, limit: int = 30) -> List[Dict[str, Any]]:
    """YouTube dan qo'shiqlarni qidirish (sinxrron qism)."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extract_flat': True,
        'skip_download': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }

    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_query = f"ytsearch{limit}:{query}"
            info = ydl.extract_info(search_query, download=False)
            entries = info.get('entries', []) if info else []

            for entry in entries:
                if not entry:
                    continue

                video_id = entry.get('id')
                raw_title = entry.get('title')
                duration = entry.get('duration') or 0
                uploader = entry.get('uploader') or ""

                if not video_id or not raw_title:
                    continue

                # Juda uzun videolarni o'tkazib yuborish (masalan 20 daqiqadan ko'p)
                if duration and duration > config.MAX_DURATION_SECONDS:
                    continue

                performer, title = clean_music_metadata(raw_title, uploader)

                results.append({
                    "video_id": video_id,
                    "raw_title": raw_title,
                    "title": title,
                    "performer": performer,
                    "duration": duration,
                    "duration_str": format_duration(duration),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                })
    except Exception as e:
        logger.error(f"YouTube qidiruvida xatolik: {e}")

    return results


async def search_youtube(query: str, limit: int = 30) -> List[Dict[str, Any]]:
    """YouTube dan qo'shiqlarni qidirish (asinxron wrapper)."""
    return await asyncio.to_thread(_sync_search_youtube, query, limit)


def _sync_download_track(video_id: str) -> Optional[Dict[str, Any]]:
    """YouTube qo'shig'ini MP3 formatida yuklab olish (sinxrron)."""
    outtmpl = str(config.DOWNLOADS_DIR / f"{video_id}.%(ext)s")
    expected_mp3 = config.DOWNLOADS_DIR / f"{video_id}.mp3"

    # Agar fayl allaqachon mavjud bo'lsa qayta yuklamaymiz
    if expected_mp3.exists() and expected_mp3.stat().st_size > 1024:
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}",
                    download=False
                )
                raw_title = info.get('title', 'Unknown')
                duration = info.get('duration', 0)
                uploader = info.get('uploader', '')
                performer, title = clean_music_metadata(raw_title, uploader)
                return {
                    "file_path": expected_mp3,
                    "video_id": video_id,
                    "title": title,
                    "performer": performer,
                    "duration": duration,
                }
        except Exception:
            pass

    ydl_opts = {
        # ── Ultra-tezkor sozlamalar ──
        'format': 'ba[ext=m4a]/ba/b',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'ffmpeg_location': config.FFMPEG_PATH,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        'outtmpl': outtmpl,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'max_filesize': 50 * 1024 * 1024,
        'socket_timeout': 15,
        'retries': 2,
        'fragment_retries': 2,
        'concurrent_fragment_downloads': 4,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            info = ydl.extract_info(video_url, download=True)

            raw_title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
            uploader = info.get('uploader', '')
            performer, title = clean_music_metadata(raw_title, uploader)

            if expected_mp3.exists():
                return {
                    "file_path": expected_mp3,
                    "video_id": video_id,
                    "title": title,
                    "performer": performer,
                    "duration": duration,
                }
    except Exception as e:
        logger.error(f"MP3 yuklab olishda xatolik ({video_id}): {e}")
        if expected_mp3.exists():
            expected_mp3.unlink(missing_ok=True)

    return None


async def download_track_as_mp3(video_id: str) -> Optional[Dict[str, Any]]:
    """Qo'shiqni asinxron tarzda MP3 qilib yuklab olish."""
    return await asyncio.to_thread(_sync_download_track, video_id)
