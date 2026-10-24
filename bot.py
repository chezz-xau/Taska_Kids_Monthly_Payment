import logging
import os

from datetime import datetime
from threading import Thread
from flask import Flask
import pytz
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


# Simpanan sesi sementara untuk pilihan edit masa manual
user_sessions = {}


# ---------------------------------------------------------
# 3. HANDLERS / FUNGSI BOT
# ---------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  is_owner = user_id in OWNER_IDS

  if is_owner:
    keyboard = [
        [
            InlineKeyboardButton(
                "📋 Kehadiran", callback_data="owner_menu_kehadiran"
            )
        ],
        [InlineKeyboardButton("💳 Yuran", callback_data="owner_menu_yuran")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👑 *Dashboard Pengurusan (Owner/Admin)*\n\nSila pilih kategori"
        " pengurusan:",
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

  # --- MENU OWNER ---
  if data == "owner_menu_kehadiran":
    keyboard = [
        [
            InlineKeyboardButton(
                "👶 1. Anak", callback_data="owner_attendance_kids"
            )
        ],
        [
            InlineKeyboardButton(
                "👩‍🏫 2. Staff", callback_data="owner_attendance_staff"
            )
        ],
        [InlineKeyboardButton("🔙 Kembali", callback_data="owner_main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="📋 *Laporan Kehadiran*\n\nSila pilih jenis kehadiran:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  elif data == "owner_attendance_kids":
    keyboard = [[
        InlineKeyboardButton(
            "🔙 Kembali", callback_data="owner_menu_kehadiran"
        )
    ]]
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
    keyboard = [[
        InlineKeyboardButton(
            "🔙 Kembali", callback_data="owner_menu_kehadiran"
        )
    ]]
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

  elif data == "owner_menu_yuran":
    keyboard = [
        [InlineKeyboardButton("🔙 Kembali", callback_data="owner_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text_yuran = (
        "💳 *Ringkasan Status Yuran*\n"
        "───────────────\n"
        "1. *Nama Anak:* Ahmad\n"
        "2. *Jumlah Yuran:* RM 350.00\n"
        "3. *Bayaran Hari Ini:* RM 100.00\n"
        "4. *Baki:* RM 0.00\n"
        "5. *Status:* Lunas ✅\n"
        "───────────────\n"
        "1. *Nama Anak:* Ali\n"
        "2. *Jumlah Yuran:* RM 350.00\n"
        "3. *Bayaran Hari Ini:* RM 0.00\n"
        "4. *Baki:* RM 150.00\n"
        "5. *Status:* Belum Lunas ❌\n"
    )
    await query.edit_message_text(
        text=text_yuran, reply_markup=reply_markup, parse_mode="Markdown"
    )

  elif data == "owner_main_menu":
    keyboard = [
        [
            InlineKeyboardButton(
                "📋 Kehadiran", callback_data="owner_menu_kehadiran"
            )
        ],
        [InlineKeyboardButton("💳 Yuran", callback_data="owner_menu_yuran")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=(
            "👑 *Dashboard Pengurusan (Owner/Admin)*\n\nSila pilih kategori"
            " pengurusan:"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  # --- MENU STAFF & CAWANAGAN ---
  elif data.startswith("branch_"):
    branch_name = data.replace("branch_", "")
    keyboard = [
        [
            InlineKeyboardButton(
                "👶 Rekod Anak-Anak", callback_data=f"menu_kids_{branch_name}"
            )
        ],
        [
            InlineKeyboardButton(
                "👩‍🏫 Kehadiran Staff", callback_data=f"menu_staff_{branch_name}"
            )
        ],
        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_branches")],
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
            InlineKeyboardButton(
                "📥 Check-In Anak", callback_data=f"list_in_{branch_name}"
            ),
            InlineKeyboardButton(
                "📤 Check-Out Anak", callback_data=f"list_out_{branch_name}"
            ),
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
            InlineKeyboardButton(
                f"👤 {kid}",
                callback_data=f"kidselect_{action}_{branch_name}_{kid}",
            )
        ])
    else:
      keyboard.append([
          InlineKeyboardButton(
              "⚠️ Tiada senarai anak", callback_data="none"
          )
      ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Kembali", callback_data=f"menu_kids_{branch_name}"
        )
    ])
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
        [
            InlineKeyboardButton(
                "⚡ Guna Masa Sekarang (Auto)",
                callback_data=f"kidact_auto_{action}_{branch_name}_{kid_name}",
            )
        ],
        [
            InlineKeyboardButton(
                "✏️ Edit Masa Manual",
                callback_data=f"kidact_manual_{action}_{branch_name}_{kid_name}",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Kembali", callback_data=f"list_{action}_{branch_name}"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=(
            f"👶 *Pilihan Masa {action_text}*\n\nNama: *{kid_name}*\nCawangan:"
            f" *{branch_name}*\n\nSila pilih kaedah penandaan masa:"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  elif data.startswith("kidact_auto_"):
    parts = data.split("_", 4)
    action, branch_name, kid_name = parts[2], parts[3], parts[4]
    now = datetime.now(MY_TZ)
    action_text = "Check-In Anak" if action == "in" else "Check-Out Anak"

    keyboard = [[
        InlineKeyboardButton(
            "🔙 Menu Anak", callback_data=f"menu_kids_{branch_name}"
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=(
            f"✅ *Rekod Berjaya Disimpan (Auto)!*\n\n"
            f"👶 Nama: *{kid_name}*\n"
            f"📍 Cawangan: *{branch_name}*\n"
            f"📝 Jenis: *{action_text}*\n"
            f"⏰ Masa: *{now.strftime('%I:%M %p')}*\n"
            f"📅 Tarikh: *{now.strftime('%d/%m/%Y')}*"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  elif data.startswith("kidact_manual_"):
    parts = data.split("_", 4)
    action, branch_name, kid_name = parts[2], parts[3], parts[4]

    user_sessions[user_id] = {
        "action": action,
        "branch": branch_name,
        "kid": kid_name,
    }

    await query.edit_message_text(
        text=(
            f"✏️ *Edit Masa Manual*\n\nSila taip masa *Check-In/Out* baharu"
            f" untuk *{kid_name}* di bawah:\n*(Contoh format: 08:15 AM atau"
            " 05:30 PM)*"
        ),
        parse_mode="Markdown",
    )

  elif data == "back_to_branches":
    keyboard = [
        [InlineKeyboardButton(f"🏢 {branch}", callback_data=f"branch_{branch}")]
        for branch in BRANCHES
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="👋 *Sistem Pengurusan Taska*\n\nSila pilih cawangan di bawah:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def handle_manual_time_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  user_id = update.effective_user.id

  if user_id in user_sessions:
    session = user_sessions[user_id]
    input_time = update.message.text.strip()
    now = datetime.now(MY_TZ)
    action_text = (
        "Check-In Anak" if session["action"] == "in" else "Check-Out Anak"
    )

    keyboard = [[
        InlineKeyboardButton(
            "🔙 Menu Anak", callback_data=f"menu_kids_{session['branch']}"
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text=(
            f"✅ *Rekod Berjaya Disimpan (Manual)!*\n\n"
            f"👶 Nama: *{session['kid']}*\n"
            f"📍 Cawangan: *{session['branch']}*\n"
            f"📝 Jenis: *{action_text}*\n"
            f"⏰ Masa Manual: *{input_time}*\n"
            f"📅 Tarikh: *{now.strftime('%d/%m/%Y')}*"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

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
      MessageHandler(filters.TEXT & (~filters.COMMAND), handle_manual_time_input)
  )

  print("Bot Taska sedang aktif berjalan...")
  application.run_polling()
