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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        headers = {"Content-Type": "application/json"}
        
        prompt = (
            f"Analiza este enlace de un videojuego: '{link}'. "
            f"Devuelve ÚNICAMENTE un objeto JSON con dos claves:\n"
            f"1. 'nombre': El nombre oficial, limpio y bien escrito del videojuego.\n"
            f"2. 'descripcion': Una descripción corta, emocionante y comercial (máximo 30 palabras) en español que explique de qué trata el juego y anime a comprarlo. Sin emojis ni saludos."
        )
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        
        res = requests.post(url, json=payload, headers=headers, timeout=8)
        if res.status_code == 200:
            datos = res.json()
            texto_json = datos["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(texto_json)
    except Exception:
        pass
        
    return {"nombre": "OFERTA GAMING", "descripcion": ""}


# ==========================================
# EXTRACTORES DE IMÁGENES
# ==========================================
def obtener_imagen_amazon(link):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        final_url = link
        if "amzn." in link or "t.co" in link or "bit.ly" in link:
            res = requests.get(link, headers=headers, allow_redirects=True, timeout=6, stream=True)
            final_url = res.url

        asin_match = re.search(r'/(?:dp|gp/product|product|asin)/([A-Z0-9]{10})', final_url, re.IGNORECASE)
        if not asin_match:
            asin_match = re.search(r'[/=]([B0-9][A-Z0-9]{9})(?:[/?#&]|$)', final_url, re.IGNORECASE)

        if asin_match:
            asin = asin_match.group(1).upper()
            return f"https://images-na.ssl-images-amazon.com/images/P/{asin}.01._SCLZZZZZZZ_.jpg"
    except Exception:
        pass
    return None


def obtener_imagen_steam(link):
    try:
        m_steam = re.search(r'/app/(\d+)', link)
        if m_steam:
            app_id = m_steam.group(1)
            return f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg"
    except Exception:
        pass
    return None


@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"]["text"]

        try:
            # 1. Extraer el enlace
            enlaces = re.findall(r'(https?://[^\s]+)', text)
            if not enlaces:
                send_message(chat_id, "⚠️ **Falta el enlace.** Envía los dos precios y el enlace del juego.")
                return "OK", 200
            
            link = enlaces[0]
            
            # 2. Extraer precios
            texto_sin_link = text.replace(link, '')
            numeros_encontrados = re.findall(r'\d+(?:[\.,]\d+)?', texto_sin_link)
            
            if len(numeros_encontrados) < 2:
                send_message(chat_id, "⚠️ **Faltan precios.** Envía el precio antiguo y el nuevo (ej: 59.99 14.99).")
                return "OK", 200

            # Convertir a flotantes
            p1 = float(numeros_encontrados[0].replace(',', '.'))
            p2 = float(numeros_encontrados[1].replace(',', '.'))

            # Asignar automáticamente el mayor como PVP y el menor como Oferta
            precio_antiguo = max(p1, p2)
            precio_nuevo = min(p1, p2)

            # 3. Calcular porcentaje de descuento
            descuento_str = ""
            if precio_antiguo > precio_nuevo:
                porcentaje = int(round(((precio_antiguo - precio_nuevo) / precio_antiguo) * 100))
                descuento_str = f" (-{porcentaje}%)"

            # 4. Obtener Nombre y Descripción desde Gemini pasando la URL
            info_gemini = obtener_info_juego_gemini(link)
            nombre = info_gemini.get("nombre", "OFERTA GAMING")
            game_desc = info_gemini.get("descripcion", "")

            # 5. Obtener imagen y procesar afiliados
            image_url = None
            if "instant-gaming.com" in link and "igr=" not in link:
                link += "?igr=gamer-a8c487" if "?" not in link else "&igr=gamer-a8c487"
                
            if "amazon" in link or "amzn" in link:
                image_url = obtener_imagen_amazon(link)
            elif "steampowered" in link or "steam" in link:
                image_url = obtener_imagen_steam(link)

            # 6. Montar mensaje final
            mensaje_final = f"🎮 **{nombre.upper()}**\n\n"
            
            if game_desc:
                mensaje_final += f"{game_desc}\n\n"
                
            mensaje_final += f"❌ Precio original: {precio_antiguo:g}€\n"
            mensaje_final += f"✅ **Save On Games:** {precio_nuevo:g}€{descuento_str}"

            if "amazon" in link or "amzn" in link:
                mensaje_final += f"\n\n🔗 [Comprar en Amazon]({link})"
            elif "steampowered" in link or "steam" in link:
                mensaje_final += f"\n\n🔗 [Comprar en Steam]({link})"
            else:
                mensaje_final += f"\n\n🔗 [Comprar aquí]({link})"

            # 7. Envío a Telegram
            res = None
            if image_url and image_url.startswith("http"):
                caption = mensaje_final if len(mensaje_final) <= 1024 else mensaje_final[:1021] + "..."
                res = send_photo(CHANNEL_ID, image_url, caption=caption)
                if res.status_code != 200:
                    res = send_message(CHANNEL_ID, mensaje_final)
            else:
                res = send_message(CHANNEL_ID, mensaje_final)

            if res.status_code == 200:
                send_message(chat_id, "✅ **¡Procesado y publicado correctamente!**")
            else:
                err = res.json().get("description", "Error desconocido")
                send_message(chat_id, f"❌ Error de envío al canal: `{err}`")

        except Exception as e:
            send_message(chat_id, f"⚠️ **Error en el proceso:**\n`{str(e)}`")

    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
