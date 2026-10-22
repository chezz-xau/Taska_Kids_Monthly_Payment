from datetime import datetime
import os
import pandas as pd
import telebot
from flask import Flask, abort, request
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

# 1. Ambil TOKEN dan Inisytiharkan Bot & Flask DI ATAS SEKALI
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


# 2. Route utama untuk elak Render 'sleep'
@app.route("/")
def index():
  return "Bot Taska sedang aktif dan sistem Excel siap sedia!", 200


# 3. Route Webhook untuk Telegram
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
# 4. HANDLER BUTANG TELEGRAM & MENU
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

  if os.path.exists(EXCEL_FILE):
    try:
      df = pd.read_excel(EXCEL_FILE)
      if (
          "Tarikh" in df.columns
          and "Nama Staff" in df.columns
          and "Aktiviti" in df.columns
      ):
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
      markup.add(
          InlineKeyboardButton(
              f"🟢 {name} (Sudah Hadir)", callback_data=f"ignore_{name}"
          )
      )
    else:
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


# Handler Laporan Kehadiran Hari Ini
@bot.message_handler(
    func=lambda message: message.text and "Laporan" in message.text
)
def handle_laporan(message):
  today_str = datetime.now().strftime("%Y-%m-%d")

  if not os.path.exists(EXCEL_FILE):
    bot.reply_to(
        message,
        "📊 Tiada fail rekod ditemui lagi. Belum ada aktiviti direkodkan.",
    )
    return

  try:
    df = pd.read_excel(EXCEL_FILE)

    if "Tarikh" in df.columns:
      df_today = df[df["Tarikh"].astype(str) == today_str]
    else:
      df_today = pd.DataFrame()

    if df_today.empty:
      bot.reply_to(
          message,
          f"📊 **Laporan Hari Ini ({today_str})**\n\nTiada sebarang rekod"
          " kehadiran lagi hari ini.",
          parse_mode="Markdown",
      )
      return

    report_text = f"📊 **Laporan Kehadiran Hari Ini ({today_str})**\n\n"

    for index, row in df_today.iterrows():
      nama = row.get("Nama Staff", "Tidak diketahui")
      aktiviti = row.get("Aktiviti", "Aktiviti")
      masa = row.get("Masa", "-")
      report_text += f"🟢 **{nama}** — *{aktiviti}* pada {masa}\n"

    bot.reply_to(message, report_text, parse_mode="Markdown")

  except Exception as e:
    bot.reply_to(message, f"Ralat membaca laporan dari Excel: {e}")


# Callback apabila staf tekan butang Clock-In
@bot.callback_query_handler(func=lambda call: call.data.startswith("clockin_"))
def callback_clockin(call):
  staff_name = call.data.split("_")[1]

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


# 5. Fungsi Tetapan Webhook
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
