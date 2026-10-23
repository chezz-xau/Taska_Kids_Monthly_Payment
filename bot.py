import logging
from telegram.ext import Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Tetapan logging untuk memantau status bot
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Fungsi yang akan dijalankan secara automatik setiap Isnin hingga Jumaat pada pukul 11:00 malam
async def hantar_laporan_malam(application: Application):
    chat_id = "MASUKKAN_CHAT_ID_ADMIN_ATAU_GROUP"  # Gantikan dengan Chat ID anda atau ID Group Telegram
    
    teks_laporan = (
        "📊 *Laporan Harian Taska (Automatik)*\n\n"
        "• Status: Draf laporan harian sedia untuk disemak.\n"
        "• Sila semak rekod kehadiran dan yuran sebelum dihantar kepada owner."
    )
    
    try:
        await application.bot.send_message(
            chat_id=chat_id,
            text=teks_laporan,
            parse_mode="Markdown"
        )
        logger.info("Laporan malam berjaya dihantar secara automatik.")
    except Exception as e:
        logger.error(f"Gagal menghantar laporan automatik: {e}")

# Fungsi untuk memulakan APScheduler
def setup_scheduler(application: Application):
    scheduler = AsyncIOScheduler(timezone="Asia/Kuala_Lumpur")
    
    # Tetapkan masa: Isnin hingga Jumaat (mon-fri) pada jam 23:00 (11:00 malam)
    scheduler.add_job(
        hantar_laporan_malam,
        trigger=CronTrigger(day_of_week='mon-fri', hour=23, minute=0),
        args=[application]
    )
    
    scheduler.start()
    logger.info("Scheduler APScheduler telah diaktifkan.")

def main():
    # Gantikan dengan Token Bot Telegram anda yang sebenar
    TOKEN = "TOKEN_BOT_ANDA"
    
    # Bina aplikasi bot
    application = Application.builder().token(TOKEN).build()
    
    # Aktifkan fungsi penjadualan automatik
    setup_scheduler(application)
    
    # ---------------------------------------------------------
    # (Anda boleh letakkan command / handler bot lain di sini)
    # Contoh: application.add_handler(CommandHandler("start", start))
    # ---------------------------------------------------------
    
    # Mula jalankan bot
    logger.info("Bot sedang berjalan...")
    application.run_polling()

if __name__ == "__main__":
    main()
