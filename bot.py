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

# Zone Waktu Malaysia
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

# Ambil Senarai Cawangan
branches_raw = os.environ.get("BRANCHES", "Taska Utama")
BRANCHES = [b.strip() for b in branches_raw.split(",") if b.strip()]


# ---------------------------------------------------------
# 3. FUNGSI PEMBANTU (HELPERS)
# ---------------------------------------------------------
def get_kids_for_branch(branch_name: str):
  """Membaca env var KIDS_<NAMA_CAWANGAN> secara automatik.

  Contoh: 'Taska Corner' -> membaca env var 'KIDS_TASKA_CORNER'
  """
  clean_name = branch_name.upper().replace(" ", "_")
  env_key = f"KIDS_{clean_name}"

  kids_raw = os.environ.get(env_key, "")
  if not kids_raw:
    return []

  return [k.strip() for k in kids_raw.split(",") if k.strip()]


# ---------------------------------------------------------
# 4. HANDLERS / FUNGSI BOT
# ---------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id

  if OWNER_IDS and user_id not in OWNER_IDS:
    await update.message.reply_text(
        "Maaf, anda tidak mempunyai kebenaran untuk mengakses bot pengurusan"
        " ini."
    )
    return

  keyboard = [
      [InlineKeyboardButton(f"🏢 {branch}", callback_data=f"branch_{branch}")]
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

  # 1. Pilih Cawangan -> Menu Utama (Anak vs Staff)
  if data.startswith("branch_"):
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
        [
            InlineKeyboardButton(
                "🔙 Kembali", callback_data="back_to_branches"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=f"📍 Cawangan: *{branch_name}*\n\nSila pilih kategori pengurusan:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  # 2. Menu Rekod Anak-Anak
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
        [
            InlineKeyboardButton(
                "🔙 Kembali", callback_data=f"branch_{branch_name}"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=f"👶 *Pengurusan Anak-Anak* ({branch_name})\n\nSila pilih tindakan:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  # 3. Paparkan Senarai Nama Anak Mengikut Environment Variable Cawangan
  elif data.startswith("list_in_") or data.startswith("list_out_"):
    action = "in" if "list_in_" in data else "out"
    branch_name = data.replace("list_in_", "").replace("list_out_", "")
    action_label = "Check-In" if action == "in" else "Check-Out"

    # Dapatkan senarai anak secara khusus dari Environment Variable
    kids_list = get_kids_for_branch(branch_name)

    keyboard = []
    if kids_list:
      for kid in kids_list:
        keyboard.append([
            InlineKeyboardButton(
                f"👤 {kid}", callback_data=f"kidact_{action}_{branch_name}_{kid}"
            )
        ])
    else:
      keyboard.append([
          InlineKeyboardButton(
              "⚠️ Tiada senarai anak (Sila semak Render)",
              callback_data="none",
          )
      ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Kembali", callback_data=f"menu_kids_{branch_name}"
        )
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=(
            f"👶 *Pilih Nama Anak untuk {action_label}* ({branch_name}):"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  # 4. Simpan Rekod Kehadiran Anak
  elif data.startswith("kidact_"):
    parts = data.split("_", 3)
    action = parts[1]
    branch_name = parts[2]
    kid_name = parts[3]

    now = datetime.now(MY_TZ)
    time_str = now.strftime("%I:%M %p")
    date_str = now.strftime("%d/%m/%Y")
    action_text = "Check-In Anak" if action == "in" else "Check-Out Anak"

    keyboard = [[
        InlineKeyboardButton(
            "🔙 Menu Anak", callback_data=f"menu_kids_{branch_name}"
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=(
            f"✅ *Rekod Berjaya Disimpan!*\n\n"
            f"👶 Nama Anak: *{kid_name}*\n"
            f"📍 Cawangan: *{branch_name}*\n"
            f"📝 Jenis: *{action_text}*\n"
            f"⏰ Waktu: *{time_str}*\n"
            f"📅 Tarikh: *{date_str}*"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  # 5. Menu Kehadiran Staff
  elif data.startswith("menu_staff_"):
    branch_name = data.replace("menu_staff_", "")

    keyboard = [
        [
            InlineKeyboardButton(
                "🟢 Clock-In Staff",
                callback_data=f"staff_clockin_{branch_name}",
            ),
            InlineKeyboardButton(
                "🔴 Clock-Out Staff",
                callback_data=f"staff_clockout_{branch_name}",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔙 Kembali", callback_data=f"branch_{branch_name}"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=f"👩‍🏫 *Kehadiran Staff* ({branch_name})\n\nSila pilih tindakan:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  # 6. Proses Rekod Staff
  elif data.startswith("staff_clockin_") or data.startswith("staff_clockout_"):
    is_clockin = "staff_clockin_" in data
    branch_name = data.replace("staff_clockin_", "").replace(
        "staff_clockout_", ""
    )

    now = datetime.now(MY_TZ)
    time_str = now.strftime("%I:%M %p")
    date_str = now.strftime("%d/%m/%Y")
    user_name = update.effective_user.first_name
    action_text = "Clock-In Staff" if is_clockin else "Clock-Out Staff"

    keyboard = [[
        InlineKeyboardButton(
            "🔙 Kembali", callback_data=f"menu_staff_{branch_name}"
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=(
            f"✅ *Kehadiran Staff Direkodkan!*\n\n"
            f"👤 Staff: *{user_name}*\n"
            f"📍 Cawangan: *{branch_name}*\n"
            f"📝 Status: *{action_text}*\n"
            f"⏰ Waktu: *{time_str}*\n"
            f"📅 Tarikh: *{date_str}*"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  # 7. Button Kembali ke Cawangan Utama
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


# ---------------------------------------------------------
# 5. MAIN PROGRAM
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
