import asyncio
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
import yt_dlp

import config
from utils.helpers import clean_music_metadata, format_duration

logger = logging.getLogger(__name__)


def _get_cookie_file() -> Optional[str]:
    """YouTube bot-blokdan o'tish uchun cookies.txt faylini topish."""
    paths = [
        config.BASE_DIR / "cookies.txt",
        Path("/etc/secrets/cookies.txt"),
        config.DATA_DIR / "cookies.txt",
    ]
    for p in paths:
        if p.exists() and p.stat().st_size > 50:
            logger.info(f"Cookie holati: Mavjud ({p})")
            return str(p)
    logger.warning("Cookie holati: Hali kiritilmagan")
    return None


def _sync_search_youtube(query: str, limit: int = 30) -> List[Dict[str, Any]]:
    """YouTube dan qo'shiqlarni qidirish (sinxrron qism)."""
    cookie_file = _get_cookie_file()
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extract_flat': True,
        'skip_download': True,
        'extractor_args': {'youtube': {'player_client': ['tv_embedded', 'android']}},
    }
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

    # "music" qo'shish - noto'g'ri natijalarni kamaytiradi (masalan "Sen" = Senator yangiliklari emas)
    enhanced_query = f"{query} music"

    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_query = f"ytsearch{limit}:{enhanced_query}"
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

                # Juda uzun videolarni o'tkazib yuborish
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


def _try_soundcloud_download(query: str, outtmpl: str, expected_mp3: Path) -> Optional[Dict[str, Any]]:
    """SoundCloud orqali qo'shiq yuklab olish (YouTube blok bo'lganda)."""
    logger.info(f"SoundCloud orqali urinish: {query}")
    sc_opts = {
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
        'socket_timeout': 60,
        'retries': 3,
    }
    try:
        with yt_dlp.YoutubeDL(sc_opts) as ydl:
            sc_query = f"scsearch1:{query}"
            info = ydl.extract_info(sc_query, download=True)
            if info and expected_mp3.exists() and expected_mp3.stat().st_size > 1024:
                raw_title = info.get('title', 'Musiqa')
                uploader = info.get('uploader', '')
                performer, title = clean_music_metadata(raw_title, uploader)
                logger.info(f"SoundCloud muvaffaqiyatli: {title}")
                return {
                    "file_path": expected_mp3,
                    "video_id": info.get('id', 'sc'),
                    "title": title,
                    "performer": performer,
                    "duration": info.get('duration', 0),
                }
    except Exception as e:
        logger.warning(f"SoundCloud xatolik: {e}")
    return None


