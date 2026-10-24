    elif "Laporan Bulanan" in input_text:
        conn = get_db_connection()
        if not conn:
            await update.message.reply_text("⚠️ Ralat sambungan database!")
            return

        cur = conn.cursor()
        
        # Ambil data yuran bersama maklumat cawangan anak
        cur.execute("""
            SELECT f.kid_name, f.total_yuran, f.bayar_hari_ini, f.total_paid, k.branch_name
            FROM fees f
            LEFT JOIN kids k ON f.kid_name = k.kid_name
            ORDER BY k.branch_name, f.kid_name;
        """)
        records = cur.fetchall()
        cur.close()
        conn.close()

        if not records:
            await update.message.reply_text("📊 *Laporan Bulanan*\n\nTiada rekod pendaftaran atau yuran lagi.", parse_mode="Markdown")
            return

        # Susun mengikut cawangan taska
        branch_data = {}
        grand_total_yuran = 0.0
        grand_total_paid = 0.0
        grand_total_baki = 0.0
        total_lunas_count = 0

        for r in records:
            kid = r['kid_name']
            yuran = float(r['total_yuran'])
            paid = float(r['total_paid'])
            baki = max(0.0, yuran - paid)
            status = "✅ Lunas" if baki <= 0 and yuran > 0 else "❌ Belum Lunas"
            branch = r['branch_name'] if r['branch_name'] else "Tanpa Cawangan"

            if status == "✅ Lunas":
                total_lunas_count += 1

            grand_total_yuran += yuran
            grand_total_paid += paid
            grand_total_baki += baki

            if branch not in branch_data:
                branch_data[branch] = []
            
            branch_data[branch].append({
                "kid": kid,
                "yuran": yuran,
                "paid": paid,
                "baki": baki,
                "status": status
            })

        # Bina Mesej Laporan Terperinci
        now = datetime.now(MY_TZ)
        report_msg = f"📊 *LAPORAN YURAN BULANAN ({now.strftime('%m/%Y')})*\n"
        report_msg += f"───────────────────────\n\n"

        for b_name, kids in branch_data.items():
            report_msg += f"🏢 *{b_name}*\n"
            for k in kids:
                report_msg += (
                    f" • *{k['kid']}*\n"
                    f"    - Dibayar: RM {k['paid']:.2f} / RM {k['yuran']:.2f}\n"
                    f"    - Baki: RM {k['baki']:.2f} ({k['status']})\n"
                )
            report_msg += "\n"

        report_msg += f"───────────────────────\n"
        report_msg += f"📈 *RINGKASAN KESELURUHAN (SEMUA TASKA)*\n"
        report_msg += f"👥 *Jumlah Anak:* {len(records)} Orang\n"
        report_msg += f"✅ *Anak Lunas:* {total_lunas_count} / {len(records)}\n"
        report_msg += f"💵 *Total Sasaran Yuran:* RM {grand_total_yuran:.2f}\n"
        report_msg += f"💰 *Total Kutipan Termasuk:* RM {grand_total_paid:.2f}\n"
        report_msg += f"⚠️ *Total Baki Belum Bayar:* RM {grand_total_baki:.2f}\n"

        keyboard = [[InlineKeyboardButton("🔙 Kembali ke Dashboard", callback_data="owner_main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text=report_msg, reply_markup=reply_markup, parse_mode="Markdown")
        return
