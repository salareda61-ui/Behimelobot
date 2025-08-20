#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
behimelobot - ربات موسیقی کامل برای Radio Javan
ساخته شده برای دختری زیبا راپونزل ایرانی بهنوش
نسخه کامل با Mini App تعاملی واقعی + پشتیبانی از Secret Files
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

# ---------- بارگذاری Secret Files ----------
def load_env_from_secrets():
    """خواندن متغیرهای محیطی از Secret File"""
    try:
        with open('/etc/secrets/.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        logging.info("✅ Secret file loaded successfully")
    except FileNotFoundError:
        logging.warning("⚠️ Secret file not found, using environment variables")
    except Exception as e:
        logging.error(f"❌ Error loading secret file: {e}")

# بارگذاری متغیرها
load_env_from_secrets()

# ---------- تنظیمات ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ACCESS_KEY = os.environ.get("ACCESS_KEY")
API_BASE = os.environ.get("API_BASE", "https://api.ineo-team.ir/rj.php")
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

def safe_api_call(action: str, params: Dict[str, Any] = None) -> Tuple[bool, Any]:
    """API call صحیح مطابق با کد PHP"""
    try:
        if params is None:
            params = {}
        
        post_data = {
            'accessKey': ACCESS_KEY,
            'action': action
        }
        post_data.update(params)
        
        logger.info(f"API Request - Action: {action}, Params: {params}")
        time.sleep(random.uniform(0.5, 1.0))
        
        response = requests.post(
            API_BASE,
            data=post_data,
            timeout=15,
            headers={
                'User-Agent': 'Behimelobot/1.0',
                'Accept': 'application/json'
            }
        )
        
        response.raise_for_status()
        
        try:
            data = response.json()
        except json.JSONDecodeError:
            return False, "پاسخ غیر JSON از سرور"
        
        if isinstance(data, dict):
            if data.get('status_code') == 200:
                return True, data.get('result', data)
            elif 'error' in data and data['error']:
                return False, data.get('message', 'خطای نامشخص')
            elif 'result' in data:
                return True, data['result']
        
        return True, data
        
    except Exception as e:
        logger.error(f"API call error: {e}")
        return False, f"خطا: {str(e)}"

def extract_songs_safe(api_response: Any) -> List[Dict[str, Any]]:
    """استخراج امن آهنگ‌ها از پاسخ API"""
    if not api_response:
        return []
    
    songs = []
    
    try:
        if isinstance(api_response, list):
            songs = api_response[:5]
        elif isinstance(api_response, dict):
            possible_keys = ['music', 'tracks', 'items', 'data', 'list', 'songs', 'results']
            
            for key in possible_keys:
                if key in api_response:
                    items = api_response[key]
                    if isinstance(items, list):
                        songs = items[:5]
                        break
                    elif isinstance(items, dict):
                        songs = [items]
                        break
            
            if not songs and api_response.get('title'):
                songs = [api_response]
        
        valid_songs = []
        for song in songs:
            if isinstance(song, dict) and (song.get('title') or song.get('name')):
                valid_songs.append(song)
        
        return valid_songs
        
    except Exception as e:
        logger.error(f"Error extracting songs: {e}")
        return []

def create_mock_songs(query: str) -> List[Dict[str, Any]]:
    """ایجاد آهنگ‌های نمونه"""
    return [
        {
            "id": f"mock_{random.randint(1000, 9999)}",
            "title": f"آهنگ مرتبط با {query}",
            "artist": "آرتیست نمونه",
            "album": "آلبوم نمونه",
            "duration": "03:45",
            "hq": "https://example.com/song1.mp3"
        },
        {
            "id": f"mock_{random.randint(1000, 9999)}", 
            "title": "آهنگ زیبای ایرانی",
            "artist": "خواننده محبوب", 
            "duration": "04:12",
            "hq": "https://example.com/song2.mp3"
        }
    ]

# ---------- Flask Routes ----------

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Behimelobot - ربات موسیقی</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Vazir', Tahoma, Arial, sans-serif;
                background: linear-gradient(135deg, #1a0033 0%, #ff6ec0 100%);
                color: white; text-align: center; min-height: 100vh; padding: 20px;
            }
            .container { max-width: 600px; margin: 50px auto; padding: 20px; }
            h1 {
                font-size: 3em; margin-bottom: 20px;
                background: linear-gradient(45deg, #ff6ec0, #d85cac, #b34b98);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                animation: glow 3s ease-in-out infinite alternate;
            }
            @keyframes glow {
                from { text-shadow: 0 0 10px rgba(255, 110, 192, 0.5); }
                to { text-shadow: 0 0 20px rgba(255, 110, 192, 0.8); }
            }
            .status {
                background: rgba(26, 0, 51, 0.8); padding: 25px; border-radius: 20px;
                margin: 30px 0; backdrop-filter: blur(15px);
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎵 Behimelobot</h1>
            <p>💝 ربات موسیقی ساخته شده برای دختری زیبا راپونزل ایرانی بهنوش</p>
            <div class="status">
                <h3>✅ ربات با موفقیت روی Render در حال اجرا است</h3>
                <p>🔧 نسخه کامل با Mini App تعاملی واقعی</p>
                <p>🔐 Secret Files پشتیبانی می‌شود</p>
                <p>🚀 آماده خدمت‌رسانی</p>
            </div>
            <p>🔗 با عشق برای بهنوش ❤️</p>
        </div>
    </body>
    </html>
    """

@app.route('/webapp')
def webapp():
    """Mini App تعاملی واقعی که مستقیماً جستجو می‌کند"""
    return """
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Behimelobot Mini App</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Vazir', Tahoma, Arial, sans-serif;
                background: linear-gradient(135deg, 
                    #0d001a 0%, #1a0033 20%, #2d1b4e 40%, #4a1c5c 60%,
                    #6b2c70 80%, #ff6ec0 100%
                );
                background-size: 400% 400%;
                animation: gradientWave 15s ease infinite;
                margin: 0; padding: 20px; color: white; text-align: center;
                min-height: 100vh; position: relative;
            }
            @keyframes gradientWave {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
            .container { max-width: 400px; margin: 0 auto; position: relative; z-index: 1; }
            h1 {
                font-size: 2.5em; margin-bottom: 20px;
                background: linear-gradient(45deg, #ff6ec0, #d85cac, #b34b98, #8e3a84);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                animation: glow 3s ease-in-out infinite alternate;
            }
            @keyframes glow {
                from { 
                    text-shadow: 0 0 15px rgba(255, 110, 192, 0.6);
                    filter: drop-shadow(0 0 10px rgba(255, 110, 192, 0.3));
                }
                to { 
                    text-shadow: 0 0 25px rgba(255, 110, 192, 0.9);
                    filter: drop-shadow(0 0 15px rgba(255, 110, 192, 0.5));
                }
            }
            .search-section {
                background: linear-gradient(135deg, 
                    rgba(26, 0, 51, 0.8) 0%, rgba(45, 27, 78, 0.6) 50%, rgba(74, 28, 92, 0.4) 100%
                );
                padding: 30px; border-radius: 25px; margin: 25px 0;
                backdrop-filter: blur(15px); border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
            }
            .search-box {
                width: 90%; padding: 18px 25px; border: none; border-radius: 30px;
                font-size: 16px; margin: 20px 0; text-align: center;
                background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(240, 240, 255, 0.9) 100%);
                color: #2d1b4e; box-shadow: 0 5px 20px rgba(0,0,0,0.3);
                transition: all 0.3s ease; font-weight: 500;
            }
            .search-box:focus {
                outline: none; transform: translateY(-2px) scale(1.02);
                box-shadow: 0 8px 25px rgba(255, 110, 192, 0.3);
                border: 2px solid rgba(255, 110, 192, 0.5);
            }
            .search-box::placeholder { color: #6b2c70; opacity: 0.7; }
            .btn {
                background: linear-gradient(135deg, #ff6ec0 0%, #d85cac 25%, #b34b98 50%, #8e3a84 75%, #6b2c70 100%);
                color: white; border: none; padding: 18px 35px; border-radius: 30px;
                font-size: 16px; font-weight: 600; margin: 12px; cursor: pointer; width: 85%;
                box-shadow: 0 6px 20px rgba(0,0,0,0.3), 0 3px 10px rgba(255, 110, 192, 0.2);
                transition: all 0.3s ease; position: relative; overflow: hidden;
            }
            .btn:hover {
                transform: translateY(-3px) scale(1.03);
                box-shadow: 0 10px 30px rgba(255, 110, 192, 0.4), 0 5px 15px rgba(0,0,0,0.3);
            }
            .result {
                background: linear-gradient(135deg, 
                    rgba(26, 0, 51, 0.9) 0%, rgba(45, 27, 78, 0.7) 50%, rgba(74, 28, 92, 0.5) 100%
                );
                padding: 25px; margin: 20px 0; border-radius: 20px; backdrop-filter: blur(15px);
                border: 1px solid rgba(255, 255, 255, 0.15); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
                animation: slideIn 0.5s ease-out; text-align: right;
            }
            @keyframes slideIn {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .song-item {
                background: linear-gradient(135deg, rgba(74, 28, 92, 0.6) 0%, rgba(107, 44, 112, 0.4) 100%);
                padding: 15px; margin: 10px 0; border-radius: 15px;
                border: 1px solid rgba(255, 110, 192, 0.2); cursor: pointer;
                transition: all 0.3s ease;
            }
            .song-item:hover {
                transform: translateY(-2px); box-shadow: 0 5px 15px rgba(255, 110, 192, 0.3);
                border-color: rgba(255, 110, 192, 0.5);
            }
            .song-title { font-weight: bold; font-size: 1.1em; margin-bottom: 5px; color: #ff6ec0; }
            .song-artist { font-size: 0.9em; opacity: 0.8; }
            .loading {
                display: inline-block; width: 20px; height: 20px;
                border: 3px solid rgba(255, 110, 192, 0.3);
                border-radius: 50%; border-top-color: #ff6ec0;
                animation: spin 1s ease-in-out infinite;
            }
            @keyframes spin { to { transform: rotate(360deg); } }
            .hidden { display: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎵 Behimelobot</h1>
            <p style="font-size: 1.1em; margin-bottom: 30px; opacity: 0.9;">💝 Mini App تعاملی برای بهنوش عزیز</p>
            
            <div class="search-section">
                <input type="text" id="searchInput" class="search-box" 
                       placeholder="🔍 نام آهنگ یا آرتیست..." 
                       onkeypress="handleEnter(event)">
                
                <button class="btn" onclick="searchMusic()">
                    <span id="searchBtnText">🔍 جستجو آهنگ</span>
                    <span id="searchBtnLoading" class="loading hidden"></span>
                </button>
                <button class="btn" onclick="getNewMusic()">
                    <span id="newBtnText">🆕 آهنگ‌های جدید</span>
                    <span id="newBtnLoading" class="loading hidden"></span>
                </button>
            </div>
            
            <div id="result"></div>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.ready();
            tg.expand();

            function handleEnter(event) {
                if (event.key === 'Enter') {
                    searchMusic();
                }
            }

            function showLoading(btnId) {
                document.getElementById(btnId + 'Text').classList.add('hidden');
                document.getElementById(btnId + 'Loading').classList.remove('hidden');
            }

            function hideLoading(btnId) {
                document.getElementById(btnId + 'Text').classList.remove('hidden');
                document.getElementById(btnId + 'Loading').classList.add('hidden');
            }

            async function searchMusic() {
                const query = document.getElementById('searchInput').value.trim();
                if (!query) {
                    tg.showAlert('لطفاً نام آهنگ را وارد کنید');
                    return;
                }

                showLoading('searchBtn');
                
                try {
                    const response = await fetch('/api/search', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query: query })
                    });

                    const data = await response.json();
                    
                    if (data.success && data.songs && data.songs.length > 0) {
                        displaySongs(data.songs, `🔍 نتایج جستجو برای "${query}"`);
                    } else {
                        showResult(`❌ هیچ آهنگی برای "${query}" پیدا نشد.<br><br>💡 نکته: ${data.message || 'لطفاً کلمات دیگری امتحان کنید'}`);
                    }
                } catch (error) {
                    showResult('❌ خطا در جستجو. لطفاً دوباره تلاش کنید.');
                    console.error('Search error:', error);
                } finally {
                    hideLoading('searchBtn');
                }
            }

            async function getNewMusic() {
                showLoading('newBtn');
                
                try {
                    const response = await fetch('/api/new', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });

                    const data = await response.json();
                    
                    if (data.success && data.songs && data.songs.length > 0) {
                        displaySongs(data.songs, '🆕 آهنگ‌های جدید');
                    } else {
                        showResult('❌ خطا در دریافت آهنگ‌های جدید.');
                    }
                } catch (error) {
                    showResult('❌ خطا در دریافت آهنگ‌های جدید.');
                    console.error('New music error:', error);
                } finally {
                    hideLoading('newBtn');
                }
            }

            function displaySongs(songs, title) {
                let html = `<h3 style="color: #ff6ec0; margin-bottom: 15px;">${title}</h3>`;
                
                songs.forEach((song, index) => {
                    const songTitle = song.title || song.name || 'نامشخص';
                    const songArtist = song.artist || song.singer || '';
                    const songDuration = song.duration || '';
                    
                    html += `
                        <div class="song-item" onclick="playSong(${index}, '${songTitle}', '${song.hq || song.url || '#'}')">
                            <div class="song-title">🎵 ${songTitle}</div>
                            <div class="song-artist">👤 ${songArtist}</div>
                            ${songDuration ? `<div style="font-size: 0.8em; opacity: 0.7; margin-top: 5px;">⏱ ${songDuration}</div>` : ''}
                        </div>
                    `;
                });

                showResult(html);
            }

            function playSong(index, title, url) {
                if (url && url !== '#' && url !== 'https://example.com/song1.mp3' && url !== 'https://example.com/song2.mp3') {
                    tg.showConfirm(`آیا می‌خواهید "${title}" را پخش کنید?`, (confirmed) => {
                        if (confirmed) {
                            window.open(url, '_blank');
                        }
                    });
                } else {
                    tg.showAlert(`💝 عزیز بهنوش!\\n\\n🎵 "${title}"\\n\\n🔧 این یک آهنگ نمونه است\\n❤️ برای دسترسی به آهنگ‌های واقعی، API باید فعال باشد`);
                }
            }

            function showResult(message) {
                document.getElementById('result').innerHTML = `<div class="result">${message}</div>`;
            }

            document.addEventListener('DOMContentLoaded', function() {
                if (tg.themeParams) {
                    document.body.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color || '#1a0033');
                    document.body.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color || '#ffffff');
                    document.body.style.setProperty('--tg-theme-button-color', tg.themeParams.button_color || '#ff6ec0');
                }

                showResult(`
                    <h3 style="color: #ff6ec0;">🌟 خوش آمدی به Mini App بهیملوبات!</h3>
                    <p>🎵 حالا می‌تونی مستقیماً از اینجا آهنگ جستجو کنی</p>
                    <p>💡 فقط کافیه نام آهنگ یا آرتیست رو بنویسی و دکمه جستجو رو بزنی</p>
                    <p style="margin-top: 15px;">💝 با عشق برای بهنوش ❤️</p>
                `);
            });
        </script>
    </body>
    </html>
    """

@app.route('/api/search', methods=['POST'])
def api_search():
    """API endpoint برای جستجو از مینی اپ"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'success': False, 'message': 'کوئری خالی است'})
        
        success, api_data = safe_api_call("search", {"query": query})
        
        if success:
            songs = extract_songs_safe(api_data)
            if songs:
                return jsonify({
                    'success': True,
                    'songs': songs,
                    'message': f'{len(songs)} آهنگ پیدا شد'
                })
            else:
                mock_songs = create_mock_songs(query)
                return jsonify({
                    'success': True,
                    'songs': mock_songs,
                    'message': 'نتایج نمونه (API غیرفعال)'
                })
        else:
            mock_songs = create_mock_songs(query)
            return jsonify({
                'success': True,
                'songs': mock_songs,
                'message': f'خطا در API: {api_data}'
            })
            
    except Exception as e:
        logger.error(f"API search error: {e}")
        return jsonify({'success': False, 'message': 'خطای سرور'})

@app.route('/api/new', methods=['POST'])
def api_new():
    """API endpoint برای آهنگ‌های جدید از مینی اپ"""
    try:
        success, api_data = safe_api_call("new", {"type": "music"})
        
        if success:
            songs = extract_songs_safe(api_data)
            if songs:
                return jsonify({
                    'success': True,
                    'songs': songs,
                    'message': f'{len(songs)} آهنگ جدید'
                })
            else:
                mock_songs = create_mock_songs("جدیدترین")
                return jsonify({
                    'success': True,
                    'songs': mock_songs,
                    'message': 'آهنگ‌های نمونه (API غیرفعال)'
                })
        else:
            mock_songs = create_mock_songs("جدیدترین")
            return jsonify({
                'success': True,
                'songs': mock_songs,
                'message': f'خطا در API: {api_data}'
            })
            
    except Exception as e:
        logger.error(f"API new error: {e}")
        return jsonify({'success': False, 'message': 'خطای سرور'})

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
        "api": "Radio Javan API v4",
        "webapp": "Interactive Mini App",
        "secret_files": "Supported",
        "timestamp": time.time()
    }), 200

