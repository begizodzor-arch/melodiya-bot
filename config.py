import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Admin IDs
admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in admin_ids_raw.split(",") if x.strip().isdigit()]

# Majburiy obuna kanallari (@username yoki -100xxx ID)
sponsor_channels_raw = os.getenv("SPONSOR_CHANNELS", "")
SPONSOR_CHANNELS = [x.strip() for x in sponsor_channels_raw.split(",") if x.strip()]

# Sozlamalar
MAX_DURATION_SECONDS = int(os.getenv("MAX_DURATION_SECONDS", "1200"))  # 20 min
RESULTS_PER_PAGE = int(os.getenv("RESULTS_PER_PAGE", "10"))

# Papkalar
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "melodiya.db"

import shutil

# FFmpeg yo'li (tizim ffmpeg yoki imageio_ffmpeg orqali)
if shutil.which("ffmpeg"):
    FFMPEG_PATH = "ffmpeg"
else:
    try:
        import imageio_ffmpeg
        FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG_PATH = "ffmpeg"

