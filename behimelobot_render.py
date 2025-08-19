#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
behimelobot - نسخه نهایی تعمیر شده برای Render
ساخته شده برای دختری زیبا راپونزل ایرانی بهنوش
تمام مشکلات import و WebApp حل شده
"""

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
import random
import os
import logging
import json
from typing import Any, Dict, List, Optional, Tuple
from flask import Flask, request, jsonify
import threading

# ---------- تنظیمات ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ACCESS_KEY = os.environ.get("ACCESS_KEY")
API_BASE = "https://api.ineo-team.ir/radiojavan.php"
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# تنظیمات لاگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("behimelobot")

# ایجاد Flask app
app = Flask(__name__)
bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")

# ---------- توابع کمکی ----------

def safe_api_call(params: Dict[str, Any]) -> Tuple[bool, Any]:
    """API call امن با مدیریت کامل خطا"""
    try:
        # اضافه کردن auth
        params = params.copy()
        params['auth'] = ACCESS_KEY
        
        logger.info(f"API Request: {params}")
        
        # تأخیر برای rate limiting
        time.sleep(random.uniform(0.5, 1.0))
        
        # درخواست API
        response = requests.get(API_BASE, params=params, timeout=15)
        logger.info(f"API Response Status: {response.status_code}")
        
        # بررسی status code
        response.raise_for_status()
        
        # پارس JSON
        try:
            data = response.json()
            logger.info(f"API Response Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON Decode Error: {e}")
            logger.error(f"Response Text: {response.text[:500]}")
            return False, "پاسخ غیر JSON از سرور"
        
        # بررسی وضعیت پاسخ
        if isinstance(data, dict):
            if data.get('status') == 'successfully':
                return True, data
            elif data.get('status') == 'error':
                error_msg = data.get('message', 'خطای نامشخص')
                logger.error(f"API Error: {error_msg}")
                return False, error_msg
            elif 'result' in data or 'data' in data:
                return True, data
            else:
                return False, "ساختار پاسخ نامعتبر"
        
        return True, data
        
    except requests.exceptions.Timeout:
        return False, "زمان درخواست تمام شد"
    except requests.exceptions.ConnectionError:
        return False, "خطا در اتصال به سرور"
    except requests.exceptions.HTTPError as e:
        return False, f"خطای HTTP: {e}"
    except Exception as e:
        logger.error(f"Unexpected error in API call: {e}")
        return False, f"خطای غیرمنتظره: {str(e)}"

def extract_songs_safe(api_response: Any) -> List[Dict[str, Any]]:
    """استخراج امن آهنگ‌ها از پاسخ API"""
    if not api_response:
        return []
    
    songs = []
    
    try:
        # جستجو در کلیدهای مختلف
        possible_keys = ['result', 'data', 'items', 'results', 'songs']
        
        for key in possible_keys:
            if isinstance(api_response, dict) and key in api_response:
                items = api_response[key]
                
                if isinstance(items, list):
                    songs = items[:5]  # حداکثر 5 آهنگ
                    break
                elif isinstance(items, dict):
                    songs = [items]
                    break
        
        # اگر خود response یک لیست است
        if not songs and isinstance(api_response, list):
            songs = api_response[:5]
        
        # فیلتر کردن آیتم‌های نامعتبر
        valid_songs = []
        for song in songs:
            if isinstance(song, dict) and (song.get('title') or song.get('name')):
                valid_songs.append(song)
        
        return valid_songs
        
    except Exception as e:
        logger.error(f"Error extracting songs: {e}")
        return []

def find_download_url_safe(song_data: Dict[str, Any]) -> Optional[str]:
    """یافتن امن لینک دانلود"""
    if not isinstance(song_data, dict):
        return None
    
    # کلیدهای احتمالی برای لینک
    url_keys = [
        'download_link', 'stream_url', 'url', 'mp3', 'link', 
        'media_url', 'play_url', 'audio_url', 'file_url', 'download_url'
    ]
    
    for key in url_keys:
        if key in song_data:
            url = song_data[key]
            if isinstance(url, str) and url.startswith('http'):
                return url
    
    return None

def format_song_info_safe(song: Dict[str, Any]) -> str:
    """فرمت امن اطلاعات آهنگ"""
    try:
        title = song.get('title') or song.get('name') or "نامشخص"
        artist = song.get('artist') or song.get('singer') or ""
        album = song.get('album') or ""
        duration = song.get('duration') or ""
        
        info = f"🎵 <b>{title}</b>"
        
        if artist:
            info += f"\n👤 آرتیست: {artist}"
        if album:
            info += f"\n💿 آلبوم: {album}"
        if duration:
            info += f"\n⏱ مدت: {duration}"
        
        return info
        
    except Exception as e:
        logger.error(f"Error formatting song info: {e}")
        return "🎵 آهنگ (خطا در نمایش اطلاعات)"

def create_song_keyboard(song: Dict[str, Any], prefix: str = "song") -> InlineKeyboardMarkup:
    """ایجاد کیبورد برای آهنگ"""
    keyboard = InlineKeyboardMarkup()
    
    song_id = str(song.get('id') or song.get('mp3_id') or random.randint(1000, 9999))
    
    # دکمه پخش
    keyboard.add(InlineKeyboardButton("🎵 پخش", callback_data=f"{prefix}_play_{song_id}"))
    
    # دکمه دانلود
    keyboard.add(InlineKeyboardButton("⬇️ دانلود", callback_data=f"{prefix}_dl_{song_id}"))
    
    return keyboard

# ---------- Flask Routes ----------

@app.route('/')
def home():
    return """
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>Behimelobot</title>
        <style>
            body { font-family: Tahoma; text-align: center; background: #667eea; color: white; }
            .container { max-width: 600px; margin: 50px auto; padding: 20px; }
            h1 { font-size: 2.5em; margin-bottom: 20px; }
            p { font-size: 1.2em; line-height: 1.6; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎵 Behimelobot</h1>
            <p>💝 ربات موسیقی برای دختری زیبا راپونزل ایرانی بهنوش</p>
            <p>✅ ربات با موفقیت روی Render در حال اجرا است</p>
            <p>🚀 آماده خدمت‌رسانی</p>
        </div>
    </body>
    </html>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return 'OK'
        else:
            return 'Bad Request', 400
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

@app.route('/health')
def health():
    return jsonify({
        "status": "OK",
        "service": "Behimelobot",
        "message": "آماده خدمت به بهنوش",
        "timestamp": time.time()
    }), 200

@app.route('/webapp')
def webapp():
    """Mini App ساده بدون وابستگی به Telegram WebApp"""
    return """
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Behimelobot Mini App</title>
        <style>
            body {
                font-family: Tahoma, Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 20px;
                color: white;
                text-align: center;
                min-height: 100vh;
            }
            .container {
                max-width: 400px;
                margin: 0 auto;
            }
            h1 {
                font-size: 2em;
                margin-bottom: 20px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }
            .search-box {
                width: 90%;
                padding: 15px;
                border: none;
                border-radius: 25px;
                font-size: 16px;
                margin: 20px 0;
                text-align: center;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }
            .btn {
                background: linear-gradient(45deg, #ff6b6b, #ff8e8e);
                color: white;
                border: none;
                padding: 15px 30px;
                border-radius: 25px;
                font-size: 16px;
                margin: 10px;
                cursor: pointer;
                width: 80%;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                transition: all 0.3s ease;
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0,0,0,0.3);
            }
            .result {
                background: rgba(255,255,255,0.1);
                padding: 20px;
                margin: 15px 0;
                border-radius: 15px;
                backdrop-filter: blur(10px);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎵 Behimelobot</h1>
            <p>💝 Mini App برای بهنوش عزیز</p>
            
            <input type="text" id="searchInput" class="search-box" 
                   placeholder="🔍 نام آهنگ یا آرتیست..." 
                   onkeypress="handleEnter(event)">
            
            <button class="btn" onclick="searchMusic()">🔍 جستجو آهنگ</button>
            <button class="btn" onclick="getNewMusic()">🆕 آهنگ‌های جدید</button>
            
            <div id="result"></div>
        </div>

        <script>
            function handleEnter(event) {
                if (event.key === 'Enter') {
                    searchMusic();
                }
            }

            function searchMusic() {
                const query = document.getElementById('searchInput').value.trim();
                if (!query) {
                    alert('لطفاً نام آهنگ را وارد کنید');
                    return;
                }
                
                showResult(`🔍 جستجو برای: <strong>${query}</strong><br><br>✅ برای جستجو، این متن را در چت ربات بفرستید:<br><br><code>/search ${query}</code>`);
            }

            function getNewMusic() {
                showResult('🆕 برای دیدن آهنگ‌های جدید، این دستور را در چت ربات بفرستید:<br><br><code>/new</code>');
            }

            function showResult(message) {
                document.getElementById('result').innerHTML = `<div class="result">${message}</div>`;
            }
        </script>
    </body>
    </html>
    """

# ---------- Bot Handlers ----------

@bot.message_handler(commands=['start'])
def start_handler(message):
    try:
        welcome_text = (
            "🎵 سلام! من Behimelobot هستم\n"
            "💝 ربات موسیقی ساخته شده برای دختری زیبا راپونزل ایرانی بهنوش\n\n"
            "📋 <b>دستورات موجود:</b>\n"
            "🔍 /search [نام آهنگ] - جستجو آهنگ\n"
            "🆕 /new - آهنگ‌های جدید\n"
            "👤 /artist [نام آرتیست] - آهنگ‌های آرتیست\n"
            "📊 /status - وضعیت ربات\n\n"
            "💡 <b>راهنما:</b>\n"
            "• می‌توانید مستقیماً نام آهنگ بنویسید\n"
            "• از Mini App برای راهنمایی استفاده کنید\n\n"
            "🔗 با عشق برای بهنوش ❤️"
        )
        
        # کیبورد اصلی (بدون وابستگی به WebAppInfo)
        keyboard = InlineKeyboardMarkup()
        
        # دکمه Mini App به عنوان لینک معمولی
        if WEBHOOK_URL:
            keyboard.add(InlineKeyboardButton("🎵 باز کردن Mini App", url=f"{WEBHOOK_URL}/webapp"))
        
        # دکمه‌های سریع
        keyboard.add(
            InlineKeyboardButton("🆕 جدیدترین", callback_data="quick_new"),
            InlineKeyboardButton("📊 وضعیت", callback_data="quick_status")
        )
        
        bot.reply_to(message, welcome_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        bot.reply_to(message, "❌ خطا در شروع ربات")

@bot.message_handler(commands=['search'])
def search_handler(message):
    try:
        # استخراج کوئری
        query = message.text.replace('/search', '').strip()
        if not query:
            bot.reply_to(
                message, 
                "🔍 لطفاً نام آهنگ را وارد کنید\n\n"
                "📝 <b>مثال:</b> <code>/search محسن یگانه</code>"
            )
            return
        
        # نمایش پیام پردازش
        processing_msg = bot.reply_to(message, "🔍 در حال جستجو برای بهنوش...")
        
        # فراخوانی API
        success, data = safe_api_call({
            'action': 'search',
            'type': 'music',
            'query': query
        })
        
        # حذف پیام پردازش
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if not success:
            bot.reply_to(message, f"❌ خطا در جستجو: {data}")
            return
        
        # استخراج آهنگ‌ها
        songs = extract_songs_safe(data)
        if not songs:
            bot.reply_to(message, f"❌ هیچ آهنگی برای '<b>{query}</b>' پیدا نشد")
            return
        
        # نمایش نتایج
        bot.reply_to(message, f"✅ <b>{len(songs)} آهنگ پیدا شد برای '{query}':</b>")
        
        for song in songs:
            try:
                song_info = format_song_info_safe(song)
                keyboard = create_song_keyboard(song, "search")
                
                bot.send_message(
                    message.chat.id,
                    song_info,
                    reply_markup=keyboard
                )
                time.sleep(0.5)  # تأخیر برای جلوگیری از spam
                
            except Exception as e:
                logger.error(f"Error sending song result: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in search handler: {e}")
        bot.reply_to(message, f"❌ خطای داخلی: {str(e)}")

@bot.message_handler(commands=['new'])
def new_handler(message):
    try:
        processing_msg = bot.reply_to(message, "🆕 در حال دریافت آهنگ‌های جدید برای بهنوش...")
        
        success, data = safe_api_call({
            'action': 'new',
            'type': 'music'
        })
        
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if not success:
            bot.reply_to(message, f"❌ خطا در دریافت آهنگ‌های جدید: {data}")
            return
        
        songs = extract_songs_safe(data)
        if not songs:
            bot.reply_to(message, "❌ هیچ آهنگ جدیدی پیدا نشد")
            return
        
        bot.reply_to(message, f"🆕 <b>{len(songs)} آهنگ جدید برای بهنوش:</b>")
        
        for song in songs:
            try:
                song_info = format_song_info_safe(song)
                keyboard = create_song_keyboard(song, "new")
                
                bot.send_message(
                    message.chat.id,
                    song_info,
                    reply_markup=keyboard
                )
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error sending new song: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in new handler: {e}")
        bot.reply_to(message, f"❌ خطای داخلی: {str(e)}")

@bot.message_handler(commands=['artist'])
def artist_handler(message):
    try:
        artist = message.text.replace('/artist', '').strip()
        if not artist:
            bot.reply_to(
                message,
                "👤 لطفاً نام آرتیست را وارد کنید\n\n"
                "📝 <b>مثال:</b> <code>/artist پیشرو</code>"
            )
            return
        
        processing_msg = bot.reply_to(message, f"👤 در حال جستجو آهنگ‌های {artist}...")
        
        success, data = safe_api_call({
            'action': 'media',
            'type': 'music',
            'artist': artist
        })
        
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if not success:
            bot.reply_to(message, f"❌ خطا در جستجو آرتیست: {data}")
            return
        
        songs = extract_songs_safe(data)
        if not songs:
            bot.reply_to(message, f"❌ هیچ آهنگی از '<b>{artist}</b>' پیدا نشد")
            return
        
        bot.reply_to(message, f"👤 <b>{len(songs)} آهنگ از {artist}:</b>")
        
        for song in songs:
            try:
                song_info = format_song_info_safe(song)
                keyboard = create_song_keyboard(song, "artist")
                
                bot.send_message(
                    message.chat.id,
                    song_info,
                    reply_markup=keyboard
                )
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error sending artist song: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in artist handler: {e}")
        bot.reply_to(message, f"❌ خطای داخلی: {str(e)}")

@bot.message_handler(commands=['status'])
def status_handler(message):
    try:
        # تست API
        success, data = safe_api_call({
            'action': 'search',
            'type': 'music',
            'query': 'test'
        })
        
        api_status = "✅ فعال" if success else "❌ خطا"
        
        status_text = (
            f"📊 <b>وضعیت Behimelobot:</b>\n\n"
            f"🤖 ربات: ✅ آنلاین\n"
            f"🌐 API Radio Javan: {api_status}\n"
            f"🏠 پلتفرم: Render.com\n"
            f"📱 Mini App: {'✅ فعال' if WEBHOOK_URL else '❌ غیرفعال'}\n"
            f"⏰ زمان سرور: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"💝 وضعیت: آماده خدمت به بهنوش"
        )
        
        bot.reply_to(message, status_text)
        
    except Exception as e:
        logger.error(f"Error in status handler: {e}")
        bot.reply_to(message, f"❌ خطا در دریافت وضعیت: {str(e)}")

# ---------- Callback Handler ----------

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        callback_data = call.data
        
        # پردازش callback های سریع
        if callback_data == "quick_new":
            bot.answer_callback_query(call.id, "🆕 در حال دریافت آهنگ‌های جدید...")
            new_handler(call.message)
            return
            
        elif callback_data == "quick_status":
            bot.answer_callback_query(call.id, "📊 بررسی وضعیت...")
            status_handler(call.message)
            return
        
        # پردازش callback های آهنگ
        parts = callback_data.split('_')
        if len(parts) >= 3:
            action_type = parts[0]  # search, new, artist
            action = parts[1]       # play, dl
            song_id = parts[2]      # شناسه آهنگ
            
            if action in ['play', 'dl']:
                action_text = "🎵 پخش" if action == 'play' else "⬇️ دانلود"
                bot.answer_callback_query(call.id, f"{action_text} برای بهنوش...")
                
                # دریافت اطلاعات آهنگ
                success, data = safe_api_call({
                    'action': 'get',
                    'type': 'music',
                    'id': song_id
                })
                
                if success:
                    song_info = data.get('result') or data.get('data') or data
                    if isinstance(song_info, dict):
                        # یافتن لینک دانلود
                        download_url = find_download_url_safe(song_info)
                        
                        if download_url:
                            title = song_info.get('title', 'آهنگ')
                            artist = song_info.get('artist', '')
                            
                            link_text = f"🎵 <b>{title}</b>"
                            if artist:
                                link_text += f"\n👤 {artist}"
                            link_text += f"\n\n🔗 <a href='{download_url}'>کلیک برای {action_text}</a>"
                            link_text += f"\n💝 با عشق برای بهنوش"
                            
                            bot.send_message(call.message.chat.id, link_text)
                        else:
                            bot.send_message(call.message.chat.id, "❌ لینک دانلود پیدا نشد")
                    else:
                        bot.send_message(call.message.chat.id, "❌ اطلاعات آهنگ نامعتبر")
                else:
                    bot.send_message(call.message.chat.id, f"❌ خطا در دریافت آهنگ: {data}")
            else:
                bot.answer_callback_query(call.id, "❌ عمل نامشناخته")
        else:
            bot.answer_callback_query(call.id, "❌ داده نامعتبر")
            
    except Exception as e:
        logger.error(f"Error in callback handler: {e}")
        bot.answer_callback_query(call.id, "❌ خطا در پردازش")

# ---------- General Message Handler ----------

@bot.message_handler(func=lambda message: True)
def general_handler(message):
    """پردازش پیام‌های عمومی به عنوان جستجو"""
    try:
        if not message.text or message.text.startswith('/'):
            return
        
        query = message.text.strip()
        if len(query) < 2:
            bot.reply_to(message, "🔍 برای جستجو، حداقل ۲ کاراکتر وارد کنید")
            return
        
        # شبیه‌سازی دستور search
        temp_message = message
        temp_message.text = f'/search {query}'
        search_handler(temp_message)
        
    except Exception as e:
        logger.error(f"Error in general handler: {e}")

# ---------- Keep Alive Function ----------

def keep_alive():
    """نگه‌داری سرویس زنده"""
    while True:
        try:
            time.sleep(840)  # هر 14 دقیقه
            if WEBHOOK_URL:
                requests.get(f"{WEBHOOK_URL}/health", timeout=10)
                logger.info("Keep-alive ping sent")
        except Exception as e:
            logger.error(f"Keep-alive error: {e}")

# ---------- Main Function ----------

def main():
    """تابع اصلی"""
    logger.info("🚀 Starting Behimelobot for Behnosh...")
    
    try:
        # تست اولیه API
        success, data = safe_api_call({
            'action': 'search',
            'type': 'music',
            'query': 'test'
        })
        
        if success:
            logger.info("✅ API connection successful")
        else:
            logger.warning(f"⚠️ API test failed: {data}")
        
        # شروع keep-alive thread
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
        
        if WEBHOOK_URL:
            # حالت Webhook برای Render
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
            logger.info(f"✅ Webhook set: {WEBHOOK_URL}/webhook")
            
            # شروع Flask server
            app.run(host='0.0.0.0', port=PORT, debug=False)
        else:
            # حالت Polling برای تست محلی
            logger.info("Starting in polling mode...")
            bot.remove_webhook()
            bot.polling(none_stop=True, interval=1, timeout=20)
            
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
    finally:
        logger.info("👋 Behimelobot terminated - Goodbye Behnosh!")

if __name__ == "__main__":
    main()