def _sync_download_track(video_id: str) -> Optional[Dict[str, Any]]:
    """YouTube qo'shig'ini MP3 formatida yuklab olish (ko'p bosqichli va barqaror)."""
    outtmpl = str(config.DOWNLOADS_DIR / f"{video_id}.%(ext)s")
    expected_mp3 = config.DOWNLOADS_DIR / f"{video_id}.mp3"

    # 1. Agar fayl allaqachon mavjud bo'lsa qayta yuklamaymiz
    if expected_mp3.exists() and expected_mp3.stat().st_size > 1024:
        return {
            "file_path": expected_mp3,
            "video_id": video_id,
            "title": "Musiqa",
            "performer": "Ijrochi",
            "duration": 0,
        }

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    metadata = {"title": "Unknown", "duration": 0, "uploader": ""}

    cookie_file = _get_cookie_file()

    # YouTube yuklab olish urinishlari
    strategies = [
        # 1-usul: TV Embedded - bot tekshiruvi yo'q (serverlarda eng yaxshi)
        {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': config.FFMPEG_PATH,
            'extractor_args': {
                'youtube': {
                    'player_client': ['tv_embedded'],
                    'player_skip': ['webpage'],
                }
            },
            'outtmpl': outtmpl,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'max_filesize': 50 * 1024 * 1024,
            'socket_timeout': 60,
            'retries': 5,
            'fragment_retries': 5,
        },
        # 2-usul: Android klient + cookies
        {
            'format': 'ba[ext=m4a]/ba/b',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': config.FFMPEG_PATH,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                }
            },
            'outtmpl': outtmpl,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'max_filesize': 50 * 1024 * 1024,
            'socket_timeout': 60,
            'retries': 5,
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12) gzip',
            },
        },
        # 3-usul: iOS klient
        {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': config.FFMPEG_PATH,
            'extractor_args': {'youtube': {'player_client': ['ios']}},
            'outtmpl': outtmpl,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'max_filesize': 50 * 1024 * 1024,
            'socket_timeout': 60,
            'retries': 5,
        },
        # 4-usul: postprocessorsiz, keyin FFmpeg qo'lda
        {
            'format': 'ba/b',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['tv_embedded', 'android']}},
            'outtmpl': outtmpl,
            'max_filesize': 50 * 1024 * 1024,
            'socket_timeout': 60,
            'retries': 5,
        }
    ]

    # Cookies'ni barcha strategiyalarga qo'shish
    for s in strategies:
        if cookie_file:
            s['cookiefile'] = cookie_file

    for strat_idx, opts in enumerate(strategies, start=1):
        try:
            logger.info(f"YouTube yuklab olish #{strat_idx} urinish: {video_id}")
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                if info:
                    metadata["title"] = info.get('title', metadata["title"])
                    metadata["duration"] = info.get('duration', metadata["duration"])
                    metadata["uploader"] = info.get('uploader', metadata["uploader"])

            # MP3 tayyormi tekshirish
            if expected_mp3.exists() and expected_mp3.stat().st_size > 1024:
                break

            # Boshqa formatda yuklangan bo'lsa FFmpeg bilan aylantirish
            other_files = list(config.DOWNLOADS_DIR.glob(f"{video_id}.*"))
            for f in other_files:
                if f != expected_mp3 and f.stat().st_size > 1024:
                    try:
                        cmd = [
                            config.FFMPEG_PATH, "-y",
                            "-i", str(f),
                            "-vn", "-ab", "192k", "-ar", "44100",
                            str(expected_mp3)
                        ]
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                        f.unlink(missing_ok=True)
                        break
                    except Exception as fe:
                        logger.warning(f"FFmpeg konvertatsiya xatosi: {fe}")

            if expected_mp3.exists() and expected_mp3.stat().st_size > 1024:
                break

        except Exception as e:
            logger.warning(f"YouTube yuklab olish #{strat_idx} xatosi ({video_id}): {e}")

    # YouTube muvaffaqiyatli bo'ldi
    if expected_mp3.exists() and expected_mp3.stat().st_size > 1024:
        performer, title = clean_music_metadata(metadata["title"], metadata["uploader"])
        logger.info(f"YouTube muvaffaqiyatli: {title}")
        return {
            "file_path": expected_mp3,
            "video_id": video_id,
            "title": title,
            "performer": performer,
            "duration": metadata["duration"],
        }

    # YouTube barchasi muvaffaqiyatsiz — SoundCloud orqali urinish
    logger.warning(f"YouTube blok qildi {video_id} — SoundCloud ga o'tilmoqda...")
    sc_result = _try_soundcloud_download(metadata["title"] or video_id, outtmpl, expected_mp3)
    if sc_result:
        return sc_result

    # Barcha usullar muvaffaqiyatsiz — tozalash
    for f in config.DOWNLOADS_DIR.glob(f"{video_id}.*"):
        f.unlink(missing_ok=True)
    logger.error(f"Barcha usullar muvaffaqiyatsiz: {video_id}")
    return None


async def download_track_as_mp3(video_id: str) -> Optional[Dict[str, Any]]:
    """Qo'shiqni asinxron tarzda MP3 qilib yuklab olish."""
    return await asyncio.to_thread(_sync_download_track, video_id)
