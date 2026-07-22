# Forzar compilación limpia - Bloques estancos (Amazon y Steam devuelven enlace)
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
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        final_url = link
        if "amzn." in link or "t.co" in link:
            res = requests.head(link, headers=headers, allow_redirects=True, timeout=5)
            final_url = res.url

        asin_match = re.search(r'/(?:dp|gp/product|product)/([A-Z0-9]{10})', final_url, re.IGNORECASE)
        if not asin_match:
            asin_match = re.search(r'/([B0-9][A-Z0-9]{9})(?:[/?#]|$)', final_url, re.IGNORECASE)

        if asin_match:
            asin = asin_match.group(1).upper()
            return f"https://images-na.ssl-images-amazon.com/images/P/{asin}.01._SCLZZZZZZZ_.jpg"
    except Exception:
        pass
    return None


# ==========================================
# BLOQUE 2: FUNCIONES ALIEXPRESS
# ==========================================
def obtener_imagen_aliexpress(link):
    """Mejora la extracción de imagen de AliExpress buscando en metadatos y código interno."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
        }
        res = requests.get(link, headers=headers, allow_redirects=True, timeout=8)
        html = res.text
        
        m_og = re.search(r'<meta[^>]*property=[\'"]og:image[\'"][^>]*content=[\'"](http[^\'"]+)[\'"]', html, re.IGNORECASE)
        if m_og:
            return m_og.group(1)
            
        m_json = re.search(r'"imagePath":"(https://ae01\.alicdn\.com/kf/[^"]+)"', html)
        if m_json:
            return m_json.group(1)
            
        m_cdn = re.search(r'(https://ae01\.alicdn\.com/kf/[a-zA-Z0-9_-]+\.(?:jpg|png))', html)
        if m_cdn:
            return m_cdn.group(1)

    except Exception:
        pass
    return None


# ==========================================
# BLOQUE 3: FUNCIONES STEAM
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

            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {
                        "role": "system",
                        "content": "Eres un asistente experto en analizar ofertas de Telegram sobre videojuegos. Debes devolver ÚNICAMENTE un objeto JSON válido (sin formato markdown ni bloques de código) con estas claves exactas: title (nombre del producto limpio), pvp (precio original de lanzamiento. DEBE ser un NÚMERO, ej: 59.99 o 69.99. NUNCA uses palabras como 'indicado'. Si el texto no lo indica, inventa el precio de salida más realista en formato numérico), price (precio de oferta sin símbolos), link (enlace de compra principal, ignora youtube), store (tienda deducida), image_url (enlace directo a la imagen o carátula oficial del juego que aparezca en el texto, o vacío si no hay), description (Solo detalles técnicos RELEVANTES, códigos o cupones. OMITE y ELIMINA CUALQUIER palabra coloquial, ruido, saludos o palabras raras como 'berrako', déjalo vacío si no hay nada útil), tagline (un título gancho corto y llamativo relacionado con el juego, en español, máximo 8 palabras, distinto del nombre del juego), game_description (una descripción breve y atractiva de qué trata el juego, en español, máximo 25 palabras), hashtags (un array de exactamente 3 o 4 hashtags en español o inglés relacionados específicamente con ese juego, cada uno empezando por # y sin espacios)."
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

            title = datos.get("title", "CHOLLO GAMING")
            pvp = datos.get("pvp", "69.99")
            price = datos.get("price", "0")
            link = datos.get("link", "")
            image_url = datos.get("image_url", "")
            desc = datos.get("description", "")
            tagline = datos.get("tagline", "")
            game_desc = datos.get("game_description", "")

            # ==========================================
            # ENRUTADOR DE TIENDAS (Manejo de Imágenes)
            # ==========================================
            if "amazon" in link or "amzn" in link:
                img_amazon = obtener_imagen_amazon(link)
                if img_amazon:
                    image_url = img_amazon
            
            elif "aliexpress" in link or "ali." in link:
                img_ali = obtener_imagen_aliexpress(link)
                if img_ali:
                    image_url = img_ali
                    
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
            # CONSTRUCCIÓN DEL MENSAJE (Estructura Base)
            # ==========================================
            mensaje_final = f"¡LA AVENTURA CONTINÚA: {title.upper()}! 🗡️✨\n"
            if tagline:
                mensaje_final += f"_{tagline}_\n"
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
                # Bloque AMAZON: Ahora SÍ muestra el enlace
                mensaje_final += f"\n\n🔗 [Comprar en Amazon]({link})"
                
            elif "steampowered" in link or "steam" in link:
                # Bloque STEAM: Muestra el enlace
                mensaje_final += f"\n\n🔗 [Comprar en Steam]({link})"
                
            elif "aliexpress" in link or "ali." in link:
                # Bloque ALIEXPRESS: Se mantiene sin mostrar enlace
                pass 
            
            else:
                # TIENDAS GENÉRICAS: Si metes otra web, sí muestra enlace por defecto
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
