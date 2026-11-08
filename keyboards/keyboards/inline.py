from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_search_results_keyboard(
    session_id: str,
    current_page: int,
    total_pages: int,
    page_items_count: int,
    start_index: int
) -> InlineKeyboardMarkup:
    """
    Qidiruv natijalari uchun sahifalash va yuklab olish tugmalari (10 tagacha).
    5 tadan 2 qatorda:
    [ 1 ] [ 2 ] [ 3 ] [ 4 ] [ 5 ]
    [ 6 ] [ 7 ] [ 8 ] [ 9 ] [ 10 ]
    [ ⬅️ Oldingi ] [ 1/3 ] [ Keyingi ➡️ ]
    [ ❌ Yopish ]
    """
    rows: List[List[InlineKeyboardButton]] = []

    # 1-qator (1 dan 5 gacha)
    row1 = []
    for i in range(min(5, page_items_count)):
        actual_index = start_index + i
        row1.append(
            InlineKeyboardButton(
                text=str(actual_index + 1),
                callback_data=f"dl:{session_id}:{actual_index}"
            )
        )
    if row1:
        rows.append(row1)

    # 2-qator (6 dan 10 gacha)
    if page_items_count > 5:
        row2 = []
        for i in range(5, page_items_count):
            actual_index = start_index + i
            row2.append(
                InlineKeyboardButton(
                    text=str(actual_index + 1),
                    callback_data=f"dl:{session_id}:{actual_index}"
                )
            )
        if row2:
            rows.append(row2)

    # Navigatsiya qatori
    nav_row = []
    if current_page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Oldingi",
                callback_data=f"pg:{session_id}:{current_page - 1}"
            )
        )

    nav_row.append(
        InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data="noop"
        )
    )

    if current_page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text="Keyingi ➡️",
                callback_data=f"pg:{session_id}:{current_page + 1}"
            )
        )
    rows.append(nav_row)

    # Yopish tugmasi
    rows.append([
        InlineKeyboardButton(text="❌ Yopish", callback_data="close_search")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_audio_action_keyboard(
    video_id: str,
    is_fav: bool = False,
    share_query: str = ""
) -> InlineKeyboardMarkup:
    """Musiqa ostidagi barcha amallar (Sevimli, Ulashish, Effektlar, Ringtone, Matn)."""
    fav_text = "💔 O'chirish" if is_fav else "❤️ Saqlash"
    rows = [
        [
            InlineKeyboardButton(text=fav_text, callback_data=f"fav:{video_id}"),
            InlineKeyboardButton(
                text="🔗 Do'stlarga ulashish",
                switch_inline_query=share_query[:30] if share_query else ""
            )
        ],
        [
            InlineKeyboardButton(text="🎛 Effektlar (8D, Bass)", callback_data=f"eff_menu:{video_id}"),
            InlineKeyboardButton(text="✂️ Ringtone (30s)", callback_data=f"make_ring:{video_id}"),
        ],
        [
            InlineKeyboardButton(text="📜 Qo'shiq matni (Lyrics)", callback_data=f"lyrics:{video_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_audio_effects_keyboard(target_id: str) -> InlineKeyboardMarkup:
    """Kengaytirilgan audio effektlar menyusi (8D, Bass, Konsert, Alvin, Robot)."""
    rows = [
        [
            InlineKeyboardButton(text="🎧 8D Audio", callback_data=f"fx:8d:{target_id}"),
            InlineKeyboardButton(text="🔊 Bass Boost", callback_data=f"fx:bass:{target_id}"),
        ],
        [
            InlineKeyboardButton(text="🏛 Konsert (Reverb)", callback_data=f"fx:concert:{target_id}"),
            InlineKeyboardButton(text="🌙 Slowed + Reverb", callback_data=f"fx:slowed:{target_id}"),
        ],
        [
            InlineKeyboardButton(text="🐿 Alvin (Ingichka)", callback_data=f"fx:chipmunk:{target_id}"),
            InlineKeyboardButton(text="🦁 Chuqur ovoz", callback_data=f"fx:deep:{target_id}"),
        ],
        [
            InlineKeyboardButton(text="⚡️ Tezlashtirilgan", callback_data=f"fx:speed:{target_id}"),
            InlineKeyboardButton(text="🤖 Robot ovozi", callback_data=f"fx:robot:{target_id}"),
        ],
        [
            InlineKeyboardButton(text="✂️ Ringtone (30s)", callback_data=f"make_ring:{target_id}"),
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"back_to_track:{target_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_video_action_keyboard(temp_file_id: str) -> InlineKeyboardMarkup:
    """
    Foydalanuvchi video yuborganda chiqadigan katalog:
    - Musiqani aniqlash (Shazam)
    - Dumaloq video (Teleskop)
    - MP3 qilib ajratish
    - Effektli MP3
    """
    rows = [
        [
            InlineKeyboardButton(text="🔍 Musiqani aniqlash (Shazam)", callback_data=f"v_shazam:{temp_file_id}"),
        ],
        [
            InlineKeyboardButton(text="⭕️ Dumaloq video (Teleskop)", callback_data=f"v_note:{temp_file_id}"),
            InlineKeyboardButton(text="🎧 MP3 formatda olish", callback_data=f"v_mp3:{temp_file_id}"),
        ],
        [
            InlineKeyboardButton(text="🔊 Bass Boost MP3", callback_data=f"v_fx:bass:{temp_file_id}"),
            InlineKeyboardButton(text="🎧 8D Audio MP3", callback_data=f"v_fx:8d:{temp_file_id}"),
        ],
        [
            InlineKeyboardButton(text="🏛 Konsert MP3", callback_data=f"v_fx:concert:{temp_file_id}"),
            InlineKeyboardButton(text="❌ Yopish", callback_data="close_search"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_referral_keyboard(bot_username: str, user_id: int) -> InlineKeyboardMarkup:
    """Referral ulashish tugmasi."""
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    share_text = f"🎵 Eng zo'r musiqalarni tez yuklab olish va 8D effektlar qo'shish boti: {ref_link}"
    share_url = f"https://t.me/share/url?url={ref_link}&text=🎵 Eng zo'r musiqaviy botga ulaning!"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Do'stlarga yuborish", url=share_url)],
            [InlineKeyboardButton(text="⭐️ Do'stlar reytingi (Top)", callback_data="ref_top")]
        ]
    )


def build_charts_keyboard(categories: Dict[str, Any], top_cached: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Trenddagi toifalar va top treklar tugmalari."""
    rows: List[List[InlineKeyboardButton]] = []

    cat_items = list(categories.items())
    for i in range(0, len(cat_items), 2):
        row = []
        key1, data1 = cat_items[i]
        row.append(InlineKeyboardButton(text=data1["title"], callback_data=f"chart:{key1}"))
        if i + 1 < len(cat_items):
            key2, data2 = cat_items[i + 1]
            row.append(InlineKeyboardButton(text=data2["title"], callback_data=f"chart:{key2}"))
        rows.append(row)

    if top_cached:
        rows.append([
            InlineKeyboardButton(text="🔝 Eng ko'p tinglanganlar (Top 10)", callback_data="chart:top_downloads")
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_favorites_keyboard(favorites: List[Dict[str, Any]], page: int = 1, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Sevimlilar ro'yxati tugmalari."""
    rows: List[List[InlineKeyboardButton]] = []

    for idx, fav in enumerate(favorites, 1):
        video_id = fav.get("video_id")
        title = fav.get("title", "Musiqa")[:30]
        rows.append([
            InlineKeyboardButton(text=f"▶️ {title}", callback_data=f"dl_id:{video_id}")
        ])

    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"favpage:{page - 1}"))
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"favpage:{page + 1}"))
        rows.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_sponsor_keyboard(channels: List[str]) -> InlineKeyboardMarkup:
    """Majburiy obuna kanallari tugmalari."""
    rows: List[List[InlineKeyboardButton]] = []
    for idx, channel in enumerate(channels, 1):
        clean_name = channel.lstrip("@")
        url = f"https://t.me/{clean_name}"
        rows.append([
            InlineKeyboardButton(text=f"➕ {idx}-kanalga a'zo bo'lish", url=url)
        ])
    rows.append([
        InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_admin_keyboard() -> InlineKeyboardMarkup:
    """Admin panel tugmalari."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 To'liq statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📢 Xabar tarqatish (Broadcast)", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_refresh")]
        ]
    )
