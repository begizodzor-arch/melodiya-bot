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
    """YouTube cookies.txt faylini topish (mavjud bo'lsa)."""
    paths = [
        config.BASE_DIR / "cookies.txt",
        Path("/etc/secrets/cookies.txt"),
        config.DATA_DIR / "cookies.txt",
    ]
    for p in paths:
        if p.exists() and p.stat().st_size > 50:
            return str(p)
    return None


def _sync_search_youtube(query: str, limit: int = 30) -> List[Dict[str, Any]]:
    """YouTube dan qo'shiqlarni qidirish (Default & VisionOS orqali)."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extract_flat': True,
        'skip_download': True,
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


def _convert_to_mp3(src_file: Path, target_mp3: Path) -> bool:
    """Istalgan audio/video faylni toza 192kbps MP3 formatga o'tkazish."""
    try:
        cmd = [
            config.FFMPEG_PATH,
            "-y",
            "-i", str(src_file),
            "-vn",
            "-codec:a", "libmp3lame",
            "-b:a", "192k",
            "-ar", "44100",
            str(target_mp3),
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0 and target_mp3.exists() and target_mp3.stat().st_size > 1024:
            return True
    except Exception as e:
        logger.warning(f"FFmpeg konvertatsiya xatosi: {e}")
    return False


def _try_soundcloud_download(query: str, outtmpl: str, expected_mp3: Path) -> Optional[Dict[str, Any]]:
    """SoundCloud fallback (YouTube server IP ni bloklaganda ishlatiladi)."""
    logger.info(f"SoundCloud orqali qidirilmoqda: {query}")
    sc_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'outtmpl': outtmpl,
        'socket_timeout': 30,
        'retries': 2,
    }
    try:
        with yt_dlp.YoutubeDL(sc_opts) as ydl:
            info = ydl.extract_info(f"scsearch1:{query}", download=True)
            entries = info.get('entries', []) if info else []
            if entries:
                track = entries[0]
                downloaded = [f for f in config.DOWNLOADS_DIR.glob(f"{expected_mp3.stem}.*") if f != expected_mp3]
                for src in downloaded:
                    if src.stat().st_size > 1024:
                        if _convert_to_mp3(src, expected_mp3):
                            src.unlink(missing_ok=True)
                            raw_title = track.get('title', query)
                            uploader = track.get('uploader', '')
                            performer, title = clean_music_metadata(raw_title, uploader)
                            logger.info(f"SoundCloud muvaffaqiyatli: {title}")
                            return {
                                "file_path": expected_mp3,
                                "video_id": track.get('id', 'sc'),
                                "title": title,
                                "performer": performer,
                                "duration": track.get('duration', 0),
                            }
    except Exception as e:
        logger.warning(f"SoundCloud yuklab olish xatosi: {e}")
    return None


def _sync_download_track(
    video_id: str,
    title_hint: str = "",
    performer_hint: str = ""
) -> Optional[Dict[str, Any]]:
    """
    YouTube qo'shig'ini MP3 formatida yuklab olish.
    VisionOS va Default mijozlar orqali YouTube bot-tekshiruvlarini aylanib o'tadi.
    """
    outtmpl = str(config.DOWNLOADS_DIR / f"{video_id}.%(ext)s")
    expected_mp3 = config.DOWNLOADS_DIR / f"{video_id}.mp3"

    # 1. Keshda allaqachon mavjud bo'lsa
    if expected_mp3.exists() and expected_mp3.stat().st_size > 1024:
        return {
            "file_path": expected_mp3,
            "video_id": video_id,
            "title": title_hint or "Musiqa",
            "performer": performer_hint or "Ijrochi",
            "duration": 0,
        }

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    metadata = {
        "title": title_hint or "Unknown",
        "duration": 0,
        "uploader": performer_hint or "",
    }

    # Strategiyalar ro'yxati
    strategies = [
        # 1-usul: VisionOS mijozi (Apple Vision Pro) — Bot-tekshiruvlar yo'q, datacenter IP lardan ham ishlaydi
        {
            'format': 'ba/b',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'outtmpl': outtmpl,
            'extractor_args': {'youtube': {'player_client': ['visionos']}},
            'socket_timeout': 30,
            'retries': 3,
        },
        # 2-usul: Standart yt-dlp default oqimlari
        {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'outtmpl': outtmpl,
            'socket_timeout': 30,
            'retries': 3,
        },
    ]

    # Cookie fayli mavjud bo'lsa, uni 3-usul sifatida qo'shamiz
    cookie_file = _get_cookie_file()
    if cookie_file:
        strategies.append({
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'cookiefile': cookie_file,
            'outtmpl': outtmpl,
            'socket_timeout': 30,
            'retries': 2,
        })

    for strat_idx, opts in enumerate(strategies, start=1):
        try:
            logger.info(f"YouTube yuklab olish #{strat_idx} ({video_id})...")
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                if info:
                    metadata["title"] = info.get('title') or metadata["title"]
                    metadata["duration"] = info.get('duration') or metadata["duration"]
                    metadata["uploader"] = info.get('uploader') or metadata["uploader"]

            # Yuklangan har qanday faylni (webm, m4a, mp4) MP3 ga o'tkazish
            downloaded = [f for f in config.DOWNLOADS_DIR.glob(f"{video_id}.*") if f != expected_mp3]
            for src in downloaded:
                if src.stat().st_size > 1024:
                    success = _convert_to_mp3(src, expected_mp3)
                    src.unlink(missing_ok=True)
                    if success:
                        break

            if expected_mp3.exists() and expected_mp3.stat().st_size > 1024:
                performer, title = clean_music_metadata(metadata["title"], metadata["uploader"])
                if title_hint:
                    title = title_hint
                if performer_hint and performer in ("Ijrochi", "Unknown", ""):
                    performer = performer_hint

                logger.info(f"Muvaffaqiyatli MP3 yaratildi: {performer} - {title}")
                return {
                    "file_path": expected_mp3,
                    "video_id": video_id,
                    "title": title,
                    "performer": performer,
                    "duration": metadata["duration"],
                }

        except Exception as e:
            logger.warning(f"Yuklab olish #{strat_idx} xatosi ({video_id}): {e}")

    # Agar YouTube butunlay bloklagan bo'lsa, SoundCloud orqali qidirib yuklab olish
    search_term = f"{performer_hint} {title_hint}".strip() or metadata["title"]
    if search_term and search_term != "Unknown":
        logger.info(f"YouTube barcha urinishlar bloklandi, SoundCloud'ga murojaat: {search_term}")
        sc_res = _try_soundcloud_download(search_term, outtmpl, expected_mp3)
        if sc_res:
            return sc_res

    # Barcha usullar muvaffaqiyatsiz bo'lsa qoldiq fayllarni tozalash
    for f in config.DOWNLOADS_DIR.glob(f"{video_id}.*"):
        f.unlink(missing_ok=True)

    logger.error(f"Barcha yuklab olish usullari muvaffaqiyatsiz: {video_id}")
    return None


async def download_track_as_mp3(
    video_id: str,
    title_hint: str = "",
    performer_hint: str = ""
) -> Optional[Dict[str, Any]]:
    """Qo'shiqni asinxron tarzda MP3 qilib yuklab olish."""
    return await asyncio.to_thread(_sync_download_track, video_id, title_hint, performer_hint)
