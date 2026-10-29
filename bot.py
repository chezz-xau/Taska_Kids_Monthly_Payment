from datetime import datetime
import os
import threading
import time
from flask import Flask, request
import pandas as pd
import requests

# ---------------------------------------------------------
# 1. SETUP FLASK (Supaya Render kesan port yang sah)
# ---------------------------------------------------------
app = Flask(__name__)


@app.route("/")
def home():
  return "Bot M30/H1 Breakout Syezz sedang aktif!"


# ---------------------------------------------------------
# 2. KONFIGURASI TELEGRAM & API (Mengikut Environment Variables Render)
# ---------------------------------------------------------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWELVE_API_KEY = os.getenv("TWELVE_DATA_API")


def send_telegram_message(message, chat_id=CHAT_ID):
  """Fungsi untuk menghantar mesej amaran ke Telegram"""
  if not TOKEN or not chat_id:
    print("Ralat: Token Telegram atau Chat ID tidak ditemui dalam env.")
    return

  url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
  payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
  try:
    response = requests.post(url, json=payload, timeout=10)
    if response.status_code != 200:
      print(f"Gagal hantar Telegram: {response.text}")
  except Exception as e:
    print(f"Ralat sambungan Telegram: {e}")


def get_market_data():
  """Mengambil data pasaran (Contoh menggunakan Twelve Data API jika berkaitan)

  Pastikan DataFrame yang dipulangkan mempunyai kolum:
  ['time', 'open', 'high', 'low', 'close']
  """
  # Contoh integrasi menggunakan TWELVE_API_KEY jika diperlukan:
  # url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1h&outputsize=50&apikey={TWELVE_API_KEY}"
  # response = requests.get(url).json()
  # if "values" in response:
  #     df = pd.DataFrame(response['values'])
  #     df = df.iloc[::-1].reset_index(drop=True) # susun dari lama ke baru
  #     for col in ['open', 'high', 'low', 'close']:
  #         df[col] = df[col].astype(float)
  #     return df
  pass


# ---------------------------------------------------------
# 3. LOGIK PENCARIAN BUCU SAH (ELAK REPAINTING)
# ---------------------------------------------------------
def get_valid_bucu(df):
  """Mencari aras Bucu High & Low yang sah (Fractal Body)."""
  if df is None or len(df) < 5:
    return None, None

  df = df.copy()
  df["body_low"] = df[["open", "close"]].min(axis=1)
  df["body_high"] = df[["open", "close"]].max(axis=1)

  valid_bucu_lows = []
  valid_bucu_highs = []

  # Imbas data (abaikan 2 candle terakhir yang belum lengkap struktur swing)
  for i in range(2, len(df) - 2):
    if (
        df["body_low"].iloc[i] < df["body_low"].iloc[i - 1]
        and df["body_low"].iloc[i] < df["body_low"].iloc[i - 2]
        and df["body_low"].iloc[i] < df["body_low"].iloc[i + 1]
        and df["body_low"].iloc[i] < df["body_low"].iloc[i + 2]
    ):
      valid_bucu_lows.append(df["body_low"].iloc[i])

    if (
        df["body_high"].iloc[i] > df["body_high"].iloc[i - 1]
        and df["body_high"].iloc[i] > df["body_high"].iloc[i - 2]
        and df["body_high"].iloc[i] > df["body_high"].iloc[i + 1]
        and df["body_high"].iloc[i] > df["body_high"].iloc[i + 2]
    ):
      valid_bucu_highs.append(df["body_high"].iloc[i])

  last_bucu_low = valid_bucu_lows[-1] if valid_bucu_lows else None
  last_bucu_high = valid_bucu_highs[-1] if valid_bucu_highs else None

  return last_bucu_high, last_bucu_low


