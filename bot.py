import os
from datetime import datetime, timedelta, timezone
from flask import Flask, abort, request as flask_request
import telebot
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from apscheduler.schedulers.background import BackgroundScheduler

# ==========================================
# ⚙️ TETAPAN UTAMA & KAWALAN AKSES (ROLES)
# ==========================================
TELEGRAM_TOKEN = "8675996323:AAFFlD67gt2HXet63MKEo08iJYm8ojVcol0"  # Token Bot Anda
TELEGRAM_CHAT_ID = "8353544393"                       # Chat ID Owner (Laporan 11 malam)

# Senarai ID Telegram Owner & Staff
OWNER_IDS = ["8353544393"]               # Masukkan Chat ID Owner
STAFF_IDS = ["111222333", "444555666"]      # Masukkan Chat ID Staff
# ==========================================

if not TELEGRAM_TOKEN:
    raise ValueError("Sila masukkan Telegram Token yang sah!")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

# Zon Masa Malaysia (UTC+8)
MY_TZ = timezone(timedelta(hours=8))

# Senarai Data Asas
STAFF_LIST = ["Siti Maryam", "Adam Harith"]
KIDS_LIST = ["Ahmad", "Aisha", "Rayyan"]
BRANCHES = ["Taska 1", "Taska 2", "Taska 3"]

# Simpanan Sesi & Status Kehadiran Semasa
user_branches = {}
user_states = {}
active_checkins = {}      # Format: {"Taska 1": {"Ahmad": "08:15 AM"}}
active_staff_clockin = {} # Format: {"Taska 1": {"Siti Maryam": "07:45 AM"}}

# 📜 REKOD SEJARAH HARIAN (DAILY HISTORY LOGS)
daily_logs = {
    branch: {
        "kids": {},   # Format: {"Ahmad": {"in": "08:15 AM", "out": "06:30 PM", "late": True}}
        "staff": {}   # Format: {"Siti Maryam": {"in": "07:45 AM", "out": "07:00 PM", "ot": True}}
    } for branch in BRANCHES
}

# 💳 REKOD PENGURUSAN YURAN & MAKLUMAT PENDAFTARAN LENGKAP
kids_fees = {
    "Taska 1": {
        "Ahmad": {"parent": "Encik Razak", "phone": "0123456789", "perlu": 300.0, "dibayar": 0.0},
        "Aisha": {"parent": "Puan Aminah", "phone": "0198765432", "perlu": 300.0, "dibayar": 0.0},
        "Rayyan": {"parent": "Encik Kamal", "phone": "0171122334", "perlu": 300.0, "dibayar": 0.0},
    },
    "Taska 2": {},
    "Taska 3": {}
}

def get_kid_fee_data(branch, kid_name):
    if branch not in kids_fees:
        kids_fees[branch] = {}
    if kid_name not in kids_fees[branch]:
        kids_fees[branch][kid_name] = {"parent": "-", "phone": "-", "perlu": 300.0, "dibayar": 0.0}
    return kids_fees[branch][kid_name]