# ---------- Bot Handlers ----------

@bot.message_handler(commands=['start'])
def start_handler(message):
    try:
        welcome_text = (
            "🎵 سلام! من Behimelobot هستم\n"
            "💝 ربات موسیقی ساخته شده برای دختری زیبا راپونزل ایرانی بهنوش\n\n"
            "🔧 <b>نسخه کامل با Mini App تعاملی واقعی</b>\n\n"
            "📋 <b>دستورات موجود:</b>\n"
            "🔍 /search [نام آهنگ] - جستجو آهنگ\n"
            "🆕 /new - آهنگ‌های جدید\n"
            "👤 /artist [نام آرتیست] - آهنگ‌های آرتیست\n"
            "📊 /status - وضعیت ربات\n\n"
            "💡 <b>راهنما:</b>\n"
            "• می‌توانید مستقیماً نام آهنگ بنویسید\n"
            "• از Mini App تعاملی برای جستجو استفاده کنید\n"
            "• حالا مینی اپ کاملاً تعاملی است!\n\n"
            "🔗 با عشق برای بهنوش ❤️"
        )
        
        keyboard = InlineKeyboardMarkup()
        
        if WEBHOOK_URL:
            keyboard.add(InlineKeyboardButton("🎵 باز کردن Mini App تعاملی", url=f"{WEBHOOK_URL}/webapp"))
        
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
        query = message.text.replace('/search', '').strip()
        if not query:
            bot.reply_to(
                message, 
                "🔍 لطفاً نام آهنگ را وارد کنید\n\n"
                "📝 <b>مثال:</b> <code>/search محسن یگانه</code>"
            )
            return
        
        processing_msg = bot.reply_to(message, "🔍 در حال جستجو برای بهنوش...")
        
        success, data = safe_api_call("search", {"query": query})
        
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if success:
            songs = extract_songs_safe(data)
            if not songs:
                songs = create_mock_songs(query)
                bot.reply_to(message, f"❌ هیچ آهنگی برای '<b>{query}</b>' پیدا نشد\n\n🎵 <b>نتایج نمونه:</b>")
            else:
                bot.reply_to(message, f"✅ <b>{len(songs)} آهنگ پیدا شد برای '{query}':</b>")
        else:
            songs = create_mock_songs(query)
            bot.reply_to(message, f"⚠️ <b>خطا در API:</b> {data}\n\n🎵 <b>نتایج نمونه:</b>")
        
        for song in songs:
            try:
                title = song.get('title', 'نامشخص')
                artist = song.get('artist', '')
                duration = song.get('duration', '')
                
                song_info = f"🎵 <b>{title}</b>"
                if artist:
                    song_info += f"\n👤 آرتیست: {artist}"
                if duration:
                    song_info += f"\n⏱ مدت: {duration}"
                
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🎵 پخش", callback_data=f"play_{song.get('id', 'mock')}"))
                
                bot.send_message(message.chat.id, song_info, reply_markup=keyboard)
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error sending song result: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in search handler: {e}")
        bot.reply_to(message, f"❌ خطای داخلی: {str(e)}")

