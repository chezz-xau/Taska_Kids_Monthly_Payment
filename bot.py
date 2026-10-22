from datetime import datetime, timedelta, timezone
import os
import pandas as pd
import telebot
from flask import Flask, abort, request
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# 1. Ambil TOKEN dan Inisytiharkan Bot & Flask
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
  raise ValueError("TELEGRAM_TOKEN tidak ditetapkan dalam environment variables!")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

EXCEL_FILE = "data_taska.xlsx"

# Tetapan Zon Masa Malaysia (UTC+8)
MY_TZ = timezone(timedelta(hours=8))

# Senarai data contoh
STAFF_LIST = ["Siti Maryam", "Adam Harith"]
KIDS_LIST = ["Ahmad", "Aisha", "Rayyan"]


# Fungsi untuk simpan data ke Excel mengikut Waktu Malaysia
def save_to_excel(name, category, action):
  now = datetime.now(MY_TZ)
  date_str = now.strftime("%Y-%m-%d")
  time_str = now.strftime("%H:%M:%S")

  new_data = {
      "Tarikh": [date_str],
      "Masa": [time_str],
      "Nama": [name],
      "Kategori": [category],  # 'Staff' atau 'Anak'
      "Aktiviti": [action],  # 'Clock-In', 'Clock-Out', 'Check-In', 'Check-Out'
  }

  df_new = pd.DataFrame(new_data)

  if os.path.exists(EXCEL_FILE):
    df_existing = pd.read_excel(EXCEL_FILE)
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    df_combined.to_excel(EXCEL_FILE, index=False)
  else:
    df_new.to_excel(EXCEL_FILE, index=False)


# Fungsi untuk bina Keyboard Menu
def get_main_menu():
  markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
  btn_checkin_anak = KeyboardButton("📥 Check-In Anak")
  btn_checkout_anak = KeyboardButton("📤 Check-Out Anak")
  btn_clockin_staff = KeyboardButton("🟢 Clock-In Staff")
  btn_clockout_staff = KeyboardButton("🔴 Clock-Out Staff")
  btn_yuran = KeyboardButton("💳 Status & Bayaran Yuran")
  btn_laporan = KeyboardButton("📊 Laporan")

  markup.add(btn_checkin_anak, btn_checkout_anak)
  markup.add(btn_clockin_staff, btn_clockout_staff)
  markup.add(btn_yuran)
  markup.add(btn_laporan)
  return markup


# 2. Route utama
@app.route("/")
def index():
  return "Bot Taska sedang aktif!", 200


# 3. Route Webhook
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
# 4. HANDLER BOT TELEGRAM
# ==========================================


@bot.message_handler(commands=["start", "menu"])
def send_welcome(message):
  bot.reply_to(
      message,
      "Selamat datang! Sila pilih menu di bawah:",
      reply_markup=get_main_menu(),
  )


# Handler Check-In Anak
@bot.message_handler(
    func=lambda message: message.text and "Check-In Anak" in message.text
)
def handle_check_in_anak(message):
  today_str = datetime.now(MY_TZ).strftime("%Y-%m-%d")
  checked_in_today = []

  if os.path.exists(EXCEL_FILE):
    try:
      df = pd.read_excel(EXCEL_FILE)
      if (
          "Tarikh" in df.columns
          and "Nama" in df.columns
          and "Aktiviti" in df.columns
      ):
        filtered = df[
            (df["Tarikh"].astype(str) == today_str)
            & (df["Aktiviti"] == "Check-In")
        ]
        checked_in_today = filtered["Nama"].tolist()
    except Exception as e:
      print(f"Ralat membaca Excel: {e}")

  markup = InlineKeyboardMarkup()
  for name in KIDS_LIST:
    if name in checked_in_today:
      markup.add(
          InlineKeyboardButton(
              f"🟢 {name} (Sudah Check-In)", callback_data=f"ignore_kid_{name}"
          )
      )
    else:
      markup.add(
          InlineKeyboardButton(
              f"📥 {name} (Check-In)", callback_data=f"checkin_kid_{name}"
          )
      )

  bot.reply_to(
      message, "Sila pilih nama anak untuk Check-In:", reply_markup=markup
  )


# Handler Check-Out Anak
@bot.message_handler(
    func=lambda message: message.text and "Check-Out Anak" in message.text
)
def handle_check_out_anak(message):
  markup = InlineKeyboardMarkup()
  for name in KIDS_LIST:
    markup.add(
        InlineKeyboardButton(
            f"📤 {name} (Check-Out)", callback_data=f"checkout_kid_{name}"
        )
    )
  bot.reply_to(message, "Sila pilih nama anak untuk Check-Out:", reply_markup=markup)


