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


def get_market_data(timeframe="1h"):
  """Mengambil data pasaran secara live daripada Twelve Data API"""
  tf_mapping = {"1h": "1h", "30min": "30min"}
  tf = tf_mapping.get(timeframe, "1h")

  url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval={tf}&outputsize=100&apikey={TWELVE_API_KEY}"

  try:
    response = requests.get(url, timeout=10)
    data = response.json()

    if "values" in data:
      df = pd.DataFrame(data["values"])
      df = df.iloc[::-1].reset_index(drop=True)
      for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
      return df
    else:
      print(f"Ralat API TwelveData ({timeframe}): {data}")
      return None
  except Exception as e:
    print(f"Ralat sambungan ke API: {e}")
    return None


# ---------------------------------------------------------
# 3. LOGIK PENCARIAN BUCU SAH (FRACTAL BODY)
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
# 4. LOGIK MAJOR TREND (MENGIKUT STRUKTUR BESAR)
# ---------------------------------------------------------
def evaluate_major_trend(df):
  """Menilai trend major berdasarkan arah pecah aras struktur body close terakhir"""
  if df is None or len(df) < 10:
    return "🟡 SIDEWAYS (Data tidak cukup)", 0, 0, 0

  df = df.copy()
  df["body_low"] = df[["open", "close"]].min(axis=1)
  df["body_high"] = df[["open", "close"]].max(axis=1)

  # Semak trend major berdasarkan pergerakan struktur bucu terkini
  major_trend = "🟡 SIDEWAYS (Dalam Range)"
  active_bucu_high, active_bucu_low = get_valid_bucu(df)

  completed_candle = df.iloc[-2]
  close_price = float(completed_candle["close"])

  # Imbas arah breakout terakhir dari struktur major
  for i in range(10, len(df) - 1):
    sub_df = df.iloc[:i]
    bh, bl = get_valid_bucu(sub_df)
    c_close = df["close"].iloc[i]

    if bl is not None and c_close < bl:
      major_trend = "🔴 BEARISH (Major Downtrend / Selepas Break Support)"
    elif bh is not None and c_close > bh:
      major_trend = "🟢 BULLISH (Major Uptrend / Selepas Break Resistance)"

  return (
      major_trend,
      close_price,
      active_bucu_high if active_bucu_high else 0,
      active_bucu_low if active_bucu_low else 0,
  )


# ---------------------------------------------------------
# 5. FUNGSI ANALISIS GABUNGAN H1 & M30 UNTUK /trend
# ---------------------------------------------------------
def analyze_current_trend():
  df_h1 = get_market_data(timeframe="1h")
  df_m30 = get_market_data(timeframe="30min")

  h1_status, h1_close, h1_high, h1_low = evaluate_major_trend(df_h1)
  m30_status, m30_close, m30_high, m30_low = evaluate_major_trend(df_m30)

  msg = (
      f"📊 *ANALISIS STRUKTUR MAJOR TREND (BODY CLOSE)*\n\n"
      f"⏰ *Analisis H1 (Major Trend):*\n"
      f"• Trend H1: {h1_status}\n"
      f"• Close H1: `${h1_close:.2f}`\n"
      f"• Bucu Body High H1: `${h1_high:.2f}`\n"
      f"• Bucu Body Low H1: `${h1_low:.2f}`\n\n"
      f"📉 *Analisis M30 (Minor Trend):*\n"
      f"• Trend M30: {m30_status}\n"
      f"• Close M30: `${m30_close:.2f}`\n"
      f"• Bucu Body High M30: `${m30_high:.2f}`\n"
      f"• Bucu Body Low M30: `${m30_low:.2f}`"
  )
  return msg


# ---------------------------------------------------------
# 6. TELEGRAM WEBHOOK ROUTE (UNTUK TERIMA ARAHAN /trend)
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
# 7. GELUNG UTAMA BOT (BACKGROUND PROCESS UNTUK ALERT)
# ---------------------------------------------------------
def run_bot():
  print("🤖 Bot Breakout Syezz dimulakan...")
  last_processed_time_m30 = None

  while True:
    try:
      df_m30 = get_market_data(timeframe="30min")

      if df_m30 is not None and len(df_m30) >= 10:
        completed_candle = df_m30.iloc[-2]
        current_candle_time = str(completed_candle["time"])
        close_price = float(completed_candle["close"])
        _, bucu_low = get_valid_bucu(df_m30)

        if current_candle_time != last_processed_time_m30:
          if bucu_low is not None and close_price < bucu_low:
            msg = (
                f"🚨 *ALERT BREAKOUT BEARISH M30*! 🔴\n\n"
                f"• Close Harga: `${close_price:.2f}`\n"
                f"• Bucu Body Low Tembus: `${bucu_low:.2f}`"
            )
            send_telegram_message(msg)
            last_processed_time_m30 = current_candle_time

      time.sleep(30)

    except Exception as e:
      print(f"Ralat gelung utama bot: {e}")
      time.sleep(30)


# ---------------------------------------------------------
# 8. EXECUTION UTAMA (FLASK + THREADING)
# ---------------------------------------------------------
if __name__ == "__main__":
  bot_thread = threading.Thread(target=run_bot)
  bot_thread.daemon = True
  bot_thread.start()

  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
