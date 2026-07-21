import os
import json
import requests
import google.generativeai as genai
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = "-1004359686735"

# Configurar la API de la IA (Gemini)
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"]["text"]

        if not GEMINI_KEY:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                          json={"chat_id": chat_id, "text": "Falta la variable GEMINI_API_KEY en Render."})
            return "OK", 200

        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"""
            Analiza el siguiente mensaje de oferta de Telegram y extrae la información. 
            Devuelve ÚNICAMENTE un objeto JSON válido (sin etiquetas markdown, sin comillas invertidas) con estas claves exactas:
            - "title": Nombre del producto o juego de forma limpia.
            - "pvp": El precio original sin símbolos (ej: 372). Si no hay, pon "0".
            - "price": El precio de oferta sin símbolos (ej: 336).
            - "link": El enlace de compra principal (ignora enlaces a YouTube o reviews).
            - "store": Nombre de la tienda deducido del enlace (ej: AliExpress, Amazon, Instant Gaming, etc.).
            - "description": Extrae cualquier detalle importante muy breve, como "Envío desde España" o "Cupón: XXXX". Si no hay nada, déjalo vacío.
            
            Mensaje a analizar:
            {text}
            """
            
            response = model.generate_content(prompt)
            respuesta_ia = response.text.strip()
            
            if respuesta_ia.startswith("```json"):
                respuesta_ia = respuesta_ia[7:-3]
            elif respuesta_ia.startswith("```"):
                respuesta_ia = respuesta_ia[3:-3]
            
            datos = json.loads(respuesta_ia)
            
            title = datos.get("title", "CHOLLO GAMING")
            pvp = datos.get("pvp", "0")
            price = datos.get("price", "0")
            link = datos.get("link", "")
            store = datos.get("store", "Tienda")
            desc = datos.get("description", "")

            # Automatización del enlace de afiliado
            if "instant-gaming.com" in link and "igr=" not in link:
                link += "?igr=gamer-a8c487" if "?" not in link else "&igr=gamer-a8c487"

            mensaje_final = f"¡LA AVENTURA CONTINÚA: {title.upper()}! 🗡️✨\n"
            if desc:
                mensaje_final += f"{desc}\n\n"
            else:
                mensaje_final += "\n"
                
            mensaje_final += f"❌ **PVP:** {pvp}€\n"
            mensaje_final += f"✅ **Save On Games:** {price}€\n\n"
            mensaje_final += f"🔗 [Comprar en {store}]({link})"

            res = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={
                    "chat_id": CHANNEL_ID,
                    "text": mensaje_final,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False,
                }
            )

            if res.status_code == 200:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                              json={"chat_id": chat_id, "text": "✅ **¡Procesado con IA y publicado!**", "parse_mode": "Markdown"})
            else:
                err = res.json().get("description", "Error desconocido")
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                              json={"chat_id": chat_id, "text": f"❌ Error de envío: `{err}`", "parse_mode": "Markdown"})

        except Exception as e:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": f"⚠️ **Error procesando con la IA:**\n`{str(e)}`", "parse_mode": "Markdown"}
            )

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
