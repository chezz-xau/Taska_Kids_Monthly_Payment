import os
from datetime import datetime, timedelta, timezone
import psycopg2
from flask import Flask, abort, request as flask_request
import telebot
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# 1. Konfigurasi Token Bot & ID Owner
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN tidak ditetapkan dalam environment variables!")

OWNER_ID_STR = os.environ.get("OWNER_IDS", "")
OWNER_IDS = [int(i.strip()) for i in OWNER_ID_STR.split(",") if i.strip().isdigit()]

DATABASE_URL = os.environ.get("DATABASE_URL")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Zon Masa Malaysia (UTC+8)
MY_TZ = timezone(timedelta(hours=8))

# Cawangan Taska & Senarai Staf/Anak
BRANCHES_LIST = ["Taska Corner", "Taska Hadhari"]
staff_corner_str = os.environ.get("STAFF_TASKA_CORNER", "Siti Maryam, Adam Harith")
staff_hadhari_str = os.environ.get("STAFF_TASKA_HADHARI", "Siti Maryam, Adam Harith")

BRANCH_STAFF = {
    "Taska Corner": [s.strip() for s in staff_corner_str.split(",") if s.strip()],
    "Taska Hadhari": [s.strip() for s in staff_hadhari_str.split(",") if s.strip()]
}

def get_staff_list(branch):
    return BRANCH_STAFF.get(branch, ["Siti Maryam", "Adam Harith"])

KIDS_LIST = ["Ahmad", "Aisha", "Rayyan"]

user_branches = {}
user_states = {}


