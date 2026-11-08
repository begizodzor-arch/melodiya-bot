#!/usr/bin/env bash
# ==============================================================================
# Melodiya Bot - Linux VPS 1-Click Server O'rnatish Skripti (Ubuntu / Debian)
# ==============================================================================

set -e

echo "🎵 Melodiya Bot - Server sozlash boshlandi..."

# 1. Tizim paketlarini yangilash
sudo apt-get update -y
sudo apt-get install -y curl git ffmpeg python3 python3-pip python3-venv

# 2. Docker va Docker Compose o'rnatish (agar o'rnatilmagan bo'lsa)
if ! command -v docker &> /dev/null; then
    echo "🐳 Docker o'rnatilmoqda..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "🐳 Docker Compose plagin o'rnatilmoqda..."
    sudo apt-get install -y docker-compose-plugin || sudo apt-get install -y docker-compose
fi

# 3. Docker containerini ishga tushirish
echo "🚀 Bot ishga tushirilmoqda..."
if docker compose version &> /dev/null; then
    docker compose up -d --build
else
    docker-compose up -d --build
fi

echo "✅ Melodiya Bot muvaffaqiyatli 24/7 rejimda ishga tushdi!"
echo "Statusni ko'rish uchun: docker compose ps"
echo "Loglarni ko'rish uchun: docker compose logs -f"

