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
# 2. ENVIRONMENT VARIABLES & SIMPANAN STATUS
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

# Database Sementara
dynamic_kids = {}
ot_staff_db = {}
db_yuran = {}
user_sessions = {}

# Rekod Status Kehadiran Harian (Anak & Staff)
attendance_status = {}  # Format: {"Ahmad": {"status": "in", "time": "08:15 AM"}}
staff_attendance_status = {}  # Format: {"Cikgu Siti": {"status": "in", "time": "07:50 AM"}}

def get_kids_for_branch(branch_name: str):
    clean_name = branch_name.upper().replace(" ", "_")
    kids_raw = os.environ.get(f"KIDS_{clean_name}", "")
    base_list = [k.strip() for k in kids_raw.split(",") if k.strip()] if kids_raw else []
    
    extra_kids = dynamic_kids.get(branch_name, [])
    all_kids = list(set(base_list + extra_kids))
    removed = dynamic_kids.get(f"removed_{branch_name}", [])
    return [k for k in all_kids if k not in removed]

def get_staff_for_branch(branch_name: str):
    clean_name = branch_name.upper().replace(" ", "_")
    staff_raw = os.environ.get(f"STAFF_{clean_name}", "")
    if not staff_raw:
        return []
    return [s.strip() for s in staff_raw.split(",") if s.strip()]

