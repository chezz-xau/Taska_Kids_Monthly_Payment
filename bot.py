import os
from threading import Thread
from datetime import datetime, timezone, timedelta
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# ----------------- FLASK FOR RENDER HEALTH CHECK -----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Taska is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ----------------- TELEGRAM BOT SETUP -----------------
# ⚠️ MASUKKAN TOKEN TELEGRAM BOT PENUH DARI @BotFather (JANGAN ADA '...')
TOKEN = "8675996323:AAFKUOuSzaVCpa..."  
OWNER_ID = 8353544393  # ID Telegram Owner / Syezz

bot = telebot.TeleBot(TOKEN)

# TETAPAN OT & WAKTU OPERATION
OFFICE_END_HOUR = 18          # 6:00 PM (18:00)
CHILD_OT_RATE_PER_HOUR = 5.0   # RM 5.00 per jam
STAFF_OT_RATE_PER_HOUR = 6.0   # RM 6.00 per jam
MONTHLY_FEE = 350.0            # Yuran Bulanan Standard (RM)

# Data simulasi kanak-kanak (Termasuk Rekod Bayaran Yuran Fleksibel)
children_data = {
    "1": {"name": "Ahmad Rayyan", "status": "out", "time": None, "ot_fee": 0, "paid_amount": 350.0}, # Full Payment
    "2": {"name": "Nur Zara Sofea", "status": "out", "time": None, "ot_fee": 0, "paid_amount": 150.0}, # Ansuran
    "3": {"name": "Muhammad Umar", "status": "out", "time": None, "ot_fee": 0, "paid_amount": 700.0}, # Lump Sum (2 Bulan)
    "4": {"name": "Siti Maryam", "status": "out", "time": None, "ot_fee": 0, "paid_amount": 0.0},   # Belum Bayar
    "5": {"name": "Adam Harith", "status": "out", "time": None, "ot_fee": 0, "paid_amount": 0.0}    # Belum Bayar
}

# Data simulasi Staff / Pengasuh
staff_data = {
    "101": {"name": "Cikgu Farah", "status": "out", "in_time": None, "out_time": None, "ot_pay": 0},
    "102": {"name": "Cikgu Aisyah", "status": "out", "in_time": None, "out_time": None, "ot_pay": 0},
    "103": {"name": "Cikgu Siti", "status": "out", "in_time": None, "out_time": None, "ot_pay": 0}
}

