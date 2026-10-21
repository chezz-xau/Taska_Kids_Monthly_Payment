# ----------------- CALLBACK QUERY HANDLER -----------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    # Zon Masa Malaysia (UTC+8)
    MY_TZ = timezone(timedelta(hours=8))
    current_time = datetime.now(MY_TZ).strftime("%I:%M %p")

    if call.data.startswith("toggle_"):
        _, action, child_id = call.data.split("_")
        
        if child_id in children_data:
            if action == "checkin":
                if children_data[child_id]["status"] == "out":
                    children_data[child_id]["status"] = "in"
                    children_data[child_id]["time"] = current_time
                else:
                    children_data[child_id]["status"] = "out"
                    children_data[child_id]["time"] = None
            else:
                if children_data[child_id]["status"] == "in":
                    children_data[child_id]["status"] = "out"
                    children_data[child_id]["time"] = current_time
                else:
                    children_data[child_id]["status"] = "in"

            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=get_children_keyboard(action=action)
            )
            bot.answer_callback_query(call.id, text=f"Status {children_data[child_id]['name']} dikemaskini!")

    elif call.data.startswith("save_"):
        action = call.data.split("_")[1]
        action_name = "Check-In" if action == "checkin" else "Check-Out"
        
        summary = f"🎉 **REKOD {action_name.upper()} BERJAYA DISIMPAN!**\n\n"
        for child in children_data.values():
            status_icon = "🟢 Hadir" if child["status"] == "in" else "🔴 Pulang/Tiada"
            time_str = f" ({child['time']})" if child['time'] else ""
            summary += f"• {child['name']}: {status_icon}{time_str}\n"

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=summary,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, text="Rekod berjaya disimpan!")
