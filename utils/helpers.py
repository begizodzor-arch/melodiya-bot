import re
import os
import uuid
import logging
from typing import Tuple, Optional, List
from pathlib import Path
from aiogram import Bot
import config

logger = logging.getLogger(__name__)

def format_duration(seconds: Optional[int]) -> str:
    """Soniyalarni mm:ss yoki hh:mm:ss formatiga o'tkazish."""
    if not seconds or seconds <= 0:
        return "00:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def clean_music_metadata(raw_title: str, uploader: Optional[str] = None) -> Tuple[str, str]:
    """
    YouTube sarlavhasidan keraksiz so'zlarni tozalab,
    (ijrochi, qo'shiq_nomi) ko'rinishida ajratib beradi.
    """
    title = raw_title
    
    # Ortiqcha qo'shimchalarni olib tashlash
    garbage_patterns = [
        r'\[.*?official.*?\]',
        r'\(.*?official.*?\)',
        r'\[.*?music.*?video.*?\]',
        r'\(.*?music.*?video.*?\]',
        r'\[.*?audio.*?\]',
        r'\(.*?audio.*?\)',
        r'\[.*?клип.*?\]',
        r'\(.*?клип.*?\)',
        r'\[.*?премьера.*?\]',
        r'\(.*?премьера.*?\)',
        r'\[.*?premyera.*?\]',
        r'\(.*?premyera.*?\)',
        r'\(.*?lyrics.*?\)',
        r'\[.*?lyrics.*?\]',
        r'\(.*?tekst.*?\)',
        r'\[.*?hd.*?\]',
        r'\[.*?4k.*?\]',
        r'#\w+',
    ]
    
    for pattern in garbage_patterns:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
    title = title.strip()
    
    # " - " yoki " — " yoki " – " orqali ajratish
    split_match = re.split(r'\s+[-—–:]\s+', title, maxsplit=1)
    
    if len(split_match) == 2:
        performer = split_match[0].strip()
        song_title = split_match[1].strip()
    else:
        # Agar defis bo'lmasa, uploader ijrochi bo'lishi mumkin
        if uploader and "topic" not in uploader.lower() and "vevo" not in uploader.lower():
            performer = uploader.replace(" - Topic", "").strip()
        else:
            performer = "Noma'lum ijrochi"
        song_title = title.strip()
        
    if not song_title:
        song_title = raw_title
    if not performer:
        performer = "Noma'lum ijrochi"
        
    return performer[:100], song_title[:100]

def generate_session_id() -> str:
    """Qidiruv natijalari uchun qisqa unikal identifikator."""
    return uuid.uuid4().hex[:10]

def safe_remove_file(file_path: Optional[str | Path]):
    """Faylni xavfsiz o'chirish."""
    if not file_path:
        return
    try:
        path = Path(file_path)
        if path.exists():
            os.remove(path)
    except Exception:
        pass

async def is_subscribed_to_sponsors(bot: Bot, user_id: int) -> Tuple[bool, List[str]]:
    """Foydalanuvchi majburiy kanallarga a'zo bo'lganini tekshirish."""
    if not config.SPONSOR_CHANNELS:
        return True, []
        
    unsubscribed = []
    for channel in config.SPONSOR_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                unsubscribed.append(channel)
        except Exception as e:
            logger.warning(f"Kanal obunasini tekshirishda xatolik ({channel}): {e}")
            
    return len(unsubscribed) == 0, unsubscribed

