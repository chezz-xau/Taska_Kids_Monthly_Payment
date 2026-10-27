import os
import psycopg2
import telebot
from telebot import types
from flask import Flask, request
from datetime import datetime

TOKEN = os.environ.get("TELEGRAM_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
# Membaca senarai ADMIN_ID dan memisahkan mengikut koma
admin_env = os.environ.get("ADMIN_ID", "")
ADMIN_LIST = [aid.strip() for aid in admin_env.split(",") if aid.strip()]

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

user_temp_data = {}

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# --- 1. SETUP DATABASE ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pelajar (
            id SERIAL PRIMARY KEY,
            nama TEXT,
            cawangan TEXT,
            status_bayaran TEXT DEFAULT 'Belum Bayar',
            status_hadir TEXT DEFAULT 'Check-Out'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff_attendance (
            id SERIAL PRIMARY KEY,
            staff_name TEXT,
            action_type TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM pelajar")
    if cursor.fetchone()[0] == 0:
        sample_data = [
            ("Ali bin Abu", "Taska Corner", "Lunas", "Check-Out"),
            ("Siti binti Omar", "Taska Corner", "Belum Bayar", "Check-Out"),
            ("Ahmad bin Ali", "Taska Hadhari", "Lunas", "Check-Out"),
            ("Fatima binti Hassan", "Taska Hadhari", "Belum Bayar", "Check-Out")
        ]
        cursor.executemany("INSERT INTO pelajar (nama, cawangan, status_bayaran, status_hadir) VALUES (%s, %s, %s, %s)", sample_data)
        conn.commit()
    cursor.close()
    conn.close()

init_db()

# --- 2. WEBHOOK ROUTE ---
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
    return "Bot Taska Admin & Staf sedang aktif!"

# --- 3. MENU UTAMA (BERDASARKAN ADMIN ATAU STAF) ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = str(message.from_user.id)
    markup = types.InlineKeyboardMarkup()
    
    if user_id in ADMIN_LIST:
        # MENU ADMIN
        markup.add(types.InlineKeyboardButton("📊 Laporan", callback_data="menu_laporan"))
        markup.add(types.InlineKeyboardButton("📝 Pendaftaran Baru Anak-Anak", callback_data="pendaftaran"))
        markup.add(types.InlineKeyboardButton("❌ Keluarkan Dari Senarai", callback_data="keluarkan"))
        markup.add(types.InlineKeyboardButton("👶 Check-In/Out Anak-Anak", callback_data="m_ci"))
        markup.add(types.InlineKeyboardButton("🕒 Staff Clock In / Out", callback_data="m_sc"))
        
        bot.send_message(message.chat.id, "👑 **Menu Utama Admin Taska**\nSila pilih tindakan di bawah:", reply_markup=markup, parse_mode="Markdown")
    else:
        # MENU STAF
        markup.add(types.InlineKeyboardButton("👶 Check-In/Out Anak-Anak", callback_data="m_ci"))
        markup.add(types.InlineKeyboardButton("🕒 Staff Clock In / Out", callback_data="m_sc"))
        
        bot.send_message(message.chat.id, "👩‍💼 **Menu Utama Staf Taska**\nSila pilih tindakan di bawah:", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "back_start")
def back_to_start(call):
    user_id = str(call.from_user.id)
    markup = types.InlineKeyboardMarkup()
    
    if user_id in ADMIN_LIST:
        markup.add(types.InlineKeyboardButton("📊 Laporan", callback_data="menu_laporan"))
        markup.add(types.InlineKeyboardButton("📝 Pendaftaran Baru Anak-Anak", callback_data="pendaftaran"))
        markup.add(types.InlineKeyboardButton("❌ Keluarkan Dari Senarai", callback_data="keluarkan"))
        markup.add(types.InlineKeyboardButton("👶 Check-In/Out Anak-Anak", callback_data="m_ci"))
        markup.add(types.InlineKeyboardButton("🕒 Staff Clock In / Out", callback_data="m_sc"))
        
        bot.edit_message_text("👑 **Menu Utama Admin Taska**\nSila pilih tindakan di bawah:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    else:
        markup.add(types.InlineKeyboardButton("👶 Check-In/Out Anak-Anak", callback_data="m_ci"))
        markup.add(types.InlineKeyboardButton("🕒 Staff Clock In / Out", callback_data="m_sc"))
        
        bot.edit_message_text("👩‍💼 **Menu Utama Staf Taska**\nSila pilih tindakan di bawah:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- 4. MENU LAPORAN & PEMBAYARAN (ADMIN) ---
@bot.callback_query_handler(func=lambda call: call.data == "menu_laporan")
def menu_laporan(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Laporan Pembayaran", callback_data="menu_pembayaran"))
    markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
    
    bot.edit_message_text("📊 **Menu Laporan**\nSila pilih jenis laporan:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "menu_pembayaran")
def menu_pembayaran(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏡 Taska Corner", callback_data="cawangan_corner"))
    markup.add(types.InlineKeyboardButton("🏫 Taska Hadhari", callback_data="cawangan_hadhari"))
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="menu_laporan"))
    
    bot.edit_message_text("🏢 **Sila pilih cawangan Taska:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ["cawangan_corner", "cawangan_hadhari"])
def pilih_cawangan(call):
    caw_key = "corner" if "corner" in call.data else "hadhari"
    caw_name = "Taska Corner" if caw_key == "corner" else "Taska Hadhari"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Sudah Lunas", callback_data=f"status_lunas_{caw_key}"))
    markup.add(types.InlineKeyboardButton("⏳ Belum Bayar", callback_data=f"status_belum_{caw_key}"))
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="menu_pembayaran"))
    
    bot.edit_message_text(f"📌 **{caw_name} - Status Yuran**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("status_"))
def papar_senarai_status(call):
    parts = call.data.split("_")
    status_type = parts[1]
    caw_key = parts[2]
    caw_name = "Taska Corner" if caw_key == "corner" else "Taska Hadhari"
    db_status = "Lunas" if status_type == "lunas" else "Belum Bayar"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nama FROM pelajar WHERE cawangan = %s AND status_bayaran = %s", (caw_name, db_status))
    senarai = cursor.fetchall()
    cursor.close()
    conn.close()
    
    text = f"📋 **Senarai Pelajar ({caw_name}) - {db_status}:**\n\n"
    if senarai:
        for idx, row in enumerate(senarai, 1):
            text += f"{idx}. {row[0]}\n"
    else:
        text += "_Tiada rekod dijumpai._\n"
        
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data=f"cawangan_{caw_key}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- 5. PENDAFTARAN & PADAM NAMA (ADMIN) ---
@bot.callback_query_handler(func=lambda call: call.data == "pendaftaran")
def pendaftaran_mulai(call):
    bot.edit_message_text("📝 **Pendaftaran Baru**\n\nSila hantar nama penuh anak:", call.message.chat.id, call.message.message_id, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Batal", callback_data="back_start")), parse_mode="Markdown")
    bot.register_next_step_handler(call.message, terima_nama_pendaftaran)

def terima_nama_pendaftaran(message):
    if message.text.startswith("/"): return
    nama_anak = message.text.strip()
    user_temp_data[message.chat.id] = nama_anak
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏡 Taska Corner", callback_data="reg_caw_corner"))
    markup.add(types.InlineKeyboardButton("🏫 Taska Hadhari", callback_data="reg_caw_hadhari"))
    markup.add(types.InlineKeyboardButton("❌ Batal", callback_data="back_start"))
    
    bot.send_message(message.chat.id, f"👤 Nama: **{nama_anak}**\nPilih cawangan:", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ["reg_caw_corner", "reg_caw_hadhari"])
def simpan_pendaftaran(call):
    caw_name = "Taska Corner" if "corner" in call.data else "Taska Hadhari"
    nama_anak = user_temp_data.get(call.message.chat.id)
    if not nama_anak:
        bot.answer_callback_query(call.id, "Sesi tamat.", show_alert=True)
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pelajar (nama, cawangan, status_bayaran, status_hadir) VALUES (%s, %s, 'Belum Bayar', 'Check-Out')", (nama_anak, caw_name))
    conn.commit()
    cursor.close()
    conn.close()
    user_temp_data.pop(call.message.chat.id, None)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Daftar Lagi", callback_data="pendaftaran"))
    markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
    bot.edit_message_text(f"✅ Berjaya mendaftar *{nama_anak}* di *{caw_name}*!", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

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
            short_caw = "Corner" if cawangan == "Taska Corner" else "Hadhari"
            markup.add(types.InlineKeyboardButton(f"❌ {nama} ({short_caw})", callback_data=f"del_{p_id}"))
    else:
        bot.answer_callback_query(call.id, "Tiada rekod.", show_alert=True)
        return
    markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
    bot.edit_message_text("❌ Klik nama anak yang ingin dikeluarkan:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def proses_padam(call):
    p_id = call.data.split("_")[1]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nama, cawangan FROM pelajar WHERE id = %s", (p_id,))
    res = cursor.fetchone()
    if res:
        nama, cawangan = res
        cursor.execute("DELETE FROM pelajar WHERE id = %s", (p_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
        bot.edit_message_text(f"🗑️ *{nama}* dari *{cawangan}* telah dipadam.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- 6. CHECK-IN / CHECK-OUT ANAK-ANAK (UNTUK STAF & ADMIN) ---
@bot.callback_query_handler(func=lambda call: call.data == "m_ci")
def menu_checkin(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⚡ Check-In Masa Terkini", callback_data="ci_live"))
    markup.add(types.InlineKeyboardButton("✍️ Check-In Manual", callback_data="ci_man"))
    markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
    
    bot.edit_message_text("👶 **Sistem Kehadiran Anak-Anak**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "ci_live")
def list_pelajar_terkini(call):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nama, cawangan, status_hadir FROM pelajar ORDER BY cawangan, nama")
    pelajar_list = cursor.fetchall()
    cursor.close()
    conn.close()
    
    markup = types.InlineKeyboardMarkup()
    if pelajar_list:
        for row in pelajar_list:
            p_id, nama, cawangan, status = row
            icon = "🟢" if status == "Check-In" else "🔴"
            short_caw = "Corner" if cawangan == "Taska Corner" else "Hadhari"
            markup.add(types.InlineKeyboardButton(f"{icon} {nama} ({short_caw})", callback_data=f"cl_{p_id}"))
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="m_ci"))
    
    bot.edit_message_text("⚡ Klik nama anak untuk Check-In masa sekarang:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("cl_"))
def proses_ci_live(call):
    p_id = call.data.split("_")[1]
    waktu_sekarang = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE pelajar SET status_hadir = 'Check-In' WHERE id = %s", (p_id,))
    cursor.execute("SELECT nama, cawangan FROM pelajar WHERE id = %s", (p_id,))
    res = cursor.fetchone()
    conn.commit()
    cursor.close()
    conn.close()
    
    if res:
        nama, cawangan = res
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
        bot.edit_message_text(f"✅ *{nama}* ({cawangan}) berjaya Check-In pada *{waktu_sekarang}*!", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "ci_man")
def list_pelajar_manual(call):
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
            short_caw = "Corner" if cawangan == "Taska Corner" else "Hadhari"
            markup.add(types.InlineKeyboardButton(f"✍️ {nama} ({short_caw})", callback_data=f"cm_{p_id}"))
    markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="m_ci"))
    
    bot.edit_message_text("✍️ Pilih anak untuk Check-In manual:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("cm_"))
def setup_ci_manual(call):
    p_id = call.data.split("_")[1]
    user_temp_data[call.message.chat.id] = p_id
    bot.edit_message_text("✍️ Sila hantar masa manual (Contoh: `08:30 AM`):", call.message.chat.id, call.message.message_id, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Batal", callback_data="ci_man")), parse_mode="Markdown")
    bot.register_next_step_handler(call.message, terima_masa_manual)

def terima_masa_manual(message):
    if message.text.startswith("/"): return
    p_id = user_temp_data.get(message.chat.id)
    masa_manual = message.text.strip()
    if not p_id: return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE pelajar SET status_hadir = 'Check-In' WHERE id = %s", (p_id,))
    cursor.execute("SELECT nama, cawangan FROM pelajar WHERE id = %s", (p_id,))
    res = cursor.fetchone()
    conn.commit()
    cursor.close()
    conn.close()
    user_temp_data.pop(message.chat.id, None)
    
    if res:
        nama, cawangan = res
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
        bot.send_message(message.chat.id, f"✅ *{nama}* ({cawangan}) direkodkan masuk pada *{masa_manual}*.", reply_markup=markup, parse_mode="Markdown")

# --- 7. STAFF CLOCK IN / OUT ---
@bot.callback_query_handler(func=lambda call: call.data == "m_sc")
def menu_staff_clock(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🟢 Clock In", callback_data="s_in"))
    markup.add(types.InlineKeyboardButton("🔴 Clock Out", callback_data="s_out"))
    markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
    bot.edit_message_text("🕒 Kehadiran Staf:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ["s_in", "s_out"])
def staff_action_prompt(call):
    action = "Clock In" if call.data == "s_in" else "Clock Out"
    user_temp_data[call.message.chat.id] = action
    bot.edit_message_text(f"🕒 Sila hantar **nama penuh anda** untuk {action}:", call.message.chat.id, call.message.message_id, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Batal", callback_data="m_sc")), parse_mode="Markdown")
    bot.register_next_step_handler(call.message, simpan_staff_clock)

def simpan_staff_clock(message):
    if message.text.startswith("/"): return
    staff_name = message.text.strip()
    action = user_temp_data.get(message.chat.id, "Clock In")
    waktu_sekarang = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO staff_attendance (staff_name, action_type, timestamp) VALUES (%s, %s, %s)", (staff_name, action, waktu_sekarang))
    conn.commit()
    cursor.close()
    conn.close()
    user_temp_data.pop(message.chat.id, None)
    
    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
    bot.send_message(message.chat.id, f"✅ *{staff_name}* berjaya *{action}* pada *{waktu_sekarang}*.", reply_markup=markup, parse_mode="Markdown")

# --- 8. JALANKAN WEBHOOK ---
if __name__ == "__main__":
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        bot.remove_webhook()
        bot.set_webhook(url=f"{render_url}/{TOKEN}")
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