# ==========================================
# 📊 FUNGSI JANA LAPORAN MULTI-BRANCH OWNER
# ==========================================
def jana_teks_laporan_lengkap_semua_cawangan():
    today_str = datetime.now(MY_TZ).strftime("%Y-%m-%d")
    report_text = f"📊 **LAPORAN HARIAN SEMUA CAWANGAN TASKA**\n📅 *Tarikh: {today_str}*\n"
    report_text += "=============================\n\n"

    for branch in BRANCHES:
        report_text += f"🏠 **[{branch.upper()}]**\n"
        
        # 1. Rekod Anak
        report_text += "👶 **Kehadiran Kanak-Kanak:**\n"
        kids_data = daily_logs[branch]["kids"]
        if kids_data:
            for k_name, times in kids_data.items():
                t_in = times.get("in", "Tiada Record")
                t_out = times.get("out", "Belum Check-Out")
                late_tag = " ⚠️ *(LATE PICK UP)*" if times.get("late") else ""
                report_text += f" • **{k_name}**: In {t_in} | Out {t_out}{late_tag}\n"
        else:
            report_text += " • Tiada rekod kehadiran anak hari ini.\n"

        # 2. Rekod Staff
        report_text += "\n👤 **Kehadiran Staff:**\n"
        staff_data = daily_logs[branch]["staff"]
        if staff_data:
            for s_name, times in staff_data.items():
                t_in = times.get("in", "Tiada Record")
                t_out = times.get("out", "Belum Clock-Out")
                ot_tag = " ⏳ *(OVERTIME / OT)*" if times.get("ot") else ""
                report_text += f" • **{s_name}**: In {t_in} | Out {t_out}{ot_tag}\n"
        else:
            report_text += " • Tiada rekod kehadiran staff hari ini.\n"

        report_text += "\n-----------------------------\n"

    return report_text

def hantar_laporan_malam_owner():
    report_text = jana_teks_laporan_lengkap_semua_cawangan()
    try:
        bot.send_message(TELEGRAM_CHAT_ID, report_text, parse_mode="Markdown")
        print("Laporan gabungan jam 11:00 malam berjaya dihantar kepada Owner.")
    except Exception as e:
        print(f"Gagal menghantar laporan automatik kepada Owner: {e}")

scheduler = BackgroundScheduler(timezone="Asia/Kuala_Lumpur")
scheduler.add_job(
    hantar_laporan_malam_owner,
    trigger='cron',
    day_of_week='mon-fri',
    hour=23,
    minute=0
)
scheduler.start()


# --- KEYBOARD MENUS ---
def get_main_branch_menu():
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        KeyboardButton("🏠 Taska 1"),
        KeyboardButton("🏠 Taska 2")
    )
    markup.add(
        KeyboardButton("🏠 Taska 3")
    )
    return markup

def get_staff_sub_menu():
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        KeyboardButton("📥 Check-In Anak"),
        KeyboardButton("📤 Check-Out Anak")
    )
    markup.add(
        KeyboardButton("🟢 Clock-In Staff"),
        KeyboardButton("🔴 Clock-Out Staff")
    )
    return markup

def get_owner_sub_menu():
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        KeyboardButton("⏱️ Late Pick Up Charges"),
        KeyboardButton("⌛ OT Staff")
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


# --- FLASK ROUTES ---
@app.route("/")
def index():
    return "Bot Taska sedang aktif!", 200

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
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
    func=lambda message: message.text in ["🏠 Taska 1", "🏠 Taska 2", "🏠 Taska 3"]
)
def handle_branch_selection(message):
    chat_id = str(message.chat.id)
    branch = message.text.replace("🏠 ", "")
    user_branches[int(message.chat.id)] = branch
    
    if chat_id in OWNER_IDS:
        menu_dipilih = get_owner_sub_menu()
        role_teks = "Owner"
    else:
        menu_dipilih = get_staff_sub_menu()
        role_teks = "Staff"

    bot.reply_to(
        message,
        f"Anda telah memilih *{branch}* (Status: {role_teks}).\nSila pilih menu tindakan di bawah:",
        parse_mode="Markdown",
        reply_markup=menu_dipilih,
    )

