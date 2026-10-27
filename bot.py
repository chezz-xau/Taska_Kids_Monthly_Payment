import os
import psycopg2
import telebot
from telebot import types
from flask import Flask, request
from datetime import datetime

TOKEN = os.environ.get("TELEGRAM_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

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
            ("Ali bin Abu", "Taska Corner", "Check-Out"),
            ("Siti binti Omar", "Taska Corner", "Check-Out"),
            ("Ahmad bin Ali", "Taska Hadhari", "Check-Out"),
            ("Fatima binti Hassan", "Taska Hadhari", "Check-Out")
        ]
        cursor.executemany("INSERT INTO pelajar (nama, cawangan, status_hadir) VALUES (%s, %s, %s)", sample_data)
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
    return "Bot Staf Taska sedang aktif!"

# --- 3. MENU UTAMA STAF ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👶 Check-In/Out Anak-Anak", callback_data="m_ci"))
    markup.add(types.InlineKeyboardButton("🕒 Staff Clock In / Out", callback_data="m_sc"))
    
    bot.send_message(message.chat.id, "👩‍💼 **Menu Utama Staf Taska**\nSila pilih tindakan di bawah:", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "back_start")
def back_to_start(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👶 Check-In/Out Anak-Anak", callback_data="m_ci"))
    markup.add(types.InlineKeyboardButton("🕒 Staff Clock In / Out", callback_data="m_sc"))
    
    bot.edit_message_text("👩‍💼 **Menu Utama Staf Taska**\nSila pilih tindakan di bawah:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- 4. BAHAGIAN CHECK-IN / CHECK-OUT ANAK-ANAK ---
@bot.callback_query_handler(func=lambda call: call.data == "m_ci")
def menu_checkin(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⚡ Check-In Masa Terkini", callback_data="ci_live"))
    markup.add(types.InlineKeyboardButton("✍️ Check-In Manual (Pilih Masa)", callback_data="ci_man"))
    markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
    
    bot.edit_message_text("👶 **Sistem Kehadiran Anak-Anak**\nSila pilih kaedah check-in:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# A. Check-In Masa Terkini
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
    
    bot.edit_message_text("⚡ **Check-In Masa Terkini**\nKlik pada nama anak untuk rekod kehadiran masuk dengan masa sekarang:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

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
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Senarai Anak", callback_data="ci_live"))
        markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
        
        bot.edit_message_text(f"✅ **Berjaya Check-In!**\n\nNama: *{nama}*\nCawangan: *{cawangan}*\nMasa: *{waktu_sekarang}*", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "Ralat rekod tidak dijumpai.", show_alert=True)

# B. Check-In Manual
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
    
    bot.edit_message_text("✍️ **Check-In Manual**\nPilih anak yang ingin dimasukkan masa secara manual:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("cm_"))
def setup_ci_manual(call):
    p_id = call.data.split("_")[1]
    user_temp_data[call.message.chat.id] = p_id
    
    bot.edit_message_text("✍️ **Masukkan Masa Manual**\n\nSila hantar teks masa kehadiran (Contoh: `08:30 AM` atau `07:45 Pagi`):", call.message.chat.id, call.message.message_id, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Batal", callback_data="ci_man")), parse_mode="Markdown")
    bot.register_next_step_handler(call.message, terima_masa_manual)

def terima_masa_manual(message):
    if message.text.startswith("/"):
        return
        
    p_id = user_temp_data.get(message.chat.id)
    masa_manual = message.text.strip()
    
    if not p_id:
        bot.send_message(message.chat.id, "Sesi tamat. Sila mula semula.")
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE pelajar SET status_hadir = 'Check-In' WHERE id = %s", (p_id,))
    cursor.execute("SELECT nama, cawangan FROM pelajar WHERE id = %s", (p_id,))
    res = cursor.fetchone()
    conn.commit()
    cursor.close()
    conn.close()
    
    user_temp_data.pop(message.chat.id, None)
    nama, cawangan = res
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
    
    bot.send_message(message.chat.id, f"✅ **Check-In Manual Berjaya!**\n\nNama: *{nama}*\nCawangan: *{cawangan}*\nMasa Direkod: *{masa_manual}*", reply_markup=markup, parse_mode="Markdown")

# --- 5. BAHAGIAN STAFF CLOCK IN / OUT ---
@bot.callback_query_handler(func=lambda call: call.data == "m_sc")
def menu_staff_clock(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🟢 Clock In (Masuk Kerja)", callback_data="s_in"))
    markup.add(types.InlineKeyboardButton("🔴 Clock Out (Balik Kerja)", callback_data="s_out"))
    markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
    
    bot.edit_message_text("🕒 **Kehadiran Staf (Clock In/Out)**\nSila pilih tindakan:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ["s_in", "s_out"])
def staff_action_prompt(call):
    action = "Clock In" if call.data == "s_in" else "Clock Out"
    user_temp_data[call.message.chat.id] = action
    
    bot.edit_message_text(f"🕒 **Staff {action}**\n\nSila hantar teks **nama penuh anda**:", call.message.chat.id, call.message.message_id, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Batal", callback_data="m_sc")), parse_mode="Markdown")
    bot.register_next_step_handler(call.message, simpan_staff_clock)

def simpan_staff_clock(message):
    if message.text.startswith("/"):
        return
        
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
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
    
    bot.send_message(message.chat.id, f"✅ **Rekod Staf Berjaya!**\n\nNama: *{staff_name}*\nTindakan: *{action}*\nMasa: *{waktu_sekarang}*", reply_markup=markup, parse_mode="Markdown")

# --- 6. MENJALANKAN APLIKASI WEBHOOK ---
if __name__ == "__main__":
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        bot.remove_webhook()
        bot.set_webhook(url=f"{render_url}/{TOKEN}")
        print(f"Webhook staf berjaya dipasang ke: {render_url}/{TOKEN}")
        
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