# ----------------- HELPER: KIRA OVERTIME -----------------
def calculate_ot_details(now_dt, rate_per_hour):
    """Mengira jam/minit lewat selepas 6:00 PM & jumlah bayaran OT"""
    end_time = now_dt.replace(hour=OFFICE_END_HOUR, minute=0, second=0, microsecond=0)
    
    if now_dt > end_time:
        diff = now_dt - end_time
        total_minutes = int(diff.total_seconds() // 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        total_hours_float = total_minutes / 60.0
        amount = round(total_hours_float * rate_per_hour, 2)
        
        duration_str = f"{hours}j {minutes}m" if hours > 0 else f"{minutes}m"
        return duration_str, amount
    
    return None, 0.0

# ----------------- SYSTEM MENU (ROLE-BASED) -----------------
def get_menu_for_user(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("📥 Check-In Anak"), KeyboardButton("📤 Check-Out Anak"))
    markup.row(KeyboardButton("🟢 Clock-In Staff"), KeyboardButton("🔴 Clock-Out Staff"))

    if user_id == OWNER_ID:
        markup.row(KeyboardButton("💳 Status & Bayaran Yuran"))
        markup.row(KeyboardButton("📊 Laporan Bulanan"))
        
    return markup

# ----------------- INLINE KEYBOARD GENERATORS -----------------
def get_children_keyboard(action="checkin"):
    markup = InlineKeyboardMarkup()
    for child_id, child_info in children_data.items():
        is_checked_in = child_info["status"] == "in"
        
        if action == "checkin":
            icon = "🟢" if is_checked_in else "⚪"
            status_text = f" ({child_info['time']})" if is_checked_in and child_info['time'] else ""
        else: # checkout
            icon = "🔴" if not is_checked_in else "🟢"
            status_text = f" ({child_info['time']})" if is_checked_in and child_info['time'] else " (Belum Hadir)"

        btn_text = f"{icon} {child_info['name']}{status_text}"
        markup.add(InlineKeyboardButton(text=btn_text, callback_data=f"toggle_child_{action}_{child_id}"))

    save_text = "✅ Simpan & Sahkan Check-In Anak" if action == "checkin" else "✅ Simpan & Sahkan Check-Out Anak"
    markup.add(InlineKeyboardButton(text=save_text, callback_data=f"save_child_{action}"))
    return markup

def get_staff_keyboard(action="clockin"):
    markup = InlineKeyboardMarkup()
    for staff_id, staff_info in staff_data.items():
        is_clocked_in = staff_info["status"] == "in"
        
        if action == "clockin":
            icon = "🟢" if is_clocked_in else "⚪"
            time_str = f" ({staff_info['in_time']})" if is_clocked_in and staff_info['in_time'] else ""
        else: # clockout
            icon = "🔴" if not is_clocked_in else "🟢"
            time_str = f" ({staff_info['out_time']})" if not is_clocked_in and staff_info['out_time'] else ""

        btn_text = f"{icon} {staff_info['name']}{time_str}"
        markup.add(InlineKeyboardButton(text=btn_text, callback_data=f"toggle_staff_{action}_{staff_id}"))

    save_text = "✅ Simpan Clock-In Staff" if action == "clockin" else "✅ Simpan Clock-Out Staff"
    markup.add(InlineKeyboardButton(text=save_text, callback_data=f"save_staff_{action}"))
    return markup

def get_fee_keyboard():
    markup = InlineKeyboardMarkup()
    for child_id, child_info in children_data.items():
        paid = child_info.get("paid_amount", 0.0)
        
        if paid >= MONTHLY_FEE * 2:
            icon = "🔵 Lump Sum"
            status = f"RM{paid:.0f} (Lebihan)"
        elif paid >= MONTHLY_FEE:
            icon = "🟢 Lunas"
            status = f"RM{paid:.0f}"
        elif paid > 0:
            icon = "🟡 Ansuran"
            status = f"RM{paid:.0f} / RM{MONTHLY_FEE:.0f}"
        else:
            icon = "🔴 Belum Bayar"
            status = "RM0"

        btn_text = f"{icon} | {child_info['name']} ({status})"
        markup.add(InlineKeyboardButton(text=btn_text, callback_data=f"view_fee_{child_id}"))
    return markup

# ----------------- COMMAND /START -----------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    role_title = "👑 **Owner Taska**" if message.from_user.id == OWNER_ID else "👩‍🏫 **Staff / Pengasuh Taska**"
    
    bot.send_message(
        message.chat.id,
        f"👋 **Selamat datang ke Bot Pengurusan Taska!**\nPeranan: {role_title}\n\nSila pilih menu di bawah:",
        parse_mode="Markdown",
        reply_markup=get_menu_for_user(message.from_user.id)
    )

# ----------------- HANDLER MENU OPERASI STAFF -----------------
@bot.message_handler(func=lambda msg: any(cmd in msg.text for cmd in ["Check-In Anak", "Check-Out Anak", "Clock-In Staff", "Clock-Out Staff"]))
def handle_staff_operations(message):
    if "Check-In Anak" in message.text:
        bot.send_message(
            message.chat.id,
            "📋 **SENARAI CHECK-IN KANAK-KANAK**\n\nTekan nama anak untuk tandakan kehadiran (🟢 = Hadir, ⚪ = Belum):",
            parse_mode="Markdown",
            reply_markup=get_children_keyboard(action="checkin")
        )
    elif "Check-Out Anak" in message.text:
        bot.send_message(
            message.chat.id,
            "📋 **SENARAI CHECK-OUT KANAK-KANAK**\n\nTekan nama anak untuk tanda pulang (🔴 = Dah Pulang, 🟢 = Di Taska):",
            parse_mode="Markdown",
            reply_markup=get_children_keyboard(action="checkout")
        )
    elif "Clock-In Staff" in message.text or "Clock-In Pengasuh" in message.text:
        bot.send_message(
            message.chat.id,
            "👩‍🏫 **CLOCK-IN STAFF / PENGASUH**\n\nTekan nama staff untuk tandakan kedatangan (🟢 = Masuk Kerja):",
            parse_mode="Markdown",
            reply_markup=get_staff_keyboard(action="clockin")
        )
    elif "Clock-Out Staff" in message.text or "Clock-Out Pengasuh" in message.text:
        bot.send_message(
            message.chat.id,
            "👩‍🏫 **CLOCK-OUT STAFF / PENGASUH**\n\nTekan nama staff untuk tandakan waktu balik (🔴 = Balik Kerja):",
            parse_mode="Markdown",
            reply_markup=get_staff_keyboard(action="clockout")
        )

# ----------------- HANDLER MENU OWNER -----------------
@bot.message_handler(func=lambda msg: any(cmd in msg.text for cmd in ["Laporan Bulanan", "Status & Bayaran Yuran"]))
def handle_owner_operations(message):
    if message.from_user.id != OWNER_ID:
        bot.send_message(message.chat.id, "⛔ Akses ditolak. Menu ini khas untuk Owner sahaja.")
        return

    if "Laporan Bulanan" in message.text:
        total_children = len(children_data)
        children_in = sum(1 for c in children_data.values() if c["status"] == "in")
        total_child_ot = sum(c.get("ot_fee", 0) for c in children_data.values())

        total_staff = len(staff_data)
        staff_in = sum(1 for s in staff_data.values() if s["status"] == "in")
        total_staff_ot = sum(s.get("ot_pay", 0) for s in staff_data.values())

        report_msg = (
            "📊 **LAPORAN & RINGKASAN TASKA**\n\n"
            f"👶 **Status Anak-Anak ({total_children} Orang):**\n"
            f"• Di Taska (Hadir): `{children_in}`\n"
            f"• Dah Pulang / Tiada: `{total_children - children_in}`\n"
            f"• Terkumpul Caj OT Lewat: `RM {total_child_ot:.2f}`\n\n"
            f"👩‍🏫 **Status Staff ({total_staff} Orang):**\n"
            f"• Sedang Bertugas: `{staff_in}`\n"
            f"• Selesai / Cuti: `{total_staff - staff_in}`\n"
            f"• Terkumpul Gaji OT Staff: `RM {total_staff_ot:.2f}`\n"
        )
        bot.send_message(message.chat.id, report_msg, parse_mode="Markdown")

    elif "Status & Bayaran Yuran" in message.text:
        total_collected = sum(c.get("paid_amount", 0.0) for c in children_data.values())
        total_target = len(children_data) * MONTHLY_FEE

        fee_msg = (
            "💳 **RINGKASAN STATUS BAYARAN YURAN**\n\n"
            f"• Yuran Standard: `RM {MONTHLY_FEE:.2f} / bulan`\n"
            f"• Total Terkumpul: `RM {total_collected:.2f}`\n"
            f"• Target Bulanan: `RM {total_target:.2f}`\n\n"
            "Tekan nama anak di bawah untuk lihat perincian / kemaskini bayaran:"
        )
        bot.send_message(message.chat.id, fee_msg, parse_mode="Markdown", reply_markup=get_fee_keyboard())

# ----------------- CALLBACK QUERY HANDLER -----------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    MY_TZ = timezone(timedelta(hours=8))
    now_dt = datetime.now(MY_TZ)
    current_time = now_dt.strftime("%I:%M %p")

    # --- HANDLE KANAK-KANAK ---
    if call.data.startswith("toggle_child_"):
        _, _, action, child_id = call.data.split("_")
        if child_id in children_data:
            if action == "checkin":
                if children_data[child_id]["status"] == "out":
                    children_data[child_id]["status"] = "in"
                    children_data[child_id]["time"] = current_time
                else:
                    children_data[child_id]["status"] = "out"
                    children_data[child_id]["time"] = None
                    children_data[child_id]["ot_fee"] = 0
            else: # checkout
                if children_data[child_id]["status"] == "in":
                    children_data[child_id]["status"] = "out"
                    children_data[child_id]["time"] = current_time
                    
                    ot_dur, ot_fee = calculate_ot_details(now_dt, CHILD_OT_RATE_PER_HOUR)
                    children_data[child_id]["ot_fee"] = ot_fee
                    children_data[child_id]["ot_dur"] = ot_dur
                else:
                    children_data[child_id]["status"] = "in"

            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=get_children_keyboard(action=action)
            )
            bot.answer_callback_query(call.id, text=f"Status {children_data[child_id]['name']} dikemaskini!")

    elif call.data.startswith("save_child_"):
        action = call.data.split("_")[2]
        action_name = "Check-In" if action == "checkin" else "Check-Out"
        
        summary = f"🎉 **REKOD {action_name.upper()} ANAK BERJAYA DISIMPAN!**\n\n"
        for child in children_data.values():
            status_icon = "🟢 Hadir" if child["status"] == "in" else "🔴 Pulang/Tiada"
            time_str = f" ({child['time']})" if child['time'] else ""
            
            ot_info = ""
            if action == "checkout" and child.get("ot_fee", 0) > 0:
                ot_info = f"\n  └ ⚠️ *OT Lewat ({child['ot_dur']}):* Caj RM{child['ot_fee']:.2f}"
                
            summary += f"• {child['name']}: {status_icon}{time_str}{ot_info}\n"

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=summary,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, text="Rekod anak berjaya disimpan!")

    # --- HANDLE STAFF / PENGASUH ---
    elif call.data.startswith("toggle_staff_"):
        _, _, action, staff_id = call.data.split("_")
        if staff_id in staff_data:
            if action == "clockin":
                if staff_data[staff_id]["status"] == "out":
                    staff_data[staff_id]["status"] = "in"
                    staff_data[staff_id]["in_time"] = current_time
                else:
                    staff_data[staff_id]["status"] = "out"
                    staff_data[staff_id]["in_time"] = None
            else: # clockout
                if staff_data[staff_id]["status"] == "in":
                    staff_data[staff_id]["status"] = "out"
                    staff_data[staff_id]["out_time"] = current_time
                    
                    ot_dur, ot_pay = calculate_ot_details(now_dt, STAFF_OT_RATE_PER_HOUR)
                    staff_data[staff_id]["ot_pay"] = ot_pay
                    staff_data[staff_id]["ot_dur"] = ot_dur
                else:
                    staff_data[staff_id]["status"] = "in"

            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=get_staff_keyboard(action=action)
            )
            bot.answer_callback_query(call.id, text=f"Status {staff_data[staff_id]['name']} dikemaskini!")

    elif call.data.startswith("save_staff_"):
        action = call.data.split("_")[2]
        action_name = "Clock-In" if action == "clockin" else "Clock-Out"
        
        summary = f"📝 **REKOD {action_name.upper()} STAFF DISIMPAN!**\n\n"
        for staff in staff_data.values():
            status_icon = "🟢 Bertugas" if staff["status"] == "in" else "🔴 Selesai/Cuti"
            time_in = f" | Masuk: {staff['in_time']}" if staff['in_time'] else ""
            time_out = f" | Balik: {staff['out_time']}" if staff['out_time'] else ""
            
            ot_info = ""
            if action == "clockout" and staff.get("ot_pay", 0) > 0:
                ot_info = f"\n  └ ⏱️ *OT Bertugas ({staff['ot_dur']}):* Gaji OT RM{staff['ot_pay']:.2f}"
                
            summary += f"• {staff['name']}: {status_icon}{time_in}{time_out}{ot_info}\n"

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=summary,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, text="Rekod staff berjaya disimpan!")

    # --- HANDLE YURAN (VIEW & BUTTON EDIT) ---
    elif call.data.startswith("view_fee_"):
        if call.from_user.id != OWNER_ID:
            bot.answer_callback_query(call.id, text="⛔ Khas untuk Owner sahaja!", show_alert=True)
            return

        child_id = call.data.split("_")[2]
        if child_id in children_data:
            child = children_data[child_id]
            paid = child.get("paid_amount", 0.0)
            balance = MONTHLY_FEE - paid

            msg = (
                f"👤 **PERINCIAN YURAN: {child['name'].upper()}**\n\n"
                f"• Yuran Bulanan: `RM {MONTHLY_FEE:.2f}`\n"
                f"• Jumlah Dibayar: `RM {paid:.2f}`\n"
            )

            if balance > 0:
                msg += f"• 🔴 **Baki Tunggakan:** `RM {balance:.2f}`\n"
            elif balance < 0:
                msg += f"• 🔵 **Lebihan Bayaran (Lump Sum):** `RM {abs(balance):.2f}`\n"
            else:
                msg += "• 🟢 **Status:** `Lunas Sepenuhnya`\n"

            # Butang Kemaskini Bayaran
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(text="✏️ Key In / Kemaskini Bayaran", callback_data=f"edit_fee_{child_id}"))

            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, msg, parse_mode="Markdown", reply_markup=markup)

