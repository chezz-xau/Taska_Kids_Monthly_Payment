import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    Updater,
)

# --- 1. SETUP DATABASE SQLITE ---
def init_db():
    conn = sqlite3.connect("taska.db")
    cursor = conn.cursor()
    # Buat jadual pelajar jika belum ada, lengkap dengan kolum cawangan dan status bayaran
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pelajar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT,
            cawangan TEXT,
            status_bayaran TEXT DEFAULT 'Belum Bayar'
        )
    """
    )
    conn.commit()
    conn.close()

# --- 2. MENU UTAMA / LAPORAN PEMBAYARAN ---
def menu_laporan_pembayaran(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    keyboard = [
        [InlineKeyboardButton("🏡 Taska Corner", callback_data="cawangan_corner")],
        [InlineKeyboardButton("🏫 Taska Hadhari", callback_data="cawangan_hadhari")],
        [InlineKeyboardButton("🔙 Menu Utama", callback_data="menu_utama")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(
        "🏢 **Sila pilih cawangan Taska untuk semakan yuran:**",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

# --- 3. PILIH STATUS BAYARAN MENGIKUT CAWANGAN ---
def pilih_cawangan(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    data = query.data  # cawangan_corner atau cawangan_hadhari
    cawangan_name = "Taska Corner" if "corner" in data else "Taska Hadhari"
    cawangan_key = "corner" if "corner" in data else "hadhari"

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Sudah Lunas", callback_data=f"status_lunas_{cawangan_key}"
            )
        ],
        [
            InlineKeyboardButton(
                "⏳ Belum Bayar", callback_data=f"status_belum_{cawangan_key}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Pilih Cawangan Lain", callback_data="menu_pembayaran"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(
        f"📌 **{cawangan_name} - Status Yuran**\nSila pilih status bayaran:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

# --- 4. PAPAR SENARAI MENGIKUT STATUS & CAWANGAN ---
def papar_senarai_status(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    data = query.data  # contoh: status_lunas_corner atau status_belum_hadhari
    parts = data.split("_")
    status_type = parts[1]  # lunas atau belum
    cawangan_key = parts[2]  # corner atau hadhari

    cawangan_name = "Taska Corner" if cawangan_key == "corner" else "Taska Hadhari"
    status_text = "Sudah Lunas" if status_type == "lunas" else "Belum Bayar"
    db_status = "Lunas" if status_type == "lunas" else "Belum Bayar"

    # Semak database
    conn = sqlite3.connect("taska.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT nama FROM pelajar WHERE cawangan = ? AND status_bayaran = ?",
        (cawangan_name, db_status),
    )
    senarai = cursor.fetchall()
    conn.close()

    # Bentukkan teks senarai
    text = f"📋 **Senarai Pelajar ({cawangan_name}) - {status_text}:**\n\n"
    if senarai:
        for idx, row in enumerate(senarai, 1):
            text += f"{idx}. {row[0]}\n"
    else:
        text += "_Tiada rekod dijumpai._\n"

    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 Kembali", callback_data=f"cawangan_{cawangan_key}"
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(
        text, reply_markup=reply_markup, parse_mode="Markdown"
    )

# --- 5. MAIN FUNCTION (CONTOH DAFTAR HANDLER) ---
def main():
    init_db()  # Mulakan database

    # Masukkan TOKEN bot Telegram anda di sini
    updater = Updater("TOKEN_BOT_ANDA_DI_SINI", use_context=True)
    dispatcher = updater.dispatcher

    # Daftarkan Callback Query Handlers
    dispatcher.add_handler(
        CallbackQueryHandler(
            menu_laporan_pembayaran, pattern="^menu_pembayaran$"
        )
    )
    dispatcher.add_handler(
        CallbackQueryHandler(
            pilih_cawangan, pattern="^cawangan_(corner|hadhari)$"
        )
    )
    dispatcher.add_handler(
        CallbackQueryHandler(
            papar_senarai_status, pattern="^status_(lunas|belum)_(corner|hadhari)$"
        )
    )

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
