# Handler untuk memaparkan Laporan Kehadiran Hari Ini
@bot.message_handler(
    func=lambda message: message.text and "Laporan" in message.text
)
def handle_laporan(message):
  today_str = datetime.now().strftime("%Y-%m-%d")

  if not os.path.exists(EXCEL_FILE):
    bot.reply_to(
        message,
        "📊 Tiada fail rekod ditemui lagi. Belum ada aktiviti direkodkan.",
    )
    return

  try:
    df = pd.read_excel(EXCEL_FILE)

    # Tapis data hanya untuk hari ini
    if "Tarikh" in df.columns:
      df_today = df[df["Tarikh"].astype(str) == today_str]
    else:
      df_today = pd.DataFrame()

    if df_today.empty:
      bot.reply_to(
          message,
          f"📊 **Laporan Hari Ini ({today_str})**\n\nTiada sebarang rekod"
          " kehadiran lagi hari ini.",
          parse_mode="Markdown",
      )
      return

    # Bina teks laporan
    report_text = f"📊 **Laporan Kehadiran Hari Ini ({today_str})**\n\n"

    for index, row in df_today.iterrows():
      nama = row.get("Nama Staff", "Tidak diketahui")
      aktiviti = row.get("Aktiviti", "Aktiviti")
      masa = row.get("Masa", "-")
      report_text += f"🟢 **{nama}** — *{aktiviti}* pada {masa}\n"

    bot.reply_to(message, report_text, parse_mode="Markdown")

  except Exception as e:
    bot.reply_to(message, f"Ralat membaca laporan dari Excel: {e}")
