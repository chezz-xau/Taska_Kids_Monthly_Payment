import os
import psycopg2
import telebot
from telebot import types
from flask import Flask, request

TOKEN = os.environ.get("TELEGRAM_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Simpanan sementara untuk proses pendaftaran baru / kemaskini bayaran
admin_temp_data = {}

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# --- 1. SETUP DATABASE ADMIN ---
def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pelajar (
                id SERIAL PRIMARY KEY,
                nama TEXT,
                cawangan TEXT,
                yuran_kena_bayar NUMERIC DEFAULT 0,
                jumlah_dibayar NUMERIC DEFAULT 0,
                status_bayaran TEXT DEFAULT 'Belum Lunas'
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

init_db()

# --- 2. WEBHOOK & RENDER CONFIG ---
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
    return "Bot Admin Taska sedang aktif!"

render_url = os.environ.get("RENDER_EXTERNAL_URL")
if render_url:
    try:
        bot.remove_webhook()
        bot.set_webhook(url=f"{render_url}/{TOKEN}")
    except Exception as e:
        print(f"Webhook Error: {e}")

# --- 3. MENU UTAMA ADMIN ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    menu_utama_admin(message.chat.id, message.message_id, is_new=True)

def menu_utama_admin(chat_id, message_id=None, is_new=False):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Pendaftaran Pelajar Baru", callback_data="adm_daftar"))
    markup.add(types.InlineKeyboardButton("📋 Senarai Nama & Status Pelajar", callback_data="adm_senarai"))
    markup.add(types.InlineKeyboardButton("💰 Semak Status & Rekod Bayaran", callback_data="adm_yuran"))
    
    text = "👑 **Menu Utama Admin Taska**\nSila pilih fungsi pengurusan di bawah:"
    if is_new:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    else:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# --- 4. CALLBACK HANDLER UNTUK ADMIN ---
@bot.callback_query_handler(func=lambda call: True)
def handle_admin_callbacks(call):
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    data = call.data

    if data == "back_start":
        menu_utama_admin(chat_id, msg_id)

    # --- PENDAFTARAN BARU ---
    elif data == "adm_daftar":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🏢 Taska Corner", callback_data="reg_c_Taska Corner"))
        markup.add(types.InlineKeyboardButton("🏢 Taska Hadhari", callback_data="reg_c_Taska Hadhari"))
        markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
        bot.edit_message_text("➕ Pilih cawangan untuk pendaftaran pelajar baru:", chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("reg_c_"):
        cawangan = data.split("_", 2)[2]
        admin_temp_data[chat_id] = {"cawangan": cawangan}
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Batal", callback_data="adm_daftar"))
        bot.edit_message_text(f"📝 Pendaftaran untuk **{cawangan}**.\n\nSila hantar **Nama Penuh Anak**:", chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
        bot.register_next_step_handler(call.message, terima_nama_pelajar)

    # --- SENARAI NAMA PELAJAR ---
    elif data == "adm_senarai":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nama, cawangan FROM pelajar ORDER BY cawangan, nama")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        markup = types.InlineKeyboardMarkup()
        if rows:
            for r in rows:
                p_id, nama, cawangan = r
                short_caw = "Corner" if cawangan == "Taska Corner" else "Hadhari"
                markup.add(types.InlineKeyboardButton(f"👤 {nama} ({short_caw})", callback_data=f"detail_{p_id}"))
        markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
        bot.edit_message_text("📋 **Senarai Nama Pelajar**\nKlik nama pelajar untuk lihat butiran lanjut:", chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("detail_"):
        p_id = data.split("_")[1]
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT nama, cawangan, yuran_kena_bayar, jumlah_dibayar, status_bayaran FROM pelajar WHERE id = %s", (p_id,))
        res = cursor.fetchone()
        cursor.close()
        conn.close()

        if res:
            nama, cawangan, yuran, bayar, status = res
            baki = float(yuran) - float(bayar)
            text = (
                f"👤 **Maklumat Pelajar**\n\n"
                f"• **Nama:** {nama}\n"
                f"• **Cawangan:** {cawangan}\n"
                f"• **Yuran Kena Bayar:** RM {yuran}\n"
                f"• **Sudah Bayar:** RM {bayar}\n"
                f"• **Baki:** RM {baki}\n"
                f"• **Status:** {status}"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🗑️ Padam Pelajar", callback_data=f"del_{p_id}"))
            markup.add(types.InlineKeyboardButton("🔙 Senarai Pelajar", callback_data="adm_senarai"))
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("del_"):
        p_id = data.split("_")[1]
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pelajar WHERE id = %s", (p_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Senarai Pelajar", callback_data="adm_senarai"))
        bot.edit_message_text("🗑️ Rekod pelajar telah berjaya dipadam.", chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

    # --- SEMAK & KEMASKINI YURAN ---
    elif data == "adm_yuran":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nama, cawangan, status_bayaran FROM pelajar ORDER BY cawangan, nama")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        markup = types.InlineKeyboardMarkup()
        if rows:
            for r in rows:
                p_id, nama, cawangan, status = r
                icon = "🟢" if status == "Lunas" else "🔴"
                short_caw = "Corner" if cawangan == "Taska Corner" else "Hadhari"
                markup.add(types.InlineKeyboardButton(f"{icon} {nama} ({status})", callback_data=f"pay_{p_id}"))
        markup.add(types.InlineKeyboardButton("🔙 Menu Utama", callback_data="back_start"))
        bot.edit_message_text("💰 **Pengurusan Yuran Bulanan**\nPilih pelajar untuk kemaskini bayaran:", chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("pay_"):
        p_id = data.split("_")[1]
        admin_temp_data[chat_id] = {"edit_id": p_id}
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Batal", callback_data="adm_yuran"))
        bot.edit_message_text("💵 Sila hantar **jumlah yuran penuh** (Contoh: `350`):", chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
        bot.register_next_step_handler(call.message, terima_jumlah_yuran)

# --- 5. NEXT STEP HANDLERS UNTUK INPUT ADMIN ---
def terima_nama_pelajar(message):
    if message.text and message.text.startswith("/"):
        return
    chat_id = message.chat.id
    nama = message.text.strip() if message.text else ""
    
    if chat_id not in admin_temp_data:
        bot.send_message(chat_id, "⚠️ Sesi tamat. Sila mula semula dari /start.")
        return
    
    admin_temp_data[chat_id]["nama"] = nama
    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Batal", callback_data="adm_daftar"))
    bot.send_message(chat_id, f"💵 Sila hantar **jumlah yuran kena bayar** untuk *{nama}* (Contoh: `350`):", reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(message, terima_yuran_pendaftaran)

def terima_yuran_pendaftaran(message):
    if message.text and message.text.startswith("/"):
        return
    chat_id = message.chat.id
    
    if chat_id not in admin_temp_data:
        bot.send_message(chat_id, "⚠️ Sesi tamat. Sila mula semula dari /start.")
        return
    
    try:
        yuran = float(message.text.strip())
    except ValueError:
        bot.send_message(chat_id, "❌ Sila masukkan nombor sahaja (Contoh: 350). Cuba hantar semula:")
        bot.register_next_step_handler(message, terima_yuran_pendaftaran)
        return

    data = admin_temp_data.pop(chat_id)
    nama = data["nama"]
    cawangan = data["cawangan"]

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO pelajar (nama, cawangan, yuran_kena_bayar, jumlah_dibayar, status_bayaran) VALUES (%s, %s, %s, 0, 'Belum Lunas')",
            (nama, cawangan, yuran)
        )
        conn.commit()
        cursor.close()
        conn.close()

        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("👑 Menu Utama", callback_data="back_start"))
        bot.send_message(chat_id, f"✅ Berjaya mendaftarkan **{nama}** di **{cawangan}** dengan yuran RM {yuran}!", reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ralat database: {e}")

def terima_jumlah_yuran(message):
    if message.text and message.text.startswith("/"):
        return
    chat_id = message.chat.id
    
    if chat_id not in admin_temp_data:
        bot.send_message(chat_id, "⚠️ Sesi tamat. Sila mula semula dari /start.")
        return
    
    try:
        yuran = float(message.text.strip())
    except ValueError:
        bot.send_message(chat_id, "❌ Sila masukkan nombor sahaja. Cuba hantar semula jumlah yuran:")
        bot.register_next_step_handler(message, terima_jumlah_yuran)
        return

    admin_temp_data[chat_id]["yuran"] = yuran
    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Batal", callback_data="adm_yuran"))
    bot.send_message(chat_id, "💵 Sila hantar **jumlah wang yang telah dibayar** (Contoh: `350` atau `200`):", reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(message, terima_jumlah_dibayar)

def terima_jumlah_dibayar(message):
    if message.text and message.text.startswith("/"):
        return
    chat_id = message.chat.id
    
    if chat_id not in admin_temp_data:
        bot.send_message(chat_id, "⚠️ Sesi tamat. Sila mula semula dari /start.")
        return
    
    try:
        dibayar = float(message.text.strip())
    except ValueError:
        bot.send_message(chat_id, "❌ Sila masukkan nombor sahaja. Cuba hantar semula jumlah dibayar:")
        bot.register_next_step_handler(message, terima_jumlah_dibayar)
        return

    data = admin_temp_data.pop(chat_id)
    p_id = data["edit_id"]
    yuran = data["yuran"]

    status = "Lunas" if dibayar >= yuran else "Belum Lunas"
    baki = yuran - dibayar

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE pelajar SET yuran_kena_bayar = %s, jumlah_dibayar = %s, status_bayaran = %s WHERE id = %s",
            (yuran, dibayar, status, p_id)
        )
        cursor.execute("SELECT nama FROM pelajar WHERE id = %s", (p_id,))
        res = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        nama_pelajar = res[0] if res else "Pelajar"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("👑 Menu Utama", callback_data="back_start"))
        bot.send_message(
            chat_id,
            f"✅ Maklumat yuran **{nama_pelajar}** dikemaskini!\n\n"
            f"• Kena Bayar: RM {yuran}\n"
            f"• Sudah Bayar: RM {dibayar}\n"
            f"• Baki: RM {baki}\n"
            f"• Status: **{status}**",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ralat database: {e}")

# --- 6. LOCAL RUN ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
