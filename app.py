# Corrección de variable
import os
import json
import requests
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = "-1004359686735"
GROQ_KEY = os.environ.get("GROQ_API_KEY")

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"]["text"]

        if not GROQ_KEY:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                          json={"chat_id": chat_id, "text": "Falta la variable GROQ_API_KEY en Render."})
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
                        "content": "Eres un asistente experto en analizar ofertas de Telegram. Debes devolver ÚNICAMENTE un objeto JSON válido (sin formato markdown ni bloques de código) con estas claves exactas: title (nombre del producto limpio), pvp (precio original sin símbolos, o '0'), price (precio de oferta sin símbolos), link (enlace de compra principal, ignora youtube), store (tienda deducida), image_url (enlace directo a la imagen o carátula oficial del juego que aparezca en el texto, o vacío si no hay), description (detalle breve o cupón, o vacío si no hay)."
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
            pvp = datos.get("pvp", "0")
            price = datos.get("price", "0")
            link = datos.get("link", "")
            store = datos.get("store", "Tienda")
            image_url = datos.get("image_url", "")
            desc = datos.get("description", "")

            # Inyección automática de link de afiliado para Instant Gaming
            if "instant-gaming.com" in link and "igr=" not in link:
                link += "?igr=gamer-a8c487" if "?" not in link else "&igr=gamer-a8c487"

            # Construimos el texto del mensaje
            mensaje_final = f"¡LA AVENTURA CONTINÚA: {title.upper()}! 🗡️✨\n"
            if desc:
                mensaje_final += f"{desc}\n\n"
            else:
                mensaje_final += "\n"
                
            mensaje_final += f"❌ **PVP:** {pvp}€\n"
            mensaje_final += f"✅ **Save On Games:** {price}€\n\n"
            mensaje_final += f"🔗 [Comprar en {store}]({link})"

            # Si la IA encontró una imagen del juego, la enviamos primero al canal
            if image_url and image_url.startswith("http"):
                requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                    json={
                        "chat_id": CHANNEL_ID,
                        "photo": image_url
                    }
                )

            # A continuación, enviamos el texto de la oferta
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
                              json={"chat_id": chat_id, "text": "✅ **¡Imagen y oferta publicadas con éxito!**", "parse_mode": "Markdown"})
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
