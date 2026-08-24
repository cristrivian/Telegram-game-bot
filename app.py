import os
import re
import json
import requests
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = "-1004359686735"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text, parse_mode="Markdown"):
    return requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    })


def send_photo(chat_id, photo_url, caption=None, parse_mode="Markdown"):
    payload = {"chat_id": chat_id, "photo": photo_url}
    if caption:
        payload["caption"] = caption
        payload["parse_mode"] = parse_mode
    return requests.post(f"{TELEGRAM_API}/sendPhoto", json=payload)


def obtener_info_juego_gemini(link):
    """Gemini deduce el nombre del juego a partir de la URL y redacta la sinopsis."""
    if not GEMINI_KEY:
        return {"nombre": "CHOLLO GAMING", "descripcion": ""}
    
    try:
        # URL ACTUALIZADA a v1 y gemini-1.5-flash-latest para solucionar el error 404
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_KEY}"
        headers = {"Content-Type": "application/json"}
        
        prompt = (
            f"Analiza este enlace de un videojuego: '{link}'. "
            f"Devuelve ÚNICAMENTE un objeto JSON válido con dos claves:\n"
            f"1. 'nombre': El nombre oficial y limpio del videojuego.\n"
            f"2. 'descripcion': Una descripción comercial y emocionante (máximo 30 palabras) en español que explique de qué trata el juego. Sin emojis."
        )
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        # Aumentamos el timeout a 15 segundos por si la API de Google va lenta
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if res.status_code == 200:
            datos = res.json()
            texto_json = datos["candidates"][0]["content"]["parts"][0]["text"]
            
            # Limpiador mágico: Quita las comillas raras o bloques markdown de Gemini
            texto_limpio = texto_json.replace("```json", "").replace("
