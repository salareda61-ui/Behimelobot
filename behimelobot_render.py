# --- اضافه کردن کیبورد و گزینه‌های خلاقانه در ربات تلگرام ---

def send_main_keyboard(chat_id):
    keyboard = {
        "keyboard": [
            [{"text": "🔍 جستجو موزیک"}, {"text": "🎵 آهنگ جدید"}],
            [{"text": "⭐ خواننده محبوب"}, {"text": "🎶 پلی‌لیست ویژه"}],
            [{"text": "⬇ دانلود آهنگ"}, {"text": "🎧 پخش آهنگ"}],
            [{"text": "📈 موزیک ترند"}, {"text": "❓ راهنما"}],
            [{"text": "🚀 پیشنهاد تصادفی"}, {"text": "🎤 موزیک هنرمند"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }
    send_telegram_message(chat_id, "لطفاً گزینه مورد نظر را انتخاب کنید:", keyboard)

# --- در webhook هنگام /start یا پیام کاربر ---
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = request.get_json()
        logger.info(f"📨 Received update: {json.dumps(update, indent=2)}")
        
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            
            if 'text' in message:
                text = message['text']
                
                # ارسال کیبورد خلاقانه هنگام شروع یا درخواست کاربر
                if text.startswith('/start'):
                    welcome_msg = """🎵 به BehimeloBot خوش آمدید!

لطفاً یکی از گزینه‌ها را از کیبورد انتخاب کنید:
🔍 جستجو موزیک | 🎵 آهنگ جدید | ⭐ خواننده محبوب | 🎶 پلی‌لیست ویژه
⬇ دانلود آهنگ | 🎧 پخش آهنگ | 📈 موزیک ترند | ❓ راهنما
🚀 پیشنهاد تصادفی | 🎤 موزیک هنرمند

همه امکانات پخش و دانلود موزیک و کشف هنرمندان و پلی‌لیست‌های خاص برای شما فعال است!
                    """
                    send_telegram_message(chat_id, welcome_msg)
                    send_main_keyboard(chat_id)
                    return jsonify({'status': 'ok'})

                # مثال: دریافت آهنگ جدید
                elif text == "🎵 آهنگ جدید":
                    # فرض: تابعی برای دریافت لیست آهنگ جدید
                    success, data = safe_api_call('new_tracks')
                    if success:
                        formatted_results = format_music_results(data, "آهنگ جدید")
                        send_telegram_message(chat_id, formatted_results)
                    else:
                        send_telegram_message(chat_id, "❌ خطا در دریافت آهنگ جدید.")
                    return jsonify({'status': 'ok'})

                # مثال: پخش یا دانلود آهنگ
                elif text == "🎧 پخش آهنگ" or text == "⬇ دانلود آهنگ":
                    send_telegram_message(chat_id, "لطفاً نام آهنگ یا خواننده را ارسال کنید:")
                    return jsonify({'status': 'ok'})

                # خواننده محبوب
                elif text == "⭐ خواننده محبوب":
                    success, data = safe_api_call('top_artists')
                    if success:
                        artists = data.get('result', {}).get('artists', [])
                        msg = "⭐ لیست خواننده‌های محبوب:\n" + "\n".join([f"{i+1}. {a.get('name')}" for i, a in enumerate(artists)])
                        send_telegram_message(chat_id, msg)
                    else:
                        send_telegram_message(chat_id, "❌ خطا در دریافت خواننده‌های محبوب.")
                    return jsonify({'status': 'ok'})

                # پلی‌لیست ویژه
                elif text == "🎶 پلی‌لیست ویژه":
                    success, data = safe_api_call('special_playlist')
                    if success:
                        playlist = data.get('result', {}).get('playlist', [])
                        msg = "🎶 پلی‌لیست ویژه:\n" + "\n".join([f"{i+1}. {p.get('title')}" for i, p in enumerate(playlist)])
                        send_telegram_message(chat_id, msg)
                    else:
                        send_telegram_message(chat_id, "❌ خطا در دریافت پلی‌لیست ویژه.")
                    return jsonify({'status': 'ok'})

                # موزیک ترند
                elif text == "📈 موزیک ترند":
                    success, data = safe_api_call('trending_tracks')
                    if success:
                        formatted_results = format_music_results(data, "موزیک ترند")
                        send_telegram_message(chat_id, formatted_results)
                    else:
                        send_telegram_message(chat_id, "❌ خطا در دریافت موزیک‌های ترند.")
                    return jsonify({'status': 'ok'})

                # پیشنهاد تصادفی موزیک
                elif text == "🚀 پیشنهاد تصادفی":
                    success, data = safe_api_call('random_track')
                    if success:
                        formatted_results = format_music_results(data, "پیشنهاد تصادفی")
                        send_telegram_message(chat_id, formatted_results)
                    else:
                        send_telegram_message(chat_id, "❌ خطا در پیشنهاد موزیک.")
                    return jsonify({'status': 'ok'})

                # موزیک هنرمند
                elif text == "🎤 موزیک هنرمند":
                    send_telegram_message(chat_id, "لطفاً نام هنرمند مورد نظر را ارسال کنید:")
                    return jsonify({'status': 'ok'})

                # راهنما
                elif text == "❓ راهنما":
                    help_text = """📖 راهنمای ربات موزیک:
- برای جستجو، گزینه "جستجو موزیک" را انتخاب کنید.
- پخش و دانلود موزیک از طریق گزینه‌های مربوطه امکان‌پذیر است.
- برای دیدن پلی‌لیست ویژه یا موزیک ترند از گزینه‌های کیبورد استفاده کنید.
- هر سوالی داشتی بنویس!
                    """
                    send_telegram_message(chat_id, help_text)
                    return jsonify({'status': 'ok'})

                # جستجو موزیک یا هر متن دیگر = جستجوی موزیک
                else:
                    handle_search_command(text, chat_id)
                    return jsonify({'status': 'ok'})
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        logger.error(f"❌ Error in webhook: {e}")
        return jsonify({'error': str(e)}), 500

# --- پخش و دانلود آهنگ در وب‌اپ (در html همین الان هست)
# تگ <audio controls src="..."></audio> برای پخش
# لینک <a href="...">⬇ دانلود</a> برای دانلود
# کافی است لینک‌ها را از API و نتیجه جستجو پر کنید (در کد فعلی هست)

# --- نکته: سایر توابع مثل safe_api_call و format_music_results باید بر اساس پارامترهای جدید اکشن (مثل 'new_tracks', 'top_artists', ...) قابل استفاده باشند ---

# --- سایر بخش‌های فایل بدون تغییر باقی می‌ماند ---
