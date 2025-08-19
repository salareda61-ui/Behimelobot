#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
behimelobot - یک ربات تلگرام برای جستجو و پخش آهنگ‌های فارسی از Radio Javan
ساخته شده برای دختری زیبا راپونزل ایرانی بهنوش
استفاده از API رسمی ineo-team.ir
ویژه Render.com (نسخه تعمیر شده)
"""

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
import random
import tempfile
import os
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from flask import Flask, request
import threading

# ---------- تنظیمات ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8233618807:AAFpQaC0EbHJ3Nt0GGnrRDwF-rC3mLucpU0")
ACCESS_KEY = os.environ.get("ACCESS_KEY", "720466:3bb9f3a71ee015a604dd23af3f92c426")
API_BASE = "https://api.ineo-team.ir/radiojavan.php"
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")

# rate limit: حداقل زمان بین درخواست‌ها (ثانیه)
MIN_API_DELAY = 1.0
MAX_API_DELAY = 1.7

# timeout برای درخواست‌ها
REQUEST_TIMEOUT = 15

# تنظیمات لاگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("behimelobot")

# ایجاد Flask app برای webhook
app = Flask(__name__)
bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")

# ---------- توابع کمکی ----------

def api_delay():
    """تأخیر تصادفی بین درخواست‌ها برای جلوگیری از اسپم کردن API"""
    t = random.uniform(MIN_API_DELAY, MAX_API_DELAY)
    logger.debug(f"API delay: {t:.2f}s")
    time.sleep(t)

def call_api(params: Dict[str, Any]) -> Tuple[bool, Any]:
    """
    فراخوانی API با پارامترها، اضافه کردن auth خودکار.
    برمی‌گرداند: (success, data_or_error_message)
    """
    params = params.copy()
    params['auth'] = ACCESS_KEY
    
    logger.info(f"API Request: {params}")
    
    try:
        api_delay()
        resp = requests.get(API_BASE, params=params, timeout=REQUEST_TIMEOUT)
        logger.info(f"API URL: {resp.url}")
        logger.info(f"Response Status: {resp.status_code}")
        
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Network error calling API: {e}")
        return False, f"خطا در ارتباط با سرور API: {str(e)}"
    
    try:
        data = resp.json()
        logger.info(f"Response JSON keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
    except ValueError as e:
        logger.error(f"Invalid JSON response: {resp.text[:200]}")
        return False, f"خطا: پاسخ نامعتبر از سرور API: {str(e)}"
    
    # هندلینگ وضعیت بر اساس API جدید
    if data.get('status') == 'successfully':
        return True, data
    elif data.get('status') == 'error':
        error_msg = data.get('message', 'خطای نامشناخته از API')
        logger.error(f"API Error: {error_msg}")
        return False, error_msg
    else:
        # برای سازگاری با پاسخ‌های مختلف
        if 'result' in data or 'data' in data:
            return True, data
        else:
            return False, "پاسخ غیرمنتظره از API"

def find_download_url(obj: Any) -> Optional[str]:
    """
    جستجو در JSON برای یافتن لینک دانلود/پخش (اولویت به mp3 یا stream).
    """
    if not obj:
        return None
    
    # فیلدهای احتمالی برای لینک دانلود
    possible_keys = [
        'download_link', 'stream_url', 'url', 'mp3', 'link', 'media_url',
        'play_url', 'audio_url', 'file_url', 'download_url'
    ]
    
    if isinstance(obj, dict):
        for key in possible_keys:
            if key in obj and isinstance(obj[key], str) and obj[key].startswith('http'):
                return obj[key]
        
        # جستجوی عمیق در زیرمجموعه‌ها
        for v in obj.values():
            url = find_download_url(v)
            if url:
                return url
                
    elif isinstance(obj, list) and obj:
        return find_download_url(obj[0])
    
    return None

def extract_items_list(api_resp: Any) -> List[Dict[str, Any]]:
    """
    استخراج لیست آیتم‌ها (آهنگ‌ها و غیره) از پاسخ API.
    """
    if not api_resp:
        return []
    
    # فیلدهای احتمالی برای لیست نتایج
    possible_lists = [
        api_resp.get('result'),
        api_resp.get('results'), 
        api_resp.get('data'),
        api_resp.get('items'),
        api_resp.get('list')
    ]
    
    for possible_list in possible_lists:
        if isinstance(possible_list, list):
            return possible_list[:5]  # محدود به ۵ نتیجه برای Render
        elif isinstance(possible_list, dict):
            # اگر یک dict است، ممکن است خود آیتم باشد
            return [possible_list]
    
    # اگر خود api_resp یک لیست است
    if isinstance(api_resp, list):
        return api_resp[:5]
    
    return []

def create_inline_keyboard(item_id: str, callback_prefix: str, item_data: Dict = None) -> InlineKeyboardMarkup:
    """ساخت کیبورد اینلاین برای پخش/دانلود"""
    keyboard = InlineKeyboardMarkup()
    
    # دکمه پخش
    keyboard.add(InlineKeyboardButton("🎵 پخش", callback_data=f"{callback_prefix}_play_{item_id}"))
    
    # دکمه دانلود
    keyboard.add(InlineKeyboardButton("⬇️ دانلود", callback_data=f"{callback_prefix}_dl_{item_id}"))
    
    # اگر اطلاعات بیشتری موجود است، دکمه جزئیات اضافه کن
    if item_data and item_data.get('artist'):
        keyboard.add(InlineKeyboardButton("👤 آرتیست", callback_data=f"artist_info_{item_data.get('artist')}"))
    
    return keyboard

def create_main_keyboard():
    """ساخت کیبورد اصلی"""
    keyboard = InlineKeyboardMarkup()
    
    # دکمه Mini App (به عنوان لینک معمولی)
    if WEBHOOK_URL:
        keyboard.add(InlineKeyboardButton("🎵 باز کردن Mini App", url=f"{WEBHOOK_URL}/webapp"))
    
    # دکمه‌های سریع
    keyboard.add(
        InlineKeyboardButton("🆕 جدیدترین", callback_data="quick_new"),
        InlineKeyboardButton("📊 وضعیت", callback_data="quick_status")
    )
    
    return keyboard

def format_song_info(item: Dict) -> str:
    """فرمت کردن اطلاعات آهنگ برای نمایش"""
    title = item.get('title') or item.get('name') or "نامشخص"
    artist = item.get('artist') or item.get('singer') or ""
    album = item.get('album') or ""
    duration = item.get('duration') or ""
    
    info = f"🎵 <b>{title}</b>"
    
    if artist:
        info += f"\n👤 آرتیست: {artist}"
    if album:
        info += f"\n💿 آلبوم: {album}"
    if duration:
        info += f"\n⏱ مدت: {duration}"
    
    return info

def send_audio_or_link(chat_id: int, url: str, title: str = "آهنگ", artist: str = ""):
    """ارسال لینک مستقیم (بهینه شده برای Render)"""
    if not url:
        bot.send_message(chat_id, "❌ لینک پخش/دانلود موجود نیست.")
        return
    
    try:
        # برای Render، بهتر است لینک مستقیم ارسال کنیم
        link_text = f"🎵 <b>{title}</b>"
        if artist:
            link_text += f"\n👤 آرتیست: {artist}"
        link_text += f"\n\n🔗 <a href='{url}'>کلیک برای دانلود/پخش</a>"
        link_text += f"\n\n💝 با عشق برای بهنوش 💝"
        
        bot.send_message(chat_id, link_text)
        
    except Exception as e:
        logger.error(f"Error sending link: {e}")
        bot.send_message(chat_id, f"❌ خطا در ارسال لینک: {str(e)}")

# ---------- Flask Routes (برای Webhook و Mini App) ----------
@app.route('/')
def index():
    return "🎵 Behimelobot is running on Render! 💝 Made with love for Behnosh"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Forbidden', 403

@app.route('/health')
def health():
    return "OK - Behimelobot is healthy!", 200

@app.route('/webapp')
def webapp():
    """صفحه Mini App"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Behimelobot - برای بهنوش</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body {
                font-family: 'Tahoma', 'Arial', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 20px;
                color: white;
                direction: rtl;
                min-height: 100vh;
            }
            .container {
                max-width: 400px;
                margin: 0 auto;
                text-align: center;
            }
            .header {
                margin-bottom: 30px;
                animation: fadeIn 1s ease-in;
            }
            .header h1 {
                font-size: 2em;
                margin-bottom: 10px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }
            .search-box {
                width: 90%;
                padding: 15px;
                border: none;
                border-radius: 25px;
                font-size: 16px;
                margin-bottom: 20px;
                text-align: center;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                transition: all 0.3s ease;
            }
            .search-box:focus {
                outline: none;
                box-shadow: 0 6px 20px rgba(0,0,0,0.3);
                transform: translateY(-2px);
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
                font-weight: bold;
            }
            .btn:hover {
                background: linear-gradient(45deg, #ff5252, #ff7979);
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0,0,0,0.3);
            }
            .btn:active {
                transform: translateY(0);
            }
            .music-item {
                background: rgba(255,255,255,0.1);
                padding: 20px;
                margin: 15px 0;
                border-radius: 15px;
                text-align: right;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255,255,255,0.2);
                animation: slideIn 0.5s ease-out;
            }
            .loading {
                display: none;
                margin: 20px 0;
            }
            .spinner {
                border: 4px solid rgba(255,255,255,0.3);
                border-radius: 50%;
                border-top: 4px solid #fff;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 0 auto;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(-20px); }
                to { opacity: 1; transform: translateY(0); }
            }
            @keyframes slideIn {
                from { opacity: 0; transform: translateX(50px); }
                to { opacity: 1; transform: translateX(0); }
            }
            .quick-buttons {
                display: flex;
                justify-content: space-around;
                margin: 20px 0;
            }
            .quick-btn {
                background: rgba(255,255,255,0.2);
                border: none;
                padding: 12px;
                border-radius: 50%;
                color: white;
                font-size: 20px;
                cursor: pointer;
                transition: all 0.3s ease;
                width: 60px;
                height: 60px;
            }
            .quick-btn:hover {
                background: rgba(255,255,255,0.3);
                transform: scale(1.1);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎵 Behimelobot</h1>
                <p>💝 ربات موسیقی برای دختری زیبا راپونزل ایرانی بهنوش</p>
            </div>
            
            <input type="text" id="searchInput" class="search-box" placeholder="🔍 نام آهنگ یا آرتیست را بنویسید..." onkeypress="handleKeyPress(event)">
            
            <button class="btn" onclick="searchMusic()">🔍 جستجو آهنگ</button>
            <button class="btn" onclick="getNewMusic()">🆕 آهنگ‌های جدید</button>
            
            <div class="quick-buttons">
                <button class="quick-btn" onclick="randomSearch()" title="جستجوی تصادفی">🎲</button>
                <button class="quick-btn" onclick="popularMusic()" title="محبوب‌ترین">🔥</button>
                <button class="quick-btn" onclick="clearResults()" title="پاک کردن">🗑️</button>
            </div>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>در حال پردازش...</p>
            </div>
            
            <div id="results"></div>
        </div>

        <script>
            // Initialize Telegram WebApp if available
            let tg = null;
            try {
                if (window.Telegram && window.Telegram.WebApp) {
                    tg = window.Telegram.WebApp;
                    tg.ready();
                    tg.expand();
                    tg.setHeaderColor('#667eea');
                    tg.setBackgroundColor('#667eea');
                }
            } catch (e) {
                console.log('Telegram WebApp not available:', e);
            }

            function showLoading() {
                document.getElementById('loading').style.display = 'block';
            }

            function hideLoading() {
                document.getElementById('loading').style.display = 'none';
            }

            function handleKeyPress(event) {
                if (event.key === 'Enter') {
                    searchMusic();
                }
            }

            function searchMusic() {
                const query = document.getElementById('searchInput').value.trim();
                if (!query) {
                    if (tg) {
                        tg.showAlert('لطفاً نام آهنگ را وارد کنید');
                    } else {
                        alert('لطفاً نام آهنگ را وارد کنید');
                    }
                    return;
                }
                
                showLoading();
                
                // Send data to bot if available
                if (tg) {
                    try {
                        tg.sendData(`search:${query}`);
                    } catch (e) {
                        console.log('Error sending data:', e);
                    }
                }
                
                // Show in results
                setTimeout(() => {
                    hideLoading();
                    document.getElementById('results').innerHTML = `
                        <div class="music-item">
                            🔍 جستجو برای: <strong>${query}</strong>
                            <br><br>✅ درخواست ارسال شد!
                            <br>نتایج در چت ربات نمایش داده می‌شود.
                            <br><br>🎵 برای دیدن نتایج به چت ربات بروید.
                        </div>
                    `;
                }, 1000);
            }

            function getNewMusic() {
                showLoading();
                
                if (tg) {
                    try {
                        tg.sendData('new:latest');
                    } catch (e) {
                        console.log('Error sending data:', e);
                    }
                }
                
                setTimeout(() => {
                    hideLoading();
                    document.getElementById('results').innerHTML = `
                        <div class="music-item">
                            🆕 درخواست آهنگ‌های جدید ارسال شد!
                            <br><br>✅ نتایج در چت ربات نمایش داده می‌شود.
                            <br><br>🎵 برای دیدن آهنگ‌های جدید به چت ربات بروید.
                        </div>
                    `;
                }, 1000);
            }

            function randomSearch() {
                const randomQueries = [
                    'محسن یگانه', 'پیشرو', 'پوزیکون', 'حمید هیراد', 'مرتضی پاشایی',
                    'شادمهر عقیلی', 'رضا صادقی', 'علی یاسینی', 'مهراد جم', 'سینا حجازی'
                ];
                const randomQuery = randomQueries[Math.floor(Math.random() * randomQueries.length)];
                
                document.getElementById('searchInput').value = randomQuery;
                searchMusic();
            }

            function popularMusic() {
                showLoading();
                
                if (tg) {
                    try {
                        tg.sendData('popular:music');
                    } catch (e) {
                        console.log('Error sending data:', e);
                    }
                }
                
                setTimeout(() => {
                    hideLoading();
                    document.getElementById('results').innerHTML = `
                        <div class="music-item">
                            🔥 درخواست محبوب‌ترین آهنگ‌ها ارسال شد!
                            <br><br>✅ نتایج در چت ربات نمایش داده می‌شود.
                        </div>
                    `;
                }, 1000);
            }

            function clearResults() {
                document.getElementById('results').innerHTML = '';
                document.getElementById('searchInput').value = '';
                if (tg) {
                    tg.showAlert('✅ پاک شد!');
                } else {
                    alert('✅ پاک شد!');
                }
            }

            // Handle theme changes if available
            if (tg) {
                try {
                    tg.onEvent('themeChanged', function() {
                        const isDark = tg.colorScheme === 'dark';
                        document.body.style.background = isDark ? 
                            'linear-gradient(135deg, #2c3e50 0%, #34495e 100%)' : 
                            'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
                    });
                } catch (e) {
                    console.log('Theme change handler error:', e);
                }
            }

            // Show welcome message
            setTimeout(() => {
                document.getElementById('results').innerHTML = `
                    <div class="music-item">
                        🎵 سلام بهنوش عزیز!
                        <br><br>💝 از Mini App Behimelobot استفاده می‌کنی
                        <br><br>🔍 می‌تونی اینجا جستجو کنی و نتایج رو در چت ربات ببینی
                        <br><br>✨ برای شروع یک آهنگ جستجو کن!
                    </div>
                `;
            }, 500);
        </script>
    </body>
    </html>
    '''

# ---------- هندلرهای ربات ----------

@bot.message_handler(commands=['start'])
def handle_start(message):
    welcome = (
        "سلام! من Behimelobot هستم، ربات موسیقی برای دختری زیبا راپونزل ایرانی بهنوش.\n"
        "ربات موسیقی با استفاده از Radio Javan API\n\n"
        "📋 <b>دستورات:</b>\n"
        "🔍 /search [نام آهنگ] - جستجو آهنگ\n"
        "🆕 /new - جدیدترین آهنگ‌ها\n"
        "👤 /artist [نام آرتیست] - آهنگ‌های آرتیست\n"
        "📊 /profile [آرتیست] - پروفایل آرتیست\n"
        "📋 /playlist [شناسه] - جزئیات پلی‌لیست\n"
        "🧪 /status - وضعیت سرور\n\n"
        "💡 <b>راهنما:</b>\n"
        "• می‌توانید لینک Radio Javan را مستقیماً ارسال کنید\n"
        "• برای جستجو بهتر از نام فارسی استفاده کنید\n"
        "• از Mini App برای تجربه بهتر استفاده کنید\n\n"
        "🔗 ساخته شده با ❤️ برای بهنوش\n"
        "🚀 میزبانی شده در Render"
    )
    bot.reply_to(message, welcome, reply_markup=create_main_keyboard())

@bot.message_handler(commands=['status'])
def handle_status(message):
    try:
        # تست API
        success, data = call_api({'action': 'search', 'type': 'music', 'query': 'test'})
        api_status = "✅ فعال" if success else "❌ خطا"
        
        status_text = (
            f"📊 <b>وضعیت سرور Behimelobot:</b>\n\n"
            f"🤖 ربات: ✅ آنلاین\n"
            f"🌐 API Radio Javan: {api_status}\n"
            f"🏠 پلتفرم: Render.com\n"
            f"📱 Mini App: {'✅ فعال' if WEBHOOK_URL else '❌ غیرفعال'}\n"
            f"⏰ زمان سرور: {time.strftime('%H:%M:%S')}\n"
            f"💝 وضعیت: آماده خدمت به بهنوش"
        )
        bot.reply_to(message, status_text)
    except Exception as e:
        bot.reply_to(message, f"❌ خطا در دریافت وضعیت: {str(e)}")

@bot.message_handler(commands=['search'])
def handle_search(message):
    try:
        query = message.text.replace('/search', '').strip()
        if not query:
            bot.reply_to(message, "🔍 لطفاً نام آهنگ را وارد کنید\n\n📝 مثال: <code>/search محسن یگانه</code>")
            return
        
        processing_msg = bot.reply_to(message, "🔍 در حال جستجو برای بهنوش...")
        
        success, data = call_api({
            'action': 'search',
            'type': 'music',
            'query': query
        })
        
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if not success:
            bot.reply_to(message, f"❌ خطا در جستجو: {data}")
            return
        
        items = extract_items_list(data)
        if not items:
            bot.reply_to(message, f"❌ هیچ نتیجه‌ای برای '<b>{query}</b>' پیدا نشد.")
            return
        
        bot.reply_to(message, f"✅ {len(items)} نتیجه پیدا شد برای '<b>{query}</b>':")
        
        for item in items:
            try:
                info_text = format_song_info(item)
                item_id = str(item.get('id') or item.get('mp3_id') or random.randint(1000, 9999))
                
                bot.send_message(
                    message.chat.id,
                    info_text,
                    reply_markup=create_inline_keyboard(item_id, 'search', item)
                )
                time.sleep(0.3)
                
            except Exception as e:
                logger.error(f"Error sending search result: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in search handler: {e}")
        bot.reply_to(message, f"❌ خطای داخلی: {str(e)}")

@bot.message_handler(commands=['new'])
def handle_new(message):
    try:
        processing_msg = bot.reply_to(message, "🆕 در حال دریافت جدیدترین آهنگ‌ها برای بهنوش...")
        
        success, data = call_api({
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
        
        items = extract_items_list(data)
        if not items:
            bot.reply_to(message, "❌ هیچ آهنگ جدیدی پیدا نشد.")
            return
        
        bot.reply_to(message, f"🆕 <b>{len(items)} آهنگ جدید برای بهنوش:</b>")
        
        for item in items:
            try:
                info_text = format_song_info(item)
                item_id = str(item.get('id') or item.get('mp3_id') or random.randint(1000, 9999))
                
                bot.send_message(
                    message.chat.id,
                    info_text,
                    reply_markup=create_inline_keyboard(item_id, 'new', item)
                )
                time.sleep(0.3)
                
            except Exception as e:
                logger.error(f"Error sending new music: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in new handler: {e}")
        bot.reply_to(message, f"❌ خطای داخلی: {str(e)}")

@bot.message_handler(commands=['artist'])
def handle_artist(message):
    try:
        artist = message.text.replace('/artist', '').strip()
        if not artist:
            bot.reply_to(message, "👤 لطفاً نام آرتیست را وارد کنید\n\n📝 مثال: <code>/artist پیشرو</code>")
            return
        
        processing_msg = bot.reply_to(message, f"👤 در حال جستجو آهنگ‌های {artist} برای بهنوش...")
        
        success, data = call_api({
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
        
        items = extract_items_list(data)
        if not items:
            bot.reply_to(message, f"❌ هیچ آهنگی از '<b>{artist}</b>' پیدا نشد.")
            return
        
        bot.reply_to(message, f"👤 <b>{len(items)} آهنگ از {artist} برای بهنوش:</b>")
        
        for item in items:
            try:
                info_text = format_song_info(item)
                item_id = str(item.get('id') or item.get('mp3_id') or random.randint(1000, 9999))
                
                bot.send_message(
                    message.chat.id,
                    info_text,
                    reply_markup=create_inline_keyboard(item_id, 'artist', item)
                )
                time.sleep(0.3)
                
            except Exception as e:
                logger.error(f"Error sending artist music: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in artist handler: {e}")
        bot.reply_to(message, f"❌ خطای داخلی: {str(e)}")

@bot.message_handler(commands=['profile'])
def handle_profile(message):
    try:
        artist = message.text.replace('/profile', '').strip()
        if not artist:
            bot.reply_to(message, "👤 لطفاً نام آرتیست را وارد کنید\n\n📝 مثال: <code>/profile پیشرو</code>")
            return
        
        processing_msg = bot.reply_to(message, f"👤 در حال دریافت پروفایل {artist}...")
        
        success, data = call_api({
            'action': 'profile',
            'artist': artist
        })
        
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if not success:
            bot.reply_to(message, f"❌ خطا در دریافت پروفایل: {data}")
            return
        
        profile_info = data.get('result') or data.get('data') or data
        if not profile_info:
            bot.reply_to(message, f"❌ پروفایل '{artist}' پیدا نشد.")
            return
        
        name = profile_info.get('name') or artist
        bio = profile_info.get('bio') or profile_info.get('description') or "اطلاعاتی موجود نیست"
        followers = profile_info.get('followers') or profile_info.get('follower_count') or "نامشخص"
        
        profile_text = f"👤 <b>پروفایل: {name}</b>\n\n"
        profile_text += f"📝 <b>بیوگرافی:</b>\n{bio}\n\n"
        profile_text += f"👥 <b>دنبال‌کنندگان:</b> {followers}\n"
        profile_text += f"💝 <b>برای بهنوش عزیز</b>"
        
        # اگر عکس پروفایل موجود باشد
        photo_url = find_download_url(profile_info.get('photo')) or find_download_url(profile_info.get('image'))
        
        if photo_url:
            try:
                bot.send_photo(message.chat.id, photo_url, caption=profile_text)
            except:
                bot.reply_to(message, profile_text)
        else:
            bot.reply_to(message, profile_text)
            
    except Exception as e:
        logger.error(f"Error in profile handler: {e}")
        bot.reply_to(message, f"❌ خطای داخلی: {str(e)}")

@bot.message_handler(commands=['playlist'])
def handle_playlist(message):
    try:
        playlist_id = message.text.replace('/playlist', '').strip()
        if not playlist_id:
            bot.reply_to(message, "📋 لطفاً شناسه پلی‌لیست را وارد کنید\n\n📝 مثال: <code>/playlist 12345</code>")
            return
        
        processing_msg = bot.reply_to(message, "📋 در حال دریافت پلی‌لیست برای بهنوش...")
        
        success, data = call_api({
            'action': 'playlist',
            'id': playlist_id
        })
        
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if not success:
            bot.reply_to(message, f"❌ خطا در دریافت پلی‌لیست: {data}")
            return
        
        playlist_info = data.get('result') or data.get('data') or data
        if not playlist_info:
            bot.reply_to(message, f"❌ پلی‌لیست با شناسه '{playlist_id}' پیدا نشد.")
            return
        
        title = playlist_info.get('title') or playlist_info.get('name') or "نامشخص"
        description = playlist_info.get('description') or ""
        
        playlist_text = f"📋 <b>پلی‌لیست: {title}</b>\n"
        if description:
            playlist_text += f"📝 {description}\n"
        playlist_text += f"💝 برای بهنوش عزیز\n"
        
        # دریافت آهنگ‌های پلی‌لیست
        songs = extract_items_list(playlist_info.get('songs') or playlist_info.get('items'))
        if songs:
            playlist_text += f"\n🎵 <b>{len(songs)} آهنگ:</b>"
            bot.reply_to(message, playlist_text)
            
            for song in songs:
                try:
                    info_text = format_song_info(song)
                    item_id = str(song.get('id') or song.get('mp3_id') or random.randint(1000, 9999))
                    
                    bot.send_message(
                        message.chat.id,
                        info_text,
                        reply_markup=create_inline_keyboard(item_id, 'playlist', song)
                    )
                    time.sleep(0.3)
                    
                except Exception as e:
                    logger.error(f"Error sending playlist song: {e}")
                    continue
        else:
            playlist_text += "\n❌ آهنگی در این پلی‌لیست پیدا نشد."
            bot.reply_to(message, playlist_text)
            
    except Exception as e:
        logger.error(f"Error in playlist handler: {e}")
        bot.reply_to(message, f"❌ خطای داخلی: {str(e)}")

# ---------- هندلر WebApp Data (تعمیر شده) ----------

@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    """پردازش داده‌های دریافتی از Mini App"""
    try:
        # بررسی امن وجود web_app_data
        if not hasattr(message, 'web_app_data') or not message.web_app_data:
            logger.warning("No web_app_data found in message")
            bot.reply_to(message, "❌ داده Mini App دریافت نشد")
            return
            
        if not hasattr(message.web_app_data, 'data') or not message.web_app_data.data:
            logger.warning("No data found in web_app_data")
            bot.reply_to(message, "❌ داده خالی از Mini App")
            return
            
        data = message.web_app_data.data
        logger.info(f"WebApp data received: {data}")
        
        if data.startswith('search:'):
            query = data.replace('search:', '').strip()
            if query:
                # شبیه‌سازی دستور search
                message.text = f'/search {query}'
                handle_search(message)
            else:
                bot.reply_to(message, "❌ نام آهنگ خالی است")
            
        elif data.startswith('new:'):
            # شبیه‌سازی دستور new
            handle_new(message)
            
        elif data.startswith('popular:'):
            # جستجوی آهنگ‌های محبوب
            message.text = '/search محبوب'
            handle_search(message)
            
        else:
            bot.reply_to(message, f"💝 سلام بهنوش! از Mini App استفاده کردی\n\nداده دریافت شده: {data}")
            
    except AttributeError as e:
        logger.error(f"AttributeError in web app data handler: {e}")
        bot.reply_to(message, "❌ خطا در پردازش درخواست Mini App - ساختار داده نامعتبر")
    except Exception as e:
        logger.error(f"Error handling web app data: {e}")
        bot.reply_to(message, "❌ خطا در پردازش درخواست Mini App")

# ---------- هندلر کال‌بک‌ها ----------

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        data_parts = call.data.split('_')
        
        # هندل کردن دکمه‌های سریع
        if call.data == 'quick_new':
            bot.answer_callback_query(call.id, "🆕 در حال دریافت آهنگ‌های جدید...")
            handle_new(call.message)
            return
            
        elif call.data == 'quick_status':
            bot.answer_callback_query(call.id, "📊 بررسی وضعیت...")
            handle_status(call.message)
            return
        
        if len(data_parts) < 3:
            bot.answer_callback_query(call.id, "❌ خطا در پردازش درخواست")
            return
        
        action_type = data_parts[0]  # search, new, artist, etc.
        action = data_parts[1]       # play, dl
        item_id = data_parts[2]      # شناسه آیتم
        
        if action == 'play':
            bot.answer_callback_query(call.id, "🎵 در حال پخش برای بهنوش...")
            handle_play_music(call.message.chat.id, item_id, action_type)
            
        elif action == 'dl':
            bot.answer_callback_query(call.id, "⬇️ در حال دانلود برای بهنوش...")
            handle_download_music(call.message.chat.id, item_id, action_type)
            
        else:
            bot.answer_callback_query(call.id, "❌ عمل نامشناخته")
            
    except Exception as e:
        logger.error(f"Error in callback handler: {e}")
        bot.answer_callback_query(call.id, "❌ خطا در پردازش")

def handle_play_music(chat_id: int, item_id: str, source: str):
    """پخش موسیقی"""
    try:
        # دریافت اطلاعات آهنگ
        success, data = call_api({
            'action': 'get',
            'type': 'music',
            'id': item_id
        })
        
        if not success:
            bot.send_message(chat_id, f"❌ خطا در دریافت اطلاعات آهنگ: {data}")
            return
        
        song_info = data.get('result') or data.get('data') or data
        if not song_info:
            bot.send_message(chat_id, "❌ اطلاعات آهنگ پیدا نشد.")
            return
        
        # یافتن لینک پخش
        play_url = find_download_url(song_info)
        if not play_url:
            bot.send_message(chat_id, "❌ لینک پخش پیدا نشد.")
            return
        
        title = song_info.get('title') or song_info.get('name') or "نامشخص"
        artist = song_info.get('artist') or song_info.get('singer') or ""
        
        # ارسال لینک (بهینه شده برای Render)
        send_audio_or_link(chat_id, play_url, title, artist)
        
    except Exception as e:
        logger.error(f"Error in play music: {e}")
        bot.send_message(chat_id, f"❌ خطا در پخش موسیقی: {str(e)}")

def handle_download_music(chat_id: int, item_id: str, source: str):
    """دانلود موسیقی"""
    # در حال حاضر مشابه پخش است
    handle_play_music(chat_id, item_id, source)

# ---------- هندلر لینک‌های Radio Javan ----------

@bot.message_handler(func=lambda message: 'radiojavan.com' in message.text.lower())
def handle_radiojavan_link(message):
    """پردازش لینک‌های Radio Javan"""
    try:
        url = message.text.strip()
        
        # استخراج نوع و شناسه از لینک
        if '/mp3/' in url:
            # لینک آهنگ
            mp3_id = url.split('/mp3/')[1].split('/')[0]
            processing_msg = bot.reply_to(message, "🔍 در حال پردازش لینک آهنگ برای بهنوش...")
            
            success, data = call_api({
                'action': 'get',
                'type': 'music',
                'id': mp3_id
            })
            
        elif '/artist/' in url:
            # لینک آرتیست
            artist_name = url.split('/artist/')[1].split('/')[0]
            processing_msg = bot.reply_to(message, f"👤 در حال دریافت اطلاعات آرتیست برای بهنوش...")
            
            success, data = call_api({
                'action': 'profile',
                'artist': artist_name
            })
            
        else:
            bot.reply_to(message, "❌ نوع لینک شناخته شده نیست.")
            return
        
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if not success:
            bot.reply_to(message, f"❌ خطا در پردازش لینک: {data}")
            return
        
        # پردازش اطلاعات دریافت شده
        info = data.get('result') or data.get('data') or data
        if not info:
            bot.reply_to(message, "❌ اطلاعاتی از لینک استخراج نشد.")
            return
        
        # نمایش اطلاعات
        if '/mp3/' in url:
            # نمایش اطلاعات آهنگ
            info_text = format_song_info(info)
            item_id = str(info.get('id') or info.get('mp3_id') or mp3_id)
            
            bot.reply_to(
                message, 
                f"🔗 <b>آهنگ از لینک برای بهنوش:</b>\n\n{info_text}",
                reply_markup=create_inline_keyboard(item_id, 'link', info)
            )
        else:
            # نمایش اطلاعات آرتیست
            name = info.get('name') or artist_name
            bio = info.get('bio') or "اطلاعاتی موجود نیست"
            
            profile_text = f"🔗 <b>آرتیست از لینک:</b>\n\n👤 <b>{name}</b>\n📝 {bio}\n💝 برای بهنوش عزیز"
            bot.reply_to(message, profile_text)
            
    except Exception as e:
        logger.error(f"Error in radiojavan link handler: {e}")
        bot.reply_to(message, f"❌ خطا در پردازش لینک: {str(e)}")

# ---------- هندلر پیام‌های عمومی ----------

@bot.message_handler(func=lambda message: True)
def handle_general_message(message):
    """پردازش پیام‌های عمومی به عنوان جستجو"""
    if message.text.startswith('/'):
        bot.reply_to(message, "❌ دستور نامشناخته. از /start برای مشاهده راهنما استفاده کنید.")
        return
    
    # استفاده از متن پیام به عنوان جستجو
    query = message.text.strip()
    if len(query) < 2:
        bot.reply_to(message, "🔍 برای جستجو، حداقل ۲ کاراکتر وارد کنید.")
        return
    
    try:
        processing_msg = bot.reply_to(message, f"🔍 جستجو برای '<b>{query}</b>' برای بهنوش...")
        
        success, data = call_api({
            'action': 'search',
            'type': 'music',
            'query': query
        })
        
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if not success:
            bot.reply_to(message, f"❌ خطا در جستجو: {data}")
            return
        
        items = extract_items_list(data)
        if not items:
            bot.reply_to(message, f"❌ هیچ نتیجه‌ای برای '<b>{query}</b>' پیدا نشد.")
            return
        
        bot.reply_to(message, f"🔍 <b>{len(items)} نتیجه برای '{query}':</b>")
        
        for item in items[:3]:  # محدود به ۳ نتیجه برای پیام‌های عمومی
            try:
                info_text = format_song_info(item)
                item_id = str(item.get('id') or item.get('mp3_id') or random.randint(1000, 9999))
                
                bot.send_message(
                    message.chat.id,
                    info_text,
                    reply_markup=create_inline_keyboard(item_id, 'general', item)
                )
                time.sleep(0.3)
                
            except Exception as e:
                logger.error(f"Error sending general search result: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in general message handler: {e}")
        bot.reply_to(message, f"❌ خطای داخلی: {str(e)}")

# ---------- تابع Keep-Alive ----------
def keep_alive():
    """تابع برای نگه داشتن سرویس زنده در Render"""
    while True:
        try:
            time.sleep(840)  # هر 14 دقیقه
            if WEBHOOK_URL:
                requests.get(f"{WEBHOOK_URL}/health", timeout=10)
                logger.info("Keep-alive ping sent")
        except Exception as e:
            logger.error(f"Keep-alive error: {e}")

# ---------- تابع اصلی ----------
def main():
    logger.info("🚀 Behimelobot starting on Render for Behnosh...")
    
    try:
        # تست اولیه API
        success, data = call_api({'action': 'search', 'type': 'music', 'query': 'test'})
        if success:
            logger.info("✅ API connection successful")
        else:
            logger.warning(f"⚠️ API test failed: {data}")
        
        # شروع keep-alive در thread جداگانه
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
        
        if WEBHOOK_URL:
            # حالت Webhook (توصیه شده برای Render)
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
            logger.info(f"Webhook set to: {WEBHOOK_URL}/webhook")
            
            # شروع Flask server
            app.run(host='0.0.0.0', port=PORT, debug=False)
        else:
            # حالت Polling (برای تست محلی)
            logger.info("Starting in polling mode...")
            bot.remove_webhook()
            bot.polling(none_stop=True, interval=1, timeout=20)
            
    except KeyboardInterrupt:
        logger.info("🛑 Behimelobot stopped by user")
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
    finally:
        logger.info("👋 Behimelobot terminated - Goodbye Behnosh!")

if __name__ == "__main__":
    main()
