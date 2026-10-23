import os
import telebot
from apscheduler.schedulers.background import BackgroundScheduler

# Token Bot Telegram anda (dalam satu baris penuh)
TOKEN = "8675996323:AAFKUOUsZaVCpauQnAN7So1TRrjmbv_VLTI"
bot = telebot.TeleBot(TOKEN)

# ==========================================
# 1. FUNGSI PENJADUALAN AUTOMATIK (11:00 MALAM)
# ==========================================
def hantar_laporan_malam():
    chat_id = "8353544393"  # Gantikan dengan Chat ID Telegram anda (cth: "123456789")
    
    teks_laporan = (
        "📊 *Laporan Harian Taska (Automatik)*\n\n"
        "• Status: Draf laporan harian sedia untuk disemak.\n"
        "• Kehadiran Kanak-kanak & Staff: Rekod harian telah dikumpul.\n"
        "• Sila semak rekod kehadiran sebelum dihantar kepada owner."
    )
    
    try:
        bot.send_message(chat_id, teks_laporan, parse_mode="Markdown")
        print("Laporan malam berjaya dihantar secara automatik.")
    except Exception as e:
        print(f"Gagal menghantar laporan automatik: {e}")

# Aktifkan Scheduler (Isnin - Jumaat jam 11:00 malam)
scheduler = BackgroundScheduler(timezone="Asia/Kuala_Lumpur")
scheduler.add_job(
    hantar_laporan_malam,
    trigger='cron',
    day_of_week='mon-fri',
    hour=23,
    minute=0
)
scheduler.start()


# ==========================================
# 2. COMMAND & HANDLER PENGURUSAN TASKA
# ==========================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "👋 Selamat datang ke *Taska1_bot*!\n\n"
        "Sila gunakan arahan di bawah:\n\n"
        "👶 *Kehadiran Kanak-kanak:*\n"
        "• /checkin_anak - Rekod anak masuk\n"
        "• /checkout_anak - Rekod anak balik\n\n"
        "👩‍💼 *Kehadiran Staff:*\n"
        "• /clockin_staff - Rekod staff masuk kerja\n"
        "• /clockout_staff - Rekod staff tamat kerja\n\n"
        "💰 *Lain-lain:*\n"
        "• /yuran - Semak status yuran bulanan\n"
        "• /laporan - Jana draf laporan harian manual"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

# Fungsi Check-In / Check-Out Kanak-kanak
@bot.message_handler(commands=['checkin_anak'])
def handle_checkin_anak(message):
    bot.reply_to(message, "👶 Sila hantar nama kanak-kanak untuk *Check-In*.", parse_mode="Markdown")

@bot.message_handler(commands=['checkout_anak'])
def handle_checkout_anak(message):
    bot.reply_to(message, "👶 Sila hantar nama kanak-kanak untuk *Check-Out*.", parse_mode="Markdown")

# Fungsi Clock-In / Clock-Out Staff
@bot.message_handler(commands=['clockin_staff'])
def handle_clockin_staff(message):
    bot.reply_to(message, "👩‍💼 Sila hantar nama staff untuk *Clock-In* (Masuk Kerja).", parse_mode="Markdown")

@bot.message_handler(commands=['clockout_staff'])
def handle_clockout_staff(message):
    bot.reply_to(message, "👩‍💼 Sila hantar nama staff untuk *Clock-Out* (Tamat Kerja).", parse_mode="Markdown")

# Fungsi Yuran & Laporan
@bot.message_handler(commands=['yuran'])
def handle_yuran(message):
    bot.reply_to(message, "💰 Semakan status yuran bulanan sedang diproses...", parse_mode="Markdown")

@bot.message_handler(commands=['laporan'])
def handle_laporan_manual(message):
    bot.reply_to(message, "📊 *Draf Laporan Manual*\n• Kehadiran & Staff: Selesai", parse_mode="Markdown")


# ==========================================
# 3. RUNNER UTAMA BOT
# ==========================================
if __name__ == "__main__":
    print("Bot Taska sedang berjalan...")
    bot.infinity_polling()
