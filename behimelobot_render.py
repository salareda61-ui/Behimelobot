import os
import json
import logging
import requests
from typing import Dict, Any, Tuple
from flask import Flask, request, jsonify, render_template_string
import time
from datetime import datetime

# تنظیمات لاگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# تنظیمات Flask
app = Flask(__name__)

# متغیرهای سراسری
TELEGRAM_TOKEN = None
ACCESS_KEY = None
API_BASE = None
WEBHOOK_URL = None
PORT = None

def load_env_from_secrets():
    """بارگذاری متغیرهای محیطی از Secret Files"""
    global TELEGRAM_TOKEN, ACCESS_KEY, API_BASE, WEBHOOK_URL, PORT
    
    try:
        # تلاش برای خواندن از فایل .env
        env_path = '/etc/secrets/.env'
        if os.path.exists(env_path):
            logger.info("✅ Loading from Secret Files (.env)")
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
        else:
            logger.info("📁 Secret file not found, using environment variables")
    except Exception as e:
        logger.error(f"❌ Error loading secrets: {e}")
    
    # دریافت متغیرها
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    ACCESS_KEY = os.getenv('ACCESS_KEY')
    API_BASE = os.getenv('API_BASE', 'https://api.ineo-team.ir/rj.php')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    PORT = int(os.getenv('PORT', 10000))
    
    # بررسی متغیرهای ضروری
    required_vars = {
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'ACCESS_KEY': ACCESS_KEY,
        'WEBHOOK_URL': WEBHOOK_URL
    }
    
    missing_vars = [k for k, v in required_vars.items() if not v]
    if missing_vars:
        logger.error(f"❌ Missing required variables: {missing_vars}")
    else:
        logger.info("✅ All required variables loaded successfully")

# بارگذاری متغیرهای محیطی
load_env_from_secrets()

# 🔧 تابع تست API در startup
def test_api_on_startup():
    """تست API در startup"""
    logger.info("🔧 Testing API on startup...")
    logger.info(f"ACCESS_KEY: {ACCESS_KEY[:20]}..." if ACCESS_KEY else "ACCESS_KEY: NOT SET")
    
    try:
        test_data = {
            'accessKey': ACCESS_KEY,
            'action': 'search',
            'query': 'test'
        }
        
        response = requests.post(API_BASE, data=test_data, timeout=10)
        logger.info(f"API Test Response Status: {response.status_code}")
        logger.info(f"API Test Response Text: {response.text[:200]}...")
        
        if response.status_code == 200:
            try:
                data = response.json()
                logger.info(f"API Test JSON Keys: {list(data.keys())}")
                logger.info(f"API Test Success Keys: {list(data.get('result', {}).keys()) if data.get('result') else 'No result'}")
            except:
                logger.error("API Test: Response is not JSON")
        else:
            logger.error(f"API Test Failed: Status {response.status_code}")
            
    except Exception as e:
        logger.error(f"API Test Error: {e}")

