import os
import requests
from flask import Flask, request

app = Flask(__name__)

# Configuración del bot
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = "-1004359686735"  # Tu canal privado


@app.route(f"/{TOKEN}", methods=["POST"])
def receive_message():
  update = request.get_json()

  if "message" in update and "text" in update["message"]:
    chat_id = update["message"]["chat"]["id"]
    text = update["message"]["text"]

    try:
      # Separar el mensaje enviado por '|'
      parts = [p.strip() for p in text.split("|")]

      if len(parts) >= 5:
        game_title = parts[0]
        pvp = parts[1]
        price = parts[2]
        link = parts[3]
        store = parts[4]

        # Si pasas un sexto elemento, se usa como texto/descripción personalizada.
        # Si no lo pasas, usa una frase predeterminada.
        description = (
            parts[5]
            if len(parts) > 5
            else "¡Hazte con él ahora a este precio de derribo!"
        )

        # Construir la plantilla formateada
        formatted_message = f"""¡LA AVENTURA CONTINÚA: {game_title.upper()}! 🗡️✨
{description}

❌ PVP: {pvp}€

✅ Save On Games: {price}€

🔗 {link}
📍 {store}"""

        # 1. Enviar el mensaje formateado al canal
        url_send = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload_channel = {
            "chat_id": CHANNEL_ID,
            "text": formatted_message,
            "disable_web_page_preview": False,
        }
        res = requests.post(url_send, json=payload_channel)

        # 2. Responder al chat privado confirmando el estado del envío
        if res.status_code == 200:
          payload_user = {
              "chat_id": chat_id,
              "text": (
                  "✅ **¡Publicado con éxito en el canal!**\n\n"
                  + formatted_message
              ),
              "parse_mode": "Markdown",
          }
          requests.post(url_send, json=payload_user)
        else:
          err_msg = res.json().get("description", "Error desconocido")
          payload_user = {
              "chat_id": chat_id,
              "text": f"❌ **Error al publicar en el canal:**\n`{err_msg}`",
              "parse_mode": "Markdown",
          }
          requests.post(url_send, json=payload_user)

      else:
        # Aviso en caso de formato incorrecto
        payload_user = {
            "chat_id": chat_id,
            "text": (
                "⚠️ **Formato incorrecto.**\n\nDebes enviar:\n`Título | PVP |"
                " Oferta | Link | Tienda`\n\n*(Opcional: añade `| Descripción`"
                " al final)*"
            ),
            "parse_mode": "Markdown",
        }
        requests.post(url_send, json=payload_user)

    except Exception as e:
      print(f"Error procesando el mensaje: {e}")

  return "OK", 200


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