@bot.message_handler(commands=['new'])
def new_handler(message):
    try:
        processing_msg = bot.reply_to(message, "🆕 در حال دریافت آهنگ‌های جدید...")
        
        success, data = safe_api_call("new", {"type": "music"})
        
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if success:
            songs = extract_songs_safe(data)
            if not songs:
                songs = create_mock_songs("جدیدترین")
                bot.reply_to(message, "❌ هیچ آهنگ جدیدی پیدا نشد\n\n🆕 <b>آهنگ‌های نمونه:</b>")
            else:
                bot.reply_to(message, f"🆕 <b>{len(songs)} آهنگ جدید:</b>")
        else:
            songs = create_mock_songs("جدیدترین")
            bot.reply_to(message, f"⚠️ <b>خطا در API:</b> {data}\n\n🆕 <b>آهنگ‌های نمونه:</b>")
        
        for song in songs:
            try:
                title = song.get('title', 'نامشخص')
                artist = song.get('artist', '')
                
                song_info = f"🎵 <b>{title}</b>"
                if artist:
                    song_info += f"\n👤 آرتیست: {artist}"
                
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🎵 پخش", callback_data=f"play_{song.get('id', 'mock')}"))
                
                bot.send_message(message.chat.id, song_info, reply_markup=keyboard)
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
                "📝 <b>مثال:</b> <code>/artist محسن یگانه</code>"
            )
            return
        
        processing_msg = bot.reply_to(message, f"👤 در حال جستجو آهنگ‌های {artist}...")
        
        success, data = safe_api_call("artist", {"artist": artist})
        
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if success:
            songs = extract_songs_safe(data)
            if not songs:
                songs = create_mock_songs(f"آرتیست {artist}")
                bot.reply_to(message, f"❌ هیچ آهنگی برای آرتیست '<b>{artist}</b>' پیدا نشد\n\n🎵 <b>نتایج نمونه:</b>")
            else:
                bot.reply_to(message, f"✅ <b>{len(songs)} آهنگ پیدا شد برای آرتیست '{artist}':</b>")
        else:
            songs = create_mock_songs(f"آرتیست {artist}")
            bot.reply_to(message, f"⚠️ <b>خطا در API:</b> {data}\n\n🎵 <b>نتایج نمونه:</b>")
        
        for song in songs:
            try:
                title = song.get('title', 'نامشخص')
                song_artist = song.get('artist', artist)
                duration = song.get('duration', '')
                
                song_info = f"🎵 <b>{title}</b>"
                if song_artist:
                    song_info += f"\n👤 آرتیست: {song_artist}"
                if duration:
                    song_info += f"\n⏱ مدت: {duration}"
                
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🎵 پخش", callback_data=f"play_{song.get('id', 'mock')}"))
                
                bot.send_message(message.chat.id, song_info, reply_markup=keyboard)
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
        success, data = safe_api_call("search", {"query": "test"})
        api_status = "✅ فعال" if success else "❌ خطا"
        
        status_text = (
            f"📊 <b>وضعیت Behimelobot:</b>\n\n"
            f"🤖 ربات: ✅ آنلاین\n"
            f"🌐 Radio Javan API v4: {api_status}\n"
            f"📱 Mini App تعاملی: ✅ فعال\n"
            f"🏠 پلتفرم: Render.com\n"
            f"🔐 Secret Files: ✅ پشتیبانی می‌شود\n"
            f"🔑 ACCESS_KEY: {'✅ تنظیم شده' if ACCESS_KEY else '❌ تنظیم نشده'}\n"
            f"⏰ زمان سرور: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"💝 وضعیت: آماده خدمت به بهنوش"
        )
        
        bot.reply_to(message, status_text)
        
    except Exception as e:
        logger.error(f"Error in status handler: {e}")
        bot.reply_to(message, f"❌ خطا در دریافت وضعیت: {str(e)}")

