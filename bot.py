import logging
import os
import pytz
from datetime import datetime
from threading import Thread
from flask import Flask
import psycopg2
from psycopg2.extras import RealDictCursor
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
    return "Bot Taska sedang berjalan 24/7 dengan PostgreSQL!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

Thread(target=run_web, daemon=True).start()

# ---------------------------------------------------------
# 2. ENVIRONMENT VARIABLES & POSTGRESQL DATABASE SETUP
# ---------------------------------------------------------
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

owner_ids_raw = os.environ.get("OWNER_IDS", "")
OWNER_IDS = [
    int(x.strip()) for x in owner_ids_raw.split(",") if x.strip().isdigit()
]

BRANCHES = [
    b.strip()
    for b in os.environ.get("BRANCHES", "Taska Utama").split(",")
    if b.strip()
]

user_sessions = {}

# Fungsi Akses Database PostgreSQL
def get_db_connection():
    if not DATABASE_URL:
        logger.error("DATABASE_URL tidak dijumpai dalam Environment Variables!")
        return None
    try:
        db_url = DATABASE_URL
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"Ralat Sambungan Database: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    # Jadual Anak Dinamik
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kids (
            id SERIAL PRIMARY KEY,
            branch_name VARCHAR(100),
            kid_name VARCHAR(100) UNIQUE,
            status VARCHAR(20) DEFAULT 'active'
        );
    """)
    # Jadual Yuran
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fees (
            kid_name VARCHAR(100) PRIMARY KEY,
            total_yuran NUMERIC(10, 2) DEFAULT 0.00,
            bayar_hari_ini NUMERIC(10, 2) DEFAULT 0.00,
            total_paid NUMERIC(10, 2) DEFAULT 0.00
        );
    """)
    # Jadual Kehadiran Harian
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            person_name VARCHAR(100) PRIMARY KEY,
            branch_name VARCHAR(100),
            person_type VARCHAR(20),
            status VARCHAR(20),
            check_time VARCHAR(20),
            date_str VARCHAR(20)
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

# Cipta jadual semasa startup
init_db()

# ---------------------------------------------------------
# FUNGSI HELPER DATABASE
# ---------------------------------------------------------
def get_kids_for_branch(branch_name: str):
    clean_name = branch_name.upper().replace(" ", "_")
    kids_raw = os.environ.get(f"KIDS_{clean_name}", "")
    base_list = [k.strip() for k in kids_raw.split(",") if k.strip()] if kids_raw else []

    conn = get_db_connection()
    db_kids = []
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT kid_name FROM kids WHERE branch_name = %s AND status = 'active';", (branch_name,))
        db_kids = [row['kid_name'] for row in cur.fetchall()]
        cur.close()
        conn.close()

    return list(set(base_list + db_kids))

def get_staff_for_branch(branch_name: str):
    clean_name = branch_name.upper().replace(" ", "_")
    staff_raw = os.environ.get(f"STAFF_{clean_name}", "")
    if not staff_raw:
        return []
    return [s.strip() for s in staff_raw.split(",") if s.strip()]

def get_attendance_record(person_name: str):
    conn = get_db_connection()
    rec = None
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM attendance WHERE person_name = %s;", (person_name,))
        rec = cur.fetchone()
        cur.close()
        conn.close()
    return rec

def set_attendance_record(person_name: str, branch_name: str, person_type: str, status: str, time_str: str):
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        today = datetime.now(MY_TZ).strftime('%d/%m/%Y')
        cur.execute("""
            INSERT INTO attendance (person_name, branch_name, person_type, status, check_time, date_str)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (person_name) 
            DO UPDATE SET status = EXCLUDED.status, check_time = EXCLUDED.check_time, date_str = EXCLUDED.date_str;
        """, (person_name, branch_name, person_type, status, time_str, today))
        conn.commit()
        cur.close()
        conn.close()

