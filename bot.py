import os
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests

from flask import Flask, abort, request as flask_request
import telebot
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# 1. Konfigurasi Token & Web App Google
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN tidak ditetapkan dalam environment variables!")

# GANTIKAN DENGAN URL WEB APP GOOGLE APPS SCRIPT ANDA
WEB_APP_URL = "MASUKKAN_URL_WEB_APP_GOOGLE_ANDA_DI_SINI"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Zon Masa Malaysia (UTC+8)
MY_TZ = timezone(timedelta(hours=8))

# Senarai Data Asas
STAFF_LIST = ["Siti Maryam", "Adam Harith"]
KIDS_LIST = ["Ahmad", "Aisha", "Rayyan"]

# Simpanan Sesi Cawangan mengikut pengguna (Chat ID)
user_branches = {}


# --- FUNGSI GOOGLE SHEETS ---
def save_to_sheet(name, category, action, branch="Taska 1"):
    now = datetime.now(MY_TZ)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    payload = {
        "action": "save",
        "cawangan": branch,
        "tarikh": date_str,
        "masa": time_str,
        "nama": name,
        "kategori": category,
        "aktiviti": action,
    }

    try:
        requests.post(WEB_APP_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"Ralat simpan ke Google Sheet: {e}")


def get_sheet_data():
    payload = {"action": "get"}
    try:
        response = requests.post(WEB_APP_URL, json=payload, timeout=10)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            return df
    except Exception as e:
        print(f"Ralat baca Google Sheet: {e}")
    return pd.DataFrame()


