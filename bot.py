import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Tetapan logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Dapatkan token dari Environment Variable di Render
TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📥 Check-In Anak", callback_data='checkin_kids'),
         InlineKeyboardButton("📤 Check-Out Anak", callback_data='checkout_kids')],
        [InlineKeyboardButton("🟢 Clock-In Pengasuh", callback_data='clockin_staff'),
         InlineKeyboardButton("🔴 Clock-Out Pengasuh", callback_data='clockout_staff')],
        [InlineKeyboardButton("📊 Laporan Bulanan", callback_data='report')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 Selamat datang ke Bot Pengurusan Taska!\nSila pilih menu di bawah:", reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == 'checkin_kids':
        await query.edit_message_text(text="✅ Fungsi Check-In Anak dipilih. (Sistem rekod masa dibuka)")
    elif data == 'checkout_kids':
        await query.edit_message_text(text="⏳ Fungsi Check-Out Anak dipilih. (Sistem pengiraan OT automatik dijalankan)")
    elif data == 'clockin_staff':
        await query.edit_message_text(text="🟢 Staff Clock-In dicatat.")
    elif data == 'clockout_staff':
        await query.edit_message_text(text="🔴 Staff Clock-Out dicatat.")
    elif data == 'report':
        await query.edit_message_text(text="📊 Laporan Excel sedang dijana...")

if __name__ == '__main__':
    if not TOKEN:
        print("Ralat: TELEGRAM_TOKEN tidak dijumpai!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_click))
        print("Bot Taska sedang berjalan...")
        app.run_polling()