def get_fee_record(kid_name: str):
    conn = get_db_connection()
    rec = None
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM fees WHERE kid_name = %s;", (kid_name,))
        rec = cur.fetchone()
        cur.close()
        conn.close()
    if not rec:
        return {"yuran": 0.0, "bayar_hari_ini": 0.0, "total_paid": 0.0}
    return {"yuran": float(rec['total_yuran']), "bayar_hari_ini": float(rec['bayar_hari_ini']), "total_paid": float(rec['total_paid'])}

def update_fee_record(kid_name: str, yuran: float = None, add_pay: float = None):
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        current = get_fee_record(kid_name)
        new_yuran = yuran if yuran is not None else current["yuran"]
        new_pay_today = add_pay if add_pay is not None else current["bayar_hari_ini"]
        new_total_paid = current["total_paid"] + (add_pay if add_pay is not None else 0.0)

        cur.execute("""
            INSERT INTO fees (kid_name, total_yuran, bayar_hari_ini, total_paid)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (kid_name)
            DO UPDATE SET total_yuran = %s, bayar_hari_ini = %s, total_paid = %s;
        """, (kid_name, new_yuran, new_pay_today, new_total_paid, new_yuran, new_pay_today, new_total_paid))
        conn.commit()
        cur.close()
        conn.close()

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
            [InlineKeyboardButton("📝 Pendaftaran Baru Anak-Anak", callback_data="owner_select_branch_register")],
            [InlineKeyboardButton("❌ Keluarkan Dari Senarai", callback_data="owner_select_branch_delete")]
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
        
        report_text = "👶 *Laporan Kehadiran Anak (Semua Taska)*\n───────────────────────\n"

        for branch in BRANCHES:
            kids_list = get_kids_for_branch(branch)
            report_text += f"\n🏢 *{branch}*\n"
            branch_has_kid = False
            for kid in kids_list:
                rec = get_attendance_record(kid)
                if rec and rec["person_type"] == "kid":
                    st_icon = "🔴 Checked-In" if rec["status"] == "in" else "⚪ Checked-Out"
                    report_text += f" • {kid}: {st_icon} (`{rec['check_time']}`)\n"
                else:
                    report_text += f" • {kid}: ⚪ Belum Check-In\n"
                branch_has_kid = True
            if not branch_has_kid:
                report_text += "  _(Tiada senarai anak)_\n"

        await query.edit_message_text(text=report_text, reply_markup=reply_markup, parse_mode="Markdown")

    elif data == "owner_attendance_staff":
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="owner_menu_kehadiran")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        staff_text = "👩‍🏫 *Rekod Kehadiran Staff (Semua Taska)*\n───────────────────────\n"

        for branch in BRANCHES:
            staff_list = get_staff_for_branch(branch)
            staff_text += f"\n🏢 *{branch}*\n"
            branch_has_staff = False
            for sname in staff_list:
                srec = get_attendance_record(sname)
                if srec and srec["person_type"] == "staff":
                    st_icon = "🔴 Clocked-In" if srec["status"] == "in" else "⚪ Clocked-Out"
                    staff_text += f" • {sname}: {st_icon} (`{srec['check_time']}`)\n"
                else:
                    staff_text += f" • {sname}: ⚪ Belum Clock-In\n"
                branch_has_staff = True
            if not branch_has_staff:
                staff_text += "  _(Tiada senarai staff)_\n"

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

    elif data == "owner_select_branch_delete":
        keyboard = [[InlineKeyboardButton(f"🏢 {branch}", callback_data=f"del_br_{branch}")] for branch in BRANCHES]
        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="owner_main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="❌ *Pilih Cawangan untuk Keluarkan Dari Senarai*:", reply_markup=reply_markup, parse_mode="Markdown")

    elif data.startswith("del_br_"):
        branch_name = data.replace("del_br_", "")
        kids_list = get_kids_for_branch(branch_name)
        keyboard = []
        if kids_list:
            for kid in kids_list:
                keyboard.append([InlineKeyboardButton(f"🗑️ {kid}", callback_data=f"del_confirm_{branch_name}_{kid}")])
        else:
            keyboard.append([InlineKeyboardButton("⚠️ Tiada senarai anak", callback_data="none")])
        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="owner_select_branch_delete")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"❌ *Pilih Anak untuk Dikeluarkan* ({branch_name}):", reply_markup=reply_markup, parse_mode="Markdown")

    elif data.startswith("del_confirm_"):
        parts = data.split("_", 3)
        branch_name, kid_name = parts[2], parts[3]
        
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM kids WHERE LOWER(kid_name) = LOWER(%s);", (kid_name,))
            cur.execute("DELETE FROM fees WHERE LOWER(kid_name) = LOWER(%s);", (kid_name,))
            cur.execute("DELETE FROM attendance WHERE LOWER(person_name) = LOWER(%s);", (kid_name,))
            conn.commit()
            cur.close()
            conn.close()

        keyboard = [[InlineKeyboardButton("🔙 Kembali ke Dashboard", callback_data="owner_main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"✅ *Berjaya Dikeluarkan!*\n\n👶 Nama: *{kid_name}*\n📍 Cawangan: *{branch_name}*\n\nTelah dipadamkan sepenuhnya daripada sistem pangkalan data.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

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
        
        info = get_fee_record(kid_name)
        total_yuran = info["yuran"]
        bayar_hari_ini = info["bayar_hari_ini"]
        total_paid = info["total_paid"]
        baki = total_yuran - total_paid
        status = "Lunas ✅" if baki <= 0 and total_yuran > 0 else "Belum Lunas ❌"

        text_detail = (
            f"💳 *Status & Bayaran Yuran*: {kid_name}\n"
            f"📍 Cawangan: {branch_name}\n"
            f"───────────────────────\n"
            f"1. *Jumlah Yuran:* RM {total_yuran:.2f}\n"
            f"2. *Bayaran (Hari Ini):* RM {bayar_hari_ini:.2f}\n"
            f"3. *Jumlah Terkini (Sudah Dibayar):* RM {total_paid:.2f}\n"
            f"4. *Baki:* RM {max(0, baki):.2f}\n"
            f"5. *Status:* {status}\n"
            f"───────────────────────"
        )
        keyboard = [
            [InlineKeyboardButton("💵 Tambah Bayaran", callback_data=f"pay_update_{branch_name}_{kid_name}")],
            [InlineKeyboardButton("✏️ Set Yuran Bulanan", callback_data=f"fee_update_{branch_name}_{kid_name}")],
            [InlineKeyboardButton("🔙 Kembali", callback_data=f"yuran_br_{branch_name}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=text_detail, reply_markup=reply_markup, parse_mode="Markdown")

    elif data.startswith("pay_update_"):
        parts = data.split("_", 3)
        user_sessions[user_id] = {"mode": "update_pay", "branch": parts[2], "kid": parts[3]}
        await query.edit_message_text(text=f"💵 Taip jumlah **bayaran baharu** untuk *{parts[3]}* (RM):", parse_mode="Markdown")

    elif data.startswith("fee_update_"):
        parts = data.split("_", 3)
        user_sessions[user_id] = {"mode": "update_fee", "branch": parts[2], "kid": parts[3]}
        await query.edit_message_text(text=f"✏️ Taip jumlah **yuran bulanan rasmi** untuk *{parts[3]}* (RM):", parse_mode="Markdown")

    elif data == "owner_main_menu":
        keyboard = [
            [InlineKeyboardButton("📋 Kehadiran", callback_data="owner_menu_kehadiran")],
            [InlineKeyboardButton("💳 Status & Bayaran Yuran", callback_data="owner_select_branch_yuran")],
            [InlineKeyboardButton("📝 Pendaftaran Baru Anak-Anak", callback_data="owner_select_branch_register")],
            [InlineKeyboardButton("❌ Keluarkan Dari Senarai", callback_data="owner_select_branch_delete")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if query:
            await query.edit_message_text(text="👑 *Dashboard Pengurusan (Owner/Admin)*\n\nSila pilih kategori pengurusan:", reply_markup=reply_markup, parse_mode="Markdown")

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

    elif data.startswith("list_in_") or data.startswith("list_out_"):
        action = "in" if "list_in_" in data else "out"
        branch_name = data.replace("list_in_", "").replace("list_out_", "")
        action_label = "Check-In" if action == "in" else "Check-Out"
        kids_list = get_kids_for_branch(branch_name)

        keyboard = []
        if kids_list:
            for kid in kids_list:
                rec = get_attendance_record(kid)
                current_st = rec["status"] if rec else "out"
                
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

        rec = get_attendance_record(kid_name)
        current_st = rec["status"] if rec else "out"

        if action == "in" and current_st == "in":
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"list_in_{branch_name}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text=f"🛑 *AMARAN: CHECK-IN DIBLOK!*\n\n"
                     f"🔴 *{kid_name}* sudah pun Check-In pada jam *{rec['check_time'] if rec else '-'}*!\n\n"
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

        set_attendance_record(kid_name, branch_name, "kid", action, time_str)

        keyboard = [[InlineKeyboardButton("🔙 Menu Anak", callback_data=f"menu_kids_{branch_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"✅ *Rekod Berjaya Disimpan di Database!*\n\n"
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

    elif data.startswith("slist_in_") or data.startswith("slist_out_"):
        action = "in" if "slist_in_" in data else "out"
        branch_name = data.replace("slist_in_", "").replace("slist_out_", "")
        action_label = "Clock-In" if action == "in" else "Clock-Out"
        staff_list = get_staff_for_branch(branch_name)

        keyboard = []
        if staff_list:
            for sname in staff_list:
                srec = get_attendance_record(sname)
                c_st = srec["status"] if srec else "out"

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

    elif data.startswith("staffselect_"):
        parts = data.split("_", 3)
        action, branch_name, staff_name = parts[1], parts[2], parts[3]
        
        srec = get_attendance_record(staff_name)
        c_st = srec["status"] if srec else "out"

        if action == "in" and c_st == "in":
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"slist_in_{branch_name}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text=f"🛑 *AMARAN: CLOCK-IN DIBLOK!*\n\n"
                     f"🔴 *{staff_name}* sudah pun Clock-In pada jam *{srec['check_time'] if srec else '-'}*!\n\n"
                     f"Tidak boleh Clock-In kali kedua.",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            return

        now = datetime.now(MY_TZ)
        time_str = now.strftime('%I:%M %p')

        set_attendance_record(staff_name, branch_name, "staff", action, time_str)

        keyboard = [[InlineKeyboardButton("🔙 Menu Staff", callback_data=f"menu_staff_{branch_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"✅ *Kehadiran Staff Direkodkan di Database!*\n\n"
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
# 4. FUNGSI MENERIMA MESEJ TAIPAN (TEXT INPUTS)
# ---------------------------------------------------------
async def handle_text_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    input_text = update.message.text.strip()
    now = datetime.now(MY_TZ)
    is_owner = user_id in OWNER_IDS

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

    elif "Keluarkan Dari Senarai" in input_text:
        keyboard = [[InlineKeyboardButton(f"🏢 {branch}", callback_data=f"del_br_{branch}")] for branch in BRANCHES]
        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="owner_main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("❌ *Pilih Cawangan untuk Keluarkan Dari Senarai*:", reply_markup=reply_markup, parse_mode="Markdown")
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
        conn = get_db_connection()
        if not conn:
            await update.message.reply_text("⚠️ Ralat sambungan database!")
            return

        cur = conn.cursor()
        
        # Ambil data yuran + padankan cawangan
        cur.execute("""
            SELECT f.kid_name, f.total_yuran, f.bayar_hari_ini, f.total_paid, 
                   COALESCE(k.branch_name, 'Taska Utama') AS branch_name
            FROM fees f
            LEFT JOIN kids k ON LOWER(f.kid_name) = LOWER(k.kid_name)
            ORDER BY branch_name, f.kid_name;
        """)
        records = cur.fetchall()
        cur.close()
        conn.close()

        if not records:
            await update.message.reply_text("📊 *Laporan Bulanan*\n\nTiada rekod pendaftaran atau yuran lagi.", parse_mode="Markdown")
            return

        # Susun data mengikut cawangan
        branch_data = {}

        for r in records:
            kid = r['kid_name']
            yuran = float(r['total_yuran'])
            paid = float(r['total_paid'])
            baki = max(0.0, yuran - paid)
            status_icon = "✅" if baki <= 0 and yuran > 0 else "❌"
            branch = r['branch_name']

            if branch not in branch_data:
                branch_data[branch] = {
                    "kids": [],
                    "sub_yuran": 0.0,
                    "sub_paid": 0.0,
                    "sub_baki": 0.0,
                    "sub_lunas": 0
                }
            
            branch_data[branch]["kids"].append({
                "kid": kid,
                "yuran": yuran,
                "paid": paid,
                "baki": baki,
                "icon": status_icon
            })
            branch_data[branch]["sub_yuran"] += yuran
            branch_data[branch]["sub_paid"] += paid
            branch_data[branch]["sub_baki"] += baki
            if baki <= 0 and yuran > 0:
                branch_data[branch]["sub_lunas"] += 1

        # Bina Mesej Laporan Mengikut Cawangan Taska
        now = datetime.now(MY_TZ)
        report_msg = f"📊 *LAPORAN YURAN BULANAN ({now.strftime('%m/%Y')})*\n"
        report_msg += f"───────────────────────\n\n"

        for b_name, b_info in branch_data.items():
            total_kids = len(b_info["kids"])
            report_msg += f"🏢 *{b_name.upper()}*\n"
            report_msg += f"👥 *Jumlah Keseluruhan Anak:* {total_kids} Orang\n"
            report_msg += f"───────────────────────\n"
            
            for k in b_info["kids"]:
                report_msg += (
                    f" {k['icon']} *{k['kid']}*\n"
                    f"    - Dibayar: RM {k['paid']:.2f} / RM {k['yuran']:.2f}\n"
                    f"    - Baki: RM {k['baki']:.2f}\n"
                    f"    ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
                )
            
            report_msg += (
                f"\n📌 *Collection ({b_name}):*\n"
                f"   👥 Jumlah Anak: {total_kids} Orang ({b_info['sub_lunas']} Lunas)\n"
                f"   💵 Sasaran Yuran: RM {b_info['sub_yuran']:.2f}\n"
                f"   💰 Total Kutipan: RM {b_info['sub_paid']:.2f}\n"
                f"   ⚠️ Baki Belum Bayar: RM {b_info['sub_baki']:.2f}\n"
                f"───────────────────────\n\n"
            )

        keyboard = [[InlineKeyboardButton("🔙 Kembali ke Dashboard", callback_data="owner_main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text=report_msg, reply_markup=reply_markup, parse_mode="Markdown")
        return

    # SEKSYEN PENANGAN SESI TAIPAN
    if user_id in user_sessions:
        session = user_sessions[user_id]
        mode = session.get("mode")

        if mode == "input_ot":
            keyboard = [[InlineKeyboardButton("🔙 Kembali ke Dashboard", callback_data="owner_main_menu")]] if is_owner else []
            reply_markup = InlineKeyboardMarkup(keyboard) if is_owner else None
            await update.message.reply_text(f"✅ *Rekod OT Disimpan*: {input_text}", reply_markup=reply_markup, parse_mode="Markdown")
            del user_sessions[user_id]

        elif mode == "register_kid_name":
            user_sessions[user_id] = {"mode": "register_kid_fee", "branch": session["branch"], "kid_name": input_text}
            await update.message.reply_text(f"💰 Taip jumlah **yuran bulanan rasmi** untuk *{input_text}* (RM):", parse_mode="Markdown")

        elif mode == "register_kid_fee":
            try:
                fee_val = float(input_text.replace("RM", "").strip())
                b_name, k_name = session["branch"], session["kid_name"]
                
                conn = get_db_connection()
                if conn:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO kids (branch_name, kid_name) VALUES (%s, %s)
                        ON CONFLICT (kid_name) 
                        DO UPDATE SET branch_name = EXCLUDED.branch_name;
                    """, (b_name, k_name))
                    conn.commit()
                    cur.close()
                    conn.close()

                update_fee_record(k_name, yuran=fee_val)

                keyboard = [[InlineKeyboardButton("🔙 Kembali ke Dashboard", callback_data="owner_main_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    text=f"✅ *Pendaftaran Berjaya & Dikemaskini ke Database!*\n\n"
                         f"👶 Nama: *{k_name}*\n"
                         f"📍 Cawangan: *{b_name}*\n"
                         f"💰 Jumlah Yuran Rasmi: *RM {fee_val:.2f}*",
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
                del user_sessions[user_id]
            except ValueError:
                await update.message.reply_text("⚠️ Sila taip nombor sahaja.")

        elif mode == "manual_time":
            k_name, act, b_name = session["kid"], session["action"], session["branch"]
            set_attendance_record(k_name, b_name, "kid", act, input_text)
            keyboard = [[InlineKeyboardButton("🔙 Menu Anak", callback_data=f"menu_kids_{b_name}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"✅ *Rekod Manual Disimpan ke Database!*\n\n👶 Nama: *{k_name}*\n⏰ Masa: *{input_text}*", reply_markup=reply_markup, parse_mode="Markdown")
            del user_sessions[user_id]

        elif mode == "update_pay":
            try:
                pay_val = float(input_text.replace("RM", "").strip())
                k_name, b_name = session["kid"], session["branch"]
                
                update_fee_record(k_name, add_pay=pay_val)
                info = get_fee_record(k_name)
                total_yuran = info["yuran"]
                total_paid = info["total_paid"]
                baki = total_yuran - total_paid
                status = "Lunas ✅" if baki <= 0 and total_yuran > 0 else "Belum Lunas ❌"

                keyboard = [
                    [InlineKeyboardButton("💳 Rekod Yuran Anak", callback_data=f"yuran_kid_{b_name}_{k_name}")],
                    [InlineKeyboardButton("🔙 Kembali ke Dashboard", callback_data="owner_main_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                text_response = (
                    f"✅ *Bayaran Yuran Berjaya Disimpan ke Database!*\n\n"
                    f"👤 Nama Anak: *{k_name}*\n"
                    f"───────────────────────\n"
                    f"1. *Jumlah Yuran:* RM {total_yuran:.2f}\n"
                    f"2. *Bayaran (Hari Ini):* RM {pay_val:.2f}\n"
                    f"3. *Jumlah Terkini (Sudah Dibayar):* RM {total_paid:.2f}\n"
                    f"4. *Baki:* RM {max(0, baki):.2f}\n"
                    f"5. *Status:* {status}\n"
                    f"───────────────────────"
                )

                await update.message.reply_text(text=text_response, reply_markup=reply_markup, parse_mode="Markdown")
                del user_sessions[user_id]
            except ValueError:
                await update.message.reply_text("⚠️ Sila taip nombor sahaja.")

        elif mode == "update_fee":
            try:
                fee_val = float(input_text.replace("RM", "").strip())
                k_name, b_name = session["kid"], session["branch"]
                
                update_fee_record(k_name, yuran=fee_val)

                keyboard = [
                    [InlineKeyboardButton("💳 Rekod Yuran Anak", callback_data=f"yuran_kid_{b_name}_{k_name}")],
                    [InlineKeyboardButton("🔙 Kembali ke Dashboard", callback_data="owner_main_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    text=f"✅ *Jumlah Yuran Bulanan Ditetapkan di Database!*\n\n"
                         f"👤 Nama Anak: *{k_name}*\n"
                         f"💰 Jumlah Yuran Rasmi: *RM {fee_val:.2f}*",
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
                del user_sessions[user_id]
            except ValueError:
                await update.message.reply_text("⚠️ Sila taip nombor sahaja.")

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
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_inputs))

    print("Bot Taska sedang aktif berjalan...")
    application.run_polling()