# ---------------------------------------------------------
# 3. HANDLERS / FUNGSI BOT
# ---------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_owner = user_id in OWNER_IDS

    if is_owner:
        keyboard = [
            [InlineKeyboardButton("📋 Kehadiran", callback_data="owner_menu_kehadiran")],
            [InlineKeyboardButton("💳 Status & Bayaran Yuran", callback_data="owner_select_branch_yuran")],
            [InlineKeyboardButton("📝 Pendaftaran Baru Anak-Anak", callback_data="owner_select_branch_register")]
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
        
        report_text = "👶 *Laporan Kehadiran Anak (Harian)*\n───────────────────────\n"
        if not attendance_status:
            report_text += "⚠️ Belum ada rekod kehadiran anak hari ini."
        else:
            for name, rec in attendance_status.items():
                st_icon = "🔴 Checked-In" if rec["status"] == "in" else "⚪ Checked-Out"
                report_text += f"👤 *{name}*: {st_icon} (`{rec['time']}`)\n"
                
        await query.edit_message_text(text=report_text, reply_markup=reply_markup, parse_mode="Markdown")

    elif data == "owner_attendance_staff":
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="owner_menu_kehadiran")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        staff_text = "👩‍🏫 *Rekod Kehadiran Staff (Harian)*\n───────────────────────\n"
        if not staff_attendance_status:
            staff_text += "⚠️ Belum ada rekod kehadiran staff hari ini."
        else:
            for sname, srec in staff_attendance_status.items():
                st_icon = "🔴 Clocked-In" if srec["status"] == "in" else "⚪ Clocked-Out"
                staff_text += f"👩‍🏫 *{sname}*: {st_icon} (`{srec['time']}`)\n"

        await query.edit_message_text(text=staff_text, reply_markup=reply_markup, parse_mode="Markdown")

    elif data == "owner_select_branch_register":
        keyboard = [[InlineKeyboardButton(f"🏢 {branch}", callback_data=f"reg_br_{branch}")] for branch in BRANCHES]
        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="owner_main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="📝 *Pendaftaran Baru Anak-Anak*", reply_markup=reply_markup, parse_mode="Markdown")

    elif data.startswith("reg_br_"):
        branch_name = data.replace("reg_br_", "")
        user_sessions[user_id] = {"mode": "register_kid_name", "branch": branch_name}
        await query.edit_message_text(text=f"📝 *Pendaftaran Baru* ({branch_name})\n\nTaip nama anak baharu:", parse_mode="Markdown")

    elif data == "owner_select_branch_yuran":
        keyboard = [[InlineKeyboardButton(f"🏢 {branch}", callback_data=f"yuran_br_{branch}")] for branch in BRANCHES]
        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="owner_main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="💳 *Pengurusan Yuran*", reply_markup=reply_markup, parse_mode="Markdown")

    elif data.startswith("yuran_br_"):
        branch_name = data.replace("yuran_br_", "")
        kids_list = get_kids_for_branch(branch_name)
        keyboard = []
        if kids_list:
            for kid in kids_list:
                keyboard.append([InlineKeyboardButton(f"👤 {kid}", callback_data=f"yuran_kid_{branch_name}_{kid}")])
        else:
            keyboard.append([InlineKeyboardButton("⚠️ Tiada senarai anak", callback_data="none")])
        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="owner_select_branch_yuran")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"💳 *Pilih Anak* ({branch_name}):", reply_markup=reply_markup, parse_mode="Markdown")

    elif data.startswith("yuran_kid_"):
        parts = data.split("_", 3)
        branch_name, kid_name = parts[2], parts[3]
        info = db_yuran.get(kid_name, {"yuran": 0.0, "bayar": 0.0})
        baki = info["yuran"] - info["bayar"]
        status = "Lunas ✅" if baki <= 0 and info["yuran"] > 0 else "Belum Lunas ❌"

        text_detail = (
            f"💳 *Status Yuran*: {kid_name}\n"
            f"• Yuran: RM {info['yuran']:.2f}\n"
            f"• Bayaran: RM {info['bayar']:.2f}\n"
            f"• Baki: RM {max(0, baki):.2f}\n"
            f"• Status: {status}"
        )
        keyboard = [
            [InlineKeyboardButton("💵 Kemaskini Bayaran", callback_data=f"pay_update_{branch_name}_{kid_name}")],
            [InlineKeyboardButton("✏️ Set Yuran Bulanan", callback_data=f"fee_update_{branch_name}_{kid_name}")],
            [InlineKeyboardButton("🔙 Kembali", callback_data=f"yuran_br_{branch_name}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=text_detail, reply_markup=reply_markup, parse_mode="Markdown")

    elif data.startswith("pay_update_"):
        parts = data.split("_", 3)
        user_sessions[user_id] = {"mode": "update_pay", "branch": parts[2], "kid": parts[3]}
        await query.edit_message_text(text=f"💵 Taip bayaran baharu untuk *{parts[3]}*:", parse_mode="Markdown")

    elif data.startswith("fee_update_"):
        parts = data.split("_", 3)
        user_sessions[user_id] = {"mode": "update_fee", "branch": parts[2], "kid": parts[3]}
        await query.edit_message_text(text=f"✏️ Taip yuran bulanan rasmi untuk *{parts[3]}*:", parse_mode="Markdown")

    elif data.startswith("del_kid_"):
        parts = data.split("_", 3)
        branch_name, kid_name = parts[2], parts[3]
        key_rem = f"removed_{branch_name}"
        if key_rem not in dynamic_kids:
            dynamic_kids[key_rem] = []
        dynamic_kids[key_rem].append(kid_name)
        keyboard = [[InlineKeyboardButton("🔙 Senarai Cawangan", callback_data="owner_main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"❌ *{kid_name}* dikeluarkan dari senarai.", reply_markup=reply_markup, parse_mode="Markdown")

    elif data == "owner_main_menu":
        keyboard = [
            [InlineKeyboardButton("📋 Kehadiran", callback_data="owner_menu_kehadiran")],
            [InlineKeyboardButton("💳 Status & Bayaran Yuran", callback_data="owner_select_branch_yuran")],
            [InlineKeyboardButton("📝 Pendaftaran Baru Anak-Anak", callback_data="owner_select_branch_register")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="👑 *Dashboard Owner*", reply_markup=reply_markup, parse_mode="Markdown")

    # ==========================================
    # 👩‍🏫 SUB-MENU STAFF & ANAK
    # ==========================================
    elif data.startswith("branch_"):
        branch_name = data.replace("branch_", "")
        keyboard = [
            [InlineKeyboardButton("👶 Rekod Anak-Anak", callback_data=f"menu_kids_{branch_name}")],
            [InlineKeyboardButton("👩‍🏫 Kehadiran Staff", callback_data=f"menu_staff_{branch_name}")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_branches")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"📍 Cawangan: *{branch_name}*", reply_markup=reply_markup, parse_mode="Markdown")

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
        await query.edit_message_text(text=f"👶 *Pengurusan Anak-Anak* ({branch_name}):", reply_markup=reply_markup, parse_mode="Markdown")

    # PAPARAN SENARAI ANAK (DENGAN NAMA MERAH JIKA SUDAH CHECK-IN)
    elif data.startswith("list_in_") or data.startswith("list_out_"):
        action = "in" if "list_in_" in data else "out"
        branch_name = data.replace("list_in_", "").replace("list_out_", "")
        action_label = "Check-In" if action == "in" else "Check-Out"
        kids_list = get_kids_for_branch(branch_name)

        keyboard = []
        if kids_list:
            for kid in kids_list:
                status_rec = attendance_status.get(kid, {})
                current_st = status_rec.get("status", "out")
                
                if current_st == "in":
                    btn_label = f"🔴 {kid} (Sudah Check-In)"
                else:
                    btn_label = f"👤 {kid}"

                keyboard.append([InlineKeyboardButton(btn_label, callback_data=f"kidselect_{action}_{branch_name}_{kid}")])
        else:
            keyboard.append([InlineKeyboardButton("⚠️ Tiada senarai anak", callback_data="none")])

        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data=f"menu_kids_{branch_name}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"👶 *Pilih Nama Anak untuk {action_label}* ({branch_name}):", reply_markup=reply_markup, parse_mode="Markdown")

    elif data.startswith("kidselect_"):
        parts = data.split("_", 3)
        action, branch_name, kid_name = parts[1], parts[2], parts[3]
        action_text = "Check-In" if action == "in" else "Check-Out"

        current_rec = attendance_status.get(kid_name, {})
        current_st = current_rec.get("status", "out")

        if action == "in" and current_st == "in":
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"list_in_{branch_name}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text=f"🛑 *AMARAN: CHECK-IN DIBLOK!*\n\n"
                     f"🔴 *{kid_name}* sudah pun Check-In pada jam *{current_rec.get('time', '-') }*!\n\n"
                     f"Tidak boleh buat Check-In kali kedua.",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            return

        keyboard = [
            [InlineKeyboardButton("⚡ Guna Masa Sekarang (Auto)", callback_data=f"kidact_auto_{action}_{branch_name}_{kid_name}")],
            [InlineKeyboardButton("✏️ Edit Masa Manual", callback_data=f"kidact_manual_{action}_{branch_name}_{kid_name}")],
            [InlineKeyboardButton("🔙 Kembali", callback_data=f"list_{action}_{branch_name}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"👶 *Pilihan Masa {action_text}*\n\nNama: *{kid_name}*\nCawangan: *{branch_name}*", reply_markup=reply_markup, parse_mode="Markdown")

    elif data.startswith("kidact_auto_"):
        parts = data.split("_", 4)
        action, branch_name, kid_name = parts[2], parts[3], parts[4]
        now = datetime.now(MY_TZ)
        time_str = now.strftime('%I:%M %p')
        action_text = "Check-In Anak" if action == "in" else "Check-Out Anak"

        attendance_status[kid_name] = {"status": action, "time": time_str}

        keyboard = [[InlineKeyboardButton("🔙 Menu Anak", callback_data=f"menu_kids_{branch_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"✅ *Rekod Berjaya Disimpan (Auto)!*\n\n"
                 f"👶 Nama: *{kid_name}*\n"
                 f"📍 Cawangan: *{branch_name}*\n"
                 f"📝 Status: *{'🔴 Check-In' if action=='in' else '⚪ Check-Out'}*\n"
                 f"⏰ Masa: *{time_str}*\n"
                 f"📅 Tarikh: *{now.strftime('%d/%m/%Y')}*",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    elif data.startswith("kidact_manual_"):
        parts = data.split("_", 4)
        user_sessions[user_id] = {
            "mode": "manual_time",
            "action": parts[2],
            "branch": parts[3],
            "kid": parts[4],
        }
        await query.edit_message_text(text=f"✏️ *Edit Masa Manual* untuk *{parts[4]}*:\n*(Contoh: 08:15 AM)*", parse_mode="Markdown")

    # ==========================================
    # 👩‍🏫 PENGURUSAN STAFF (SENARAI NAMA & KUNCI MERAH)
    # ==========================================
    elif data.startswith("menu_staff_"):
        branch_name = data.replace("menu_staff_", "")
        keyboard = [
            [
                InlineKeyboardButton("🟢 Clock-In Staff", callback_data=f"slist_in_{branch_name}"),
                InlineKeyboardButton("🔴 Clock-Out Staff", callback_data=f"slist_out_{branch_name}")
            ],
            [InlineKeyboardButton("🔙 Kembali", callback_data=f"branch_{branch_name}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"👩‍🏫 *Kehadiran Staff* ({branch_name}):", reply_markup=reply_markup, parse_mode="Markdown")

    # PAPARAN SENARAI STAFF DENGAN WARNA MERAH JIKA SUDAH CLOCK-IN
    elif data.startswith("slist_in_") or data.startswith("slist_out_"):
        action = "in" if "slist_in_" in data else "out"
        branch_name = data.replace("slist_in_", "").replace("slist_out_", "")
        action_label = "Clock-In" if action == "in" else "Clock-Out"
        staff_list = get_staff_for_branch(branch_name)

        keyboard = []
        if staff_list:
            for sname in staff_list:
                s_rec = staff_attendance_status.get(sname, {})
                c_st = s_rec.get("status", "out")

                if c_st == "in":
                    s_label = f"🔴 {sname} (Sudah Clock-In)"
                else:
                    s_label = f"👩‍🏫 {sname}"

                keyboard.append([InlineKeyboardButton(s_label, callback_data=f"staffselect_{action}_{branch_name}_{sname}")])
        else:
            keyboard.append([InlineKeyboardButton("⚠️ Tiada senarai staff (Semak Render)", callback_data="none")])

        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data=f"menu_staff_{branch_name}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"👩‍🏫 *Pilih Nama Staff untuk {action_label}* ({branch_name}):", reply_markup=reply_markup, parse_mode="Markdown")

    # KAWALAN HALANGAN CLOCK-IN STAFF 2 KALI
    elif data.startswith("staffselect_"):
        parts = data.split("_", 3)
        action, branch_name, staff_name = parts[1], parts[2], parts[3]
        
        s_rec = staff_attendance_status.get(staff_name, {})
        c_st = s_rec.get("status", "out")

        if action == "in" and c_st == "in":
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"slist_in_{branch_name}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text=f"🛑 *AMARAN: CLOCK-IN DIBLOK!*\n\n"
                     f"🔴 *{staff_name}* sudah pun Clock-In pada jam *{s_rec.get('time', '-') }*!\n\n"
                     f"Tidak boleh Clock-In kali kedua.",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            return

        now = datetime.now(MY_TZ)
        time_str = now.strftime('%I:%M %p')
        action_text = "Clock-In Staff" if action == "in" else "Clock-Out Staff"

        # Kemaskini Status Staff
        staff_attendance_status[staff_name] = {"status": action, "time": time_str}

        keyboard = [[InlineKeyboardButton("🔙 Menu Staff", callback_data=f"menu_staff_{branch_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"✅ *Kehadiran Staff Direkodkan!*\n\n"
                 f"👩‍🏫 Staff: *{staff_name}*\n"
                 f"📍 Cawangan: *{branch_name}*\n"
                 f"📝 Status: *{'🟢 Clock-In' if action=='in' else '🔴 Clock-Out'}*\n"
                 f"⏰ Masa: *{time_str}*\n"
                 f"📅 Tarikh: *{now.strftime('%d/%m/%Y')}*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif data == "back_to_branches":
        keyboard = [[InlineKeyboardButton(f"🏢 {branch}", callback_data=f"branch_{branch}")] for branch in BRANCHES]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="👋 *Sistem Pengurusan Taska*", reply_markup=reply_markup, parse_mode="Markdown")

# ---------------------------------------------------------
# FUNGSI MENERIMA MESEJ TAIPAN
# ---------------------------------------------------------
async def handle_text_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    input_text = update.message.text.strip()
    now = datetime.now(MY_TZ)

    if "Late Pick Up" in input_text:
        await update.message.reply_text("⏱️ *Kiraan Denda Lewat Pick-Up*: RM 10.00 / 30 Minit selepas 06:00 PM.", parse_mode="Markdown")
        return

    elif "OT Staff" in input_text:
        user_sessions[user_id] = {"mode": "input_ot"}
        await update.message.reply_text("⏳ Taip nama staff dan jumlah jam OT (Contoh: Cikgu Siti - 2 Jam):", parse_mode="Markdown")
        return

    elif "Pendaftaran Baru" in input_text:
        keyboard = [[InlineKeyboardButton(f"🏢 {branch}", callback_data=f"reg_br_{branch}")] for branch in BRANCHES]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📝 *Pendaftaran Baru Anak-Anak*:", reply_markup=reply_markup, parse_mode="Markdown")
        return

    elif "Edit Masa Manual" in input_text:
        keyboard = [[InlineKeyboardButton(f"🏢 {branch}", callback_data=f"branch_{branch}")] for branch in BRANCHES]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✏️ Pilih cawangan untuk edit masa manual:", reply_markup=reply_markup, parse_mode="Markdown")
        return

    elif "Status & Bayaran Yuran" in input_text:
        keyboard = [[InlineKeyboardButton(f"🏢 {branch}", callback_data=f"yuran_br_{branch}")] for branch in BRANCHES]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("💳 *Pengurusan Yuran*:", reply_markup=reply_markup, parse_mode="Markdown")
        return

    elif "Laporan Harian" in input_text:
        keyboard = [
            [InlineKeyboardButton("📋 Kehadiran Anak", callback_data="owner_attendance_kids")],
            [InlineKeyboardButton("👩‍🏫 Kehadiran Staff", callback_data="owner_attendance_staff")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"📊 *Ringkasan Laporan Harian* ({now.strftime('%d/%m/%Y')}):", reply_markup=reply_markup, parse_mode="Markdown")
        return

    elif "Laporan Bulanan" in input_text:
        total_kutipan = sum([v.get("bayar", 0.0) for v in db_yuran.values()])
        await update.message.reply_text(f"📊 *Laporan Bulanan*: RM {total_kutipan:.2f} (Total Anak: {len(db_yuran)})", parse_mode="Markdown")
        return

    elif "Keluarkan Dari Senarai" in input_text:
        keyboard = []
        for branch in BRANCHES:
            kids = get_kids_for_branch(branch)
            for k in kids:
                keyboard.append([InlineKeyboardButton(f"❌ {k} ({branch})", callback_data=f"del_kid_{branch}_{k}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("❌ *Keluarkan Anak Dari Senarai*:", reply_markup=reply_markup, parse_mode="Markdown")
        return

    # SEKSYEN SESSION
    if user_id in user_sessions:
        session = user_sessions[user_id]
        mode = session.get("mode")

        if mode == "input_ot":
            await update.message.reply_text(f"✅ *Rekod OT Disimpan*: {input_text}", parse_mode="Markdown")
            del user_sessions[user_id]

        elif mode == "register_kid_name":
            user_sessions[user_id] = {"mode": "register_kid_fee", "branch": session["branch"], "kid_name": input_text}
            await update.message.reply_text(f"💰 Taip jumlah yuran bulanan rasmi untuk *{input_text}*:", parse_mode="Markdown")

        elif mode == "register_kid_fee":
            try:
                fee_val = float(input_text.replace("RM", "").strip())
                b_name, k_name = session["branch"], session["kid_name"]
                if b_name not in dynamic_kids:
                    dynamic_kids[b_name] = []
                dynamic_kids[b_name].append(k_name)
                db_yuran[k_name] = {"yuran": fee_val, "bayar": 0.0}
                await update.message.reply_text(f"✅ *{k_name}* berjaya didaftarkan dengan Yuran RM {fee_val:.2f}!", parse_mode="Markdown")
                del user_sessions[user_id]
            except ValueError:
                await update.message.reply_text("⚠️ Sila taip nombor sahaja.")

        elif mode == "manual_time":
            k_name, act, b_name = session["kid"], session["action"], session["branch"]
            attendance_status[k_name] = {"status": act, "time": input_text}
            keyboard = [[InlineKeyboardButton("🔙 Menu Anak", callback_data=f"menu_kids_{b_name}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"✅ *Rekod Manual Disimpan!*\n\n👶 Nama: *{k_name}*\n⏰ Masa: *{input_text}*", reply_markup=reply_markup, parse_mode="Markdown")
            del user_sessions[user_id]

        elif mode == "update_pay":
            try:
                pay_val = float(input_text.replace("RM", "").strip())
                k_name, b_name = session["kid"], session["branch"]
                if k_name not in db_yuran:
                    db_yuran[k_name] = {"yuran": 0.0, "bayar": 0.0}
                db_yuran[k_name]["bayar"] = pay_val
                await update.message.reply_text(f"✅ Bayaran *{k_name}* dikemaskini: RM {pay_val:.2f}", parse_mode="Markdown")
                del user_sessions[user_id]
            except ValueError:
                await update.message.reply_text("⚠️ Sila taip nombor sahaja.")

        elif mode == "update_fee":
            try:
                fee_val = float(input_text.replace("RM", "").strip())
                k_name = session["kid"]
                if k_name not in db_yuran:
                    db_yuran[k_name] = {"yuran": fee_val, "bayar": 0.0}
                else:
                    db_yuran[k_name]["yuran"] = fee_val
                await update.message.reply_text(f"✅ Yuran *{k_name}* ditetapkan: RM {fee_val:.2f}", parse_mode="Markdown")
                del user_sessions[user_id]
            except ValueError:
                await update.message.reply_text("⚠️ Sila taip nombor sahaja.")

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
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_inputs))

    print("Bot Taska sedang aktif berjalan...")
    application.run_polling()
