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

# 1. Konfigurasi Token Bot
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN tidak ditetapkan dalam environment variables!")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Zon Masa Malaysia (UTC+8)
MY_TZ = timezone(timedelta(hours=8))

# Senarai Data Asas
STAFF_LIST = ["Siti Maryam", "Adam Harith"]
KIDS_LIST = ["Ahmad", "Aisha", "Rayyan"]

# Simpanan Sesi & Status Sementara (Dalam Memori Bot)
user_branches = {}
active_checkins = {}      # Format: {"Taska 1": {"Ahmad": "08:15 AM"}}
active_staff_clockin = {} # Format: {"Taska 1": {"Siti Maryam": "07:45 AM"}}
fee_status = {}           # Format: {"Taska 1": {"Ahmad": "Belum Bayar", "Aisha": "Lunas", ...}}


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


def get_sub_menu(branch_name):
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        KeyboardButton("📥 Check-In Anak"),
        KeyboardButton("📤 Check-Out Anak")
    )
    markup.add(
        KeyboardButton("⏱️ Late Pick Up Charges")
    )
    markup.add(
        KeyboardButton("🟢 Clock-In Staff"),
        KeyboardButton("🔴 Clock-Out Staff")
    )
    markup.add(
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


# Handler Pemilihan Cawangan
@bot.message_handler(
    func=lambda message: message.text in ["🏠 Taska 1", "🏠 Taska 2", "🏠 Taska 3"]
)
def handle_branch_selection(message):
    chat_id = message.chat.id
    branch = message.text.replace("🏠 ", "")
    user_branches[chat_id] = branch

    bot.reply_to(
        message,
        f"Anda telah memilih *{branch}*.\nSila pilih menu tindakan di bawah:",
        parse_mode="Markdown",
        reply_markup=get_sub_menu(branch),
    )


# Handler Check-In Anak
@bot.message_handler(
    func=lambda message: message.text and "Check-In Anak" in message.text
)
def handle_check_in_anak(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    checked_in_today = active_checkins.get(branch, {})

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


# Handler Check-Out Anak
@bot.message_handler(
    func=lambda message: message.text and "Check-Out Anak" in message.text
)
def handle_check_out_anak(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    checked_in_today = active_checkins.get(branch, {})
    
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


# Handler Late Pick Up Charges
@bot.message_handler(
    func=lambda message: message.text and "Late Pick Up Charges" in message.text
)
def handle_late_pickup(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    bot.reply_to(
        message,
        f"⏱️ **[{branch}] Semakan Caj Late Pick Up**\n\nSila pilih nama anak atau semak rekod kelewatan pengambilan.",
        parse_mode="Markdown"
    )


# Handler Clock-In Staff
@bot.message_handler(
    func=lambda message: message.text and "Clock-In Staff" in message.text
)
def handle_clock_in_staff(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    clocked_in_today = active_staff_clockin.get(branch, {})

    markup = InlineKeyboardMarkup()
    for name in STAFF_LIST:
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


# Handler Clock-Out Staff
@bot.message_handler(
    func=lambda message: message.text and "Clock-Out Staff" in message.text
)
def handle_clock_out_staff(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    clocked_in_today = active_staff_clockin.get(branch, {})
    
    markup = InlineKeyboardMarkup()
    for name in STAFF_LIST:
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


# Handler OT Staff
@bot.message_handler(
    func=lambda message: message.text and "OT Staff" in message.text
)
def handle_ot_staff(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    bot.reply_to(
        message,
        f"⌛ **[{branch}] Rekod Overtime (OT) Staff**\n\nSila masukkan butiran jam OT staff.",
        parse_mode="Markdown"
    )


# Handler Pendaftaran Baru Anak-Anak (Papar 3 Pilihan Cawangan)
@bot.message_handler(
    func=lambda message: message.text and "Pendaftaran Baru Anak-Anak" in message.text
)
def handle_pendaftaran_baru(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🏠 Taska 1", callback_data="reg_branch_Taska 1"),
        InlineKeyboardButton("🏠 Taska 2", callback_data="reg_branch_Taska 2"),
        InlineKeyboardButton("🏠 Taska 3", callback_data="reg_branch_Taska 3")
    )
    bot.reply_to(
        message,
        "📝 **Menu Pendaftaran Baru Anak-Anak**\n\nSila pilih cawangan taska untuk pendaftaran:",
        parse_mode="Markdown",
        reply_markup=markup
    )


# Handler Keluarkan Dari Senarai (Papar 3 Pilihan Cawangan)
@bot.message_handler(
    func=lambda message: message.text and "Keluarkan Dari Senarai" in message.text
)
def handle_keluarkan_senarai(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🏠 Taska 1", callback_data="rem_branch_Taska 1"),
        InlineKeyboardButton("🏠 Taska 2", callback_data="rem_branch_Taska 2"),
        InlineKeyboardButton("🏠 Taska 3", callback_data="rem_branch_Taska 3")
    )
    bot.reply_to(
        message,
        "❌ **Menu Keluarkan Dari Senarai**\n\nSila pilih cawangan taska:",
        parse_mode="Markdown",
        reply_markup=markup
    )


# Handler Status & Bayaran Yuran (Papar 3 Pilihan Cawangan)
@bot.message_handler(
    func=lambda message: message.text and "Status & Bayaran Yuran" in message.text
)
def handle_status_yuran(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🏠 Taska 1", callback_data="fee_branch_Taska 1"),
        InlineKeyboardButton("🏠 Taska 2", callback_data="fee_branch_Taska 2"),
        InlineKeyboardButton("🏠 Taska 3", callback_data="fee_branch_Taska 3")
    )
    bot.reply_to(
        message,
        "💳 **Menu Status & Bayaran Yuran**\n\nSila pilih cawangan taska:",
        parse_mode="Markdown",
        reply_markup=markup
    )


# Handler Laporan
@bot.message_handler(
    func=lambda message: message.text and "Laporan" in message.text
)
def handle_laporan(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    today_str = datetime.now(MY_TZ).strftime("%Y-%m-%d")
    
    checked_in_kids = active_checkins.get(branch, {})
    clocked_staff = active_staff_clockin.get(branch, {})
    
    report_text = f"📊 **Laporan Semasa - [{branch}] ({today_str})**\n\n"
    report_text += f"👶 **Anak Sedang Check-In:**\n"
    if checked_in_kids:
        for name, time_str in checked_in_kids.items():
            report_text += f"• **{name}** — Check-In pada *{time_str}*\n"
    else:
        report_text += "• Tiada\n"
        
    report_text += f"\n👤 **Staff Hadir (Clock-In):**\n"
    if clocked_staff:
        for name, time_str in clocked_staff.items():
            report_text += f"• **{name}** — Clock-In pada *{time_str}*\n"
    else:
        report_text += "• Tiada\n"

    bot.reply_to(
        message, report_text, parse_mode="Markdown", reply_markup=get_sub_menu(branch)
    )


# --- CALLBACK QUERY HANDLERS ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("checkin_kid_"))
def callback_checkin_kid(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    kid_name = call.data.replace("checkin_kid_", "")
    now_time = datetime.now(MY_TZ).strftime("%I:%M %p")
    
    if branch not in active_checkins:
        active_checkins[branch] = {}
    active_checkins[branch][kid_name] = now_time
        
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
    branch = user_branches.get(chat_id, "Taska 1")
    kid_name = call.data.replace("checkout_kid_", "")
    now_time = datetime.now(MY_TZ).strftime("%I:%M %p")
    
    checkin_time = active_checkins.get(branch, {}).pop(kid_name, "N/A")
        
    bot.answer_callback_query(call.id, f"{kid_name} telah Check-Out pada {now_time}!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📤 [{branch}] **{kid_name}** telah berjaya Check-Out pada jam **{now_time}**!\n*(Check-In: {checkin_time})*",
        parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("clockin_staff_"))
def callback_clockin_staff(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    staff_name = call.data.replace("clockin_staff_", "")
    now_time = datetime.now(MY_TZ).strftime("%I:%M %p")
    
    if branch not in active_staff_clockin:
        active_staff_clockin[branch] = {}
    active_staff_clockin[branch][staff_name] = now_time
        
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
    branch = user_branches.get(chat_id, "Taska 1")
    staff_name = call.data.replace("clockout_staff_", "")
    now_time = datetime.now(MY_TZ).strftime("%I:%M %p")
    
    clockin_time = active_staff_clockin.get(branch, {}).pop(staff_name, "N/A")
        
    bot.answer_callback_query(call.id, f"{staff_name} telah Clock-Out pada {now_time}!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔴 [{branch}] **{staff_name}** telah berjaya Clock-Out pada jam **{now_time}**!\n*(Clock-In: {clockin_time})*",
        parse_mode="Markdown"
    )


# --- CALLBACKS UNTUK YURAN (DENGAN PILIHAN CAWANGAN) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("fee_branch_"))
def callback_fee_branch(call):
    branch = call.data.replace("fee_branch_", "")
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📋 Semak Status Yuran Anak", callback_data=f"fee_check_{branch}"),
        InlineKeyboardButton("✅ Kemaskini Status Yuran (Lunas)", callback_data=f"fee_update_{branch}")
    )
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"💳 **[{branch}] Pengurusan Status & Bayaran Yuran**\n\nSila pilih tindakan di bawah:",
        parse_mode="Markdown",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("fee_check_"))
def callback_fee_check(call):
    branch = call.data.replace("fee_check_", "")
    
    if branch not in fee_status:
        fee_status[branch] = {name: "Belum Bayar" for name in KIDS_LIST}
        
    text = f"📋 **Status Yuran Semasa - [{branch}]**\n\n"
    for name in KIDS_LIST:
        status = fee_status[branch].get(name, "Belum Bayar")
        icon = "✅" if status == "Lunas" else "❌"
        text += f"• {name}: {icon} *{status}*\n"
        
    bot.answer_callback_query(call.id, "Memaparkan status yuran.")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("fee_update_"))
def callback_fee_update(call):
    branch = call.data.replace("fee_update_", "")
    
    markup = InlineKeyboardMarkup()
    for name in KIDS_LIST:
        markup.add(
            InlineKeyboardButton(f"✅ Set Lunas: {name}", callback_data=f"set_fee_paid_{branch}_{name}")
        )
        
    bot.answer_callback_query(call.id, "Sila pilih nama anak.")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"💳 **[{branch}] Kemaskini Status Yuran**\nSila pilih anak yang telah menjelaskan yuran:",
        parse_mode="Markdown",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("set_fee_paid_"))
def callback_set_fee_paid(call):
    parts = call.data.replace("set_fee_paid_", "").split("_", 1)
    branch = parts[0]
    kid_name = parts[1]
    
    if branch not in fee_status:
        fee_status[branch] = {}
    fee_status[branch][kid_name] = "Lunas"
    
    bot.answer_callback_query(call.id, f"Yuran {kid_name} dikemaskini kepada Lunas!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ [{branch}] Status yuran untuk **{kid_name}** telah berjaya dikemaskini kepada **Lunas**!",
        parse_mode="Markdown"
    )


# Callback: Selepas pilih cawangan untuk Pendaftaran Baru
@bot.callback_query_handler(func=lambda call: call.data.startswith("reg_branch_"))
def callback_reg_branch(call):
    branch = call.data.replace("reg_branch_", "")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📝 **[{branch}] Borang Pendaftaran Anak Baru**\n\nSila hantar maklumat anak mengikut format berikut:\n\n*Nama Anak:*\n*Nama Penjaga:*\n*No. Telefon:*",
        parse_mode="Markdown"
    )


# Callback: Selepas pilih cawangan untuk Keluarkan Dari Senarai
@bot.callback_query_handler(func=lambda call: call.data.startswith("rem_branch_"))
def callback_rem_branch(call):
    branch = call.data.replace("rem_branch_", "")
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("👶 Keluarkan Nama Anak", callback_data=f"rem_type_kid_{branch}"),
        InlineKeyboardButton("👤 Keluarkan Nama Staff", callback_data=f"rem_type_staff_{branch}")
    )
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"❌ **[{branch}]**\nSila pilih kategori yang ingin dikeluarkan:",
        parse_mode="Markdown",
        reply_markup=markup
    )


# Callback: Pilih Senarai Anak Mengikut Cawangan
@bot.callback_query_handler(func=lambda call: call.data.startswith("rem_type_kid_"))
def callback_rem_type_kid(call):
    branch = call.data.replace("rem_type_kid_", "")
    
    markup = InlineKeyboardMarkup()
    for name in KIDS_LIST:
        markup.add(
            InlineKeyboardButton(f"❌ {name}", callback_data=f"remove_kid_{branch}_{name}")
        )
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"[{branch}] Sila pilih nama anak untuk dikeluarkan:",
        reply_markup=markup
    )


# Callback: Pilih Senarai Staff Mengikut Cawangan
@bot.callback_query_handler(func=lambda call: call.data.startswith("rem_type_staff_"))
def callback_rem_type_staff(call):
    branch = call.data.replace("rem_type_staff_", "")
    
    markup = InlineKeyboardMarkup()
    for name in STAFF_LIST:
        markup.add(
            InlineKeyboardButton(f"❌ {name}", callback_data=f"remove_staff_{branch}_{name}")
        )
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"[{branch}] Sila pilih nama staff untuk dikeluarkan:",
        reply_markup=markup
    )


# Callback: Tindakan Eksekusi Buang Anak
@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_kid_"))
def callback_remove_kid_action(call):
    parts = call.data.replace("remove_kid_", "").split("_", 1)
    branch = parts[0]
    kid_name = parts[1]
    
    bot.answer_callback_query(call.id, f"{kid_name} telah dikeluarkan!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"❌ [{branch}] {kid_name} telah berjaya dikeluarkan dari senarai.",
    )


# Callback: Tindakan Eksekusi Buang Staff
@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_staff_"))
def callback_remove_staff_action(call):
    parts = call.data.replace("remove_staff_", "").split("_", 1)
    branch = parts[0]
    staff_name = parts[1]
    
    bot.answer_callback_query(call.id, f"{staff_name} telah dikeluarkan!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"❌ [{branch}] {staff_name} telah berjaya dikeluarkan dari senarai.",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("ignore_"))
def callback_ignore(call):
    bot.answer_callback_query(call.id, "Rekod sudah didaftarkan hari ini.")


@bot.message_handler(func=lambda message: True)
def handle_fallback(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id)
    if branch:
        reply_markup = get_sub_menu(branch)
    else:
        reply_markup = get_main_branch_menu()

    bot.reply_to(
        message,
        "Sila gunakan butang menu di bawah untuk berurusan dengan bot.",
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
