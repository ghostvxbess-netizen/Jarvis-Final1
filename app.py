import os
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq

# --- Инициализация ---
app = FastAPI(
    title="AI Assistant API",
    description="Backend AI System for Sardarbek Kurbanaliev",
    version="1.0.0",
)

# CORS (Разрешаем подключение фронтенда)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# --- Схемы данных ---
class TextRequest(BaseModel):
    message: str
    user_id: Optional[str] = "guest"

class TextResponse(BaseModel):
    reply: str
    timestamp: str

class WeatherResponse(BaseModel):
    city: str
    temperature: float
    description: str
    timestamp: str

# --- 1. Реальный Интеллект (Groq) ---
@app.post("/api/chat", response_model=TextResponse, tags=["Интеллект"])
async def chat(request: TextRequest):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY не установлен в системе.")

    try:
        client = Groq(api_key=api_key)
        
        # Настройка личности ИИ
        system_msg = (
            "Ты — мощный Искусственный Интеллект. Твой создатель — Сардарбек Курбаналиев. "
            "Будь лаконичным, умным и профессиональным. Сейчас ты общаешься в режиме API."
        )

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": request.message}
            ],
            temperature=0.7
        )
        
        reply = completion.choices[0].message.content
        return TextResponse(reply=reply, timestamp=datetime.utcnow().isoformat())
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Error: {str(e)}")

# --- 2. Погода (Open-Meteo) ---
WMO_CODES = {0: "Ясно", 1: "Ясно", 2: "Облачно", 3: "Пасмурно", 45: "Туман", 61: "Дождь", 95: "Гроза"}

@app.get("/api/weather", response_model=WeatherResponse, tags=["Инструменты"])
async def get_weather(city: str = Query(..., description="Город")):
    async with httpx.AsyncClient(timeout=10) as client:
        # Геокодинг
        geo = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search", 
            params={"name": city, "count": 1, "language": "ru"}
        )
        if not geo.json().get("results"):
            raise HTTPException(status_code=404, detail="Город не найден")
        
        loc = geo.json()["results"][0]
        
        # Погода
        w_resp = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": loc["latitude"], "longitude": loc["longitude"], "current_weather": True}
        )
        curr = w_resp.json()["current_weather"]
        
        return WeatherResponse(
            city=loc["name"],
            temperature=curr["temperature"],
            description=WMO_CODES.get(curr["weathercode"], "Неизвестно"),
            timestamp=datetime.utcnow().isoformat()
        )

# --- 3. Файловая Система ---
@app.post("/api/upload", tags=["Файлы"])
async def upload_file(file: UploadFile = File(...)):
    # Генерируем безопасное имя
    file_id = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f"{file_id}_{file.filename}"
    save_path = UPLOAD_DIR / filename
    
    with save_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "status": "success",
        "filename": file.filename,
        "saved_path": str(save_path),
        "size_kb": round(save_path.stat().st_size / 1024, 2)
    }

@app.get("/api/files", tags=["Файлы"])
async def list_files():
    files = [{"name": f.name, "size": f.stat().st_size} for f in UPLOAD_DIR.iterdir() if f.is_file()]
    return {"files": files}

# --- Системные эндпоинты ---
@app.get("/", tags=["Система"])
async def root():
    return {"status": "online", "owner": "Sardarbek", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    # Запуск: python app.py
    uvicorn.run(app, host="0.0.0.0", port=8000)