# ---------------------------------------------------------
# 4. FUNGSI ANALISIS TREND SEMASA
# ---------------------------------------------------------
def analyze_current_trend():
  df = get_market_data()
  if df is None or len(df) < 5:
    return "⚠️ Data pasaran tidak mencukupi buat masa ini."

  completed_candle = df.iloc[-2]
  close_price = float(completed_candle["close"])
  bucu_high, bucu_low = get_valid_bucu(df)

  # Tentukan status berdasarkan body close terhadap bucu sah
  trend_status = "🟡 SIDEWAYS (Dalam Range)"
  if bucu_low is not None and close_price < bucu_low:
    trend_status = "🔴 BEARISH (TURUN - Breakout Support)"
  elif bucu_high is not None and close_price > bucu_high:
    trend_status = "🟢 BULLISH (NAIK - Breakout Resistance)"

  msg = (
      f"📊 *ANALISIS STRUKTUR BUCU (BODY CLOSE)*\n\n"
      f"• **Trend Semasa:** {trend_status}\n"
      f"• **Close Terkini:** `${close_price:.2f}`\n"
      f"• **Bucu Body High:** `${bucu_high if bucu_high else 0:.2f}`\n"
      f"• **Bucu Body Low:** `${bucu_low if bucu_low else 0:.2f}`"
  )
  return msg


# ---------------------------------------------------------
# 5. TELEGRAM WEBHOOK ROUTE (UNTUK TERIMA ARAHAN /trend)
# ---------------------------------------------------------
@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
  data = request.get_json()
  if "message" in data:
    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    if text.startswith("/trend"):
      response_text = analyze_current_trend()
      send_telegram_message(response_text, chat_id=chat_id)

  return "OK", 200


# ---------------------------------------------------------
# 6. GELUNG UTAMA BOT (BACKGROUND PROCESS UNTUK ALERT)
# ---------------------------------------------------------
def run_bot():
  print("🤖 Bot Breakout Syezz dimulakan...")
  last_processed_time = None

  while True:
    try:
      df = get_market_data()

      if df is not None and len(df) >= 5:
        completed_candle = df.iloc[-2]
        current_candle_time = str(completed_candle["time"])
        close_price = float(completed_candle["close"])

        bucu_high, bucu_low = get_valid_bucu(df)

        # Semak jika ini candle baharu yang baru selesai tutup
        if current_candle_time != last_processed_time:

          # Amaran Breakout Sell (Bearish)
          if bucu_low is not None and close_price < bucu_low:
            msg = (
                f"🚨 *ALERT BREAKOUT BEARISH (BODY CLOSE)*! 🔴\n\n"
                f"Candle baharu sahaja *CLOSE* di bawah support!\n"
                f"• Close Harga: `${close_price:.2f}`\n"
                f"• Bucu Body Low Tembus: `${bucu_low:.2f}`\n\n"
                f"_Struktur sah bertukar kepada Downtrend / Bearish!_"
            )
            send_telegram_message(msg)
            last_processed_time = current_candle_time
            print(f"[{datetime.now()}] Alert Breakout Sell berjaya dihantar!")

          # Amaran Breakout Buy (Bullish)
          elif bucu_high is not None and close_price > bucu_high:
            msg = (
                f"🚨 *ALERT BREAKOUT BULLISH (BODY CLOSE)*! 🟢\n\n"
                f"Candle baharu sahaja *CLOSE* di atas resistance!\n"
                f"• Close Harga: `${close_price:.2f}`\n"
                f"• Bucu Body High Tembus: `${bucu_high:.2f}`\n\n"
                f"_Struktur sah bertukar kepada Uptrend / Bullish!_"
            )
            send_telegram_message(msg)
            last_processed_time = current_candle_time
            print(f"[{datetime.now()}] Alert Breakout Buy berjaya dihantar!")

      # Semak setiap 30 saat
      time.sleep(30)

    except Exception as e:
      print(f"Ralat berlaku dalam gelung utama bot: {e}")
      time.sleep(30)


# ---------------------------------------------------------
# 7. EXECUTION UTAMA (FLASK + THREADING)
# ---------------------------------------------------------
if __name__ == "__main__":
  # Jalankan bot di background thread
  bot_thread = threading.Thread(target=run_bot)
  bot_thread.daemon = True
  bot_thread.start()

  # Jalankan server Flask pada port Render
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