@bot.message_handler(commands=['help'])
def help_handler(message):
    try:
        help_text = (
            "📖 <b>راهنمای کامل Behimelobot:</b>\n\n"
            "🔍 <b>جستجو آهنگ:</b>\n"
            "• <code>/search [نام آهنگ]</code>\n"
            "• مثال: <code>/search دل دیوونه</code>\n\n"
            "👤 <b>جستجو آرتیست:</b>\n"
            "• <code>/artist [نام آرتیست]</code>\n"
            "• مثال: <code>/artist محسن یگانه</code>\n\n"
            "🆕 <b>آهنگ‌های جدید:</b>\n"
            "• <code>/new</code>\n\n"
            "📊 <b>وضعیت ربات:</b>\n"
            "• <code>/status</code>\n\n"
            "📱 <b>Mini App تعاملی:</b>\n"
            "• از دکمه 'Mini App' استفاده کنید\n"
            "• جستجو مستقیم بدون دستور\n\n"
            "💡 <b>نکات:</b>\n"
            "• می‌توانید مستقیماً نام آهنگ بنویسید\n"
            "• از کلمات فارسی و انگلیسی استفاده کنید\n"
            "• برای نتایج بهتر از Mini App استفاده کنید\n\n"
            "💝 با عشق برای بهنوش ❤️"
        )
        
        bot.reply_to(message, help_text)
        
    except Exception as e:
        logger.error(f"Error in help handler: {e}")
        bot.reply_to(message, "❌ خطا در نمایش راهنما")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        if call.data == "quick_new":
            bot.answer_callback_query(call.id, "🆕 در حال دریافت آهنگ‌های جدید...")
            new_handler(call.message)
        elif call.data == "quick_status":
            bot.answer_callback_query(call.id, "📊 بررسی وضعیت...")
            status_handler(call.message)
        elif call.data.startswith("play_"):
            bot.answer_callback_query(call.id, "🎵 برای دسترسی به آهنگ از Mini App استفاده کنید")
            bot.send_message(
                call.message.chat.id,
                "💝 <b>عزیز بهنوش!</b>\n\n"
                "🎵 برای پخش و دانلود آهنگ‌ها از Mini App تعاملی استفاده کن\n"
                "📱 حالا می‌تونی مستقیماً از مینی اپ جستجو کنی!"
            )
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Error in callback handler: {e}")
        bot.answer_callback_query(call.id, "❌ خطا در پردازش")

