import os
import json
import requests
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = "-1004359686735"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

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
            # Petición directa usando la versión v1 y gemini-1.5-flash
            prompt = f"""
            Analiza el siguiente mensaje de oferta y extrae la información. 
            Devuelve ÚNICAMENTE un objeto JSON válido (sin formato markdown, sin comillas invertidas) con estas claves exactas:
            - "title": Nombre del producto.
            - "pvp": Precio original sin símbolos. Si no hay, pon "0".
            - "price": Precio de oferta sin símbolos.
            - "link": Enlace de compra principal (ignora reviews/YouTube).
            - "store": Nombre de la tienda (AliExpress, Amazon, etc.).
            - "description": Cualquier detalle clave muy breve (envío, cupón). Vacío si no hay.
            
            Mensaje:
            {text}
            """
            
            url_gemini = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
            gemini_payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            
            gemini_req = requests.post(url_gemini, json=gemini_payload)
            
            if gemini_req.status_code != 200:
                raise Exception(f"Error HTTP API: {gemini_req.text}")
            
            datos_gemini = gemini_req.json()
            try:
                respuesta_ia = datos_gemini['candidates'][0]['content']['parts'][0]['text'].strip()
            except KeyError:
                raise Exception(f"Gemini no devolvió texto válido: {datos_gemini}")
            
            # Limpieza del texto por si la IA añade etiquetas Markdown
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

            # Inyección automática de link de afiliado para Instant Gaming
            if "instant-gaming.com" in link and "igr=" not in link:
                link += "?igr=gamer-a8c487" if "?" not in link else "&igr=gamer-a8c487"

            # Construimos el mensaje de Telegram
            mensaje_final = f"¡LA AVENTURA CONTINÚA: {title.upper()}! 🗡️✨\n"
            if desc:
                mensaje_final += f"{desc}\n\n"
            else:
                mensaje_final += "\n"
                
            mensaje_final += f"❌ **PVP:** {pvp}€\n"
            mensaje_final += f"✅ **Save On Games:** {price}€\n\n"
            mensaje_final += f"🔗 [Comprar en {store}]({link})"

            # Publicar en el canal privado
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
                              json={"chat_id": chat_id, "text": f"❌ Error de envío al canal: `{err}`", "parse_mode": "Markdown"})

        except Exception as e:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": f"⚠️ **Error en el proceso:**\n`{str(e)}`", "parse_mode": "Markdown"}
            )

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
