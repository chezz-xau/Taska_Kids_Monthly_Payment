import os
import logging
from threading import Thread
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 1. FLASK HEARTBEAT (SUPAYA RENDER FREE TIER TIDAK SLEEP)
# ---------------------------------------------------------
app_web = Flask("")


@app_web.route("/")
def home():
    return "Bot Taska sedang berjalan 24/7!"


def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)


# Jalankan Flask dalam background thread
Thread(target=run_web, daemon=True).start()


# ---------------------------------------------------------
# 2. AMBIL TETAPAN DARIPADA ENVIRONMENT VARIABLES RENDER
# ---------------------------------------------------------
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()

# Ambil senarai Owner ID (Pisah dengan koma)
owner_ids_raw = os.environ.get("OWNER_IDS", "")
OWNER_IDS = [
    int(x.strip()) for x in owner_ids_raw.split(",") if x.strip().isdigit()
]

# Ambil Chat ID Utama
chat_id_raw = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_ID = (
    int(chat_id_raw.strip())
    if chat_id_raw.strip().isdigit()
    else (OWNER_IDS[0] if OWNER_IDS else 0)
)

# Ambil Senarai Cawangan Secara Dinamik
branches_raw = os.environ.get("BRANCHES", "Taska Utama")
BRANCHES = [b.strip() for b in branches_raw.split(",") if b.strip()]


# ---------------------------------------------------------
# 3. FUNGSI BOT (HANDLERS)
# ---------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id

  # Semak sekiranya Owner ID ditetapkan dan pengguna bukan owner
  if OWNER_IDS and user_id not in OWNER_IDS:
    await update.message.reply_text(
        "Maaf, anda tidak mempunyai kebenaran untuk mengakses bot pengurusan"
        " ini."
    )
    return

  # Bina butang cawangan secara dinamik berdasarkan environment variable BRANCHES
  keyboard = [
      [InlineKeyboardButton(branch, callback_data=f"branch_{branch}")]
      for branch in BRANCHES
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  await update.message.reply_text(
      "👋 *Sistem Pengurusan Taska*\n\nSila pilih cawangan di bawah:",
      reply_markup=reply_markup,
      parse_mode="Markdown",
  )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()

  data = query.data

  if data.startswith("branch_"):
    branch_name = data.replace("branch_", "")

    # Menu pilihan rekod (Check-In / Check-Out)
    keyboard = [
        [
            InlineKeyboardButton(
                "📥 Masa Check-In", callback_data=f"checkin_{branch_name}"
            ),
            InlineKeyboardButton(
                "📤 Masa Check-Out", callback_data=f"checkout_{branch_name}"
            ),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=(
            f"📍 Cawangan dipilih: *{branch_name}*\n\nSila pilih jenis rekod:"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  elif data.startswith("checkin_") or data.startswith("checkout_"):
    parts = data.split("_", 1)
    action = parts[0]
    branch_name = parts[1]
    action_text = "Check-In" if action == "checkin" else "Check-Out"

    await query.edit_message_text(
        text=(
            f"✏️ Sila taip masa *{action_text}* baharu untuk cawangan"
            f" *{branch_name}* di bawah:\n*(Contoh format: 08:15 AM atau 05:30"
            " PM)*"
        ),
        parse_mode="Markdown",
    )


# ---------------------------------------------------------
# 4. MAIN PROGRAM
# ---------------------------------------------------------
if __name__ == "__main__":
  if not TOKEN:
    print("ERROR: TELEGRAM_TOKEN tidak dijumpai dalam Environment Variables!")
    exit(1)

  print("Memulakan aplikasi bot...")
  application = ApplicationBuilder().token(TOKEN).build()

  # Daftarkan handlers
  application.add_handler(CommandHandler("start", start))
  application.add_handler(CallbackQueryHandler(button_handler))

  print("Bot Telegram sedang aktif berjalan (Polling mode)...")
  application.run_polling()