# --- HANDLER CHECK-IN/OUT ---
@bot.message_handler(func=lambda message: message.text and "Check-In Anak" in message.text)
def handle_check_in_anak(message):
    branch = user_branches.get(message.chat.id, "Taska 1")
    checked_in_today = active_checkins.get(branch, {})
    markup = InlineKeyboardMarkup()
    for name in KIDS_LIST:
        if name in checked_in_today:
            time_str = checked_in_today[name]
            markup.add(InlineKeyboardButton(f"🔴 {name} (Sudah Check-In: {time_str})", callback_data=f"ignore_{name}"))
        else:
            markup.add(InlineKeyboardButton(f"📥 {name} (Check-In)", callback_data=f"checkin_kid_{name}"))
    bot.reply_to(message, f"[{branch}]\nSila pilih nama anak untuk Check-In:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text and "Check-Out Anak" in message.text)
def handle_check_out_anak(message):
    branch = user_branches.get(message.chat.id, "Taska 1")
    checked_in_today = active_checkins.get(branch, {})
    markup = InlineKeyboardMarkup()
    for name in KIDS_LIST:
        if name in checked_in_today:
            time_str = checked_in_today[name]
            markup.add(InlineKeyboardButton(f"📤 {name} (Check-In jam {time_str})", callback_data=f"checkout_kid_{name}"))
        else:
            markup.add(InlineKeyboardButton(f"⚪ {name} (Belum Check-In)", callback_data=f"ignore_uncheck_{name}"))
    bot.reply_to(message, f"[{branch}]\nSila pilih nama anak untuk Check-Out:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text and "Clock-In Staff" in message.text)
def handle_clock_in_staff(message):
    branch = user_branches.get(message.chat.id, "Taska 1")
    clocked_in_today = active_staff_clockin.get(branch, {})
    markup = InlineKeyboardMarkup()
    for name in STAFF_LIST:
        if name in clocked_in_today:
            time_str = clocked_in_today[name]
            markup.add(InlineKeyboardButton(f"🟢 {name} (Sudah Hadir: {time_str})", callback_data=f"ignore_{name}"))
        else:
            markup.add(InlineKeyboardButton(f"🔴 {name} (Belum Hadir)", callback_data=f"clockin_staff_{name}"))
    bot.reply_to(message, f"[{branch}]\nSila pilih nama staff untuk Clock-In:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text and "Clock-Out Staff" in message.text)
def handle_clock_out_staff(message):
    branch = user_branches.get(message.chat.id, "Taska 1")
    clocked_in_today = active_staff_clockin.get(branch, {})
    markup = InlineKeyboardMarkup()
    for name in STAFF_LIST:
        if name in clocked_in_today:
            time_str = clocked_in_today[name]
            markup.add(InlineKeyboardButton(f"🔴 {name} (Clock-In: {time_str})", callback_data=f"clockout_staff_{name}"))
        else:
            markup.add(InlineKeyboardButton(f"⚪ {name} (Belum Clock-In)", callback_data=f"ignore_uncheck_{name}"))
    bot.reply_to(message, f"[{branch}]\nSila pilih nama staff untuk Clock-Out:", reply_markup=markup)


# --- CALLBACK QUERY HANDLERS ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("checkin_kid_"))
def callback_checkin_kid(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    kid_name = call.data.replace("checkin_kid_", "")
    now_time = datetime.now(MY_TZ).strftime("%I:%M %p")
    
    active_checkins.setdefault(branch, {})[kid_name] = now_time
    daily_logs[branch]["kids"].setdefault(kid_name, {})["in"] = now_time
    
    bot.answer_callback_query(call.id, f"{kid_name} telah Check-In!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📥 [{branch}] **{kid_name}** telah berjaya Check-In pada jam **{now_time}**!",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("checkout_kid_"))
def callback_checkout_kid(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    kid_name = call.data.replace("checkout_kid_", "")
    now_dt = datetime.now(MY_TZ)
    now_time = now_dt.strftime("%I:%M %p")
    
    is_late = now_dt.hour >= 18
    checkin_time = active_checkins.get(branch, {}).pop(kid_name, "N/A")
    kid_log = daily_logs[branch]["kids"].setdefault(kid_name, {})
    kid_log["out"] = now_time
    kid_log["late"] = is_late

    late_text = "\n⚠️ *(Diandaikan Late Pick Up)*" if is_late else ""
    
    bot.answer_callback_query(call.id, f"{kid_name} telah Check-Out!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📤 [{branch}] **{kid_name}** telah berjaya Check-Out pada jam **{now_time}**!\n*(Check-In: {checkin_time})*{late_text}",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("clockin_staff_"))
def callback_clockin_staff(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    staff_name = call.data.replace("clockin_staff_", "")
    now_time = datetime.now(MY_TZ).strftime("%I:%M %p")
    
    active_staff_clockin.setdefault(branch, {})[staff_name] = now_time
    daily_logs[branch]["staff"].setdefault(staff_name, {})["in"] = now_time
    
    bot.answer_callback_query(call.id, f"{staff_name} telah Clock-In!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🟢 [{branch}] **{staff_name}** telah berjaya Clock-In pada jam **{now_time}**!",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("clockout_staff_"))
def callback_clockout_staff(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    staff_name = call.data.replace("clockout_staff_", "")
    now_dt = datetime.now(MY_TZ)
    now_time = now_dt.strftime("%I:%M %p")
    
    is_ot = now_dt.hour >= 18
    clockin_time = active_staff_clockin.get(branch, {}).pop(staff_name, "N/A")
    staff_log = daily_logs[branch]["staff"].setdefault(staff_name, {})
    staff_log["out"] = now_time
    staff_log["ot"] = is_ot

    ot_text = "\n⏳ *(Dikira Overtime / OT)*" if is_ot else ""

    bot.answer_callback_query(call.id, f"{staff_name} telah Clock-Out!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔴 [{branch}] **{staff_name}** telah berjaya Clock-Out pada jam **{now_time}**!\n*(Clock-In: {clockin_time})*{ot_text}",
        parse_mode="Markdown"
    )


# --- HANDLER KHAS OWNER ---
def semak_owner(message):
    if str(message.chat.id) not in OWNER_IDS:
        bot.reply_to(message, "⚠️ Maaf, menu ini hanya boleh diakses oleh Owner Taska sahaja.")
        return False
    return True

@bot.message_handler(func=lambda message: message.text and "Late Pick Up Charges" in message.text)
def handle_late_pickup(message):
    if not semak_owner(message): return
    bot.reply_to(message, "⏱️ Semakan Caj Late Pick Up", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text and "OT Staff" in message.text)
def handle_ot_staff(message):
    if not semak_owner(message): return
    bot.reply_to(message, "⌛ Rekod Overtime (OT) Staff", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text and "Pendaftaran Baru Anak-Anak" in message.text)
def handle_pendaftaran_baru(message):
    if not semak_owner(message): return
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🏠 Taska 1", callback_data="reg_branch_Taska 1"),
        InlineKeyboardButton("🏠 Taska 2", callback_data="reg_branch_Taska 2"),
        InlineKeyboardButton("🏠 Taska 3", callback_data="reg_branch_Taska 3")
    )
    bot.reply_to(message, "📝 **Menu Pendaftaran Baru Anak-Anak**\n\nSila pilih cawangan taska:", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("reg_branch_"))
def callback_reg_branch(call):
    branch = call.data.replace("reg_branch_", "")
    user_states[call.message.chat.id] = {"action": "reg_step_name", "branch": branch}
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📝 **[{branch}] Pendaftaran Baru**\n\nSila taip **Nama Anak** di bawah:",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text and "Keluarkan Dari Senarai" in message.text)
def handle_keluarkan_senarai(message):
    if not semak_owner(message): return
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🏠 Taska 1", callback_data="rem_branch_Taska 1"),
        InlineKeyboardButton("🏠 Taska 2", callback_data="rem_branch_Taska 2"),
        InlineKeyboardButton("🏠 Taska 3", callback_data="rem_branch_Taska 3")
    )
    bot.reply_to(message, "❌ Menu Keluarkan Dari Senarai", reply_markup=markup)

# --- MENU STATUS & BAYARAN YURAN TERKEMASKINI ---
@bot.message_handler(func=lambda message: message.text and "Status & Bayaran Yuran" in message.text)
def handle_status_yuran(message):
    if not semak_owner(message): return
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🏠 Taska 1", callback_data="fee_branch_Taska 1"),
        InlineKeyboardButton("🏠 Taska 2", callback_data="fee_branch_Taska 2"),
        InlineKeyboardButton("🏠 Taska 3", callback_data="fee_branch_Taska 3")
    )
    bot.reply_to(message, "💳 **Menu Status & Bayaran Yuran**\n\nSila pilih cawangan taska:", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("fee_branch_"))
def callback_fee_branch(call):
    branch = call.data.replace("fee_branch_", "")
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📋 Semak Status Yuran Anak", callback_data=f"fee_check_{branch}"),
        InlineKeyboardButton("💵 Kemaskini Bayaran Manual", callback_data=f"fee_update_{branch}")
    )
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"💳 **[{branch}] Pengurusan Status & Bayaran Yuran**\n\nSila pilih tindakan di bawah:",
        parse_mode="Markdown",
        reply_markup=markup
    )

# --- PAPARAN YURAN DENGAN STATUS TERPERINCI ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("fee_check_"))
def callback_fee_check(call):
    branch = call.data.replace("fee_check_", "")
    text = f"💳 **Penyata Status Yuran - [{branch}]**\n"
    text += "=============================\n\n"

    branch_kids = kids_fees.get(branch, {})
    if branch_kids:
        for name in branch_kids:
            data = get_kid_fee_data(branch, name)
            perlu = data["perlu"]
            dibayar = data["dibayar"]
            baki = perlu - dibayar
            
            status_str = "✅ *Lunas*" if baki <= 0 else "❌ *Belum Lunas*"
            
            text += (
                f"👶 **{name}**\n"
                f" • 💳 **Jumlah Yuran**: RM {perlu:.2f}\n"
                f" • 💵 **Dah Bayar**: RM {dibayar:.2f}\n"
                f" • ⏳ **Baki**: RM {baki:.2f}\n"
                f" • 📌 **Status**: {status_str}\n"
                f"-----------------------------\n"
            )
    else:
        text += "• Tiada rekod pendaftaran anak untuk cawangan ini.\n"
        
    bot.answer_callback_query(call.id, "Memaparkan penyata yuran.")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("fee_update_"))
def callback_fee_update(call):
    branch = call.data.replace("fee_update_", "")
    branch_kids = kids_fees.get(branch, {})
    markup = InlineKeyboardMarkup()
    
    if branch_kids:
        for name in branch_kids:
            markup.add(
                InlineKeyboardButton(f"💵 Bayar: {name}", callback_data=f"input_pay_{branch}_{name}")
            )
        bot.answer_callback_query(call.id, "Sila pilih nama anak.")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"💳 **[{branch}] Kemaskini Bayaran Yuran Manual**\n\nSila pilih nama anak untuk masukkan bayaran:",
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        bot.answer_callback_query(call.id, "Tiada rekod anak.")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"💳 **[{branch}]** Tiada rekod pendaftaran anak lagi.",
            parse_mode="Markdown"
        )