@bot.message_handler(func=lambda message: True)
def general_handler(message):
    """پردازش پیام‌های عمومی"""
    try:
        if not message.text or message.text.startswith('/'):
            return
        
        query = message.text.strip()
        if len(query) < 2:
            bot.reply_to(message, "🔍 برای جستجو، حداقل ۲ کاراکتر وارد کنید")
            return
        
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
    logger.info("🚀 Starting Behimelobot (Interactive WebApp + Secret Files) for Behnosh...")
    
    try:
        if not TELEGRAM_TOKEN:
            logger.error("❌ TELEGRAM_TOKEN not set!")
            return
        
        if not ACCESS_KEY:
            logger.error("❌ ACCESS_KEY not set!")
        else:
            logger.info(f"✅ ACCESS_KEY: {ACCESS_KEY[:15]}...")
        
        logger.info(f"✅ API URL: {API_BASE}")
        logger.info(f"✅ Port: {PORT}")
        logger.info(f"✅ Webhook URL: {WEBHOOK_URL or 'Not set (polling mode)'}")
        
        # تست اولیه API
        success, data = safe_api_call("search", {"query": "test"})
        
        if success:
            logger.info("✅ API connection successful")
        else:
            logger.warning(f"⚠️ API test failed: {data}")
            logger.info("🔧 Bot will work with mock data")
        
        # شروع keep-alive thread
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
        logger.info("✅ Keep-alive thread started")
        
        if WEBHOOK_URL:
            # حالت Webhook برای Render
            try:
                bot.remove_webhook()
                time.sleep(1)
                bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
                logger.info(f"✅ Webhook set: {WEBHOOK_URL}/webhook")
            except Exception as e:
                logger.error(f"❌ Webhook setup failed: {e}")
            
            # شروع Flask server
            logger.info("🌐 Starting Flask server with Interactive WebApp...")
            app.run(host='0.0.0.0', port=PORT, debug=False)
        else:
            # حالت Polling برای تست محلی
            logger.info("🔄 Starting in polling mode...")
            bot.remove_webhook()
            bot.polling(none_stop=True, interval=1, timeout=20)
            
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        raise
    finally:
        logger.info("👋 Behimelobot terminated - Goodbye Behnosh!")

if __name__ == "__main__":
    main()
