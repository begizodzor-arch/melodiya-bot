import json
import logging
from typing import Optional, List, Dict, Any
import aiosqlite
from config import DB_PATH

logger = logging.getLogger(__name__)

async def init_db():
    """Ma'lumotlar bazasini yaratish va jadvallarni sozlash."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                referred_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Eski bazalarda referred_by ustuni bo'lmasa qo'shish
        try:
            await db.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        except Exception:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS cached_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT UNIQUE NOT NULL,
                file_id TEXT NOT NULL,
                title TEXT,
                performer TEXT,
                duration INTEGER,
                download_count INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                video_id TEXT NOT NULL,
                title TEXT,
                performer TEXT,
                duration INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, video_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS search_sessions (
                session_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                results_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS lyrics_cache (
                query TEXT PRIMARY KEY,
                lyrics TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS temp_media (
                media_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()
    logger.info("Ma'lumotlar bazasi to'liq tayyor!")

async def add_user(user_id: int, username: Optional[str], full_name: str, referred_by: Optional[int] = None):
    """Foydalanuvchini bazaga qo'shish yoki yangilash."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Agar yangi foydalanuvchi bo'lsa va referral mavjud bo'lsa
        async with db.execute("SELECT user_id, referred_by FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()

        if not row:
            # Yangi foydalanuvchi
            ref = referred_by if (referred_by and referred_by != user_id) else None
            await db.execute("""
                INSERT INTO users (user_id, username, full_name, referred_by, last_active)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, username, full_name, ref))
        else:
            await db.execute("""
                UPDATE users SET username = ?, full_name = ?, last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (username, full_name, user_id))

        await db.commit()

async def update_user_activity(user_id: int):
    """Foydalanuvchi faolligini yangilash."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()

async def get_user_count() -> int:
    """Jami foydalanuvchilar soni."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_all_users() -> List[int]:
    """Barcha foydalanuvchilar ID ro'yxati (xabar tarqatish uchun)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_referral_count(user_id: int) -> int:
    """Foydalanuvchi taklif qilgan do'stlar soni."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_cached_track(video_id: str) -> Optional[Dict[str, Any]]:
    """Telegram file_id keshdan qo'shiqni olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM cached_tracks WHERE video_id = ?", (video_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None

async def save_cached_track(
    video_id: str,
    file_id: str,
    title: str,
    performer: str,
    duration: int
):
    """Qo'shiqni tezkor keshga saqlash."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO cached_tracks (video_id, file_id, title, performer, duration, download_count)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(video_id) DO UPDATE SET
                file_id = excluded.file_id,
                download_count = download_count + 1
        """, (video_id, file_id, title, performer, duration))
        await db.commit()

async def increment_download_count(video_id: str):
    """Qo'shiq yuklanishlar sonini 1 taga oshirish."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE cached_tracks SET download_count = download_count + 1 WHERE video_id = ?",
            (video_id,)
        )
        await db.commit()

async def get_top_downloaded_tracks(limit: int = 10) -> List[Dict[str, Any]]:
    """Eng ko'p yuklab olingan qo'shiqlar (Top chart)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT video_id, title, performer, duration, download_count
            FROM cached_tracks
            ORDER BY download_count DESC
            LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def add_favorite(
    user_id: int,
    video_id: str,
    title: str,
    performer: str,
    duration: int
) -> bool:
    """Sevimlilarga qo'shish."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("""
                INSERT INTO favorites (user_id, video_id, title, performer, duration)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, video_id, title, performer, duration))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def remove_favorite(user_id: int, video_id: str) -> bool:
    """Sevimlilardan o'chirish."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            DELETE FROM favorites WHERE user_id = ? AND video_id = ?
        """, (user_id, video_id))
        await db.commit()
        return cursor.rowcount > 0

async def is_favorite(user_id: int, video_id: str) -> bool:
    """Qo'shiq foydalanuvchining sevimlilarida bormi tekshirish."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND video_id = ?",
            (user_id, video_id)
        ) as cursor:
            return await cursor.fetchone() is not None

async def get_favorites(user_id: int, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """Foydalanuvchining sevimlilar ro'yxati."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT video_id, title, performer, duration
            FROM favorites
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def save_search_session(session_id: str, query: str, results: List[Dict[str, Any]]):
    """Qidiruv natijalarini vaqtinchalik saqlash (sahifalash uchun)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO search_sessions (session_id, query, results_json)
            VALUES (?, ?, ?)
        """, (session_id, query, json.dumps(results, ensure_ascii=False)))
        await db.commit()

async def get_search_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Qidiruv sessiyasini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM search_sessions WHERE session_id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "session_id": row["session_id"],
                    "query": row["query"],
                    "results": json.loads(row["results_json"])
                }
    return None

async def cleanup_old_sessions():
    """Eski qidiruv sessiyalarini tozalash (24 soatdan oshgan)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            DELETE FROM search_sessions
            WHERE created_at < datetime('now', '-1 day')
        """)
        await db.commit()

async def get_cached_lyrics(query: str) -> Optional[str]:
    """Qo'shiq matnini keshdan olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT lyrics FROM lyrics_cache WHERE query = ?", (query.lower().strip(),)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def save_cached_lyrics(query: str, lyrics: str):
    """Qo'shiq matnini keshga saqlash."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO lyrics_cache (query, lyrics)
            VALUES (?, ?)
        """, (query.lower().strip(), lyrics))
        await db.commit()

async def save_temp_media(file_id: str, file_type: str = "media") -> str:
    """Telegram file_id uchun qisqa 8 belgili ID yaratish (Telegram 64-bayt limiti uchun)."""
    import uuid
    short_id = uuid.uuid4().hex[:8]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO temp_media (media_id, file_id, file_type)
            VALUES (?, ?, ?)
        """, (short_id, file_id, file_type))
        await db.commit()
    return short_id

async def get_temp_media(media_id: str) -> Optional[str]:
    """Qisqa ID orqali asl Telegram file_id ni olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT file_id FROM temp_media WHERE media_id = ?", (media_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
