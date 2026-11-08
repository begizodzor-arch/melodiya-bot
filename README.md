# 🎵 Melodiya Bot — Professional Musiqaviy Telegram Bot

Telegram uchun ultra-tezkor va to'liq funksiyali musiqaviy bot (Tarona va VK Music botlari uslubida). 
YouTube, TikTok, Instagram Reels-dan musiqa yuklash, ovozli xabar yoki videodan Shazam orqali qo'shiq topish, 8D/Bass effektlar qo'shish, 30s ringtone qirqish va teleskop (dumaloq video) yaratish imkoniyatlariga ega.

---

## ✨ Imkoniyatlar ro'yxati

| Bo'lim | Funksiya | Tavsif |
|---|---|---|
| 🔍 **Qidiruv** | 10 ta namuna | Toza va tezkor qidiruv, sahifalash bilan (ortiqcha "kuting" xabarisiz) |
| ⚡️ **Tezkor yuklash** | Android Extractor | 2-4 soniyada MP3 formatida yuqori sifatda yuklab yuborish |
| 💾 **Kesh tizimi** | Instant send | Bir marta yuklangan qo'shiqlar bazada saqlanadi va keyingi safar 0.5s da yuboriladi |
| ✂️ **Ringtone** | 30 soniyalik gudok | Musiqadan silliq boshlanib-tugaydigan (fade) telefon qo'ng'iroq ohangini kesish |
| 📜 **Lyrics** | Qo'shiq matnlari | Qo'shiq so'zlarini bitta tugma bilan topib berish |
| 📱 **Ijtimoiy tarmoqlar**| TikTok & Reels | TikTok va Instagram Reels linklaridan audioni MP3 qilib ajratib olish |
| 🎙 **Shazam** | Ovozli xabar / Dumaloq video | Ovoz yoki videoni eshitib, qaysi qo'shiqligini topish |
| ⭕️ **Teleskop** | Dumaloq video | Istalgan videoni Telegram dumaloq video (Video Note) formatiga o'tkazish |
| 🎛 **Effektlar** | 8D / Bass / Konsert / Alvin | 8D Audio, Bass Boost, Konsert (Reverb), Slowed, Nightcore, Alvin, Robot |
| 👥 **Referral** | Do'stlarni taklif qilish | Shaxsiy taklif havolasi orqali bot auditoriyasini virusli ko'paytirish |
| 🔥 **Trendlar** | O'zbek & Jahon xitlari | Eng so'nggi xit taronalar katalogi |
| ⭐️ **Sevimlilar** | Shaxsiy pleylist | Yoqqan taronalarni saqlash va tez tinglash |
| 📣 **Inline Mode** | `@melodiyauz_bot` | Istalgan chatda `@melodiyauz_bot qo'shiq` deb yozib to'g'ridan yuborish |
| 👑 **Admin Panel** | Statistika & Broadcast | Barcha foydalanuvchilarga xabar tarqatish, to'liq hisobot |

---

## 🚀 24/7 Serverga o'rnatish (Linux VPS)

Serveringiz (Ubuntu 22.04 / Debian) bo'lsa, botni 24/7 rejimda ishga tushirish **1 ta buyruq** bilan amalga oshadi:

```bash
# 1. Loyihani serverga yuklang
git clone <sizning_repoyingiz> melodiya_bot
cd melodiya_bot

# 2. .env fayliga bot token va ID ni kiriting
nano .env

# 3. Avtomatik o'rnatish skriptini ishga tushiring
chmod +x deploy.sh
./deploy.sh
```

Docker container avtomatik tarzda yaratiladi va bot **24/7 uzluksiz** ishlaydi (`restart: unless-stopped`).

* **Bot holatini ko'rish:** `docker compose ps`
* **Loglarni jonli ko'rish:** `docker compose logs -f`
* **Qayta ishga tushirish:** `docker compose restart`

---

## 💻 Kompyuterda ishga tushirish (Windows)

1. `c:\soft\Melodiya bot\.env` faylini ochib, BotFather bergan tokenni kiriting.
2. Oddiy oynada ishlatish: **`run.bat`** faylini ikki marta bosing.
3. Fonda (yashirin oynasiz) ishlatish: **`start_hidden.vbs`** faylini bosing.

---

## 📁 Loyiha arxitekturasi

```
Melodiya bot/
├── main.py                  # Bot kirish nuqtasi va hodisalar dispetcheri
├── config.py                # Konfiguratsiya va tizim yo'llari
├── requirements.txt         # Kerakli Python kutubxonalari
├── Dockerfile               # 24/7 Linux server konteyneri
├── docker-compose.yml       # Docker Compose sozlamalari
├── deploy.sh                # 1-klikda VPS serverga o'rnatish skripti
├── run.bat                  # Windows konsol ishga tushirgich
├── start_hidden.vbs         # Windows yashirin fon ishga tushirgich
│
├── database/                # SQLite asinxron ma'lumotlar bazasi
│   └── db.py                # Foydalanuvchilar, kesh, sevimlilar, referral, lyrics
│
├── handlers/                # Telegram buyruqlari va routerlari
│   ├── common.py            # /start, /help, referral tizimi
│   ├── search.py            # 10 ta namunali ultra-tez qidiruv
│   ├── download.py          # YouTube, TikTok, Instagram yuklovchi
│   ├── media_actions.py     # Video katalogi, 8D/Bass effektlar, Ringtone, Lyrics
│   ├── audio_recognition.py # Shazam ovoz aniqlagich
│   ├── charts.py            # Trenddagi xitlar
│   ├── favorites.py         # Sevimlilar ro'yxati
│   ├── inline_mode.py       # Inline audio qidiruv
│   └── admin.py             # Admin panel va xabar tarqatish
│
├── services/                # Asosiy biznes logika va qayta ishlovchilar
│   ├── music_downloader.py  # yt-dlp tezkor Android extractor
│   ├── media_processor.py   # FFmpeg 8D, Bass, Teleskop, Ringtone filtrlari
│   ├── shazam_service.py    # Shazamio musiqa identifikatsiyasi
│   ├── lyrics_service.py    # Qo'shiq matnlarini olish
│   ├── social_service.py    # TikTok va Instagram Reels yuklovchi
│   └── chart_service.py     # Trend toifalari
│
├── keyboards/               # Interaktiv tugmalar
│   ├── reply.py             # Pastki doimiy menyu
│   └── inline.py            # 10 talik qidiruv, effektlar, ringtone, referral
│
├── middlewares/             # Filtrlar va oraliq qatlamlar
│   ├── user_tracking.py     # Har bir foydalanuvchini avtomatik bazaga kiritish
│   └── rate_limit.py        # Spam va ortiqcha yuklamalardan himoya
│
└── utils/                   # Yordamchi vositalar
    └── helpers.py           # Matn tozalash, formatlash, obuna tekshirish
```
