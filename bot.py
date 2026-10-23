import os
import telebot
from apscheduler.schedulers.background import BackgroundScheduler

# 1. Token Bot Telegram anda
TOKEN = "8675996323:AAFKUOUsZaVCpauQnAN7So1TRrjmbv_VLTI"
bot = telebot.TeleBot(TOKEN)

# ==========================================
# 2. FUNGSI PENJADUALAN AUTOMATIK (11:00 MALAM)
# ==========================================
def hantar_laporan_malam():
    chat_id = "8353544393"  # Gantikan dengan Chat ID anda atau Group Admin
    
    teks_laporan = (
        "📊 *Laporan Harian Taska (Automatik)*\n\n"
        "• Status: Draf laporan harian sedia untuk disemak.\n"
        "• Sila semak rekod kehadiran dan yuran sebelum dihantar kepada owner."
    )
    
    try:
        bot.send_message(chat_id, teks_laporan, parse_mode="Markdown")
        print("Laporan malam berjaya dihantar secara automatik.")
    except Exception as e:
        print(f"Gagal menghantar laporan automatik: {e}")

# Aktifkan Scheduler
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
# 3. KOD / HANDLER BOT ANDA (Sila masukkan di sini)
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Bot Taska 1 sedang aktif!")

# [--> Letakkan fungsi/handler check-in, yuran, atau menu taska anda yang lain di sini <---]


# ==========================================
# 4. RUNNER UTAMA BOT
# ==========================================
if __name__ == "__main__":
    print("Bot sedang berjalan...")
    bot.infinity_polling()
