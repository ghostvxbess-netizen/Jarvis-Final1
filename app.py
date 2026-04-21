“””
AI Assistant Backend — app.py
Разработано для проекта Сардарбека Курбаналиева
Стек: FastAPI + Uvicorn
“””

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ──────────────────────────────────────────────

# Инициализация приложения

# ──────────────────────────────────────────────

app = FastAPI(
title=“AI Assistant API”,
description=“Базовый бэкенд искусственного интеллекта”,
version=“0.1.0”,
)

app.add_middleware(
CORSMiddleware,
allow_origins=[”*”],          # В продакшене укажи конкретные домены
allow_credentials=True,
allow_methods=[”*”],
allow_headers=[”*”],
)

UPLOAD_DIR = Path(“uploads”)
UPLOAD_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────────

# Схемы данных

# ──────────────────────────────────────────────

class TextRequest(BaseModel):
message: str
language: Optional[str] = “ru”

class TextResponse(BaseModel):
reply: str
timestamp: str

class WeatherResponse(BaseModel):
city: str
temperature: float
description: str
humidity: int
wind_speed: float
timestamp: str

# ──────────────────────────────────────────────

# 1. Обработка текстовых запросов

# ──────────────────────────────────────────────

# Простой словарь ответов — замени на LLM-вызов (OpenAI, Anthropic и т.д.)

SIMPLE_RESPONSES: dict[str, str] = {
“привет”: “Привет! Я ваш ИИ-ассистент. Чем могу помочь?”,
“hello”: “Hello! How can I assist you today?”,
“как дела”: “Отлично, спасибо! Готов помогать.”,
“помощь”: “Я умею отвечать на вопросы, показывать погоду и обрабатывать файлы.”,
}

@app.post(”/api/chat”, response_model=TextResponse, tags=[“Текст”])
async def chat(request: TextRequest):
“””
Принимает текстовое сообщение и возвращает ответ ИИ.
Сейчас использует простой словарь; подключи LLM для расширения.
“””
lower_msg = request.message.lower().strip()
reply = SIMPLE_RESPONSES.get(
lower_msg,
f”Вы написали: «{request.message}». “
“Я пока учусь — скоро буду отвечать на любые вопросы!”
)
return TextResponse(reply=reply, timestamp=datetime.utcnow().isoformat())

# ──────────────────────────────────────────────

# 2. Погода (через Open-Meteo — бесплатно, без API-ключа)

# ──────────────────────────────────────────────

GEOCODE_URL = “https://geocoding-api.open-meteo.com/v1/search”
WEATHER_URL = “https://api.open-meteo.com/v1/forecast”

WMO_DESCRIPTIONS: dict[int, str] = {
0: “Ясно”, 1: “Преимущественно ясно”, 2: “Переменная облачность”,
3: “Пасмурно”, 45: “Туман”, 48: “Изморозь”,
51: “Лёгкая морось”, 53: “Умеренная морось”, 55: “Сильная морось”,
61: “Небольшой дождь”, 63: “Умеренный дождь”, 65: “Сильный дождь”,
71: “Небольшой снег”, 73: “Умеренный снег”, 75: “Сильный снег”,
80: “Ливень”, 81: “Умеренный ливень”, 82: “Сильный ливень”,
95: “Гроза”, 99: “Гроза с градом”,
}

@app.get(”/api/weather”, response_model=WeatherResponse, tags=[“Погода”])
async def get_weather(city: str = Query(…, description=“Название города”)):
“””
Возвращает текущую погоду для указанного города.
Использует бесплатный API Open-Meteo (без ключа).
“””
async with httpx.AsyncClient(timeout=10) as client:
# Геокодинг: город → координаты
geo_resp = await client.get(
GEOCODE_URL, params={“name”: city, “count”: 1, “language”: “ru”}
)
geo_data = geo_resp.json()
results = geo_data.get(“results”)
if not results:
raise HTTPException(status_code=404, detail=f”Город «{city}» не найден”)

```
    loc = results[0]
    lat, lon = loc["latitude"], loc["longitude"]
    city_name = loc.get("name", city)

    # Погода по координатам
    weather_resp = await client.get(
        WEATHER_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "hourly": "relativehumidity_2m",
            "timezone": "auto",
        },
    )
    w = weather_resp.json()
    current = w["current_weather"]
    humidity = w["hourly"]["relativehumidity_2m"][0]

return WeatherResponse(
    city=city_name,
    temperature=current["temperature"],
    description=WMO_DESCRIPTIONS.get(current["weathercode"], "Неизвестно"),
    humidity=humidity,
    wind_speed=current["windspeed"],
    timestamp=datetime.utcnow().isoformat(),
)
```

