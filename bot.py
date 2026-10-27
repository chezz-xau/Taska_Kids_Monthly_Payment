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


# --- KEYBOARD MENUS (KHAS UNTUK STAFF - 4 BUTANG SAHAJA) ---
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
        KeyboardButton("🟢 Clock-In Staff"),
        KeyboardButton("🔴 Clock-Out Staff")
    )
    return markup


# --- FLASK ROUTES ---
@app.route("/")
def index():
    return "Bot Staff Taska sedang aktif!", 200


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


@bot.callback_query_handler(func=lambda call: call.data.startswith("ignore_"))
def callback_ignore(call):
    bot.answer_callback_query(call.id, "Status sudah dikemas kini.")


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
