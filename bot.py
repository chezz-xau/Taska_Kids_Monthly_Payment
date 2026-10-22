from datetime import datetime
import os
import pandas as pd
import telebot
from flask import Flask, abort, request
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

# Ambil TOKEN dari Environment Variables Render
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
  raise ValueError("TELEGRAM_TOKEN tidak ditetapkan dalam environment variables!")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

EXCEL_FILE = "data_taska.xlsx"


# Fungsi untuk simpan data ke Excel
def save_to_excel(staff_name, action):
  now = datetime.now()
  date_str = now.strftime("%Y-%m-%d")
  time_str = now.strftime("%H:%M:%S")

  new_data = {
      "Tarikh": [date_str],
      "Masa": [time_str],
      "Nama Staff": [staff_name],
      "Aktiviti": [action],
  }

  df_new = pd.DataFrame(new_data)

  if os.path.exists(EXCEL_FILE):
    df_existing = pd.read_excel(EXCEL_FILE)
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    df_combined.to_excel(EXCEL_FILE, index=False)
  else:
    df_new.to_excel(EXCEL_FILE, index=False)


# 1. Route utama untuk elak Render 'sleep'
@app.route("/")
def index():
  return "Bot Taska sedang aktif dan sistem Excel siap sedia!", 200


# 2. Route Webhook untuk Telegram
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
  bot.reply_to(message, "📥 Check-In Anak diterima.")


@bot.message_handler(
    func=lambda message: message.text and "Check-Out Anak" in message.text
)
def handle_check_out_anak(message):
  bot.reply_to(message, "📤 Check-Out Anak diterima.")


# Handler untuk Clock-In Staff (Semak Excel untuk hari ini)
@bot.message_handler(
    func=lambda message: message.text and "Clock-In Staff" in message.text
)
def handle_clock_in_staff(message):
  today_str = datetime.now().strftime("%Y-%m-%d")
  clocked_in_today = []

  # Semak fail Excel jika wujud
  if os.path.exists(EXCEL_FILE):
    try:
      df = pd.read_excel(EXCEL_FILE)
      if (
          "Tarikh" in df.columns
          and "Nama Staff" in df.columns
          and "Aktiviti" in df.columns
      ):
        # Tapis rekod untuk tarikh hari ini dan aktiviti Clock-In
        filtered = df[
            (df["Tarikh"].astype(str) == today_str)
            & (df["Aktiviti"] == "Clock-In")
        ]
        clocked_in_today = filtered["Nama Staff"].tolist()
    except Exception as e:
      print(f"Ralat membaca Excel: {e}")

  markup = InlineKeyboardMarkup()
  staff_list = ["Siti Maryam", "Adam Harith"]

  for name in staff_list:
    if name in clocked_in_today:
      # Jika sudah ada dalam Excel hari ini, paparkan status sudah hadir
      markup.add(
          InlineKeyboardButton(
              f"🟢 {name} (Sudah Hadir)", callback_data=f"ignore_{name}"
          )
      )
    else:
      # Jika belum, paparkan butang untuk Clock-In
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


# Callback apabila staf tekan butang Clock-In
@bot.callback_query_handler(func=lambda call: call.data.startswith("clockin_"))
def callback_clockin(call):
  staff_name = call.data.split("_")[1]

  # Simpan terus ke fail Excel
  save_to_excel(staff_name, "Clock-In")

  bot.answer_callback_query(call.id, f"{staff_name} berjaya direkod ke Excel!")
  bot.edit_message_text(
      chat_id=call.message.chat.id,
      message_id=call.message.message_id,
      text=(
          f"🟢 {staff_name} telah berjaya Clock-In dan direkodkan ke dalam"
          " Excel!"
      ),
  )


# Callback jika tekan butang staff yang sudah hadir
@bot.callback_query_handler(func=lambda call: call.data.startswith("ignore_"))
def callback_ignore(call):
  staff_name = call.data.split("_")[1]
  bot.answer_callback_query(
      call.id, f"{staff_name} sudah pun clock-in hari ini!"
  )


@bot.message_handler(func=lambda message: True)
def handle_fallback(message):
  bot.reply_to(
      message, "Sila gunakan butang menu di bawah untuk berurusan dengan bot."
  )


# 4. Fungsi Tetapan Webhook
def set_webhook():
  render_url = "https://taska-kids-monthly-payment.onrender.com"
  webhook_url = f"{render_url}/{TOKEN}"
  bot.remove_webhook()
  bot.set_webhook(url=webhook_url)
  print(f"Webhook dipautkan ke: {webhook_url}")


set_webhook()

if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
