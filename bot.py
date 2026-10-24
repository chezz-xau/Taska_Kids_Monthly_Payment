import logging
import os
import pytz
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

MY_TZ = pytz.timezone("Asia/Kuala_Lumpur")

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

Thread(target=run_web, daemon=True).start()

# ---------------------------------------------------------
# 2. ENVIRONMENT VARIABLES FROM RENDER
# ---------------------------------------------------------
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()

owner_ids_raw = os.environ.get("OWNER_IDS", "")
OWNER_IDS = [
    int(x.strip()) for x in owner_ids_raw.split(",") if x.strip().isdigit()
]

BRANCHES = [
    b.strip()
    for b in os.environ.get("BRANCHES", "Taska Utama").split(",")
    if b.strip()
]

def get_kids_for_branch(branch_name: str):
    clean_name = branch_name.upper().replace(" ", "_")
    kids_raw = os.environ.get(f"KIDS_{clean_name}", "")
    return [k.strip() for k in kids_raw.split(",") if k.strip()] if kids_raw else []

# Data Simpanan Sementara (In-Memory Database)
user_sessions = {}
db_yuran = {}  # Format: {"Ahmad": {"yuran": 350, "bayar": 100}}

# ---------------------------------------------------------
# 3. HANDLERS / FUNGSI BOT
# ---------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_owner = user_id in OWNER_IDS

    if is_owner:
        keyboard = [
            [InlineKeyboardButton("📋 Kehadiran", callback_data="owner_menu_kehadiran")],
            [InlineKeyboardButton("💳 Status & Bayaran Yuran", callback_data="owner_select_branch_yuran")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "👑 *Dashboard Pengurusan (Owner/Admin)*\n\nSila pilih kategori pengurusan:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    else:
        keyboard = [
            [InlineKeyboardButton(f"🏢 {branch}", callback_data=f"branch_{branch}")]
            for branch in BRANCHES
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "👋 *Sistem Kehadiran Staff & Anak*\n\nSila pilih cawangan tugas anda:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    # ==========================================
    # 👑 SUB-MENU OWNER / ADMIN
    # ==========================================
    if data == "owner_menu_kehadiran":
        keyboard = [
            [InlineKeyboardButton("👶 1. Anak", callback_data="owner_attendance_kids")],
            [InlineKeyboardButton("👩‍🏫 2. Staff", callback_data="owner_attendance_staff")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="owner_main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="📋 *Laporan Kehadiran*\n\nSila pilih jenis kehadiran:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    elif data == "owner_attendance_kids":
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="owner_menu_kehadiran")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        report_text = (
            "👶 *Laporan Kehadiran Anak (Harian)*\n"
            "───────────────────────\n"
            "👤 *Nama Anak:* Ahmad\n"
            "📥 Check-In: `08:15 AM`\n"
            "📤 Check-Out: `05:30 PM`\n"
            "───────────────────────\n"
            "👤 *Nama Anak:* Ali\n"
            "📥 Check-In: `08:30 AM`\n"
            "📤 Check-Out: `Belum Keluar`\n"
        )
        await query.edit_message_text(
            text=report_text, reply_markup=reply_markup, parse_mode="Markdown"
        )

    elif data == "owner_attendance_staff":
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="owner_menu_kehadiran")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        staff_text = (
            "👩‍🏫 *Rekod Jam Kerja Staff (Harian)*\n"
            "───────────────────────\n"
            "👤 *Staff:* Cikgu Siti\n"
            "🟢 Clock-In: `07:50 AM`\n"
            "🔴 Clock-Out: `06:00 PM`\n"
            "───────────────────────\n"
            "👤 *Staff:* Cikgu Aminah\n"
            "🟢 Clock-In: `08:05 AM`\n"
            "🔴 Clock-Out: `Belum Keluar`\n"
        )
        await query.edit_message_text(
            text=staff_text, reply_markup=reply_markup, parse_mode="Markdown"
        )

    # 1. OWNER PILIH CAWANAGAN UNTUK YURAN
    elif data == "owner_select_branch_yuran":
        keyboard = [
            [InlineKeyboardButton(f"🏢 {branch}", callback_data=f"yuran_br_{branch}")]
            for branch in BRANCHES
        ]
        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="owner_main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="💳 *Pengurusan Yuran*\n\nSila pilih cawangan:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    # 2. OWNER PILIH NAMA ANAK UNTUK YURAN
    elif data.startswith("yuran_br_"):
        branch_name = data.replace("yuran_br_", "")
        kids_list = get_kids_for_branch(branch_name)

        keyboard = []
        if kids_list:
            for kid in kids_list:
                keyboard.append([
                    InlineKeyboardButton(f"👤 {kid}", callback_data=f"yuran_kid_{branch_name}_{kid}")
                ])
        else:
            keyboard.append([InlineKeyboardButton("⚠️ Tiada senarai anak", callback_data="none")])

        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="owner_select_branch_yuran")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"💳 *Pilih Anak untuk Kemaskini Yuran* ({branch_name}):",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    # 3. PAPARAN STATUS YURAN ANAK + BUTANG KEMASKINI
    elif data.startswith("yuran_kid_"):
        parts = data.split("_", 3)
        branch_name, kid_name = parts[2], parts[3]

        # Ambil data yuran anak dari db_yuran (default: Yuran RM350, Bayar RM0)
        info = db_yuran.get(kid_name, {"yuran": 350.0, "bayar": 0.0})
        baki = info["yuran"] - info["bayar"]
        status = "Lunas ✅" if baki <= 0 else "Belum Lunas ❌"

        text_detail = (
            f"💳 *Status & Bayaran Yuran*\n"
            f"───────────────────────\n"
            f"1. *Nama Anak:* {kid_name}\n"
            f"2. *Jumlah Yuran:* RM {info['yuran']:.2f}\n"
            f"3. *Bayaran Hari Ini/Terkini:* RM {info['bayar']:.2f}\n"
            f"4. *Baki:* RM {max(0, baki):.2f}\n"
            f"5. *Status:* {status}\n"
            f"───────────────────────"
        )

        keyboard = [
            [InlineKeyboardButton("💵 Kemaskini Bayaran Hari Ini", callback_data=f"pay_update_{branch_name}_{kid_name}")],
            [InlineKeyboardButton("✏️ Set Jumlah Yuran", callback_data=f"fee_update_{branch_name}_{kid_name}")],
            [InlineKeyboardButton("🔙 Kembali", callback_data=f"yuran_br_{branch_name}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=text_detail,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    # 4. BOT MINTA INPUT TAIPAN BAYARAN HARI INI
    elif data.startswith("pay_update_"):
        parts = data.split("_", 3)
        branch_name, kid_name = parts[2], parts[3]

        user_sessions[user_id] = {
            "mode": "update_pay",
            "branch": branch_name,
            "kid": kid_name
        }

        await query.edit_message_text(
            text=f"💵 *Masukkan Jumlah Bayaran Hari Ini*\n\nSila taip jumlah bayaran baharu untuk *{kid_name}* dalam RM:\n*(Contoh: 100 atau 350)*",
            parse_mode="Markdown"
        )

    # 5. BOT MINTA INPUT TAIPAN TOTAL YURAN
    elif data.startswith("fee_update_"):
        parts = data.split("_", 3)
        branch_name, kid_name = parts[2], parts[3]

        user_sessions[user_id] = {
            "mode": "update_fee",
            "branch": branch_name,
            "kid": kid_name
        }

        await query.edit_message_text(
            text=f"✏️ *Tetapkan Jumlah Yuran Bulanan*\n\nSila taip jumlah yuran rasmi untuk *{kid_name}* dalam RM:\n*(Contoh: 350 atau 400)*",
            parse_mode="Markdown"
        )

    elif data == "owner_main_menu":
        keyboard = [
            [InlineKeyboardButton("📋 Kehadiran", callback_data="owner_menu_kehadiran")],
            [InlineKeyboardButton("💳 Status & Bayaran Yuran", callback_data="owner_select_branch_yuran")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="👑 *Dashboard Pengurusan (Owner/Admin)*\n\nSila pilih kategori pengurusan:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    # ==========================================
    # 👩‍🏫 SUB-MENU STAFF / CIKGU
    # ==========================================
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
            parse_mode="Markdown",
        )

    elif data.startswith("menu_kids_"):
        branch_name = data.replace("menu_kids_", "")
        keyboard = [
            [
                InlineKeyboardButton("📥 Check-In Anak", callback_data=f"list_in_{branch_name}"),
                InlineKeyboardButton("📤 Check-Out Anak", callback_data=f"list_out_{branch_name}")
            ],
            [InlineKeyboardButton("🔙 Kembali", callback_data=f"branch_{branch_name}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"👶 *Pengurusan Anak-Anak* ({branch_name}):",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    elif data.startswith("list_in_") or data.startswith("list_out_"):
        action = "in" if "list_in_" in data else "out"
        branch_name = data.replace("list_in_", "").replace("list_out_", "")
        action_label = "Check-In" if action == "in" else "Check-Out"
        kids_list = get_kids_for_branch(branch_name)

        keyboard = []
        if kids_list:
            for kid in kids_list:
                keyboard.append([
                    InlineKeyboardButton(f"👤 {kid}", callback_data=f"kidselect_{action}_{branch_name}_{kid}")
                ])
        else:
            keyboard.append([InlineKeyboardButton("⚠️ Tiada senarai anak", callback_data="none")])

        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data=f"menu_kids_{branch_name}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"👶 *Pilih Nama Anak untuk {action_label}* ({branch_name}):",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    elif data.startswith("kidselect_"):
        parts = data.split("_", 3)
        action, branch_name, kid_name = parts[1], parts[2], parts[3]
        action_text = "Check-In" if action == "in" else "Check-Out"

        keyboard = [
            [InlineKeyboardButton("⚡ Guna Masa Sekarang (Auto)", callback_data=f"kidact_auto_{action}_{branch_name}_{kid_name}")],
            [InlineKeyboardButton("✏️ Edit Masa Manual", callback_data=f"kidact_manual_{action}_{branch_name}_{kid_name}")],
            [InlineKeyboardButton("🔙 Kembali", callback_data=f"list_{action}_{branch_name}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"👶 *Pilihan Masa {action_text}*\n\nNama: *{kid_name}*\nCawangan: *{branch_name}*\n\nSila pilih kaedah penandaan masa:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    elif data.startswith("kidact_auto_"):
        parts = data.split("_", 4)
        action, branch_name, kid_name = parts[2], parts[3], parts[4]
        now = datetime.now(MY_TZ)
        action_text = "Check-In Anak" if action == "in" else "Check-Out Anak"

        keyboard = [[InlineKeyboardButton("🔙 Menu Anak", callback_data=f"menu_kids_{branch_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"✅ *Rekod Berjaya Disimpan (Auto)!*\n\n"
                 f"👶 Nama: *{kid_name}*\n"
                 f"📍 Cawangan: *{branch_name}*\n"
                 f"📝 Jenis: *{action_text}*\n"
                 f"⏰ Masa: *{now.strftime('%I:%M %p')}*\n"
                 f"📅 Tarikh: *{now.strftime('%d/%m/%Y')}*",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    elif data.startswith("kidact_manual_"):
        parts = data.split("_", 4)
        action, branch_name, kid_name = parts[2], parts[3], parts[4]

        user_sessions[user_id] = {
            "mode": "manual_time",
            "action": action,
            "branch": branch_name,
            "kid": kid_name,
        }

        await query.edit_message_text(
            text=f"✏️ *Edit Masa Manual*\n\nSila taip masa *Check-In/Out* baharu untuk *{kid_name}* di bawah:\n*(Contoh format: 08:15 AM atau 05:30 PM)*",
            parse_mode="Markdown",
        )

    elif data == "back_to_branches":
        keyboard = [[InlineKeyboardButton(f"🏢 {branch}", callback_data=f"branch_{branch}")] for branch in BRANCHES]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="👋 *Sistem Pengurusan Taska*\n\nSila pilih cawangan di bawah:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

# FUNGSI MENERIMA MESEJ TAIPAN (MASA MANUAL & KEMASKINI YURAN)
async def handle_text_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in user_sessions:
        session = user_sessions[user_id]
        mode = session.get("mode")
        input_text = update.message.text.strip()
        now = datetime.now(MY_TZ)

        # 1. PROCESS TAIPAN MASA MANUAL
        if mode == "manual_time":
            action_text = "Check-In Anak" if session["action"] == "in" else "Check-Out Anak"
            keyboard = [[InlineKeyboardButton("🔙 Menu Anak", callback_data=f"menu_kids_{session['branch']}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                text=f"✅ *Rekod Berjaya Disimpan (Manual)!*\n\n"
                     f"👶 Nama: *{session['kid']}*\n"
                     f"📍 Cawangan: *{session['branch']}*\n"
                     f"📝 Jenis: *{action_text}*\n"
                     f"⏰ Masa Manual: *{input_text}*\n"
                     f"📅 Tarikh: *{now.strftime('%d/%m/%Y')}*",
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )

        # 2. PROCESS KEMASKINI BAYARAN HARI INI
        elif mode == "update_pay":
            try:
                pay_val = float(input_text.replace("RM", "").strip())
                kid_name = session["kid"]
                branch_name = session["branch"]

                if kid_name not in db_yuran:
                    db_yuran[kid_name] = {"yuran": 350.0, "bayar": 0.0}

                # Tambah atau kemaskini bayaran
                db_yuran[kid_name]["bayar"] = pay_val
                info = db_yuran[kid_name]
                baki = info["yuran"] - info["bayar"]
                status = "Lunas ✅" if baki <= 0 else "Belum Lunas ❌"

                keyboard = [[InlineKeyboardButton("💳 Kembali ke Rekod Yuran", callback_data=f"yuran_kid_{branch_name}_{kid_name}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    text=f"✅ *Bayaran Yuran Berjaya Dikemaskini!*\n\n"
                         f"👤 Nama Anak: *{kid_name}*\n"
                         f"💵 Bayaran Terkini: *RM {pay_val:.2f}*\n"
                         f"📊 Baki Yuran: *RM {max(0, baki):.2f}*\n"
                         f"📌 Status: *{status}*",
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            except ValueError:
                await update.message.reply_text("⚠️ Sila taip nombor sahaja (contoh: `100` atau `350`).")
                return

        # 3. PROCESS KEMASKINI TOTAL YURAN BULANAN
        elif mode == "update_fee":
            try:
                fee_val = float(input_text.replace("RM", "").strip())
                kid_name = session["kid"]
                branch_name = session["branch"]

                if kid_name not in db_yuran:
                    db_yuran[kid_name] = {"yuran": fee_val, "bayar": 0.0}
                else:
                    db_yuran[kid_name]["yuran"] = fee_val

                keyboard = [[InlineKeyboardButton("💳 Kembali ke Rekod Yuran", callback_data=f"yuran_kid_{branch_name}_{kid_name}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    text=f"✅ *Jumlah Yuran Bulanan Berjaya Ditetapkan!*\n\n"
                         f"👤 Nama Anak: *{kid_name}*\n"
                         f"💰 Yuran Rasmi: *RM {fee_val:.2f}*",
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            except ValueError:
                await update.message.reply_text("⚠️ Sila taip nombor sahaja (contoh: `350` atau `400`).")
                return

        del user_sessions[user_id]

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
    application.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_inputs)
    )

    print("Bot Taska sedang aktif berjalan...")
    application.run_polling()
