FROM python:3.11-slim

# FFmpeg va tizim vositalarini o'rnatish
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Kutubxonalarni o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha fayllarini nusxalash
COPY . .

# Ma'lumotlar papkalarini yaratish
RUN mkdir -p data downloads

ENV PORT=10000
EXPOSE 10000

CMD ["python", "main.py"]