# --- KEYBOARD MENUS ---
def get_main_branch_menu():
    """Menu Utama: Pilih Cawangan Taska"""
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
    """Sub-Menu Utama mengikut Cawangan (Tukar Cawangan Dipadamkan)"""
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
    today_str = datetime.now(MY_TZ).strftime("%Y-%m-%d")
    df = get_sheet_data()
    checked_in_today = []

    if not df.empty and "Tarikh" in df.columns:
        filtered = df[
            (df["Tarikh"].astype(str) == today_str) & (df["Aktiviti"] == "Check-In")
        ]
        checked_in_today = filtered["Nama"].tolist()

    markup = InlineKeyboardMarkup()
    for name in KIDS_LIST:
        if name in checked_in_today:
            markup.add(
                InlineKeyboardButton(
                    f"🟢 {name} (Sudah Check-In)", callback_data=f"ignore_{name}"
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
    
    markup = InlineKeyboardMarkup()
    for name in KIDS_LIST:
        markup.add(
            InlineKeyboardButton(
                f"📤 {name} (Check-Out)", callback_data=f"checkout_kid_{name}"
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
    today_str = datetime.now(MY_TZ).strftime("%Y-%m-%d")
    df = get_sheet_data()
    clocked_in_today = []

    if not df.empty and "Tarikh" in df.columns:
        filtered = df[
            (df["Tarikh"].astype(str) == today_str) & (df["Aktiviti"] == "Clock-In")
        ]
        clocked_in_today = filtered["Nama"].tolist()

    markup = InlineKeyboardMarkup()
    for name in STAFF_LIST:
        if name in clocked_in_today:
            markup.add(
                InlineKeyboardButton(
                    f"🟢 {name} (Sudah Hadir)", callback_data=f"ignore_{name}"
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
    
    markup = InlineKeyboardMarkup()
    for name in STAFF_LIST:
        markup.add(
            InlineKeyboardButton(
                f"🔴 {name} (Clock-Out)", callback_data=f"clockout_staff_{name}"
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


# Handler Status & Bayaran Yuran
@bot.message_handler(
    func=lambda message: message.text and "Status & Bayaran Yuran" in message.text
)
def handle_status_yuran(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    bot.reply_to(message, f"💳 [{branch}] Memaparkan Status & Bayaran Yuran.")


# Handler Laporan
@bot.message_handler(
    func=lambda message: message.text and "Laporan" in message.text
)
def handle_laporan(message):
    chat_id = message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    today_str = datetime.now(MY_TZ).strftime("%Y-%m-%d")
    df = get_sheet_data()

    if df.empty or "Tarikh" not in df.columns:
        bot.reply_to(
            message,
            "📊 Tiada rekod dijumpai lagi dalam Google Sheet.",
            reply_markup=get_sub_menu(branch),
        )
        return

    df_today = df[df["Tarikh"].astype(str) == today_str]

    if df_today.empty:
        bot.reply_to(
            message,
            f"📊 **Laporan Hari Ini - [{branch}] ({today_str})**\n\nTiada sebarang rekod aktiviti lagi hari ini.",
            parse_mode="Markdown",
            reply_markup=get_sub_menu(branch),
        )
        return

    report_text = f"📊 **Laporan Kehadiran Hari Ini - [{branch}] ({today_str})**\n\n"

    for index, row in df_today.iterrows():
        nama = row.get("Nama", "Tidak diketahui")
        kategori = row.get("Kategori", "-")
        aktiviti = row.get("Aktiviti", "Aktiviti")
        masa = row.get("Masa", "-")
        report_text += f"• **{nama}** ({kategori}) — *{aktiviti}* pada {masa}\n"

    bot.reply_to(
        message, report_text, parse_mode="Markdown", reply_markup=get_sub_menu(branch)
    )


# --- CALLBACK QUERY HANDLERS ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("checkin_kid_"))
def callback_checkin_kid(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    kid_name = call.data.replace("checkin_kid_", "")
    
    save_to_sheet(kid_name, "Anak", "Check-In", branch)
    bot.answer_callback_query(call.id, f"{kid_name} telah Check-In!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📥 [{branch}] {kid_name} telah berjaya Check-In dan direkodkan ke Google Sheets!",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("checkout_kid_"))
def callback_checkout_kid(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    kid_name = call.data.replace("checkout_kid_", "")
    
    save_to_sheet(kid_name, "Anak", "Check-Out", branch)
    bot.answer_callback_query(call.id, f"{kid_name} telah Check-Out!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📤 [{branch}] {kid_name} telah berjaya Check-Out dan direkodkan ke Google Sheets!",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("clockin_staff_"))
def callback_clockin_staff(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    staff_name = call.data.replace("clockin_staff_", "")
    
    save_to_sheet(staff_name, "Staff", "Clock-In", branch)
    bot.answer_callback_query(call.id, f"{staff_name} telah Clock-In!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🟢 [{branch}] {staff_name} telah berjaya Clock-In dan direkodkan ke Google Sheets!",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("clockout_staff_"))
def callback_clockout_staff(call):
    chat_id = call.message.chat.id
    branch = user_branches.get(chat_id, "Taska 1")
    staff_name = call.data.replace("clockout_staff_", "")
    
    save_to_sheet(staff_name, "Staff", "Clock-Out", branch)
    bot.answer_callback_query(call.id, f"{staff_name} telah Clock-Out!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔴 [{branch}] {staff_name} telah berjaya Clock-Out dan direkodkan ke Google Sheets!",
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
    
    save_to_sheet(kid_name, "Anak", "Keluarkan Dari Senarai", branch)
    bot.answer_callback_query(call.id, f"{kid_name} telah dikeluarkan!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"❌ [{branch}] {kid_name} telah berjaya dikeluarkan dari senarai dan direkodkan.",
    )


# Callback: Tindakan Eksekusi Buang Staff
@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_staff_"))
def callback_remove_staff_action(call):
    parts = call.data.replace("remove_staff_", "").split("_", 1)
    branch = parts[0]
    staff_name = parts[1]
    
    save_to_sheet(staff_name, "Staff", "Keluarkan Dari Senarai", branch)
    bot.answer_callback_query(call.id, f"{staff_name} telah dikeluarkan!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"❌ [{branch}] {staff_name} telah berjaya dikeluarkan dari senarai dan direkodkan.",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("ignore_"))
def callback_ignore(call):
    bot.answer_callback_query(call.id, "Rekod ini sudah didaftarkan hari ini.")


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
