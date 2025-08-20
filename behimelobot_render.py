#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
behimelobot - ربات موسیقی کامل برای Radio Javan
ساخته شده برای دختری زیبا راپونزل ایرانی بهنوش
نسخه کامل و نهایی با تمام قابلیت‌ها و WebApp بنفش زیبا
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
API_BASE = "https://api.ineo-team.ir/rj.php"
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
        
        # پارامترهای اصلی مطابق PHP
        post_data = {
            'accessKey': ACCESS_KEY,
            'action': action
        }
        
        # اضافه کردن پارامترهای اضافی
        post_data.update(params)
        
        logger.info(f"API Request - Action: {action}, Params: {params}")
        
        # تأخیر برای rate limiting
        time.sleep(random.uniform(0.5, 1.0))
        
        # درخواست POST مطابق PHP
        response = requests.post(
            API_BASE,
            data=post_data,
            timeout=15,
            headers={
                'User-Agent': 'Behimelobot/1.0',
                'Accept': 'application/json'
            }
        )
        
        logger.info(f"API Response Status: {response.status_code}")
        
        # بررسی status code
        response.raise_for_status()
        
        # بررسی content type
        content_type = response.headers.get('content-type', '').lower()
        if 'html' in content_type:
            logger.error("Received HTML instead of JSON")
            return False, "سرور HTML برگرداند به جای JSON"
        
        # پارس JSON
        try:
            data = response.json()
            logger.info(f"API Response Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON Decode Error: {e}")
            logger.error(f"Response Text: {response.text[:500]}")
            return False, "پاسخ غیر JSON از سرور"
        
        # بررسی وضعیت پاسخ مطابق PHP
        if isinstance(data, dict):
            if data.get('status_code') == 200:
                return True, data.get('result', data)
            elif 'error' in data and data['error']:
                error_msg = data.get('message', 'خطای نامشخص')
                logger.error(f"API Error: {error_msg}")
                return False, error_msg
            elif 'result' in data:
                return True, data['result']
        
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
        # اگر مستقیماً یک لیست است
        if isinstance(api_response, list):
            songs = api_response[:5]
        
        # اگر یک دیکشنری است
        elif isinstance(api_response, dict):
            # جستجو در کلیدهای مختلف
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
            
            # اگر هیچ کلید پیدا نشد، خود دیکشنری را بررسی کن
            if not songs and api_response.get('title'):
                songs = [api_response]
        
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
        'hq', 'lq', 'download', 'stream_url', 'url', 'mp3', 'link', 
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

