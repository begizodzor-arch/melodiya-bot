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
        'extractor_args': {'youtube': {'player_client': ['android']}},
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


import subprocess

def _sync_download_track(video_id: str) -> Optional[Dict[str, Any]]:
    """YouTube qo'shig'ini MP3 formatida yuklab olish (ko'p bosqichli va barqaror)."""
    outtmpl = str(config.DOWNLOADS_DIR / f"{video_id}.%(ext)s")
    expected_mp3 = config.DOWNLOADS_DIR / f"{video_id}.mp3"

    # 1. Agar fayl allaqachon mavjud bo'lsa qayta yuklamaymiz
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
            return {
                "file_path": expected_mp3,
                "video_id": video_id,
                "title": "Musiqa",
                "performer": "Ijrochi",
                "duration": 0,
            }

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    metadata = {"title": "Unknown", "duration": 0, "uploader": ""}

    # 2. Sinab ko'rish variantlari (Server va Render cheklovlarini aylanib o'tish uchun)
    strategies = [
        # 1-usul: Android mobil klient (bot-tekshiruvsiz va tezkor)
        {
            'format': 'ba[ext=m4a]/ba/b',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': config.FFMPEG_PATH,
            'extractor_args': {'youtube': {'player_client': ['android']}},
            'outtmpl': outtmpl,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'max_filesize': 50 * 1024 * 1024,
            'socket_timeout': 35,
            'retries': 3,
            'fragment_retries': 3,
            'concurrent_fragment_downloads': 4,
        },
        # 2-usul: Umumiy standart format
        {
            'format': 'bestaudio/best',
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
            'max_filesize': 50 * 1024 * 1024,
            'socket_timeout': 45,
            'retries': 3,
        },
        # 3-usul: Postprocessorsiz yuklab olib, o'zimiz FFmpeg bilan aylantirish
        {
            'format': 'ba/b',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['android']}},
            'outtmpl': outtmpl,
            'max_filesize': 50 * 1024 * 1024,
            'socket_timeout': 45,
            'retries': 3,
        }
    ]

    for strat_idx, opts in enumerate(strategies, start=1):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                if info:
                    metadata["title"] = info.get('title', metadata["title"])
                    metadata["duration"] = info.get('duration', metadata["duration"])
                    metadata["uploader"] = info.get('uploader', metadata["uploader"])

            # MP3 tayyormi tekshirish
            if expected_mp3.exists() and expected_mp3.stat().st_size > 1024:
                break

            # Agar boshqa formatda yuklangan bo'lsa (masalan mp4 yoki m4a yoki webm)
            other_files = list(config.DOWNLOADS_DIR.glob(f"{video_id}.*"))
            for f in other_files:
                if f != expected_mp3 and f.stat().st_size > 1024:
                    # FFmpeg orqali mp3 ga o'tkazish
                    try:
                        cmd = [
                            config.FFMPEG_PATH, "-y",
                            "-i", str(f),
                            "-vn",
                            "-ab", "192k",
                            "-ar", "44100",
                            str(expected_mp3)
                        ]
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                        f.unlink(missing_ok=True)
                        break
                    except Exception as fe:
                        logger.warning(f"Qo'lda FFmpeg konvertatsiya xatosi: {fe}")

            if expected_mp3.exists() and expected_mp3.stat().st_size > 1024:
                break

        except Exception as e:
            logger.warning(f"Yuklab olish strategiyasi #{strat_idx} xatosi ({video_id}): {e}")

    if expected_mp3.exists() and expected_mp3.stat().st_size > 1024:
        performer, title = clean_music_metadata(metadata["title"], metadata["uploader"])
        return {
            "file_path": expected_mp3,
            "video_id": video_id,
            "title": title,
            "performer": performer,
            "duration": metadata["duration"],
        }

    # Barcha usullar muvaffaqiyatsiz bo'lsa tozalash
    for f in config.DOWNLOADS_DIR.glob(f"{video_id}.*"):
        f.unlink(missing_ok=True)

    return None


async def download_track_as_mp3(video_id: str) -> Optional[Dict[str, Any]]:
    """Qo'shiqni asinxron tarzda MP3 qilib yuklab olish."""
    return await asyncio.to_thread(_sync_download_track, video_id)