# ----------------- PROSES KEY IN YURAN (TEXT STEP) -----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_fee_"))
def prompt_update_fee(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, text="⛔ Khas untuk Owner sahaja!", show_alert=True)
        return
    
    child_id = call.data.split("_")[2]
    child_name = children_data[child_id]["name"]
    
    bot.answer_callback_query(call.id)
    sent_msg = bot.send_message(
        call.message.chat.id,
        f"✍️ Sila taip **jumlah bayaran terkini** (dalam nombor sahaja, contoh: `150` atau `350`) untuk **{child_name}**:",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(sent_msg, save_updated_fee, child_id)

def save_updated_fee(message, child_id):
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        new_amount = float(message.text.strip())
        children_data[child_id]["paid_amount"] = new_amount
        
        child_name = children_data[child_id]["name"]
        balance = MONTHLY_FEE - new_amount
        
        confirmation = (
            f"✅ **BERJAYA DIKEMASKINI!**\n\n"
            f"• Nama Anak: `{child_name}`\n"
            f"• Jumlah Dibayar Baru: `RM {new_amount:.2f}`\n"
        )
        if balance > 0:
            confirmation += f"• 🔴 **Baki Tunggakan:** `RM {balance:.2f}`"
        elif balance < 0:
            confirmation += f"• 🔵 **Lebihan Bayaran:** `RM {abs(balance):.2f}`"
        else:
            confirmation += "• 🟢 **Status:** `Lunas Sepenuhnya`"
            
        bot.send_message(message.chat.id, confirmation, parse_mode="Markdown")
        
    except ValueError:
        bot.send_message(
            message.chat.id, 
            "❌ **Ralat:** Sila masukkan nombor sahaja (Contoh: `200` atau `350.50`). Sila tekan semula butang kemaskini."
        )

# ----------------- MAIN RUNNER -----------------
if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    print("Bot Taska sedang berjalan...")
    bot.infinity_polling()