@bot.message_handler(func=lambda message: message.text and "Laporan" in message.text)
def handle_laporan_manual(message):
    if not semak_owner(message): return
    report_text = jana_teks_laporan_lengkap_semua_cawangan()
    bot.reply_to(message, report_text, parse_mode="Markdown", reply_markup=get_owner_sub_menu())


# --- HANDLER ALIRAN PENDAFTARAN & INPUT TEKS ---
@bot.message_handler(func=lambda message: True)
def handle_all_text_inputs(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    if chat_id in user_states:
        action = user_states[chat_id].get("action")
        
        # ALIRAN PENDAFTARAN
        if action == "reg_step_name":
            user_states[chat_id]["kid_name"] = text
            user_states[chat_id]["action"] = "reg_step_parent"
            bot.reply_to(message, f"👤 **Nama Anak:** {text}\n\nSila taip **Nama Penjaga** di bawah:", parse_mode="Markdown")
            return

        if action == "reg_step_parent":
            user_states[chat_id]["parent_name"] = text
            user_states[chat_id]["action"] = "reg_step_phone"
            bot.reply_to(message, f"📞 **Nama Penjaga:** {text}\n\nSila taip **No. HP Penjaga** (Contoh: 0123456789):", parse_mode="Markdown")
            return

        if action == "reg_step_phone":
            user_states[chat_id]["phone_no"] = text
            user_states[chat_id]["action"] = "reg_step_fee"
            bot.reply_to(message, f"💵 **No. HP:** {text}\n\nSila taip **Yuran Bulanan (RM)** (Contoh: 300 atau 350):", parse_mode="Markdown")
            return

        if action == "reg_step_fee":
            state = user_states.pop(chat_id)
            branch = state["branch"]
            kid_name = state["kid_name"]
            parent_name = state["parent_name"]
            phone_no = state["phone_no"]
            
            try:
                fee_amount = float(text)
                if kid_name not in KIDS_LIST:
                    KIDS_LIST.append(kid_name)
                    
                kids_fees.setdefault(branch, {})[kid_name] = {
                    "parent": parent_name,
                    "phone": phone_no,
                    "perlu": fee_amount,
                    "dibayar": 0.0
                }
                
                bot.reply_to(
                    message,
                    f"✅ **[{branch}] Pendaftaran Anak Baru Berjaya!**\n\n"
                    f"👶 **Nama Anak:** {kid_name}\n"
                    f"👤 **Nama Penjaga:** {parent_name}\n"
                    f"📞 **No. HP:** {phone_no}\n"
                    f"💳 **Jumlah Yuran:** RM {fee_amount:.2f}\n"
                    f" Status Yuran: ❌ *Belum Lunas*",
                    parse_mode="Markdown",
                    reply_markup=get_owner_sub_menu()
                )
            except ValueError:
                bot.reply_to(message, "⚠️ Sila masukkan nombor jumlah yuran yang sah (Contoh: 300).")
            return

        # ALIRAN BAYARAN MANUAL TERKEMASKINI
        if action == "input_payment":
            state = user_states.pop(chat_id)
            branch = state["branch"]
            kid_name = state["kid_name"]
            try:
                amount = float(text)
                data = get_kid_fee_data(branch, kid_name)
                data["dibayar"] += amount
                perlu = data["perlu"]
                dibayar = data["dibayar"]
                baki = perlu - dibayar
                status_str = "✅ *Lunas*" if baki <= 0 else "❌ *Belum Lunas*"
                
                bot.reply_to(
                    message,
                    f"💵 **[{branch}] Bayaran Berjaya Dikemaskini!**\n\n"
                    f"👶 **Nama Anak:** {kid_name}\n"
                    f" • 💳 **Jumlah Yuran**: RM {perlu:.2f}\n"
                    f" • 💵 **Dah Bayar**: RM {dibayar:.2f} *(+RM {amount:.2f})*\n"
                    f" • ⏳ **Baki**: RM {baki:.2f}\n"
                    f" • 📌 **Status**: {status_str}",
                    parse_mode="Markdown",
                    reply_markup=get_owner_sub_menu()
                )
            except ValueError:
                bot.reply_to(message, "⚠️ Sila masukkan nombor jumlah bayaran yang sah.")
            return

    menu_aktif = get_owner_sub_menu() if str(chat_id) in OWNER_IDS else get_staff_sub_menu()
    bot.reply_to(message, "Sila gunakan butang menu di bawah:", reply_markup=menu_aktif)


# --- WEBHOOK & SERVER START ---
def set_webhook():
    render_url = "https://taska-kids-monthly-payment.onrender.com"
    webhook_url = f"{render_url}/{TELEGRAM_TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    print(f"Webhook dipautkan ke: {webhook_url}")

set_webhook()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
