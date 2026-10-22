import os
import telebot
from flask import Flask, abort, request
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

# Ambil TOKEN dari Environment Variables Render (TELEGRAM_TOKEN)
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
  raise ValueError("TELEGRAM_TOKEN tidak ditetapkan dalam environment variables!")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)


# 1. Route utama untuk elak Render 'sleep' (Sesuai untuk UptimeRobot ping)
@app.route("/")
def index():
  return "Bot Taska sedang aktif dan berjalan lancar!", 200


# 2. Route Webhook untuk Telegram hantar data ke Flask
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
  if request.headers.get("content-type") == "application/json":
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "", 200
  else:
    abort(403)


# ==========================================
# 3. HANDLER BUTANG TELEGRAM & MENU
# ==========================================


@bot.message_handler(
    func=lambda message: message.text and "Check-In Anak" in message.text
)
def handle_check_in_anak(message):
  bot.reply_to(message, "📥 Check-In Anak diterima (Logik Excel menyusul).")


@bot.message_handler(
    func=lambda message: message.text and "Check-Out Anak" in message.text
)
def handle_check_out_anak(message):
  bot.reply_to(message, "📤 Check-Out Anak diterima (Logik Excel menyusul).")


# Handler untuk butang Clock-In Staff (Memaparkan Senarai Nama)
@bot.message_handler(
    func=lambda message: message.text and "Clock-In Staff" in message.text
)
def handle_clock_in_staff(message):
  markup = InlineKeyboardMarkup()
  staff_list = ["Siti Maryam", "Adam Harith"]

  for name in staff_list:
    markup.add(
        InlineKeyboardButton(
            f"🔴 {name} (Belum Hadir)", callback_data=f"clockin_{name}"
        )
    )

  bot.reply_to(
      message, "Sila pilih nama staff untuk Clock-In:", reply_markup=markup
  )


@bot.message_handler(
    func=lambda message: message.text and "Clock-Out Staff" in message.text
)
def handle_clock_out_staff(message):
  bot.reply_to(message, "🔴 Clock-Out Staff direkodkan.")


@bot.message_handler(
    func=lambda message: message.text and "Status & Bayaran Yuran" in message.text
)
def handle_status_yuran(message):
  bot.reply_to(message, "💳 Memaparkan Status & Bayaran Yuran.")


@bot.message_handler(
    func=lambda message: message.text and "Laporan Bulanan" in message.text
)
def handle_laporan_bulanan(message):
  bot.reply_to(message, "📊 Menjana Laporan Bulanan Taska.")


# Handler Callback untuk Inline Button Nama Staff
@bot.callback_query_handler(func=lambda call: call.data.startswith("clockin_"))
def callback_clockin(call):
  staff_name = call.data.split("_")[1]
  bot.answer_callback_query(call.id, f"{staff_name} telah Clock-In!")
  bot.edit_message_text(
      chat_id=call.message.chat.id,
      message_id=call.message.message_id,
      text=f"🟢 {staff_name} telah berjaya Clock-In!",
  )


@bot.message_handler(func=lambda message: True)
def handle_fallback(message):
  bot.reply_to(
      message, "Sila gunakan butang menu di bawah untuk berurusan dengan bot."
  )


# 4. Fungsi Tetapan Webhook
def set_webhook():
  render_url = (
      "https://taska-kids-monthly-payment.onrender.com"  # URL Render anda
  )
  webhook_url = f"{render_url}/{TOKEN}"
  bot.remove_webhook()
  bot.set_webhook(url=webhook_url)
  print(f"Webhook dipautkan ke: {webhook_url}")


# Panggil fungsi webhook secara terus untuk Gunicorn
set_webhook()

if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