# ──────────────────────────────────────────────

# 3. Загрузка файлов

# ──────────────────────────────────────────────

ALLOWED_EXTENSIONS = {”.txt”, “.pdf”, “.png”, “.jpg”, “.jpeg”, “.csv”, “.json”}
MAX_FILE_SIZE_MB = 10

@app.post(”/api/upload”, tags=[“Файлы”])
async def upload_file(file: UploadFile = File(…)):
“””
Принимает файл, проверяет расширение и размер, сохраняет на диск.
“””
suffix = Path(file.filename).suffix.lower()
if suffix not in ALLOWED_EXTENSIONS:
raise HTTPException(
status_code=400,
detail=f”Тип файла не поддерживается. Разрешены: {’, ’.join(ALLOWED_EXTENSIONS)}”,
)

```
contents = await file.read()
if len(contents) > MAX_FILE_SIZE_MB * 1024 * 1024:
    raise HTTPException(status_code=413, detail=f"Файл превышает {MAX_FILE_SIZE_MB} МБ")

save_path = UPLOAD_DIR / f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
save_path.write_bytes(contents)

return {
    "filename": file.filename,
    "saved_as": save_path.name,
    "size_kb": round(len(contents) / 1024, 2),
    "timestamp": datetime.utcnow().isoformat(),
}
```

@app.get(”/api/files”, tags=[“Файлы”])
async def list_files():
“”“Возвращает список всех загруженных файлов.”””
files = [
{“name”: f.name, “size_kb”: round(f.stat().st_size / 1024, 2)}
for f in UPLOAD_DIR.iterdir()
if f.is_file()
]
return {“files”: files, “total”: len(files)}

# ──────────────────────────────────────────────

# 4. Интеграция с внешними сервисами

# ──────────────────────────────────────────────

@app.get(”/api/news”, tags=[“Интеграции”])
async def get_news(topic: str = Query(“technology”, description=“Тема новостей”)):
“””
Получает новости через NewsAPI.
Установи переменную окружения NEWS_API_KEY для работы.
Зарегистрируйся бесплатно на https://newsapi.org
“””
api_key = os.getenv(“NEWS_API_KEY”)
if not api_key:
return {“error”: “NEWS_API_KEY не задан. Добавь его в переменные окружения.”}

```
url = "https://newsapi.org/v2/everything"
async with httpx.AsyncClient(timeout=10) as client:
    resp = await client.get(
        url, params={"q": topic, "language": "ru", "pageSize": 5, "apiKey": api_key}
    )
    data = resp.json()

articles = [
    {"title": a["title"], "source": a["source"]["name"], "url": a["url"]}
    for a in data.get("articles", [])
]
return {"topic": topic, "articles": articles}
```

@app.get(”/api/translate”, tags=[“Интеграции”])
async def translate_text(
text: str = Query(…, description=“Текст для перевода”),
target_lang: str = Query(“en”, description=“Язык перевода (en, ru, de, fr…)”),
):
“””
Переводит текст через LibreTranslate (бесплатный, без ключа).
“””
url = “https://libretranslate.com/translate”
async with httpx.AsyncClient(timeout=15) as client:
resp = await client.post(
url,
json={“q”: text, “source”: “auto”, “target”: target_lang, “format”: “text”},
)
if resp.status_code != 200:
raise HTTPException(status_code=502, detail=“Ошибка сервиса перевода”)
result = resp.json()
return {“original”: text, “translated”: result.get(“translatedText”), “target_lang”: target_lang}

# ──────────────────────────────────────────────

# Healthcheck

# ──────────────────────────────────────────────

@app.get(”/”, tags=[“Система”])
async def root():
return {“status”: “ok”, “message”: “AI Assistant API работает!”, “version”: “0.1.0”}

# ──────────────────────────────────────────────

# Запуск напрямую: python app.py

# ──────────────────────────────────────────────

if **name** == “**main**”:
import uvicorn
uvicorn.run(“app:app”, host=“0.0.0.0”, port=8000, reload=True)
