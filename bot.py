import os
import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# ---------------------------------------------------------
# AMBIL TETAPAN DARI ENVIRONMENT VARIABLES RENDER
# ---------------------------------------------------------
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()

# Ambil senarai Owner ID (Pisahkan dengan koma)
owner_ids_raw = os.environ.get("OWNER_IDS", "")
OWNER_IDS = [int(x.strip()) for x in owner_ids_raw.split(",") if x.strip().isdigit()]

# Ambil Chat ID Utama
chat_id_raw = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_ID = int(chat_id_raw.strip()) if chat_id_raw.strip().isdigit() else (OWNER_IDS[0] if OWNER_IDS else 0)

# Ambil Senarai Cawangan
branches_raw = os.environ.get("BRANCHES", "Taska Utama")
BRANCHES = [b.strip() for b in branches_raw.split(",") if b.strip()]
# ---------------------------------------------------------

# Pastikan bahagian pelancaran bot menggunakan TOKEN yang dibaca tadi:
if __name__ == '__main__':
    if not TOKEN:
        print("ERROR: TELEGRAM_TOKEN tidak dijumpai dalam Environment Variables!")
        exit(1)
        
    app = ApplicationBuilder().token(TOKEN).build()
    
    # ... (Handler & Logic anda) ...
    
    print("Bot sedang berjalan...")
    app.run_polling()
