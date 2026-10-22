import os
import telebot
from flask import Flask, abort, request

# Ambil TOKEN dari Environment Variables Render (Paling selamat)
# Atau anda boleh letak token terus dalam string jika mahu
TOKEN = os.environ.get("BOT_TOKEN", "MASUKKAN_TOKEN_BOT_ANDA_DI_SINI")
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
# 3. HANDLER BUTANG TELEGRAM (Mengikut Menu Anda)
# ==========================================

# Handler untuk butang Check-In Anak
@bot.message_handler(
    func=lambda message: message.text and "Check-In Anak" in message.text
)
def handle_check_in_anak(message):
  # Tulis logik database / proses anda di sini
  bot.reply_to(message, "📥 Sila hantar butiran untuk Check-In anak.")


# Handler untuk butang Check-Out Anak
@bot.message_handler(
    func=lambda message: message.text and "Check-Out Anak" in message.text
)
def handle_check_out_anak(message):
  # Tulis logik database / proses anda di sini
  bot.reply_to(message, "📤 Proses Check-Out anak sedang dikemaskini.")


# Handler untuk butang Clock-In Staff
@bot.message_handler(
    func=lambda message: message.text and "Clock-In Staff" in message.text
)
def handle_clock_in_staff(message):
  bot.reply_to(message, "🟢 Kehadiran staff telah direkodkan.")


# Handler untuk butang Clock-Out Staff
@bot.message_handler(
    func=lambda message: message.text and "Clock-Out Staff" in message.text
)
def handle_clock_out_staff(message):
  bot.reply_to(message, "🔴 Waktu tamat bertugas staff telah direkodkan.")


# Handler untuk butang Status & Bayaran Yuran
@bot.message_handler(
    func=lambda message: message.text and "Status & Bayaran Yuran" in message.text
)
def handle_status_yuran(message):
  bot.reply_to(message, "💳 Memuatkan data status yuran bulanan...")


# Handler untuk butang Laporan Bulanan
@bot.message_handler(
    func=lambda message: message.text and "Laporan Bulanan" in message.text
)
def handle_laporan_bulanan(message):
  bot.reply_to(message, "📊 Menjana laporan bulanan Taska...")


# Handler fallback untuk mesej biasa / teks lain
@bot.message_handler(func=lambda message: True)
def handle_fallback(message):
  bot.reply_to(
      message,
      "Maaf, arahan tidak dikenali. Sila gunakan menu butang di bawah.",
  )


# 4. Fungsi Tetapan Webhook Automatik
def set_webhook():
  render_url = (
      "https://taska-kids-monthly-payment.onrender.com"  # URL Render anda
  )
  webhook_url = f"{render_url}/{TOKEN}"
  bot.remove_webhook()
  bot.set_webhook(url=webhook_url)
  print(f"Webhook berjaya dipautkan ke: {webhook_url}")


if __name__ == "__main__":
  # Set webhook semasa permulaan
  set_webhook()
  # Jalankan aplikasi Flask mengikut port dinamik Render
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
