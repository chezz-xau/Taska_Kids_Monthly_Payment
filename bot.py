import os
import telebot
from apscheduler.schedulers.background import BackgroundScheduler

# Token Bot Telegram anda
TOKEN = "8675996323:AAFKUOUsZaVCpauQnAN7So1TRrjmbv_VLTI"
bot = telebot.TeleBot(TOKEN)

# Fungsi yang akan dijalankan secara automatik setiap Isnin hingga Jumaat pada pukul 11:00 malam
def hantar_laporan_malam():
    chat_id = "MASUKKAN_CHAT_ID_ANDA"  # Gantikan dengan Chat ID Telegram anda atau ID Group
    
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

# Tetapan APScheduler (Isnin - Jumaat jam 11:00 malam)
scheduler = BackgroundScheduler(timezone="Asia/Kuala_Lumpur")
scheduler.add_job(
    hantar_laporan_malam,
    trigger='cron',
    day_of_week='mon-fri',
    hour=23,
    minute=0
)
scheduler.start()

# Contoh Command Handler sedia ada
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Bot Taska 1 sedang aktif!")

if __name__ == "__main__":
    print("Bot sedang berjalan...")
    bot.infinity_polling()
