import asyncio
import logging
import subprocess
import uuid
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

EFFECT_FILTERS = {
    "8d": "apulsator=hz=0.125:amount=1,aecho=0.8:0.88:60:0.4",
    "bass": "equalizer=f=60:width_type=h:width=50:g=10,equalizer=f=100:width_type=h:width=50:g=8",
    "concert": "aecho=0.8:0.88:60|120:0.4|0.3",
    "slowed": "atempo=0.88,asetrate=44100*0.9,aecho=0.8:0.88:60:0.4",
    "speed": "atempo=1.2,asetrate=44100*1.1",
    "chipmunk": "asetrate=44100*1.3,atempo=1.0",
    "deep": "asetrate=44100*0.8,atempo=1.0",
    "robot": "flanger=delay=10:depth=5:regen=70:width=70:speed=2",
}

EFFECT_NAMES = {
    "8d": "🎧 8D Audio (Quloqchinlarda tinglang)",
    "bass": "🔊 Bass Boost",
    "concert": "🏛 Konsert (Reverb / Echo)",
    "slowed": "🌙 Slowed + Reverb",
    "speed": "⚡️ Tezlashtirilgan (Nightcore)",
    "chipmunk": "🐿 Alvin (Ingichka ovoz)",
    "deep": "🦁 Chuqur erkak ovozi",
    "robot": "🤖 Robot ovozi",
}


def _sync_apply_audio_effect(input_path: str, effect_type: str) -> Optional[str]:
    """Audio faylga effekt berish (sinxrron qism)."""
    filter_str = EFFECT_FILTERS.get(effect_type)
    if not filter_str:
        return None

    out_id = uuid.uuid4().hex[:8]
    output_path = str(config.DOWNLOADS_DIR / f"effect_{effect_type}_{out_id}.mp3")

    cmd = [
        config.FFMPEG_PATH, "-y",
        "-i", str(input_path),
        "-af", filter_str,
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        output_path
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if res.returncode == 0 and Path(output_path).exists():
            return output_path
        else:
            logger.error(f"Effekt berishda xatolik: {res.stderr}")
    except Exception as e:
        logger.error(f"FFmpeg xatosi: {e}")

    return None


async def apply_audio_effect(input_path: str, effect_type: str) -> Optional[str]:
    """Audio faylga effekt berish (asinxron wrapper)."""
    return await asyncio.to_thread(_sync_apply_audio_effect, input_path, effect_type)


def _sync_make_ringtone(input_path: str, start_sec: int = 30, duration: int = 30) -> Optional[str]:
    """Qo'shiqdan 30 soniyalik silliq Ringtone (Gudok) yasash."""
    out_id = uuid.uuid4().hex[:8]
    output_path = str(config.DOWNLOADS_DIR / f"ringtone_{out_id}.mp3")

    fade_out_start = max(1, duration - 2)
    filter_str = f"afade=t=in:ss=0:d=1,afade=t=out:st={fade_out_start}:d=2"

    cmd = [
        config.FFMPEG_PATH, "-y",
        "-ss", str(start_sec),
        "-t", str(duration),
        "-i", str(input_path),
        "-af", filter_str,
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        output_path
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode == 0 and Path(output_path).exists():
            return output_path
        else:
            logger.error(f"Ringtone kesishda xatolik: {res.stderr}")
    except Exception as e:
        logger.error(f"FFmpeg ringtone xatosi: {e}")

    return None


async def make_ringtone(input_path: str, start_sec: int = 30, duration: int = 30) -> Optional[str]:
    """Musiqadan ringtone qirqib olish (asinxron)."""
    return await asyncio.to_thread(_sync_make_ringtone, input_path, start_sec, duration)


def _sync_convert_to_video_note(video_path: str) -> Optional[str]:
    """Videoni Telegram dumaloq video (Teleskop / video note) formatiga o'tkazish."""
    out_id = uuid.uuid4().hex[:8]
    output_path = str(config.DOWNLOADS_DIR / f"vnote_{out_id}.mp4")

    cmd = [
        config.FFMPEG_PATH, "-y",
        "-i", str(video_path),
        "-t", "60",
        "-vf", "crop=min(iw\\,ih):min(iw\\,ih),scale=480:480",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "26",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-movflags", "+faststart",
        output_path
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode == 0 and Path(output_path).exists():
            return output_path
        else:
            logger.error(f"Dumaloq video tayyorlashda xatolik: {res.stderr}")
    except Exception as e:
        logger.error(f"FFmpeg dumaloq video xatosi: {e}")

    return None


async def convert_to_video_note(video_path: str) -> Optional[str]:
    """Videoni dumaloq video (Teleskop) formatiga aylantirish."""
    return await asyncio.to_thread(_sync_convert_to_video_note, video_path)


def _sync_extract_audio_from_video(video_path: str) -> Optional[str]:
    """Videodan MP3 musiqani ajratib olish."""
    out_id = uuid.uuid4().hex[:8]
    output_path = str(config.DOWNLOADS_DIR / f"extracted_{out_id}.mp3")

    cmd = [
        config.FFMPEG_PATH, "-y",
        "-i", str(video_path),
        "-vn",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        output_path
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode == 0 and Path(output_path).exists():
            return output_path
        else:
            logger.error(f"Videodan audio ajratishda xatolik: {res.stderr}")
    except Exception as e:
        logger.error(f"FFmpeg audio ajratish xatosi: {e}")

    return None


async def extract_audio_from_video(video_path: str) -> Optional[str]:
    """Videodan audioni MP3 qilib ajratib olish."""
    return await asyncio.to_thread(_sync_extract_audio_from_video, video_path)
