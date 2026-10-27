import os
import psycopg2
import telebot
from telebot import types
from flask import Flask, request

TOKEN = os.environ.get("TELEGRAM_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Kamus sementara untuk menyimpan data pendaftaran mengikut chat_id
user_temp_data = {}


# Fungsi untuk sambung ke database Neon PostgreSQL
def get_db_connection():
  return psycopg2.connect(DATABASE_URL, sslmode="require")


# --- 1. SETUP DATABASE POSTGRESQL ---
def init_db():
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS pelajar (
            id SERIAL PRIMARY KEY,
            nama TEXT,
            cawangan TEXT,
            status_bayaran TEXT DEFAULT 'Belum Bayar'
        )
    """)
  conn.commit()

  # Masukkan data contoh jika jadual kosong
  cursor.execute("SELECT COUNT(*) FROM pelajar")
  if cursor.fetchone()[0] == 0:
    sample_data = [
        ("Ali bin Abu", "Taska Corner", "Lunas"),
        ("Siti binti Omar", "Taska Corner", "Belum Bayar"),
        ("Ahmad bin Ali", "Taska Hadhari", "Lunas"),
        ("Fatima binti Hassan", "Taska Hadhari", "Belum Bayar"),
    ]
    cursor.executemany(
        "INSERT INTO pelajar (nama, cawangan, status_bayaran) VALUES (%s, %s,"
        " %s)",
        sample_data,
    )
    conn.commit()
  cursor.close()
  conn.close()


init_db()


# --- 2. WEBHOOK ROUTE UNTUK TELEGRAM ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
  if request.headers.get("content-type") == "application/json":
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "", 200
  else:
    return "Unauthorized", 403


@app.route("/")
def index():
  return "Bot Taska Neon Database & Webhook sedang aktif!"


# --- 3. COMMAND /START & MENU UTAMA ---
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


# --- 4. MENU LAPORAN ---
@bot.callback_query_handler(func=lambda call: call.data == "menu_laporan")
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

  bot.edit_message_text(
      "📊 **Menu Laporan**\nSila pilih jenis laporan yang ingin dilihat:",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
      parse_mode="Markdown",
  )


# --- 5. LAPORAN PEMBAYARAN: PILIH CAWANGAN ---
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


# --- 6. PILIH STATUS BAYARAN MENGIKUT CAWANGAN ---
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


# --- 7. PAPAR SENARAI MENGIKUT STATUS & CAWANGAN ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("status_"))
def papar_senarai_status(call):
  parts = call.data.split("_")
  status_type = parts[1]
  cawangan_key = parts[2]

  cawangan_name = "Taska Corner" if cawangan_key == "corner" else "Taska Hadhari"
  status_text = "Sudah Lunas" if status_type == "lunas" else "Belum Bayar"
  db_status = "Lunas" if status_type == "lunas" else "Belum Bayar"

  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT nama FROM pelajar WHERE cawangan = %s AND status_bayaran = %s",
      (cawangan_name, db_status),
  )
  senarai = cursor.fetchall()
  cursor.close()
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


# --- 8. PENDAFTARAN BARU ANAK-ANAK ---
@bot.callback_query_handler(func=lambda call: call.data == "pendaftaran")
def pendaftaran_mulai(call):
  bot.edit_message_text(
      "📝 **Pendaftaran Baru Anak-Anak**\n\nSila hantar teks mengandungi"
      " **nama penuh anak** yang ingin didaftarkan:",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=types.InlineKeyboardMarkup().add(
          types.InlineKeyboardButton("🔙 Batal", callback_data="back_start")
      ),
      parse_mode="Markdown",
  )
  bot.register_next_step_handler(call.message, terima_nama_pendaftaran)


def terima_nama_pendaftaran(message):
  if message.text.startswith("/"):
    return

  nama_anak = message.text.strip()
  user_temp_data[message.chat.id] = nama_anak

  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton(
          "🏡 Taska Corner", callback_data="reg_cawangan_corner"
      )
  )
  markup.add(
      types.InlineKeyboardButton(
          "🏫 Taska Hadhari", callback_data="reg_cawangan_hadhari"
      )
  )
  markup.add(types.InlineKeyboardButton("❌ Batal", callback_data="back_start"))

  bot.send_message(
      message.chat.id,
      f"👤 Nama Anak: **{nama_anak}**\n\nSila pilih cawangan untuk pendaftaran"
      " ini:",
      reply_markup=markup,
      parse_mode="Markdown",
  )


@bot.callback_query_handler(
    func=lambda call: call.data
    in ["reg_cawangan_corner", "reg_cawangan_hadhari"]
)
def simpan_pendaftaran(call):
  cawangan_name = (
      "Taska Corner" if "corner" in call.data else "Taska Hadhari"
  )
  nama_anak = user_temp_data.get(call.message.chat.id)

  if not nama_anak:
    bot.answer_callback_query(
        call.id, "Sesi tamat. Sila mula semula.", show_alert=True
    )
    return

  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO pelajar (nama, cawangan, status_bayaran) VALUES (%s, %s,"
      " 'Belum Bayar')",
      (nama_anak, cawangan_name),
  )
  conn.commit()
  cursor.close()
  conn.close()

  user_temp_data.pop(call.message.chat.id, None)

  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton("➕ Daftar Lagi", callback_data="pendaftaran")
  )
  markup.add(
      types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start")
  )

  bot.edit_message_text(
      f"✅ **Berjaya Didaftarkan!**\n\nNama: *{nama_anak}*\nCawangan:"
      f" *{cawangan_name}*\nStatus Yuran: *Belum Bayar*",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
      parse_mode="Markdown",
  )


# --- 9. KELUARKAN DARI SENARAI (PADAM NAMA) ---
@bot.callback_query_handler(func=lambda call: call.data == "keluarkan")
def menu_keluarkan(call):
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute("SELECT id, nama, cawangan FROM pelajar ORDER BY cawangan, nama")
  pelajar_list = cursor.fetchall()
  cursor.close()
  conn.close()

  markup = types.InlineKeyboardMarkup()
  if pelajar_list:
    for row in pelajar_list:
      p_id, nama, cawangan = row
      short_cawangan = "Corner" if cawangan == "Taska Corner" else "Hadhari"
      markup.add(
          types.InlineKeyboardButton(
              f"❌ {nama} ({short_cawangan})", callback_data=f"del_{p_id}"
          )
      )
  else:
    bot.answer_callback_query(call.id, "Tiada rekod pelajar.", show_alert=True)
    return

  markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))

  bot.edit_message_text(
      "❌ **Buang Nama Pelajar**\n\nSila klik pada nama anak yang ingin"
      " dikeluarkan dari senarai:",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
      parse_mode="Markdown",
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def proses_padam(call):
  p_id = call.data.split("_")[1]

  conn = get_db_connection()
  cursor = conn.cursor()
  # Ambil nama untuk paparan mesej pengesahan sebelum padam
  cursor.execute("SELECT nama, cawangan FROM pelajar WHERE id = %s", (p_id,))
  result = cursor.fetchone()

  if result:
    nama, cawangan = result
    cursor.execute("DELETE FROM pelajar WHERE id = %s", (p_id,))
    conn.commit()
    cursor.close()
    conn.close()

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "❌ Buang Nama Lain", callback_data="keluarkan"
        )
    )
    markup.add(
        types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start")
    )

    bot.edit_message_text(
        f"🗑️ **Berjaya Dikeluarkan!**\n\nNama: *{nama}*\nCawangan:"
        f" *{cawangan}* telah dipadam daripada sistem.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
    )
  else:
    cursor.close()
    conn.close()
    bot.answer_callback_query(
        call.id, "Rekod tidak dijumpai atau sudah dipadam.", show_alert=True
    )


# --- 10. PLACEHOLDER UNTUK MENU LAIN ---
@bot.callback_query_handler(
    func=lambda call: call.data in ["laporan_harian", "late_pickup"]
)
def menu_lain(call):
  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start")
  )

  feature_names = {
      "laporan_harian": "Laporan Harian",
      "late_pickup": "Late Pick Up Charges",
  }
  title = feature_names.get(call.data, "Fungsi")

  bot.edit_message_text(
      f"🛠️ **{title}**\nBahagian ini sedang dalam pembangunan.",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
      parse_mode="Markdown",
  )


# --- 11. MENJALANKAN APLIKASI WEBHOOK ---
if __name__ == "__main__":
  render_url = os.environ.get("RENDER_EXTERNAL_URL")
  if render_url:
    bot.remove_webhook()
    bot.set_webhook(url=f"{render_url}/{TOKEN}")
    print(f"Webhook berjaya dipasang ke: {render_url}/{TOKEN}")

  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
