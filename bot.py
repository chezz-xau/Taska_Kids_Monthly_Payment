import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Server mini supaya Render Web Service sentiasa aktif
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Taska is running!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Tetapan logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ditambah butang yuran bulanan dalam senarai menu
    keyboard = [
        [InlineKeyboardButton("📥 Check-In Anak", callback_data='checkin_kids'),
         InlineKeyboardButton("📤 Check-Out Anak", callback_data='checkout_kids')],
        [InlineKeyboardButton("🟢 Clock-In Pengasuh", callback_data='clockin_staff'),
         InlineKeyboardButton("🔴 Clock-Out Pengasuh", callback_data='clockout_staff')],
        [InlineKeyboardButton("💳 Status & Bayaran Yuran", callback_data='payment_status')],
        [InlineKeyboardButton("📊 Laporan Bulanan", callback_data='report')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 Selamat datang ke Bot Pengurusan Taska!\nSila pilih menu di bawah:", reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == 'checkin_kids':
        await query.edit_message_text(text="✅ Fungsi Check-In Anak dipilih. (Rekod kehadiran dicatat)")
    elif data == 'checkout_kids':
        await query.edit_message_text(text="⏳ Fungsi Check-Out Anak dipilih. (Pengiraan OT dijalankan)")
    elif data == 'clockin_staff':
        await query.edit_message_text(text="🟢 Staff Clock-In dicatat.")
    elif data == 'clockout_staff':
        await query.edit_message_text(text="🔴 Staff Clock-Out dicatat.")
    elif data == 'payment_status':
        await query.edit_message_text(text="💳 **Modul Bayaran Yuran Bulanan**\n\nSila hantar resit pembayaran (gambar) atau masukkan nama anak untuk semak status yuran.")
    elif data == 'report':
        await query.edit_message_text(text="📊 Laporan Excel sedang dijana...")

if __name__ == '__main__':
    if not TOKEN:
        print("Ralat: TELEGRAM_TOKEN tidak dijumpai!")
    else:
        # Jalankan HTTP server di thread latar belakang
        threading.Thread(target=run_dummy_server, daemon=True).start()
        
        # Jalankan Bot Telegram
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_click))
        print("Bot Taska sedang berjalan...")
        app.run_polling()