def safe_api_call(action: str, params: Dict[str, Any] = None) -> Tuple[bool, Any]:
    """API call صحیح با تشخیص کامل"""
    try:
        if not ACCESS_KEY:
            logger.error("❌ ACCESS_KEY not provided")
            return False, "ACCESS_KEY تنظیم نشده"
        
        if params is None:
            params = {}
        
        post_data = {
            'accessKey': ACCESS_KEY,
            'action': action
        }
        post_data.update(params)
        
        logger.info(f"🔧 API Call - Action: {action}")
        logger.info(f"🔧 API Call - URL: {API_BASE}")
        logger.info(f"🔧 API Call - Data: {post_data}")
        
        response = requests.post(
            API_BASE,
            data=post_data,
            timeout=15,
            headers={
                'User-Agent': 'Behimelobot/1.0',
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        
        logger.info(f"🔧 API Response Status: {response.status_code}")
        logger.info(f"🔧 API Response Headers: {dict(response.headers)}")
        logger.info(f"🔧 API Response Text: {response.text[:500]}...")
        
        if response.status_code != 200:
            logger.error(f"❌ HTTP Error: {response.status_code}")
            return False, f"HTTP {response.status_code}"
        
        try:
            data = response.json()
            logger.info(f"✅ JSON parsed successfully")
            
            # 🔧 لاگ‌های تشخیصی اضافه شده
            logger.info(f"✅ JSON Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            logger.info(f"✅ Result keys: {list(data.get('result', {}).keys()) if data.get('result') else 'No result'}")
            
            return True, data
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON Decode Error: {e}")
            return False, "Invalid JSON response"
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Request Error: {e}")
        return False, f"Network error: {str(e)}"
    except Exception as e:
        logger.error(f"❌ Unexpected Error: {e}")
        return False, f"Unexpected error: {str(e)}"

def format_music_results(data: Dict, query: str) -> str:
    """فرمت کردن نتایج موسیقی"""
    
    # 🔧 لاگ‌های تشخیصی اضافه شده
    logger.info(f"🔧 format_music_results called with query: {query}")
    logger.info(f"🔧 Data type: {type(data)}")
    
    if not isinstance(data, dict):
        logger.error(f"❌ Data is not dict: {type(data)}")
        return generate_sample_results(query)
    
    # بررسی وجود ok و status
    if not data.get('ok'):
        logger.error(f"❌ API returned ok=false")
        return generate_sample_results(query)
    
    result = data.get('result', {})
    if not result:
        logger.error(f"❌ No result in data")
        return generate_sample_results(query)
    
    search_result = result.get('search_result', {})
    if not search_result:
        logger.error(f"❌ No search_result in result")
        return generate_sample_results(query)
    
    # 🔧 لاگ اضافی برای search_result
    logger.info(f"✅ search_result keys: {list(search_result.keys())}")
    
    # دریافت موسیقی‌ها
    musics = search_result.get('musics', {})
    videos = search_result.get('videos', {})
    artists = search_result.get('artists', [])
    
    logger.info(f"✅ Found: {len(musics)} musics, {len(videos)} videos, {len(artists)} artists")
    
    if not musics and not videos and not artists:
        logger.warning(f"⚠️ No results found for: {query}")
        return f"❌ هیچ آهنگی برای '{query}' پیدا نشد\n\n" + generate_sample_results(query)
    
    # فرمت کردن نتایج
    results = []
    results.append(f"🎵 نتایج جستجو برای '{query}':\n")
    
    # نمایش موسیقی‌ها
    count = 0
    for music_id, music_data in musics.items():
        if count >= 10:  # حداکثر 10 نتیجه
            break
        
        title = music_data.get('title', 'نامشخص')
        artist_name = music_data.get('artist_name', {})
        song_name = music_data.get('song_name', {})
        share_link = music_data.get('share_link', '')
        
        # نام آرتیست
        artist = artist_name.get('fa') or artist_name.get('en') or 'نامشخص'
        song = song_name.get('fa') or song_name.get('en') or ''
        
        # فرمت نتیجه
        result_text = f"🎵 {title}\n"
        result_text += f"👤 آرتیست: {artist}\n"
        if song:
            result_text += f"🎼 آهنگ: {song}\n"
        if share_link:
            result_text += f"🔗 لینک: {share_link}\n"
        
        results.append(result_text)
        count += 1
    
    # نمایش ویدیوها
    for video_id, video_data in videos.items():
        if count >= 10:
            break
        
        title = video_data.get('title', 'نامشخص')
        artist_name = video_data.get('artist_name', {})
        share_link = video_data.get('share_link', '')
        
        artist = artist_name.get('fa') or artist_name.get('en') or 'نامشخص'
        
        result_text = f"🎬 {title}\n"
        result_text += f"👤 آرتیست: {artist}\n"
        if share_link:
            result_text += f"🔗 لینک: {share_link}\n"
        
        results.append(result_text)
        count += 1
    
    logger.info(f"✅ Formatted {len(results)-1} results for query: {query}")
    return '\n'.join(results)

def generate_sample_results(query: str) -> str:
    """تولید نتایج نمونه"""
    return f"""🎵 نتایج نمونه:

🎵 آهنگ مرتبط با {query}
👤 آرتیست: آرتیست نمونه
⏱ مدت: 03:45

🎵 آهنگ زیبای ایرانی
👤 آرتیست: خواننده محبوب
⏱ مدت: 04:12"""

def send_telegram_message(chat_id: int, text: str, reply_markup=None):
    """ارسال پیام تلگرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        if reply_markup:
            data['reply_markup'] = json.dumps(reply_markup)
        
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Message sent to {chat_id}")
            return True
        else:
            logger.error(f"❌ Failed to send message: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Error sending message: {e}")
        return False

def handle_search_command(message_text: str, chat_id: int):
    """پردازش دستور جستجو"""
    try:
        # استخراج کلمه جستجو
        if message_text.startswith('/search'):
            query = message_text[7:].strip()  # حذف '/search'
        else:
            query = message_text.strip()
        
        if not query:
            send_telegram_message(chat_id, "❌ لطفاً نام آهنگ یا خواننده را وارد کنید\n\nمثال: /search محسن یگانه")
            return
        
        logger.info(f"🔍 Search query: {query}")
        
        # جستجو در API
        success, data = safe_api_call('search', {'query': query})
        
        if not success:
            error_msg = f"❌ خطا در جستجو: {data}\n\n" + generate_sample_results(query)
            send_telegram_message(chat_id, error_msg)
            return
        
        # فرمت کردن نتایج
        formatted_results = format_music_results(data, query)
        
        # ارسال نتایج
        send_telegram_message(chat_id, formatted_results)
        
    except Exception as e:
        logger.error(f"❌ Error in handle_search_command: {e}")
        error_msg = f"❌ خطا در پردازش جستجو\n\n" + generate_sample_results(query if 'query' in locals() else 'نامشخص')
        send_telegram_message(chat_id, error_msg)

@app.route('/webhook', methods=['POST'])
def webhook():
    """پردازش webhook تلگرام"""
    try:
        update = request.get_json()
        logger.info(f"📨 Received update: {update}")
        
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            
            if 'text' in message:
                text = message['text']
                
                if text.startswith('/start'):
                    welcome_msg = """🎵 سلام! به ربات بهیمه لو خوش آمدید!

🔍 برای جستجو آهنگ از دستور زیر استفاده کنید:
/search نام آهنگ یا خواننده

📱 یا از Mini App استفاده کنید!

مثال:
/search محسن یگانه
/search عاشقانه"""
                    
                    keyboard = {
                        'inline_keyboard': [[
                            {'text': '🎵 Mini App', 'web_app': {'url': f'{WEBHOOK_URL}/'}}
                        ]]
                    }
                    
                    send_telegram_message(chat_id, welcome_msg, keyboard)
                    
                elif text.startswith('/search'):
                    handle_search_command(text, chat_id)
                    
                else:
                    # جستجو بدون دستور
                    handle_search_command(text, chat_id)
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        logger.error(f"❌ Error in webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search', methods=['POST'])
def api_search():
    """API جستجو برای Mini App"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        logger.info(f"🔍 Mini App search: {query}")
        
        # جستجو در API
        success, api_data = safe_api_call('search', {'query': query})
        
        if not success:
            return jsonify({'error': f'Search failed: {api_data}'}), 500
        
        # بازگرداندن نتایج خام برای Mini App
        return jsonify(api_data)
        
    except Exception as e:
        logger.error(f"❌ Error in api_search: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """بررسی سلامت سرویس"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'api_base': API_BASE,
        'access_key_set': bool(ACCESS_KEY)
    })

@app.route('/')
def index():
    """صفحه اصلی Mini App"""
    html_template = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>بهیمه لو - جستجو موزیک</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 600px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .search-box { 
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
        }
        .search-input { 
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            margin-bottom: 15px;
        }
        .search-btn { 
            width: 100%;
            padding: 15px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 18px;
            cursor: pointer;
        }
        .search-btn:hover { background: #45a049; }
        .results { 
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            max-height: 400px;
            overflow-y: auto;
        }
        .result-item { 
            background: rgba(255,255,255,0.1);
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 10px;
        }
        .loading { text-align: center; font-size: 18px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎵 بهیمه لو</h1>
            <p>جستجو در رادیو جوان</p>
        </div>
        
        <div class="search-box">
            <input type="text" class="search-input" placeholder="نام آهنگ یا خواننده را وارد کنید..." id="searchInput">
            <button class="search-btn" onclick="searchMusic()">🔍 جستجو</button>
        </div>
        
        <div class="results" id="results" style="display: none;">
            <div class="loading" id="loading">در حال جستجو...</div>
        </div>
    </div>

    <script>
        // Initialize Telegram WebApp
        let tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();

        // Set theme
        document.body.style.backgroundColor = tg.themeParams.bg_color || '#667eea';

        function searchMusic() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) {
                alert('لطفاً نام آهنگ یا خواننده را وارد کنید');
                return;
            }

            const resultsDiv = document.getElementById('results');
            const loadingDiv = document.getElementById('loading');
            
            resultsDiv.style.display = 'block';
            loadingDiv.style.display = 'block';
            resultsDiv.innerHTML = '<div class="loading">در حال جستجو...</div>';

            fetch('/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({query: query})
            })
            .then(response => response.json())
            .then(data => {
                displayResults(data, query);
            })
            .catch(error => {
                console.error('Error:', error);
                resultsDiv.innerHTML = '<div class="result-item">❌ خطا در جستجو</div>';
            });
        }

        function displayResults(data, query) {
            const resultsDiv = document.getElementById('results');
            
            if (!data.result || !data.result.search_result) {
                resultsDiv.innerHTML = '<div class="result-item">❌ نتیجه‌ای یافت نشد</div>';
                return;
            }

            const searchResult = data.result.search_result;
            const musics = searchResult.musics || {};
            const videos = searchResult.videos || {};
            
            let html = `<h3>🎵 نتایج جستجو برای "${query}":</h3>`;
            
            // Display musics
            let count = 0;
            for (let id in musics) {
                if (count >= 10) break;
                const music = musics[id];
                const artist = music.artist_name?.fa || music.artist_name?.en || 'نامشخص';
                const song = music.song_name?.fa || music.song_name?.en || '';
                
                html += `
                    <div class="result-item">
                        <div style="font-weight: bold;">🎵 ${music.title}</div>
                        <div>👤 ${artist}</div>
                        ${song ? `<div>🎼 ${song}</div>` : ''}
                        ${music.share_link ? `<div><a href="${music.share_link}" target="_blank" style="color: #4CAF50;">🔗 لینک</a></div>` : ''}
                    </div>
                `;
                count++;
            }
            
            // Display videos
            for (let id in videos) {
                if (count >= 10) break;
                const video = videos[id];
                const artist = video.artist_name?.fa || video.artist_name?.en || 'نامشخص';
                
                html += `
                    <div class="result-item">
                        <div style="font-weight: bold;">🎬 ${video.title}</div>
                        <div>👤 ${artist}</div>
                        ${video.share_link ? `<div><a href="${video.share_link}" target="_blank" style="color: #4CAF50;">🔗 لینک</a></div>` : ''}
                    </div>
                `;
                count++;
            }
            
            if (count === 0) {
                html = '<div class="result-item">❌ نتیجه‌ای یافت نشد</div>';
            }
            
            resultsDiv.innerHTML = html;
        }

        // Handle enter key
        document.getElementById('searchInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchMusic();
            }
        });
    </script>
</body>
</html>
    """
    return render_template_string(html_template)

def main():
    """تابع اصلی"""
    logger.info("🚀 Starting Behimelobot...")
    
    # 🔧 تست API در startup
    test_api_on_startup()
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN not found")
        return
    
    # تنظیم webhook
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        set_webhook_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        
        response = requests.post(set_webhook_url, data={'url': webhook_url}, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Webhook set successfully: {webhook_url}")
        else:
            logger.error(f"❌ Failed to set webhook: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error setting webhook: {e}")
    
    # اجرای Flask
    logger.info(f"🌐 Starting Flask on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)

if __name__ == '__main__':
    main()
