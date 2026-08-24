import os
import re
import urllib.parse
import requests
import time
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = "-1004359686735"

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
# EXTRACTOR DE NOMBRES DESDE LA URL
# ==========================================
def extraer_nombre_url(link):
    try:
        parsed = urllib.parse.urlparse(link)
        path = urllib.parse.unquote(parsed.path) 
        
        if "steampowered" in link or "steam" in link:
            match = re.search(r'/app/\d+/([^/]+)', path)
            if match:
                return match.group(1).replace('_', ' ').upper()
                
        if "instant-gaming" in link:
            match = re.search(r'\d+-comprar-(?:juego-)?([^/]+)', path)
            if match:
                return match.group(1).replace('-', ' ').upper()
                
        if "amazon" in link or "amzn" in link:
            partes = [p for p in path.split('/') if p]
            if partes and "dp" not in partes[0] and len(partes[0]) > 5:
                return partes[0].replace('-', ' ').upper()

        partes = [p for p in path.split('/') if p]
        if partes:
            for p in reversed(partes):
                if len(p) > 4 and not re.match(r'^[A-Z0-9]{10}$', p):
                    return re.sub(r'[-_]', ' ', p).upper()
    except Exception:
        pass
    return "CHOLLO GAMING"


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

        # Dividimos el mensaje completo en bloques usando las líneas en blanco
        bloques = re.split(r'\n\s*\n', text.strip())
        
        ofertas_procesadas = 0
        errores = []

        for i, bloque in enumerate(bloques, 1):
            if not bloque.strip():
                continue

            try:
                # 1. Extraer el enlace de este bloque en concreto
                enlaces = re.findall(r'(https?://[^\s]+)', bloque)
                if not enlaces:
                    continue  # Si escribes texto normal sin enlace, lo ignora
                
                link = enlaces[0]
                
                # 2. Extraer precios del bloque
                texto_sin_link = bloque.replace(link, '')
                numeros_encontrados = re.findall(r'\d+(?:[\.,]\d+)?', texto_sin_link)
                
                if len(numeros_encontrados) < 2:
                    errores.append(f"⚠️ Oferta {i}: Faltan precios para el enlace {link}")
                    continue

                p1 = float(numeros_encontrados[0].replace(',', '.'))
                p2 = float(numeros_encontrados[1].replace(',', '.'))

                precio_antiguo = max(p1, p2)
                precio_nuevo = min(p1, p2)

                # 3. Calcular descuento
                descuento_str = ""
                if precio_antiguo > precio_nuevo:
                    porcentaje = int(round(((precio_antiguo - precio_nuevo) / precio_antiguo) * 100))
                    descuento_str = f" (-{porcentaje}%)"

                # 4. Nombre
                nombre = extraer_nombre_url(link)

                # 5. Imagen y afiliados
                image_url = None
                if "instant-gaming.com" in link and "igr=" not in link:
                    link += "?igr=gamer-a8c487" if "?" not in link else "&igr=gamer-a8c487"
                    
                if "amazon" in link or "amzn" in link:
                    image_url = obtener_imagen_amazon(link)
                elif "steampowered" in link or "steam" in link:
                    image_url = obtener_imagen_steam(link)

                # 6. Mensaje final
                mensaje_final = f"🎮 **{nombre}**\n\n"
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
                    ofertas_procesadas += 1
                else:
                    err = res.json().get("description", "Error desconocido")
                    errores.append(f"❌ Error enviando oferta {i}: `{err}`")

                # Pausa de medio segundo para no saturar a Telegram enviando 10 fotos a la vez
                time.sleep(0.5)

            except Exception as e:
                errores.append(f"⚠️ Error procesando oferta {i}:\n`{str(e)}`")

        # 8. Resumen final para ti en el bot privado
        if ofertas_procesadas > 0:
            msg_exito = f"✅ **¡{ofertas_procesadas} ofertas publicadas correctamente!**"
            send_message(chat_id, msg_exito)
        
        if errores:
            msg_error = "⚠️ **Resumen de problemas:**\n" + "\n".join(errores)
            send_message(chat_id, msg_error)
            
        # Si el mensaje no tenía enlaces, avisamos
        if ofertas_procesadas == 0 and not errores:
            send_message(chat_id, "🤔 No encontré ninguna oferta válida con enlaces en ese mensaje.")

    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
