import os
import requests
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = (
    "@tu_canal_de_telegram"  # Pon aquí el identificador o @nombre de tu canal
)


@app.route(f"/{TOKEN}", methods=["POST"])
def receive_message():
  update = request.get_json()

  if "message" in update and "text" in update["message"]:
    text = update["message"]["text"]

    try:
      # Formato esperado: Título | PVP | Precio Oferta | Enlace | Tienda
      parts = [p.strip() for p in text.split("|")]
      if len(parts) == 5:
        game_title, pvp, price, link, store = parts

        formatted_message = f"""¡LA AVENTURA CONTINÚA: {game_title.upper()}! 🗡️✨
Cloud y sus aliados regresan en esta segunda parte de la trilogía que redefine un clásico absoluto. Explora un mundo abierto vastísimo, vive momentos legendarios con una calidad gráfica espectacular y profundiza en una historia que te atrapará desde el primer segundo. ¡Hazte con él ahora a este precio de derribo!

❌ PVP: {pvp}€

✅ Save On Games: {price}€

🔗 {link}
📍 {store}"""

        # Enviar mensaje formateado al canal de Telegram
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL_ID,
            "text": formatted_message,
            "disable_web_page_preview": False,
        }
        requests.post(url, json=payload)

    except Exception as e:
      print(f"Error procesando el mensaje: {e}")

  return "OK", 200


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