# Handler Clock-In Staff
@bot.message_handler(
    func=lambda message: message.text and "Clock-In Staff" in message.text
)
def handle_clock_in_staff(message):
  today_str = datetime.now(MY_TZ).strftime("%Y-%m-%d")
  clocked_in_today = []

  if os.path.exists(EXCEL_FILE):
    try:
      df = pd.read_excel(EXCEL_FILE)
      if (
          "Tarikh" in df.columns
          and "Nama" in df.columns
          and "Aktiviti" in df.columns
      ):
        filtered = df[
            (df["Tarikh"].astype(str) == today_str)
            & (df["Aktiviti"] == "Clock-In")
        ]
        clocked_in_today = filtered["Nama"].tolist()
    except Exception as e:
      print(f"Ralat membaca Excel: {e}")

  markup = InlineKeyboardMarkup()
  for name in STAFF_LIST:
    if name in clocked_in_today:
      markup.add(
          InlineKeyboardButton(
              f"🟢 {name} (Sudah Hadir)", callback_data=f"ignore_staff_{name}"
          )
      )
    else:
      markup.add(
          InlineKeyboardButton(
              f"🔴 {name} (Belum Hadir)", callback_data=f"clockin_staff_{name}"
          )
      )

  bot.reply_to(
      message, "Sila pilih nama staff untuk Clock-In:", reply_markup=markup
  )


# Handler Clock-Out Staff
@bot.message_handler(
    func=lambda message: message.text and "Clock-Out Staff" in message.text
)
def handle_clock_out_staff(message):
  markup = InlineKeyboardMarkup()
  for name in STAFF_LIST:
    markup.add(
        InlineKeyboardButton(
            f"🔴 {name} (Clock-Out)", callback_data=f"clockout_staff_{name}"
        )
    )
  bot.reply_to(
      message, "Sila pilih nama staff untuk Clock-Out:", reply_markup=markup
  )


@bot.message_handler(
    func=lambda message: message.text and "Status & Bayaran Yuran" in message.text
)
def handle_status_yuran(message):
  bot.reply_to(message, "💳 Memaparkan Status & Bayaran Yuran.")


# Handler Laporan
@bot.message_handler(
    func=lambda message: message.text and "Laporan" in message.text
)
def handle_laporan(message):
  today_str = datetime.now(MY_TZ).strftime("%Y-%m-%d")

  if not os.path.exists(EXCEL_FILE):
    bot.reply_to(
        message,
        "📊 Tiada fail rekod ditemui lagi. Belum ada aktiviti direkodkan.",
        reply_markup=get_main_menu(),
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
          " aktiviti lagi hari ini.",
          parse_mode="Markdown",
          reply_markup=get_main_menu(),
      )
      return

    report_text = f"📊 **Laporan Kehadiran Hari Ini ({today_str})**\n\n"

    for index, row in df_today.iterrows():
      nama = row.get("Nama", "Tidak diketahui")
      kategori = row.get("Kategori", "-")
      aktiviti = row.get("Aktiviti", "Aktiviti")
      masa = row.get("Masa", "-")
      report_text += f"• **{nama}** ({kategori}) — *{aktiviti}* pada {masa}\n"

    bot.reply_to(
        message, report_text, parse_mode="Markdown", reply_markup=get_main_menu()
    )

  except Exception as e:
    bot.reply_to(
        message,
        f"Ralat membaca laporan dari Excel: {e}",
        reply_markup=get_main_menu(),
    )


# ==========================================
# 5. CALLBACK HANDLERS (INLINE BUTTONS)
# ==========================================


@bot.callback_query_handler(func=lambda call: call.data.startswith("checkin_kid_"))
def callback_checkin_kid(call):
  kid_name = call.data.split("_")[2]
  save_to_excel(kid_name, "Anak", "Check-In")
  bot.answer_callback_query(call.id, f"{kid_name} telah Check-In!")
  bot.edit_message_text(
      chat_id=call.message.chat.id,
      message_id=call.message.message_id,
      text=f"📥 {kid_name} telah berjaya Check-In dan direkodkan ke Excel!",
  )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("checkout_kid_")
)
def callback_checkout_kid(call):
  kid_name = call.data.split("_")[2]
  save_to_excel(kid_name, "Anak", "Check-Out")
  bot.answer_callback_query(call.id, f"{kid_name} telah Check-Out!")
  bot.edit_message_text(
      chat_id=call.message.chat.id,
      message_id=call.message.message_id,
      text=f"📤 {kid_name} telah berjaya Check-Out dan direkodkan ke Excel!",
  )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("clockin_staff_")
)
def callback_clockin_staff(call):
  staff_name = call.data.split("_")[2]
  save_to_excel(staff_name, "Staff", "Clock-In")
  bot.answer_callback_query(call.id, f"{staff_name} telah Clock-In!")
  bot.edit_message_text(
      chat_id=call.message.chat.id,
      message_id=call.message.message_id,
      text=f"🟢 {staff_name} telah berjaya Clock-In dan direkodkan ke Excel!",
  )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("clockout_staff_")
)
def callback_clockout_staff(call):
  staff_name = call.data.split("_")[2]
  save_to_excel(staff_name, "Staff", "Clock-Out")
  bot.answer_callback_query(call.id, f"{staff_name} telah Clock-Out!")
  bot.edit_message_text(
      chat_id=call.message.chat.id,
      message_id=call.message.message_id,
      text=f"🔴 {staff_name} telah berjaya Clock-Out dan direkodkan ke Excel!",
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith("ignore_"))
def callback_ignore(call):
  bot.answer_callback_query(call.id, "Rekod ini sudah didaftarkan hari ini.")


@bot.message_handler(func=lambda message: True)
def handle_fallback(message):
  bot.reply_to(
      message,
      "Sila gunakan butang menu di bawah untuk berurusan dengan bot.",
      reply_markup=get_main_menu(),
  )


# 6. Tetapan Webhook
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
