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
    cursor.close()
    conn.close()

init_db()

# --- 2. WEBHOOK ROUTE & AUTO-SETUP ---
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

# Tetapkan webhook secara automatik semasa aplikasi mula berjalan di Render
render_url = os.environ.get("RENDER_EXTERNAL_URL")
if render_url:
    bot.remove_webhook()
    bot.set_webhook(url=f"{render_url}/{TOKEN}")

# --- 3. MENU UTAMA STAF ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👶 Check-In/Out Anak-Anak", callback_data="m_ci"))
    markup.add(types.InlineKeyboardButton("🕒 Staff Clock In / Out", callback_data="m_sc"))
    
    bot.send_message(message.chat.id, "👩‍💼 **Menu Utama Staf Taska**\nSila pilih tindakan di bawah:", reply_markup=markup, parse_mode="Markdown")

# --- 4. CENTRALIZED CALLBACK HANDLER ---
@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    if call.data == "m_ci":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⚡ Check-In Masa Terkini", callback_data="ci_live"))
        markup.add(types.InlineKeyboardButton("✍️ Check-In Manual", callback_data="ci_man"))
        markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
        bot.edit_message_text("👶 **Sistem Kehadiran Anak-Anak**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "ci_live":
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
                markup.add(types.InlineKeyboardButton(f"⚡ {nama} ({short_caw})", callback_data=f"live_{p_id}"))
        markup.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="m_ci"))
        bot.edit_message_text("⚡ [Live] Pilih anak untuk Check-In sekarang:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("live_"):
        parts = call.data.split("_")
        p_id = parts[1]
        waktu_sekarang = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE pelajar SET status_hadir = 'Check-In' WHERE id = %s", (p_id,))
        cursor.execute("SELECT nama, cawangan FROM pelajar WHERE id = %s", (p_id,))
        res = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        bot.answer_callback_query(call.id, "Berjaya Check-In!")
        
        if res:
            nama, cawangan = res
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
            bot.edit_message_text(f"✅ *{nama}* ({cawangan}) berjaya Check-In pada *{waktu_sekarang}*!", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.edit_message_text(f"✅ Pelajar ID {p_id} berjaya Check-In pada *{waktu_sekarang}*!", call.message.chat.id, call.message.message_id, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start")), parse_mode="Markdown")

    elif call.data == "ci_man":
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

    elif call.data.startswith("cm_"):
        p_id = call.data.split("_")[1]
        user_temp_data[call.message.chat.id] = p_id
        bot.edit_message_text("✍️ Sila hantar masa manual (Contoh: `08:30 AM`):", call.message.chat.id, call.message.message_id, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Batal", callback_data="ci_man")), parse_mode="Markdown")
        bot.register_next_step_handler(call.message, terima_masa_manual)

    elif call.data == "back_start":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("👶 Check-In/Out Anak-Anak", callback_data="m_ci"))
        markup.add(types.InlineKeyboardButton("🕒 Staff Clock In / Out", callback_data="m_sc"))
        bot.edit_message_text("👩‍💼 **Menu Utama Staf Taska**\nSila pilih tindakan di bawah:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "m_sc":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🟢 Clock In", callback_data="s_in"))
        markup.add(types.InlineKeyboardButton("🔴 Clock Out", callback_data="s_out"))
        markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
        bot.edit_message_text("🕒 Kehadiran Staf:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data in ["s_in", "s_out"]:
        action = "Clock In" if call.data == "s_in" else "Clock Out"
        user_temp_data[call.message.chat.id] = action
        bot.edit_message_text(f"🕒 Sila hantar **nama penuh anda** untuk {action}:", call.message.chat.id, call.message.message_id, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Batal", callback_data="m_sc")), parse_mode="Markdown")
        bot.register_next_step_handler(call.message, simpan_staff_clock)

# --- 5. NEXT STEP HANDLERS ---
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

# --- 6. LOCAL RUN (Fallback) ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
