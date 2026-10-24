import os
import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# ---------------------------------------------------------
# 1. TETAPAN DINAMIK DARIPADA ENVIRONMENT VARIABLES (RENDER)
# ---------------------------------------------------------

# Token Bot Telegram
TOKEN = os.environ.get("TELEGRAM_TOKEN", "PUT_YOUR_DEFAULT_TOKEN_HERE")

# Chat ID Owner/Admin (Boleh letak satu atau lebih ID, dipisahkan dengan koma)
# Contoh di Render: OWNER_IDS = 123456789,987654321
owner_ids_raw = os.environ.get("OWNER_IDS", "")
OWNER_IDS = [x.strip() for x in owner_ids_raw.split(",") if x.strip()]

# Chat ID Utama untuk Terima Laporan Harian/Bulanan Automatik
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", OWNER_IDS[0] if OWNER_IDS else "")

# Senarai Cawangan Taska (Dinamik)
# Contoh 1 Cawangan : BRANCHES = Taska Utama
# Contoh 3 Cawangan : BRANCHES = Cawangan Indera Mahkota, Cawangan Taman Bebas, Cawangan Bandar
branches_raw = os.environ.get("BRANCHES", "Taska Utama")
BRANCHES = [b.strip() for b in branches_raw.split(",") if b.strip()]

# ---------------------------------------------------------
