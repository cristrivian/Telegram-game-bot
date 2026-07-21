# Forzar compilación limpia - Imagen adjunta al mensaje de la oferta sin enlace
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
        "disable_web_page_preview": False,
    })


def send_photo(chat_id, photo_url, caption=None, parse_mode="Markdown"):
    payload = {"chat_id": chat_id, "photo": photo_url}
    if caption:
        payload["caption"] = caption
        payload["parse_mode"] = parse_mode
    return requests.post(f"{TELEGRAM_API}/sendPhoto", json=payload)


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
                        "content": "Eres un asistente experto en analizar ofertas de Telegram sobre videojuegos. Debes devolver ÚNICAMENTE un objeto JSON válido (sin formato markdown ni bloques de código) con estas claves exactas: title (nombre del producto limpio), pvp (precio original: si el texto lo indica, ponlo; si no lo indica, estima y pon el precio original de lanzamiento más probable que tuvo el juego cuando salió al mercado, por ejemplo 59.99 o 69.99 en lugar de 0), price (precio de oferta sin símbolos), link (enlace de compra principal, ignora youtube), store (tienda deducida), image_url (enlace directo a la imagen o carátula oficial del juego que aparezca en el texto, o vacío si no hay), description (detalle breve o cupón, o vacío si no hay), tagline (un título gancho corto y llamativo relacionado con el juego, en español, máximo 8 palabras, distinto del nombre del juego), game_description (una descripción breve y atractiva de qué trata el juego, en español, máximo 25 palabras), hashtags (un array de exactamente 3 o 4 hashtags en español o inglés relacionados específicamente con ese juego -género, saga, plataforma, etc-, cada uno empezando por # y sin espacios)."
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
            store = datos.get("store", "Tienda")
            image_url = datos.get("image_url", "")
            desc = datos.get("description", "")
            tagline = datos.get("tagline", "")
            game_desc = datos.get("game_description", "")

            # NUEVO: Intentar extraer imagen de la web (Amazon u otras) si Groq no la devuelve
            if (not image_url or not image_url.startswith("http")) and link.startswith("http"):
                try:
                    headers_web = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    r_web = requests.get(link, headers=headers_web, timeout=5)
                    # Buscamos la etiqueta og:image general
                    m_og = re.search(r'<meta[^>]*property=[\'"]og:image[\'"][^>]*content=[\'"](http[^\'"]+)[\'"]', r_web.text, re.IGNORECASE)
                    if m_og:
                        image_url = m_og.group(1)
                    else:
                        m_og2 = re.search(r'<meta[^>]*content=[\'"](http[^\'"]+)[\'"][^>]*property=[\'"]og:image[\'"]', r_web.text, re.IGNORECASE)
                        if m_og2:
                            image_url = m_og2.group(1)
                        elif "amazon" in link:
                            # Fallback específico para sacar la foto en alta resolución de Amazon
                            m_amz = re.search(r'"large":"(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"', r_web.text)
                            if m_amz:
                                image_url = m_amz.group(1)
                except Exception:
                    pass

            hashtags_raw = datos.get("hashtags", [])
            if isinstance(hashtags_raw, str):
                hashtags_raw = hashtags_raw.split()
            hashtags = [h if h.startswith("#") else f"#{h}" for h in hashtags_raw if h][:4]
            hashtags_line = " ".join(hashtags)

            # Inyección automática de link de afiliado para Instant Gaming (se queda interno por si lo usas más adelante, aunque no se imprima)
            if "instant-gaming.com" in link and "igr=" not in link:
                link += "?igr=gamer-a8c487" if "?" not in link else "&igr=gamer-a8c487"

            # Construimos el texto del mensaje (SIN EL ENLACE AL FINAL)
            mensaje_final = f"¡LA AVENTURA CONTINÚA: {title.upper()}! 🗡️✨\n"
            if tagline:
                mensaje_final += f"_{tagline}_\n"
            if game_desc:
                mensaje_final += f"{game_desc}\n"
            mensaje_final += "\n"

            if desc:
                mensaje_final += f"{desc}\n\n"

            mensaje_final += f"❌ **PVP:** {pvp}€\n"
            mensaje_final += f"✅ **Save On Games:** {price}€"

            if hashtags_line:
                mensaje_final += f"\n\n{hashtags_line}"

            res = None

            # Si logramos extraer la imagen, se manda como foto con el texto abajo.
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
                send_message(chat_id, "✅ **¡Procesado con imagen adjunta y publicado!**")
            else:
                err = res.json().get("description", "Error desconocido")
                send_message(chat_id, f"❌ Error de envío al canal: `{err}`")

        except Exception as e:
            send_message(chat_id, f"⚠️ **Error en el proceso:**\n`{str(e)}`")

    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
