@echo off
chcp 65001 >nul
title 🎵 Melodiya Bot
echo.
echo  ============================================
echo    🎵  Melodiya Bot - Ishga tushirilmoqda...
echo  ============================================
echo.

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [XATO] Python topilmadi! Python 3.10+ o'rnating.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [XATO] .env fayli topilmadi!
    echo .env.example faylidan nusxa olib, token kiriting.
    pause
    exit /b 1
)

echo [OK] Kutubxonalar tekshirilmoqda...
pip install -r requirements.txt -q

echo.
echo [OK] Bot ishga tushmoqda... (To'xtatish uchun: Ctrl+C)
echo.
python main.py

echo.
echo Bot to'xtatildi.
pause

