import os
import logging
from datetime import datetime
import pytz
from threading import Thread
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

MY_TZ = pytz.timezone("Asia/Kuala_Lumpur")

# ---------------------------------------------------------
# 1. FLASK HEARTBEAT
# ---------------------------------------------------------
app_web = Flask("")

@app_web.route("/")
def home():
    return "Bot Taska sedang berjalan 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

Thread(target=run_web, daemon=True).start()

# ---------------------------------------------------------
# 2. ENVIRONMENT VARIABLES FROM RENDER
# ---------------------------------------------------------
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()

# Senarai Owner ID
owner_ids_raw = os.environ.get("OWNER_IDS", "")
OWNER_IDS = [int(x.strip()) for x in owner_ids_raw.split(",") if x.strip().isdigit()]

# Senarai Staff ID (Opsional: Jika kosong, semua bukan owner dianggap staff)
staff_ids_raw = os.environ.get("STAFF_IDS", "")
STAFF_IDS = [int(x.strip()) for x in staff_ids_raw.split(",") if x.strip().isdigit()]

BRANCHES = [b.strip() for b in os.environ.get("BRANCHES", "Taska Utama").split(",") if b.strip()]

def get_kids_for_branch(branch_name: str):
    clean_name = branch_name.upper().replace(" ", "_")
    kids_raw = os.environ.get(f"KIDS_{clean_name}", "")
    return [k.strip() for k in kids_raw.split(",") if k.strip()] if kids_raw else []

# ---------------------------------------------------------
# 3. HANDLERS / FUNGSI BOT
# ---------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_owner = user_id in OWNER_IDS

    if is_owner:
        # MENU UTAMA UNTUK OWNER (Tiada Menu Check-In Harian)
        keyboard = [
            [InlineKeyboardButton("📊 Laporan Kehadiran Harian", callback_data="owner_report")],
            [InlineKeyboardButton("💳 Semakan Yuran & Denda", callback_data="owner_fees")],
            [InlineKeyboardButton("👩‍🏫 Senarai Kehadiran Staff", callback_data="owner_staff_logs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "👑 *Dashboard Pengurusan (Owner/Admin)*\n\nSila pilih tindakan pengurusan di bawah:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        # MENU UTAMA UNTUK STAFF / CIKGU (Ada Menu Check-In Anak & Clock-In)
        keyboard = [[InlineKeyboardButton(f"🏢 {branch}", callback_data=f"branch_{branch}")] for branch in BRANCHES]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "👋 *Sistem Kehadiran Staff & Anak*\n\nSila pilih cawangan tugas anda:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    is_owner = user_id in OWNER_IDS

    # --- MENU OWNER ---
    if data == "owner_report":
        await query.edit_message_text(
            "📊 *Laporan Kehadiran Harian*\n\n(Fungsi paparan laporan & eksport PDF/Excel akan disambungkan di sini)",
            parse_mode="Markdown"
        )
    elif data == "owner_fees":
        await query.edit_message_text(
            "💳 *Semakan Yuran & Denda Lewat*\n\n(Fungsi semakan pembayaran akan disambungkan di sini)",
            parse_mode="Markdown"
        )
    elif data == "owner_staff_logs":
        await query.edit_message_text(
            "👩‍🏫 *Rekod Jam Kerja Staff*\n\n(Fungsi semakan clock-in staff akan disambungkan di sini)",
            parse_mode="Markdown"
        )

    # --- MENU STAFF ---
    elif data.startswith("branch_"):
        branch_name = data.replace("branch_", "")
        keyboard = [
            [InlineKeyboardButton("👶 Rekod Anak-Anak", callback_data=f"menu_kids_{branch_name}")],
            [InlineKeyboardButton("👩‍🏫 Kehadiran Staff", callback_data=f"menu_staff_{branch_name}")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_branches")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"📍 Cawangan: *{branch_name}*\n\nSila pilih kategori:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif data.startswith("menu_kids_"):
        branch_name = data.replace("menu_kids_", "")
        keyboard = [
            [
                InlineKeyboardButton("📥 Check-In Anak", callback_data=f"list_in_{branch_name}"),
                InlineKeyboardButton("📤 Check-Out Anak", callback_data=f"list_out_{branch_name}")
            ],
            [InlineKeyboardButton("🔙 Kembali", callback_data=f"branch_{branch_name}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"👶 *Pengurusan Anak-Anak* ({branch_name}):",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif data.startswith("list_in_") or data.startswith("list_out_"):
        action = "in" if "list_in_" in data else "out"
        branch_name = data.replace("list_in_", "").replace("list_out_", "")
        action_label = "Check-In" if action == "in" else "Check-Out"
        kids_list = get_kids_for_branch(branch_name)

        keyboard = []
        if kids_list:
            for kid in kids_list:
                keyboard.append([InlineKeyboardButton(f"👤 {kid}", callback_data=f"kidact_{action}_{branch_name}_{kid}")])
        else:
            keyboard.append([InlineKeyboardButton("⚠️ Tiada senarai anak", callback_data="none")])

        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data=f"menu_kids_{branch_name}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"👶 *Pilih Nama Anak untuk {action_label}* ({branch_name}):",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif data.startswith("kidact_"):
        parts = data.split("_", 3)
        action, branch_name, kid_name = parts[1], parts[2], parts[3]
        now = datetime.now(MY_TZ)
        action_text = "Check-In Anak" if action == "in" else "Check-Out Anak"

        keyboard = [[InlineKeyboardButton("🔙 Menu Anak", callback_data=f"menu_kids_{branch_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"✅ *Rekod Berjaya Disimpan!*\n\n"
                 f"👶 Nama: *{kid_name}*\n"
                 f"📍 Cawangan: *{branch_name}*\n"
                 f"📝 Jenis: *{action_text}*\n"
                 f"⏰ Masa: *{now.strftime('%I:%M %p')}*\n"
                 f"📅 Tarikh: *{now.strftime('%d/%m/%Y')}*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif data == "back_to_branches":
        keyboard = [[InlineKeyboardButton(f"🏢 {branch}", callback_data=f"branch_{branch}")] for branch in BRANCHES]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="👋 *Sistem Pengurusan Taska*\n\nSila pilih cawangan di bawah:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

# ---------------------------------------------------------
# 4. MAIN PROGRAM
# ---------------------------------------------------------
if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: TELEGRAM_TOKEN tidak dijumpai!")
        exit(1)

    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    print("Bot Taska sedang aktif berjalan...")
    application.run_polling()
