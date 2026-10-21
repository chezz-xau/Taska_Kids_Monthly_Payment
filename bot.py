import os
from threading import Thread
from datetime import datetime
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# ----------------- FLASK FOR RENDER HEALTH CHECK -----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Taska is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ----------------- TELEGRAM BOT SETUP -----------------
TOKEN = "8675996323:AAFKUOuSzaVCpauQnAN7So1TRrjmbv_VLTI"
bot = telebot.TeleBot(TOKEN)

# Data simulasi kanak-kanak
children_data = {
    "1": {"name": "Ahmad Rayyan", "status": "out", "time": None},
    "2": {"name": "Nur Zara Sofea", "status": "out", "time": None},
    "3": {"name": "Muhammad Umar", "status": "out", "time": None},
    "4": {"name": "Siti Maryam", "status": "out", "time": None},
    "5": {"name": "Adam Harith", "status": "out", "time": None}
}

# ----------------- MENU UTAMA -----------------
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("📥 Check-In Anak"), KeyboardButton("📤 Check-Out Anak"))
    markup.row(KeyboardButton("🟢 Clock-In Pengasuh"), KeyboardButton("🔴 Clock-Out Pengasuh"))
    markup.row(KeyboardButton("💳 Status & Bayaran Yuran"))
    markup.row(KeyboardButton("📊 Laporan Bulanan"))
    return markup

# ----------------- INLINE KEYBOARD GENERATOR -----------------
def get_children_keyboard(action="checkin"):
    markup = InlineKeyboardMarkup()
    
    for child_id, child_info in children_data.items():
        is_checked_in = child_info["status"] == "in"
        
        if action == "checkin":
            icon = "🟢" if is_checked_in else "⚪"
            status_text = f" ({child_info['time']})" if is_checked_in and child_info['time'] else ""
        else: # checkout
            icon = "🔴" if not is_checked_in else "🟢"
            status_text = f" ({child_info['time']})" if is_checked_in and child_info['time'] else " (Belum Hadir)"

        btn_text = f"{icon} {child_info['name']}{status_text}"
        callback_data = f"toggle_{action}_{child_id}"
        markup.add(InlineKeyboardButton(text=btn_text, callback_data=callback_data))

    save_text = "✅ Simpan & Sahkan Check-In" if action == "checkin" else "✅ Simpan & Sahkan Check-Out"
    markup.add(InlineKeyboardButton(text=save_text, callback_data=f"save_{action}"))
    return markup

# ----------------- COMMAND /START -----------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        "👋 **Selamat datang ke Bot Pengurusan Taska!**\nSila pilih menu di bawah:",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

# ----------------- HANDLER CHECK-IN & CHECK-OUT -----------------
@bot.message_handler(func=lambda msg: msg.text in ["📥 Check-In Anak", "📤 Check-Out Anak"])
def handle_checkin_checkout_menu(message):
    if message.text == "📥 Check-In Anak":
        bot.send_message(
            message.chat.id,
            "📋 **SENARAI CHECK-IN KANAK-KANAK**\n\nTekan nama anak untuk tandakan kehadiran (🟢 = Hadir, ⚪ = Belum):",
            parse_mode="Markdown",
            reply_markup=get_children_keyboard(action="checkin")
        )
    else:
        bot.send_message(
            message.chat.id,
            "📋 **SENARAI CHECK-OUT KANAK-KANAK**\n\nTekan nama anak untuk tanda pulang/diambil (🔴 = Dah Pulang, 🟢 = Di Taska):",
            parse_mode="Markdown",
            reply_markup=get_children_keyboard(action="checkout")
        )

# ----------------- CALLBACK QUERY HANDLER -----------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    current_time = datetime.now().strftime("%I:%M %p")

    if call.data.startswith("toggle_"):
        _, action, child_id = call.data.split("_")
        
        if child_id in children_data:
            if action == "checkin":
                if children_data[child_id]["status"] == "out":
                    children_data[child_id]["status"] = "in"
                    children_data[child_id]["time"] = current_time
                else:
                    children_data[child_id]["status"] = "out"
                    children_data[child_id]["time"] = None
            else:
                if children_data[child_id]["status"] == "in":
                    children_data[child_id]["status"] = "out"
                    children_data[child_id]["time"] = current_time
                else:
                    children_data[child_id]["status"] = "in"

            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=get_children_keyboard(action=action)
            )
            bot.answer_callback_query(call.id, text=f"Status {children_data[child_id]['name']} dikemaskini!")

    elif call.data.startswith("save_"):
        action = call.data.split("_")[1]
        action_name = "Check-In" if action == "checkin" else "Check-Out"
        
        summary = f"🎉 **REKOD {action_name.upper()} BERJAYA DISIMPAN!**\n\n"
        for child in children_data.values():
            status_icon = "🟢 Hadir" if child["status"] == "in" else "🔴 Pulang/Tiada"
            time_str = f" ({child['time']})" if child['time'] else ""
            summary += f"• {child['name']}: {status_icon}{time_str}\n"

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=summary,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, text="Rekod berjaya disimpan!")

# ----------------- MAIN RUNNER -----------------
if __name__ == "__main__":
    # Jalankan Flask dalam Thread berasingan
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    print("Bot Taska sedang berjalan...")
    bot.infinity_polling()