# --- FUNGSI DATABASE (NEON POSTGRESQL) ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    if not DATABASE_URL:
        print("Amaran: DATABASE_URL tidak dijumpai!")
        return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS attendance_records (
            branch TEXT,
            category TEXT,
            name TEXT,
            time_str TEXT,
            record_date TEXT,
            PRIMARY KEY (branch, category, name, record_date)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS kids_fees (
            branch TEXT,
            kid_name TEXT,
            perlu NUMERIC,
            dibayar NUMERIC,
            PRIMARY KEY (branch, kid_name)
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()


def db_save_record(branch, category, name, time_str):
    today_str = datetime.now(MY_TZ).strftime("%Y-%m-%d")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO attendance_records (branch, category, name, time_str, record_date)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (branch, category, name, record_date) 
        DO UPDATE SET time_str = EXCLUDED.time_str
    ''', (branch, category, name, time_str, today_str))
    conn.commit()
    cur.close()
    conn.close()

def db_remove_record(branch, category, name):
    today_str = datetime.now(MY_TZ).strftime("%Y-%m-%d")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        DELETE FROM attendance_records 
        WHERE branch = %s AND category = %s AND name = %s AND record_date = %s
    ''', (branch, category, name, today_str))
    conn.commit()
    cur.close()
    conn.close()

def db_get_records(branch, category):
    today_str = datetime.now(MY_TZ).strftime("%Y-%m-%d")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT name, time_str FROM attendance_records 
        WHERE branch = %s AND category = %s AND record_date = %s
    ''', (branch, category, today_str))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {row[0]: row[1] for row in rows}


# --- KEYBOARD MENUS ---
def get_main_branch_menu():
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        KeyboardButton("🏠 Taska Corner"),
        KeyboardButton("🏠 Taska Hadhari")
    )
    return markup

def get_owner_sub_menu(branch_name):
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        KeyboardButton("⏱️ Late Pick Up Charges")
    )
    markup.add(
        KeyboardButton("📝 Pendaftaran Baru Anak-Anak")
    )
    markup.add(
        KeyboardButton("💳 Status & Bayaran Yuran"),
        KeyboardButton("📊 Laporan")
    )
    markup.add(
        KeyboardButton("❌ Keluarkan Dari Senarai")
    )
    return markup

# Menu Staff Ditambah Butang Check-In/Out Manual
def get_staff_sub_menu(branch_name):
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        KeyboardButton("📥 Check-In Anak"),
        KeyboardButton("📤 Check-Out Anak")
    )
    markup.add(
        KeyboardButton("✍️ Manual Check-In/Out Anak")
    )
    markup.add(
        KeyboardButton("🟢 Clock-In Staff"),
        KeyboardButton("🔴 Clock-Out Staff")
    )
    return markup

def get_appropriate_sub_menu(user_id, branch_name):
    if OWNER_IDS and user_id in OWNER_IDS:
        return get_owner_sub_menu(branch_name)
    else:
        return get_staff_sub_menu(branch_name)


# --- FLASK ROUTES ---
@app.route("/")
def index():
    return "Bot Taska dengan Neon Database sedang aktif!", 200

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    if flask_request.headers.get("content-type") == "application/json":
        json_string = flask_request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "", 200
    else:
        abort(403)


# --- TELEGRAM HANDLERS ---
@bot.message_handler(commands=["start", "menu"])
def send_welcome(message):
    bot.reply_to(
        message,
        "Selamat datang! Sila pilih cawangan taska anda:",
        reply_markup=get_main_branch_menu(),
    )

@bot.message_handler(
    func=lambda message: message.text in ["🏠 Taska Corner", "🏠 Taska Hadhari"]
)
def handle_branch_selection(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    branch = message.text.replace("🏠 ", "")
    user_branches[chat_id] = branch

    reply_markup = get_appropriate_sub_menu(user_id, branch)
    role_text = "(Mod Owner)" if (OWNER_IDS and user_id in OWNER_IDS) else "(Mod Staff)"

    bot.reply_to(
        message,
        f"Anda telah memilih *{branch}* {role_text}.\nSila pilih menu tindakan di bawah:",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )

@bot.message_handler(
    func=lambda message: message.text and "Check-In Anak" in message.text
)
def handle_check_in_anak(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska Corner")
    checked_in_today = db_get_records(branch, "kid_checkin")

    markup = InlineKeyboardMarkup()
    for name in KIDS_LIST:
        if name in checked_in_today:
            time_str = checked_in_today[name]
            markup.add(
                InlineKeyboardButton(
                    f"🔴 {name} (Sudah Check-In: {time_str})", callback_data=f"ignore_{name}"
                )
            )
        else:
            markup.add(
                InlineKeyboardButton(
                    f"📥 {name} (Check-In)", callback_data=f"checkin_kid_{name}"
                )
            )

    bot.reply_to(
        message, f"[{branch}]\nSila pilih nama anak untuk Check-In:", reply_markup=markup
    )

@bot.message_handler(
    func=lambda message: message.text and "Check-Out Anak" in message.text
)
def handle_check_out_anak(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska Corner")
    checked_in_today = db_get_records(branch, "kid_checkin")
    
    markup = InlineKeyboardMarkup()
    for name in KIDS_LIST:
        if name in checked_in_today:
            time_str = checked_in_today[name]
            markup.add(
                InlineKeyboardButton(
                    f"📤 {name} (Check-In jam {time_str})", callback_data=f"checkout_kid_{name}"
                )
            )
        else:
            markup.add(
                InlineKeyboardButton(
                    f"⚪ {name} (Belum Check-In)", callback_data=f"ignore_uncheck_{name}"
                )
            )
            
    bot.reply_to(
        message, f"[{branch}]\nSila pilih nama anak untuk Check-Out:", reply_markup=markup
    )

# Handler untuk Butang Manual Check-In/Out
@bot.message_handler(
    func=lambda message: message.text and "Manual Check-In/Out Anak" in message.text
)
def handle_manual_attendance(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska Corner")
    
    markup = InlineKeyboardMarkup()
    for name in KIDS_LIST:
        markup.add(
            InlineKeyboardButton(f"✍️ Manual: {name}", callback_data=f"manual_kid_{branch}_{name}")
        )
        
    bot.reply_to(
        message,
        f"[{branch}] ✍️ **Sila pilih nama anak untuk tetapan masa manual:**",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(
    func=lambda message: message.text and "Late Pick Up Charges" in message.text
)
def handle_late_pickup(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska Corner")
    bot.reply_to(
        message,
        f"⏱️ **[{branch}] Semakan Caj Late Pick Up**\n\nSila pilih nama anak atau semak rekod kelewatan pengambilan.",
        parse_mode="Markdown"
    )

@bot.message_handler(
    func=lambda message: message.text and "Clock-In Staff" in message.text
)
def handle_clock_in_staff(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska Corner")
    clocked_in_today = db_get_records(branch, "staff_clockin")
    staff_list = get_staff_list(branch)

    markup = InlineKeyboardMarkup()
    for name in staff_list:
        if name in clocked_in_today:
            time_str = clocked_in_today[name]
            markup.add(
                InlineKeyboardButton(
                    f"🟢 {name} (Sudah Hadir: {time_str})", callback_data=f"ignore_{name}"
                )
            )
        else:
            markup.add(
                InlineKeyboardButton(
                    f"🔴 {name} (Belum Hadir)", callback_data=f"clockin_staff_{name}"
                )
            )

    bot.reply_to(
        message, f"[{branch}]\nSila pilih nama staff untuk Clock-In:", reply_markup=markup
    )

@bot.message_handler(
    func=lambda message: message.text and "Clock-Out Staff" in message.text
)
def handle_clock_out_staff(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska Corner")
    clocked_in_today = db_get_records(branch, "staff_clockin")
    staff_list = get_staff_list(branch)
    
    markup = InlineKeyboardMarkup()
    for name in staff_list:
        if name in clocked_in_today:
            time_str = clocked_in_today[name]
            markup.add(
                InlineKeyboardButton(
                    f"🔴 {name} (Clock-In: {time_str})", callback_data=f"clockout_staff_{name}"
                )
            )
        else:
            markup.add(
                InlineKeyboardButton(
                    f"⚪ {name} (Belum Clock-In)", callback_data=f"ignore_uncheck_{name}"
                )
            )

    bot.reply_to(
        message, f"[{branch}]\nSila pilih nama staff untuk Clock-Out:", reply_markup=markup
    )

@bot.message_handler(
    func=lambda message: message.text and "Pendaftaran Baru Anak-Anak" in message.text
)
def handle_pendaftaran_baru(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🏠 Taska Corner", callback_data="reg_branch_Taska Corner"),
        InlineKeyboardButton("🏠 Taska Hadhari", callback_data="reg_branch_Taska Hadhari")
    )
    bot.reply_to(
        message,
        "📝 **Menu Pendaftaran Baru Anak-Anak**\n\nSila pilih cawangan taska untuk pendaftaran:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(
    func=lambda message: message.text and "Keluarkan Dari Senarai" in message.text
)
def handle_keluarkan_senarai(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🏠 Taska Corner", callback_data="rem_branch_Taska Corner"),
        InlineKeyboardButton("🏠 Taska Hadhari", callback_data="rem_branch_Taska Hadhari")
    )
    bot.reply_to(
        message,
        "❌ **Menu Keluarkan Dari Senarai**\n\nSila pilih cawangan taska:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(
    func=lambda message: message.text and "Status & Bayaran Yuran" in message.text
)
def handle_status_yuran(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🏠 Taska Corner", callback_data="fee_branch_Taska Corner"),
        InlineKeyboardButton("🏠 Taska Hadhari", callback_data="fee_branch_Taska Hadhari")
    )
    bot.reply_to(
        message,
        "💳 **Menu Status & Bayaran Yuran**\n\nSila pilih cawangan taska:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(
    func=lambda message: message.text and "Laporan" in message.text
)
def handle_laporan(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    branch = user_branches.get(chat_id, "Taska Corner")
    today_str = datetime.now(MY_TZ).strftime("%Y-%m-%d")
    
    checked_in_kids = db_get_records(branch, "kid_checkin")
    clocked_staff = db_get_records(branch, "staff_clockin")
    
    report_text = f"📊 **Laporan Semasa - [{branch}] ({today_str})**\n\n"
    report_text += f"👶 **Anak Sedang Check-In:**\n"
    if checked_in_kids:
        for name, time_str in checked_in_kids.items():
            report_text += f"• <u>{name}</u> — 🟢 Check-In pada *{time_str}*\n"
    else:
        report_text += "• Tiada\n"
        
    report_text += f"\n👤 **Staff Hadir (Clock-In):**\n"
    if clocked_staff:
        for name, time_str in clocked_staff.items():
            report_text += f"• <u>{name}</u> — 🟢 Clock-In pada *{time_str}*\n"
    else:
        report_text += "• Tiada\n"

    reply_markup = get_appropriate_sub_menu(user_id, branch)
    bot.reply_to(
        message, report_text, parse_mode="HTML", reply_markup=reply_markup
    )


# --- CALLBACK QUERY HANDLERS ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("checkin_kid_"))
def callback_checkin_kid(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska Corner")
    kid_name = call.data.replace("checkin_kid_", "")
    now_time = datetime.now(MY_TZ).strftime("%I:%M %p")
    
    db_save_record(branch, "kid_checkin", kid_name, now_time)
        
    bot.answer_callback_query(call.id, f"{kid_name} telah Check-In pada {now_time}!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📥 [{branch}] **{kid_name}** telah berjaya Check-In pada jam **{now_time}**!",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("checkout_kid_"))
def callback_checkout_kid(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska Corner")
    kid_name = call.data.replace("checkout_kid_", "")
    now_time = datetime.now(MY_TZ).strftime("%I:%M %p")
    
    checked_records = db_get_records(branch, "kid_checkin")
    checkin_time = checked_records.get(kid_name, "N/A")
    db_remove_record(branch, "kid_checkin", kid_name)
        
    bot.answer_callback_query(call.id, f"{kid_name} telah Check-Out pada {now_time}!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📤 [{branch}] **{kid_name}** telah berjaya Check-Out pada jam **{now_time}**!\n*(Check-In: {checkin_time})*",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("manual_kid_"))
def callback_manual_kid(call):
    parts = call.data.replace("manual_kid_", "").split("_", 1)
    branch = parts[0]
    kid_name = parts[1]
    chat_id = call.message.chat.id
    
    user_states[chat_id] = {"action": "input_manual_time", "branch": branch, "kid_name": kid_name}
    
    bot.answer_callback_query(call.id, f"Masukkan masa untuk {kid_name}")
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"✍️ [{branch}] **{kid_name}**\n\nSila taip masa secara manual (Contoh: `08:30 AM` atau `05:15 PM`):",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("clockin_staff_"))
def callback_clockin_staff(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska Corner")
    staff_name = call.data.replace("clockin_staff_", "")
    now_time = datetime.now(MY_TZ).strftime("%I:%M %p")
    
    db_save_record(branch, "staff_clockin", staff_name, now_time)
        
    bot.answer_callback_query(call.id, f"{staff_name} telah Clock-In pada {now_time}!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🟢 [{branch}] **{staff_name}** telah berjaya Clock-In pada jam **{now_time}**!",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("clockout_staff_"))
def callback_clockout_staff(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska Corner")
    staff_name = call.data.replace("clockout_staff_", "")
    now_time = datetime.now(MY_TZ).strftime("%I:%M %p")
    
    clocked_records = db_get_records(branch, "staff_clockin")
    clockin_time = clocked_records.get(staff_name, "N/A")
    db_remove_record(branch, "staff_clockin", staff_name)
        
    bot.answer_callback_query(call.id, f"{staff_name} telah Clock-Out pada {now_time}!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔴 [{branch}] **{staff_name}** telah berjaya Clock-Out pada jam **{now_time}**!\n*(Clock-In: {clockin_time})*",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("ignore_"))
def callback_ignore(call):
    bot.answer_callback_query(call.id, "Rekod sudah didaftarkan hari ini.")


@bot.message_handler(func=lambda message: True)
def handle_all_text_inputs(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Pengurusan Input Manual Masa Check-In Anak
    if chat_id in user_states and user_states[chat_id].get("action") == "input_manual_time":
        state = user_states.pop(chat_id)
        branch = state["branch"]
        kid_name = state["kid_name"]
        
        db_save_record(branch, "kid_checkin", kid_name, text)
        
        bot.reply_to(
            message,
            f"✅ **[{branch}] Rekod Manual Berjaya Disimpan!**\n\n👶 **{kid_name}** — Masa: *{text}*",
            parse_mode="Markdown",
            reply_markup=get_appropriate_sub_menu(user_id, branch)
        )
        return

    branch = user_branches.get(chat_id)
    reply_markup = get_appropriate_sub_menu(user_id, branch) if branch else get_main_branch_menu()
    bot.reply_to(
        message,
        "Sila gunakan butang menu di bawah.",
        reply_markup=reply_markup,
    )


# --- WEBHOOK & SERVER START ---
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
