# Forzar compilación limpia - Extracción Amazon reforzada y Prompt sin cupones/ruido
import os
import json
import re
import requests
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = "-1004359686735"
GROQ_KEY = os.environ.get("GROQ_API_KEY")

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


# ==========================================
# BLOQUE 1: FUNCIONES AMAZON
# ==========================================
def obtener_imagen_amazon(link):
    """Obtiene la imagen de alta resolución de Amazon a través de su CDN usando el ASIN."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        final_url = link
        
        # Uso de GET con stream=True para seguir la redirección sin descargar todo el contenido
        if "amzn." in link or "t.co" in link or "bit.ly" in link:
            res = requests.get(link, headers=headers, allow_redirects=True, timeout=6, stream=True)
            final_url = res.url

        # Expresión regular ampliada para capturar el ASIN (10 caracteres alfanuméricos)
        asin_match = re.search(r'/(?:dp|gp/product|product|asin)/([A-Z0-9]{10})', final_url, re.IGNORECASE)
        if not asin_match:
            asin_match = re.search(r'[/=]([B0-9][A-Z0-9]{9})(?:[/?#&]|$)', final_url, re.IGNORECASE)

        if asin_match:
            asin = asin_match.group(1).upper()
            return f"https://images-na.ssl-images-amazon.com/images/P/{asin}.01._SCLZZZZZZZ_.jpg"
    except Exception:
        pass
    return None


# ==========================================
# BLOQUE 2: FUNCIONES STEAM
# ==========================================
def obtener_imagen_steam(link):
    """Extrae el ID del juego de la URL de Steam y obtiene la carátula oficial."""
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

        if not GROQ_KEY:
            send_message(chat_id, "Falta la variable GROQ_API_KEY en Render.")
            return "OK", 200

        try:
            url_groq = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_KEY}",
                "Content-Type": "application/json"
            }

            # PROMPT LIMPIO: Sin menciones a cupones ni ruido
            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {
                        "role": "system",
                        "content": "Eres un asistente experto en redactar ofertas irresistibles de videojuegos para un canal de Telegram. Debes devolver ÚNICAMENTE un objeto JSON válido (sin formato markdown) con estas claves: header (El título principal del mensaje, TODO EN MAYÚSCULAS. Debe ser un gancho muy llamativo, original y relacionado con la temática del juego, incluyendo el nombre del juego y 2 o 3 emojis al final. Ej: '¡OFERTAZO! FINAL FANTASY I-VI PARA SWITCH ⚔️🔮' o '¡PREPARA TU NAVE PARA LA AVENTURA CON ASSASSIN'S CREED IV! 🏴‍☠️⚓'), title (nombre del producto limpio), pvp (precio original de lanzamiento. DEBE ser NÚMERO. Si no lo indica, inventa el más realista), price (precio de oferta sin símbolos), link (enlace de compra principal), store (tienda deducida), image_url (enlace a imagen si aparece en el texto, o vacío), description (Detalles relevantes de la edición o versión del juego si los hay. Si no hay nada, déjalo vacío. OMITE cualquier saludo o palabra coloquial), game_description (Una descripción atractiva, comercial y épica de qué trata el juego, destacando sus puntos fuertes para incentivar la compra. Entre 30 y 45 palabras), hashtags (array de 3 o 4 hashtags, empezando por #)."
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                "response_format": {"type": "json_object"}
            }

            groq_req = requests.post(url_groq, json=payload, headers=headers)

            if groq_req.status_code != 200:
                raise Exception(f"Error HTTP Groq: {groq_req.text}")

            datos_groq = groq_req.json()
            respuesta_ia = datos_groq['choices'][0]['message']['content'].strip()

            datos = json.loads(respuesta_ia)

            header = datos.get("header", f"¡CHOLLO GAMING: {datos.get('title', 'OFERTA').upper()}! 🎮🔥")
            title = datos.get("title", "CHOLLO GAMING")
            pvp = datos.get("pvp", "69.99")
            price = datos.get("price", "0")
            link = datos.get("link", "")
            image_url = datos.get("image_url", "")
            desc = datos.get("description", "")
            game_desc = datos.get("game_description", "")

            # ==========================================
            # ENRUTADOR DE TIENDAS (Manejo de Imágenes)
            # ==========================================
            if "amazon" in link or "amzn" in link:
                img_amazon = obtener_imagen_amazon(link)
                if img_amazon:
                    image_url = img_amazon
                    
            elif "steampowered" in link or "steam" in link:
                img_steam = obtener_imagen_steam(link)
                if img_steam:
                    image_url = img_steam

            if "instant-gaming.com" in link and "igr=" not in link:
                link += "?igr=gamer-a8c487" if "?" not in link else "&igr=gamer-a8c487"

            hashtags_raw = datos.get("hashtags", [])
            if isinstance(hashtags_raw, str):
                hashtags_raw = hashtags_raw.split()
            hashtags = [h if h.startswith("#") else f"#{h}" for h in hashtags_raw if h][:4]
            hashtags_line = " ".join(hashtags)

            # ==========================================
            # CONSTRUCCIÓN DEL MENSAJE (Estructura Dinámica)
            # ==========================================
            mensaje_final = f"{header}\n"
            
            if game_desc:
                mensaje_final += f"{game_desc}\n\n"

            if desc and desc.lower() not in ["", "null", "none"]:
                mensaje_final += f"{desc}\n\n"

            mensaje_final += f"❌ **PVP:** {pvp}€\n"
            mensaje_final += f"✅ **Save On Games:** {price}€"

            # ==========================================
            # INSERCIÓN DE ENLACES (Bloques Estancos)
            # ==========================================
            if "amazon" in link or "amzn" in link:
                mensaje_final += f"\n\n🔗 [Comprar en Amazon]({link})"
                
            elif "steampowered" in link or "steam" in link:
                mensaje_final += f"\n\n🔗 [Comprar en Steam]({link})"
            
            else:
                if link:
                    mensaje_final += f"\n\n🔗 [Comprar aquí]({link})"

            # ==========================================
            # INSERCIÓN DE HASHTAGS
            # ==========================================
            if hashtags_line:
                mensaje_final += f"\n\n{hashtags_line}"

            res = None

            # Envío a Telegram
            if image_url and image_url.startswith("http"):
                caption = mensaje_final
                if len(caption) > 1024:
                    caption = caption[:1021] + "..."

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