def create_mock_songs(query: str) -> List[Dict[str, Any]]:
    """ایجاد آهنگ‌های نمونه در صورت عدم دسترسی به API"""
    mock_songs = [
        {
            "id": "mock_1",
            "title": f"آهنگ مرتبط با {query}",
            "artist": "آرتیست نمونه",
            "album": "آلبوم نمونه",
            "duration": "03:45"
        },
        {
            "id": "mock_2", 
            "title": "آهنگ زیبای ایرانی",
            "artist": "خواننده محبوب",
            "album": "مجموعه طلایی",
            "duration": "04:12"
        }
    ]
    return mock_songs

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
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Vazir', Tahoma, Arial, sans-serif;
                background: linear-gradient(135deg, 
                    #1a0033 0%,
                    #2d1b4e 15%, 
                    #4a1c5c 30%,
                    #6b2c70 45%,
                    #8e3a84 60%,
                    #b34b98 75%,
                    #d85cac 90%,
                    #ff6ec0 100%
                );
                background-attachment: fixed;
                margin: 0;
                padding: 20px;
                color: white;
                text-align: center;
                min-height: 100vh;
                position: relative;
                overflow-x: hidden;
            }
            
            body::before {
                content: '';
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: radial-gradient(
                    circle at 20% 80%,
                    rgba(0, 0, 0, 0.3) 0%,
                    transparent 50%
                ),
                radial-gradient(
                    circle at 80% 20%,
                    rgba(0, 0, 0, 0.2) 0%,
                    transparent 50%
                ),
                radial-gradient(
                    circle at 40% 40%,
                    rgba(139, 69, 19, 0.1) 0%,
                    transparent 50%
                );
                pointer-events: none;
                z-index: -1;
            }
            
            .container {
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                position: relative;
                z-index: 1;
            }
            
            h1 {
                font-size: 3em;
                margin-bottom: 20px;
                text-shadow: 3px 3px 6px rgba(0,0,0,0.5);
                background: linear-gradient(45deg, #ff6ec0, #d85cac, #b34b98);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                animation: glow 3s ease-in-out infinite alternate;
            }
            
            @keyframes glow {
                from { text-shadow: 0 0 10px rgba(255, 110, 192, 0.5); }
                to { text-shadow: 0 0 20px rgba(255, 110, 192, 0.8), 0 0 30px rgba(216, 92, 172, 0.6); }
            }
            
            p {
                font-size: 1.2em;
                line-height: 1.8;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
            }
            
            .status {
                background: linear-gradient(135deg, 
                    rgba(26, 0, 51, 0.8) 0%,
                    rgba(74, 28, 92, 0.6) 50%,
                    rgba(107, 44, 112, 0.4) 100%
                );
                padding: 25px;
                border-radius: 20px;
                margin: 30px 0;
                backdrop-filter: blur(15px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            }
            
            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 25px;
                margin: 40px 0;
            }
            
            .feature {
                background: linear-gradient(135deg, 
                    rgba(45, 27, 78, 0.7) 0%,
                    rgba(74, 28, 92, 0.5) 50%,
                    rgba(142, 58, 132, 0.3) 100%
                );
                padding: 20px;
                border-radius: 15px;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                transition: all 0.4s ease;
                position: relative;
                overflow: hidden;
            }
            
            .feature::before {
                content: '';
                position: absolute;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: linear-gradient(45deg, 
                    transparent, 
                    rgba(255, 110, 192, 0.1), 
                    transparent
                );
                transform: rotate(-45deg);
                transition: all 0.6s ease;
                opacity: 0;
            }
            
            .feature:hover::before {
                opacity: 1;
                animation: shimmer 1.5s linear infinite;
            }
            
            @keyframes shimmer {
                0% { transform: translateX(-100%) rotate(-45deg); }
                100% { transform: translateX(100%) rotate(-45deg); }
            }
            
            .feature:hover {
                transform: translateY(-8px) scale(1.02);
                box-shadow: 0 15px 40px rgba(255, 110, 192, 0.2);
                border-color: rgba(255, 110, 192, 0.3);
            }
            
            .feature h4 {
                color: #ff6ec0;
                margin-bottom: 15px;
                font-size: 1.3em;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
            }
            
            .footer {
                margin-top: 60px;
                font-size: 0.95em;
                opacity: 0.9;
                background: linear-gradient(135deg, 
                    rgba(26, 0, 51, 0.6) 0%,
                    rgba(45, 27, 78, 0.4) 100%
                );
                padding: 20px;
                border-radius: 15px;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            .heart {
                color: #ff6ec0;
                animation: heartbeat 2s ease-in-out infinite;
                display: inline-block;
            }
            
            @keyframes heartbeat {
                0%, 50%, 100% { transform: scale(1); }
                25%, 75% { transform: scale(1.1); }
            }
            
            .floating {
                animation: float 6s ease-in-out infinite;
            }
            
            @keyframes float {
                0%, 100% { transform: translateY(0px); }
                50% { transform: translateY(-10px); }
            }
            
            @media (max-width: 768px) {
                .container { padding: 15px; margin: 20px auto; }
                h1 { font-size: 2.2em; }
                p { font-size: 1.1em; }
                .features { grid-template-columns: 1fr; gap: 20px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="floating">🎵 Behimelobot</h1>
            <p>💝 ربات موسیقی ساخته شده برای دختری زیبا راپونزل ایرانی بهنوش</p>
            
            <div class="status">
                <h3>✅ ربات با موفقیت روی Render در حال اجرا است</h3>
                <p>🔧 نسخه کامل و نهایی - API صحیح شده</p>
                <p>🚀 آماده خدمت‌رسانی</p>
            </div>
            
            <div class="features">
                <div class="feature">
                    <h4>🔍 جستجو آهنگ</h4>
                    <p>جستجو در میلیون‌ها آهنگ ایرانی با کیفیت بالا</p>
                </div>
                <div class="feature">
                    <h4>🆕 آهنگ‌های جدید</h4>
                    <p>آخرین و جدیدترین آهنگ‌های منتشر شده</p>
                </div>
                <div class="feature">
                    <h4>👤 آهنگ‌های آرتیست</h4>
                    <p>تمام آهنگ‌های مورد علاقه از یک خواننده</p>
                </div>
                <div class="feature">
                    <h4>⬇️ دانلود مستقیم</h4>
                    <p>دانلود آهنگ با کیفیت بالا و سرعت فوق العاده</p>
                </div>
            </div>
            
            <div class="footer">
                <p>🔗 با عشق برای بهنوش <span class="heart">❤️</span></p>
                <p>Powered by Radio Javan API v4</p>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/webapp')
def webapp():
    """Mini App برای جستجو آهنگ با طراحی بنفش زیبا"""
    return """
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Behimelobot Mini App</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Vazir', Tahoma, Arial, sans-serif;
                background: linear-gradient(135deg, 
                    #0d001a 0%,
                    #1a0033 10%,
                    #2d1b4e 20%, 
                    #4a1c5c 30%,
                    #1a0033 40%,
                    #2d1b4e 50%,
                    #4a1c5c 60%,
                    #6b2c70 70%,
                    #4a1c5c 80%,
                    #2d1b4e 90%,
                    #1a0033 100%
                );
                background-size: 400% 400%;
                animation: gradientWave 15s ease infinite;
                margin: 0;
                padding: 20px;
                color: white;
                text-align: center;
                min-height: 100vh;
                position: relative;
                overflow-x: hidden;
            }
            
            @keyframes gradientWave {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
            
            body::before {
                content: '';
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: 
                    radial-gradient(circle at 25% 25%, rgba(0, 0, 0, 0.4) 0%, transparent 50%),
                    radial-gradient(circle at 75% 75%, rgba(0, 0, 0, 0.3) 0%, transparent 50%),
                    radial-gradient(circle at 50% 50%, rgba(139, 69, 19, 0.1) 0%, transparent 70%);
                pointer-events: none;
                z-index: -1;
            }
            
            .container {
                max-width: 400px;
                margin: 0 auto;
                position: relative;
                z-index: 1;
            }
            
            h1 {
                font-size: 2.5em;
                margin-bottom: 20px;
                text-shadow: 3px 3px 6px rgba(0,0,0,0.7);
                background: linear-gradient(45deg, #ff6ec0, #d85cac, #b34b98, #8e3a84);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                animation: glow 3s ease-in-out infinite alternate;
            }
            
            @keyframes glow {
                from { 
                    text-shadow: 0 0 15px rgba(255, 110, 192, 0.6);
                    filter: drop-shadow(0 0 10px rgba(255, 110, 192, 0.3));
                }
                to { 
                    text-shadow: 0 0 25px rgba(255, 110, 192, 0.9), 0 0 35px rgba(216, 92, 172, 0.7);
                    filter: drop-shadow(0 0 15px rgba(255, 110, 192, 0.5));
                }
            }
            
            .subtitle {
                font-size: 1.1em;
                margin-bottom: 30px;
                opacity: 0.9;
                text-shadow: 1px 1px 3px rgba(0,0,0,0.6);
            }
            
            .search-section {
                background: linear-gradient(135deg, 
                    rgba(26, 0, 51, 0.8) 0%,
                    rgba(45, 27, 78, 0.6) 50%,
                    rgba(74, 28, 92, 0.4) 100%
                );
                padding: 30px;
                border-radius: 25px;
                margin: 25px 0;
                backdrop-filter: blur(15px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
                position: relative;
                overflow: hidden;
            }
            
            .search-section::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(45deg, 
                    transparent, 
                    rgba(255, 110, 192, 0.05), 
                    transparent
                );
                border-radius: 25px;
                pointer-events: none;
            }
            
            .search-box {
                width: 90%;
                padding: 18px 25px;
                border: none;
                border-radius: 30px;
                font-size: 16px;
                margin: 20px 0;
                text-align: center;
                background: linear-gradient(135deg, 
                    rgba(255, 255, 255, 0.95) 0%,
                    rgba(240, 240, 255, 0.9) 100%
                );
                color: #2d1b4e;
                box-shadow: 
                    0 5px 20px rgba(0,0,0,0.3),
                    inset 0 1px 3px rgba(0,0,0,0.1);
                transition: all 0.3s ease;
                font-weight: 500;
                position: relative;
                z-index: 2;
            }
            
            .search-box:focus {
                outline: none;
                transform: translateY(-2px) scale(1.02);
                box-shadow: 
                    0 8px 25px rgba(255, 110, 192, 0.3),
                    inset 0 1px 3px rgba(0,0,0,0.1);
                border: 2px solid rgba(255, 110, 192, 0.5);
            }
            
            .search-box::placeholder {
                color: #6b2c70;
                opacity: 0.7;
            }
            
            .btn {
                background: linear-gradient(135deg, 
                    #ff6ec0 0%, 
                    #d85cac 25%,
                    #b34b98 50%,
                    #8e3a84 75%,
                    #6b2c70 100%
                );
                color: white;
                border: none;
                padding: 18px 35px;
                border-radius: 30px;
                font-size: 16px;
                font-weight: 600;
                margin: 12px;
                cursor: pointer;
                width: 85%;
                box-shadow: 
                    0 6px 20px rgba(0,0,0,0.3),
                    0 3px 10px rgba(255, 110, 192, 0.2);
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
                z-index: 2;
            }
            
            .btn::before {
                content: '';
                position: absolute;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: linear-gradient(45deg, 
                    transparent, 
                    rgba(255, 255, 255, 0.1), 
                    transparent
                );
                transform: rotate(-45deg);
                transition: all 0.6s ease;
                opacity: 0;
            }
            
            .btn:hover::before {
                opacity: 1;
                animation: shimmer 0.8s linear infinite;
            }
            
            @keyframes shimmer {
                0% { transform: translateX(-100%) rotate(-45deg); }
                100% { transform: translateX(100%) rotate(-45deg); }
            }
            
            .btn:hover {
                transform: translateY(-3px) scale(1.03);
                box-shadow: 
                    0 10px 30px rgba(255, 110, 192, 0.4),
                    0 5px 15px rgba(0,0,0,0.3);
            }
            
            .btn:active {
                transform: translateY(-1px) scale(1.01);
                box-shadow: 
                    0 5px 15px rgba(255, 110, 192, 0.3),
                    0 2px 8px rgba(0,0,0,0.3);
            }
            
            .result {
                background: linear-gradient(135deg, 
                    rgba(26, 0, 51, 0.9) 0%,
                    rgba(45, 27, 78, 0.7) 50%,
                    rgba(74, 28, 92, 0.5) 100%
                );
                padding: 25px;
                margin: 20px 0;
                border-radius: 20px;
                backdrop-filter: blur(15px);
                border: 1px solid rgba(255, 255, 255, 0.15);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
                animation: slideIn 0.5s ease-out;
                position: relative;
                overflow: hidden;
            }
            
            .result::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(45deg, 
                    transparent, 
                    rgba(0, 0, 0, 0.1), 
                    transparent
                );
                border-radius: 20px;
                pointer-events: none;
            }
            
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .result code {
                background: rgba(255, 110, 192, 0.2);
                padding: 8px 12px;
                border-radius: 8px;
                color: #ff6ec0;
                font-weight: bold;
                border: 1px solid rgba(255, 110, 192, 0.3);
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
                position: relative;
                z-index: 2;
            }
            
            .heart {
                color: #ff6ec0;
                animation: heartbeat 2s ease-in-out infinite;
                display: inline-block;
            }
            
            @keyframes heartbeat {
                0%, 50%, 100% { transform: scale(1); }
                25%, 75% { transform: scale(1.1); }
            }
            
            /* Floating particles effect */
            .floating-particles {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
                z-index: 0;
            }
            
            .particle {
                position: absolute;
                width: 3px;
                height: 3px;
                background: rgba(255, 110, 192, 0.4);
                border-radius: 50%;
                animation: floatUp 12s infinite linear;
            }
            
            @keyframes floatUp {
                0% {
                    transform: translateY(100vh) translateX(0px) rotate(0deg);
                    opacity: 0;
                }
                10% {
                    opacity: 1;
                }
                90% {
                    opacity: 1;
                }
                100% {
                    transform: translateY(-10vh) translateX(100px) rotate(360deg);
                    opacity: 0;
                }
            }
            
            @media (max-width: 768px) {
                .container { padding: 15px; }
                h1 { font-size: 2em; }
                .search-section { padding: 20px; margin: 15px 0; }
                .search-box { width: 95%; padding: 15px 20px; }
                .btn { width: 90%; padding: 15px 30px; }
            }
        </style>
    </head>
    <body>
        <div class="floating-particles">
            <div class="particle" style="left: 10%; animation-delay: 0s;"></div>
            <div class="particle" style="left: 20%; animation-delay: 2s;"></div>
            <div class="particle" style="left: 30%; animation-delay: 4s;"></div>
            <div class="particle" style="left: 40%; animation-delay: 6s;"></div>
            <div class="particle" style="left: 50%; animation-delay: 8s;"></div>
            <div class="particle" style="left: 60%; animation-delay: 1s;"></div>
            <div class="particle" style="left: 70%; animation-delay: 3s;"></div>
            <div class="particle" style="left: 80%; animation-delay: 5s;"></div>
            <div class="particle" style="left: 90%; animation-delay: 7s;"></div>
        </div>
        
        <div class="container">
            <h1>🎵 Behimelobot</h1>
            <p class="subtitle">💝 Mini App برای بهنوش عزیز</p>
            
            <div class="search-section">
                <input type="text" id="searchInput" class="search-box" 
                       placeholder="🔍 نام آهنگ یا آرتیست..." 
                       onkeypress="handleEnter(event)">
                
                <button class="btn" onclick="searchMusic()">🔍 جستجو آهنگ</button>
                <button class="btn" onclick="getNewMusic()">🆕 آهنگ‌های جدید</button>
                <button class="btn" onclick="showCommands()">📋 دستورات</button>
            </div>
            
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

            function showCommands() {
                showResult(`
                    📋 <strong>دستورات ربات:</strong><br><br>
                    🔍 <code>/search [نام آهنگ]</code> - جستجو آهنگ<br>
                    🆕 <code>/new</code> - آهنگ‌های جدید<br>
                    👤 <code>/artist [نام آرتیست]</code> - آهنگ‌های آرتیست<br>
                    📊 <code>/status</code> - وضعیت ربات<br>
                    🧪 <code>/test</code> - تست API<br><br>
                    💡 می‌توانید مستقیماً نام آهنگ بنویسید<br><br>
                    💝 با عشق برای بهنوش <span class="heart">❤️</span>
                `);
            }

            function showResult(message) {
                document.getElementById('result').innerHTML = `<div class="result">${message}</div>`;
            }

            // Add more floating particles dynamically
            function createParticles() {
                const particlesContainer = document.querySelector('.floating-particles');
                for (let i = 0; i < 15; i++) {
                    const particle = document.createElement('div');
                    particle.className = 'particle';
                    particle.style.left = Math.random() * 100 + '%';
                    particle.style.animationDelay = Math.random() * 12 + 's';
                    particle.style.animationDuration = (Math.random() * 8 + 8) + 's';
                    particlesContainer.appendChild(particle);
                }
            }

            // Initialize particles when page loads
            window.addEventListener('load', createParticles);
        </script>
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
        "api": "Radio Javan API v4",
        "timestamp": time.time()
    }), 200

@app.route('/test-api')
def test_api():
    """تست API endpoint"""
    success, data = safe_api_call("search", {"query": "test"})
    
    return jsonify({
        "api_working": success,
        "response": str(data)[:500] if not success else "OK",
        "access_key": ACCESS_KEY[:10] + "..." if ACCESS_KEY else "NOT SET",
        "api_url": API_BASE
    })

# ---------- Bot Handlers ----------

@bot.message_handler(commands=['start'])
def start_handler(message):
    try:
        welcome_text = (
            "🎵 سلام! من Behimelobot هستم\n"
            "💝 ربات موسیقی ساخته شده برای دختری زیبا راپونزل ایرانی بهنوش\n\n"
            "🔧 <b>نسخه کامل و نهایی</b> - API صحیح شده\n\n"
            "📋 <b>دستورات موجود:</b>\n"
            "🔍 /search [نام آهنگ] - جستجو آهنگ\n"
            "🆕 /new - آهنگ‌های جدید\n"
            "👤 /artist [نام آرتیست] - آهنگ‌های آرتیست\n"
            "📊 /status - وضعیت ربات\n"
            "🧪 /test - تست API\n\n"
            "💡 <b>راهنما:</b>\n"
            "• می‌توانید مستقیماً نام آهنگ بنویسید\n"
            "• از Mini App برای راهنمایی استفاده کنید\n"
            "• API اصلی Radio Javan v4 استفاده می‌شود\n\n"
            "🔗 با عشق برای بهنوش ❤️"
        )
        
        # کیبورد اصلی
        keyboard = InlineKeyboardMarkup()
        
        # دکمه Mini App
        if WEBHOOK_URL:
            keyboard.add(InlineKeyboardButton("🎵 باز کردن Mini App", url=f"{WEBHOOK_URL}/webapp"))
        
        # دکمه‌های سریع
        keyboard.add(
            InlineKeyboardButton("🆕 جدیدترین", callback_data="quick_new"),
            InlineKeyboardButton("📊 وضعیت", callback_data="quick_status")
        )
        keyboard.add(InlineKeyboardButton("🧪 تست API", callback_data="quick_test"))
        
        bot.reply_to(message, welcome_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        bot.reply_to(message, "❌ خطا در شروع ربات")

@bot.message_handler(commands=['test'])
def test_handler(message):
    """تست API"""
    try:
        processing_msg = bot.reply_to(message, "🧪 در حال تست API...")
        
        success, data = safe_api_call("search", {"query": "test"})
        
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if success:
            test_result = (
                "✅ <b>تست API موفق</b>\n\n"
                f"🔑 ACCESS_KEY: {ACCESS_KEY[:15]}...\n"
                f"📡 API URL: {API_BASE}\n"
                f"📊 Response Type: {type(data).__name__}\n"
                f"🎵 Radio Javan API v4\n"
                f"💝 آماده خدمت به بهنوش"
            )
        else:
            test_result = (
                "❌ <b>تست API ناموفق</b>\n\n"
                f"🔑 ACCESS_KEY: {ACCESS_KEY[:15] if ACCESS_KEY else 'NOT SET'}...\n"
                f"📡 API URL: {API_BASE}\n"
                f"❌ Error: {data}\n"
                f"💝 در حال بررسی مشکل"
            )
        
        bot.reply_to(message, test_result)
        
    except Exception as e:
        logger.error(f"Error in test handler: {e}")
        bot.reply_to(message, f"❌ خطا در تست: {str(e)}")

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
        
        # فراخوانی API با action صحیح
        success, data = safe_api_call("search", {"query": query})
        
        # حذف پیام پردازش
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if not success:
            # در صورت خطا، از آهنگ‌های نمونه استفاده کن
            songs = create_mock_songs(query)
            bot.reply_to(message, f"⚠️ <b>خطا در API:</b> {data}\n\n🎵 <b>نتایج نمونه برای '{query}':</b>")
        else:
            # استخراج آهنگ‌ها
            songs = extract_songs_safe(data)
            if not songs:
                songs = create_mock_songs(query)
                bot.reply_to(message, f"❌ هیچ آهنگی برای '<b>{query}</b>' پیدا نشد\n\n🎵 <b>نتایج نمونه:</b>")
            else:
                bot.reply_to(message, f"✅ <b>{len(songs)} آهنگ پیدا شد برای '{query}':</b>")
        
        # نمایش نتایج
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
        
        # استفاده از action صحیح برای آهنگ‌های جدید
        success, data = safe_api_call("new", {"type": "music"})
        
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if not success:
            songs = create_mock_songs("جدیدترین")
            bot.reply_to(message, f"⚠️ <b>خطا در API:</b> {data}\n\n🆕 <b>آهنگ‌های نمونه:</b>")
        else:
            songs = extract_songs_safe(data)
            if not songs:
                songs = create_mock_songs("جدیدترین")
                bot.reply_to(message, "❌ هیچ آهنگ جدیدی پیدا نشد\n\n🆕 <b>آهنگ‌های نمونه:</b>")
            else:
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
        
        # استفاده از action صحیح برای آرتیست
        success, data = safe_api_call("media", {"type": "music", "artist": artist})
        
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
        except:
            pass
        
        if not success:
            songs = create_mock_songs(artist)
            bot.reply_to(message, f"⚠️ <b>خطا در API:</b> {data}\n\n👤 <b>آهنگ‌های نمونه از {artist}:</b>")
        else:
            songs = extract_songs_safe(data)
            if not songs:
                songs = create_mock_songs(artist)
                bot.reply_to(message, f"❌ هیچ آهنگی از '<b>{artist}</b>' پیدا نشد\n\n👤 <b>آهنگ‌های نمونه:</b>")
            else:
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
        success, data = safe_api_call("search", {"query": "test"})
        
        api_status = "✅ فعال" if success else "❌ خطا"
        
        status_text = (
            f"📊 <b>وضعیت Behimelobot:</b>\n\n"
            f"🤖 ربات: ✅ آنلاین\n"
            f"🌐 Radio Javan API v4: {api_status}\n"
            f"📡 API URL: {API_BASE}\n"
            f"🏠 پلتفرم: Render.com\n"
            f"📱 Mini App: {'✅ فعال' if WEBHOOK_URL else '❌ غیرفعال'}\n"
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
            "📋 <b>راهنمای کامل Behimelobot:</b>\n\n"
            
            "🔍 <b>جستجو آهنگ:</b>\n"
            "• <code>/search محسن یگانه</code>\n"
            "• <code>/search دلم گرفته</code>\n"
            "• یا مستقیماً نام آهنگ بنویسید\n\n"
            
            "🆕 <b>آهنگ‌های جدید:</b>\n"
            "• <code>/new</code> - آخرین آهنگ‌ها\n\n"
            
            "👤 <b>جستجو آرتیست:</b>\n"
            "• <code>/artist پیشرو</code>\n"
            "• <code>/artist محسن یگانه</code>\n\n"
            
            "📊 <b>وضعیت و تست:</b>\n"
            "• <code>/status</code> - وضعیت ربات\n"
            "• <code>/test</code> - تست API\n\n"
            
            "🎵 <b>ویژگی‌ها:</b>\n"
            "• جستجو در میلیون‌ها آهنگ\n"
            "• دانلود مستقیم با کیفیت بالا\n"
            "• پخش آنلاین آهنگ‌ها\n"
            "• Mini App برای راحتی بیشتر\n\n"
            
            "💝 <b>ساخته شده با عشق برای بهنوش</b> ❤️"
        )
        
        keyboard = InlineKeyboardMarkup()
        if WEBHOOK_URL:
            keyboard.add(InlineKeyboardButton("🎵 Mini App", url=f"{WEBHOOK_URL}/webapp"))
        
        bot.reply_to(message, help_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in help handler: {e}")
        bot.reply_to(message, "❌ خطا در نمایش راهنما")

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
            
        elif callback_data == "quick_test":
            bot.answer_callback_query(call.id, "🧪 تست API...")
            test_handler(call.message)
            return
        
        # پردازش callback های آهنگ
        if callback_data.startswith("info_mock_"):
            bot.answer_callback_query(call.id, "ℹ️ این یک آهنگ نمونه است")
            bot.send_message(
                call.message.chat.id,
                "ℹ️ <b>اطلاعات:</b>\n\n"
                "این آهنگ نمونه است که در صورت عدم دسترسی به API نمایش داده می‌شود.\n\n"
                "🔧 برای دسترسی به آهنگ‌های واقعی، ACCESS_KEY باید صحیح تنظیم شود.\n\n"
                "💝 با عشق برای بهنوش"
            )
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
                
                # اگر آهنگ mock است
                if song_id.startswith('mock_'):
                    bot.send_message(
                        call.message.chat.id,
                        f"💝 <b>عزیز بهنوش!</b>\n\n"
                        f"🔧 این یک آهنگ نمونه است\n"
                        f"🎵 برای دسترسی به آهنگ‌های واقعی، API باید فعال باشد\n\n"
                        f"❤️ با صبر و عشق منتظر باش"
                    )
                    return
                
                # دریافت اطلاعات آهنگ واقعی
                success, data = safe_api_call("media", {"type": "music", "id": song_id})
                
                if success:
                    # یافتن لینک دانلود
                    download_url = find_download_url_safe(data)
                    
                    if download_url:
                        title = data.get('title', 'آهنگ')
                        artist = data.get('artist', '')
                        
                        link_text = f"🎵 <b>{title}</b>"
                        if artist:
                            link_text += f"\n👤 {artist}"
                        link_text += f"\n\n🔗 <a href='{download_url}'>کلیک برای {action_text}</a>"
                        link_text += f"\n💝 با عشق برای بهنوش"
                        
                        bot.send_message(call.message.chat.id, link_text)
                    else:
                        bot.send_message(call.message.chat.id, "❌ لینک دانلود پیدا نشد")
                else:
                    bot.send_message(call.message.chat.id, f"❌ خطا در دریافت آهنگ: {data}")
        
        bot.answer_callback_query(call.id)
        
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

# ---------- Error Handler ----------

@bot.message_handler(content_types=['photo', 'video', 'audio', 'document', 'voice', 'sticker'])
def media_handler(message):
    """پردازش رسانه‌ها"""
    try:
        bot.reply_to(
            message,
            "🎵 <b>سلام بهنوش!</b>\n\n"
            "من فقط متن پردازش می‌کنم.\n"
            "لطفاً نام آهنگ یا آرتیست را بنویس تا برات پیدا کنم! 💝"
        )
    except Exception as e:
        logger.error(f"Error in media handler: {e}")

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
    logger.info("🚀 Starting Behimelobot (Complete Version) for Behnosh...")
    
    try:
        # بررسی متغیرهای محیطی
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
            logger.info("🔧 Bot will work in fallback mode")
        
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
            logger.info("🌐 Starting Flask server...")
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
