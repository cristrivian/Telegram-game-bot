import os
import requests
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = "-1004359686735"


@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
  data = request.get_json()

  if "message" in data and "text" in data["message"]:
    chat_id = data["message"]["chat"]["id"]
    text = data["message"]["text"]

    try:
      parts = [p.strip() for p in text.split("|")]

      if len(parts) >= 5:
        title = parts[0]
        pvp = parts[1]
        price = parts[2]
        link = parts[3]
        store = parts[4]

        # Comprobar si la 6ª posición es una URL de imagen
        image_url = None
        desc = "¡Hazte con él ahora a este precio de derribo!"

        if len(parts) > 5:
          if parts[5].startswith("http://") or parts[5].startswith("https://"):
            image_url = parts[5]
            if len(parts) > 6:
              desc = parts[6]
          else:
            desc = parts[5]

        # Plantilla formateada en Markdown
        mensaje = f"""¡LA AVENTURA CONTINÚA: {title.upper()}! 🗡️✨

{desc}

❌ **PVP:** {pvp}€
✅ **Save On Games:** {price}€

🔗 [Comprar en {store}]({link})"""

        # Enviar con foto si hay imagen URL, o solo texto si no la hay
        if image_url:
          url_api = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
          payload_channel = {
              "chat_id": CHANNEL_ID,
              "photo": image_url,
              "caption": mensaje,
              "parse_mode": "Markdown",
          }
        else:
          url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
          payload_channel = {
              "chat_id": CHANNEL_ID,
              "text": mensaje,
              "parse_mode": "Markdown",
              "disable_web_page_preview": False,
          }

        res = requests.post(url_api, json=payload_channel)

        # Confirmación al chat privado
        url_reply = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        if res.status_code == 200:
          requests.post(
              url_reply,
              json={
                  "chat_id": chat_id,
                  "text": "✅ **¡Publicado con éxito en el canal!**",
                  "parse_mode": "Markdown",
              },
          )
        else:
          err_msg = res.json().get("description", "Error desconocido")
          requests.post(
              url_reply,
              json={
                  "chat_id": chat_id,
                  "text": f"❌ **Error:** `{err_msg}`",
                  "parse_mode": "Markdown",
              },
          )

      else:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": (
                    "⚠️ **Formato:** `Título | PVP | Oferta | Link | Tienda |"
                    " [URL_Imagen] | [Descripción]`"
                ),
                "parse_mode": "Markdown",
            },
        )

    except Exception as e:
      print(f"Error: {e}")

  return "OK", 200


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
