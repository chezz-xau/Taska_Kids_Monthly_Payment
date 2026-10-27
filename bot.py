import os
import sqlite3
import telebot
from telebot import types

# Mengambil token secara automatik dari Environment Variable Render
TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)


# --- 1. SETUP DATABASE SQLITE ---
def init_db():
  conn = sqlite3.connect("taska.db")
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS pelajar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT,
            cawangan TEXT,
            status_bayaran TEXT DEFAULT 'Belum Bayar'
        )
    """)
  conn.commit()

  # Masukkan data contoh (dummy data) jika database kosong
  cursor.execute("SELECT COUNT(*) FROM pelajar")
  if cursor.fetchone()[0] == 0:
    sample_data = [
        ("Ali bin Abu", "Taska Corner", "Lunas"),
        ("Siti binti Omar", "Taska Corner", "Belum Bayar"),
        ("Ahmad bin Ali", "Taska Hadhari", "Lunas"),
        ("Fatima binti Hassan", "Taska Hadhari", "Belum Bayar"),
    ]
    cursor.executemany(
        "INSERT INTO pelajar (nama, cawangan, status_bayaran) VALUES (?, ?, ?)",
        sample_data,
    )
    conn.commit()
  conn.close()


init_db()


# --- 2. COMMAND /START & MENU UTAMA ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
  markup = types.InlineKeyboardMarkup()
  markup.add(types.InlineKeyboardButton("📊 Laporan", callback_data="menu_laporan"))
  markup.add(
      types.InlineKeyboardButton(
          "⏰ Late Pick Up Charges", callback_data="late_pickup"
      )
  )
  markup.add(
      types.InlineKeyboardButton(
          "📝 Pendaftaran Baru Anak-Anak", callback_data="pendaftaran"
      )
  )
  markup.add(
      types.InlineKeyboardButton(
          "❌ Keluarkan Dari Senarai", callback_data="keluarkan"
      )
  )

  bot.send_message(
      message.chat.id,
      "🤖 **Selamat Datang ke Taska Bot**\nSila pilih menu tindakan di bawah:",
      reply_markup=markup,
      parse_mode="Markdown",
  )


# --- 3. MENU LAPORAN ---
@bot.callback_query_handler(
    func=lambda call: call.data == "menu_laporan" or call.data == "menu_utama"
)
def menu_laporan(call):
  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton(
          "📅 Laporan Harian", callback_data="laporan_harian"
      )
  )
  markup.add(
      types.InlineKeyboardButton(
          "💳 Laporan Pembayaran", callback_data="menu_pembayaran"
      )
  )
  markup.add(
      types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start")
  )

  try:
    bot.edit_message_text(
        "📊 **Menu Laporan**\nSila pilih jenis laporan yang ingin dilihat:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )
  except Exception:
    bot.send_message(
        call.message.chat.id,
        "📊 **Menu Laporan**\nSila pilih jenis laporan yang ingin dilihat:",
        reply_markup=markup,
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data == "back_start")
def back_to_start(call):
  markup = types.InlineKeyboardMarkup()
  markup.add(types.InlineKeyboardButton("📊 Laporan", callback_data="menu_laporan"))
  markup.add(
      types.InlineKeyboardButton(
          "⏰ Late Pick Up Charges", callback_data="late_pickup"
      )
  )
  markup.add(
      types.InlineKeyboardButton(
          "📝 Pendaftaran Baru Anak-Anak", callback_data="pendaftaran"
      )
  )
  markup.add(
      types.InlineKeyboardButton(
          "❌ Keluarkan Dari Senarai", callback_data="keluarkan"
      )
  )

  bot.edit_message_text(
      "🤖 **Selamat Datang ke Taska Bot**\nSila pilih menu tindakan di bawah:",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
      parse_mode="Markdown",
  )


# --- 4. PILIH CAWANGAN UNTUK LAPORAN PEMBAYARAN ---
@bot.callback_query_handler(func=lambda call: call.data == "menu_pembayaran")
def menu_pembayaran(call):
  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton(
          "🏡 Taska Corner", callback_data="cawangan_corner"
      )
  )
  markup.add(
      types.InlineKeyboardButton(
          "🏫 Taska Hadhari", callback_data="cawangan_hadhari"
      )
  )
  markup.add(
      types.InlineKeyboardButton("🔙 Kembali", callback_data="menu_laporan")
  )

  bot.edit_message_text(
      "🏢 **Sila pilih cawangan Taska untuk semakan yuran:**",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
      parse_mode="Markdown",
  )


# --- 5. PILIH STATUS BAYARAN MENGIKUT CAWANGAN ---
@bot.callback_query_handler(
    func=lambda call: call.data in ["cawangan_corner", "cawangan_hadhari"]
)
def pilih_cawangan(call):
  cawangan_key = "corner" if "corner" in call.data else "hadhari"
  cawangan_name = "Taska Corner" if cawangan_key == "corner" else "Taska Hadhari"

  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton(
          "✅ Sudah Lunas", callback_data=f"status_lunas_{cawangan_key}"
      )
  )
  markup.add(
      types.InlineKeyboardButton(
          "⏳ Belum Bayar", callback_data=f"status_belum_{cawangan_key}"
      )
  )
  markup.add(
      types.InlineKeyboardButton(
          "🔙 Pilih Cawangan Lain", callback_data="menu_pembayaran"
      )
  )

  bot.edit_message_text(
      f"📌 **{cawangan_name} - Status Yuran**\nSila pilih status bayaran:",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
      parse_mode="Markdown",
  )


# --- 6. PAPAR SENARAI MENGIKUT STATUS & CAWANGAN ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("status_"))
def papar_senarai_status(call):
  parts = call.data.split("_")
  status_type = parts[1]  # lunas atau belum
  cawangan_key = parts[2]  # corner atau hadhari

  cawangan_name = "Taska Corner" if cawangan_key == "corner" else "Taska Hadhari"
  status_text = "Sudah Lunas" if status_type == "lunas" else "Belum Bayar"
  db_status = "Lunas" if status_type == "lunas" else "Belum Bayar"

  conn = sqlite3.connect("taska.db")
  cursor = conn.cursor()
  cursor.execute(
      "SELECT nama FROM pelajar WHERE cawangan = ? AND status_bayaran = ?",
      (cawangan_name, db_status),
  )
  senarai = cursor.fetchall()
  conn.close()

  text = f"📋 **Senarai Pelajar ({cawangan_name}) - {status_text}:**\n\n"
  if senarai:
    for idx, row in enumerate(senarai, 1):
      text += f"{idx}. {row[0]}\n"
  else:
    text += "_Tiada rekod dijumpai._\n"

  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton(
          "🔙 Kembali", callback_data=f"cawangan_{cawangan_key}"
      )
  )

  bot.edit_message_text(
      text,
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
      parse_mode="Markdown",
  )


# --- 7. PLACEHOLDER UNTUK MENU LAIN ---
@bot.callback_query_handler(
    func=lambda call: call.data
    in ["laporan_harian", "late_pickup", "pendaftaran", "keluarkan"]
)
def menu_lain(call):
  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start")
  )

  feature_names = {
      "laporan_harian": "Laporan Harian",
      "late_pickup": "Late Pick Up Charges",
      "pendaftaran": "Pendaftaran Baru Anak-Anak",
      "keluarkan": "Keluarkan Dari Senarai",
  }
  title = feature_names.get(call.data, "Fungsi")

  bot.edit_message_text(
      f"🛠️ **{title}**\nBahagian ini sedang dalam pembangunan.",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
      parse_mode="Markdown",
  )


# Jalankan bot
print("Bot sedang berjalan...")
bot.remove_webhook()  # Membuang webhook lama bagi mengelakkan ralat 409 Conflict
bot.infinity_polling()
