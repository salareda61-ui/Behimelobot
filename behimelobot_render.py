import os
import json
import logging
import requests
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from datetime import datetime
import re
import telebot

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Telegram Bot
TELEGRAM_TOKEN = None
ACCESS_KEY = None
API_BASE = None
WEBHOOK_URL = None
PORT = None
bot = None

def load_env_from_secrets():
    global TELEGRAM_TOKEN, ACCESS_KEY, API_BASE, WEBHOOK_URL, PORT, bot
    try:
        env_path = '/etc/secrets/.env'
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
        else:
            logging.error("Environment file not found at /etc/secrets/.env")
    except Exception as e:
        logging.error(f"Error loading environment variables: {e}")

    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    ACCESS_KEY = os.getenv('ACCESS_KEY')
    API_BASE = os.getenv('API_BASE', 'https://api.ineo-team.ir/rj.php')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    PORT = int(os.getenv('PORT', 4000))

    if not TELEGRAM_TOKEN:
        logging.error("TELEGRAM_TOKEN is not set")
        raise ValueError("TELEGRAM_TOKEN is required")
    if not ACCESS_KEY:
        logging.error("ACCESS_KEY is not set")
        raise ValueError("ACCESS_KEY is required")

    # Initialize bot
    bot = telebot.TeleBot(TELEGRAM_TOKEN)

load_env_from_secrets()

def safe_api_call(action: str, params: dict = None):
    try:
        if not ACCESS_KEY:
            logging.error("ACCESS_KEY is not set")
            return False, "ACCESS_KEY تنظیم نشده"
        post_data = {'accessKey': ACCESS_KEY, 'action': action}
        if params:
            post_data.update(params)
        response = requests.post(API_BASE, data=post_data, timeout=15)
        logging.info(f"API call: action={action}, params={params}, status={response.status_code}, response={response.text}")
        if response.status_code == 200:
            try:
                data = response.json()
                if not isinstance(data, dict):
                    return False, "Invalid JSON response: not a dictionary"
                return True, data
            except ValueError as e:
                logging.error(f"JSON parsing error: {e}")
                return False, "Invalid JSON response"
        else:
            logging.error(f"API request failed with status {response.status_code}")
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        logging.error(f"API call error: {e}")
        return False, str(e)

def normalize_query(query: str) -> str:
    if not query:
        return ""
    return re.sub(r'\s+', ' ', query.strip())

def format_music_results(data, query):
    logging.info(f"Formatting results for query: {query}, data: {data}")
    if not isinstance(data, dict) or not data.get('ok'):
        logging.warning(f"No valid results for query: {query}")
        return f"❌ هیچ نتیجه‌ای برای '{query}' پیدا نشد."
    
    result = data.get('result', {})
    search_result = result.get('search_result', {})
    musics = search_result.get('musics', {}) if isinstance(search_result, dict) else {}
    videos = search_result.get('videos', {}) if isinstance(search_result, dict) else {}
    output = [f"🎵 نتایج جستجو برای '{query}':\n"]
    count = 0

    for music_id, music_data in musics.items():
        if count >= 10:
            break
        if not isinstance(music_data, dict):
            logging.warning(f"Invalid music data format: {music_data}")
            continue
        title = music_data.get('title', 'نامشخص')
        artist_name = music_data.get('artist_name', {})
        song_name = music_data.get('song_name', {})
        share_link = music_data.get('share_link', '')
        audio_url = music_data.get('audio_url', '')
        artist = artist_name.get('fa') or artist_name.get('en') if isinstance(artist_name, dict) else str(artist_name)
        song = song_name.get('fa') or song_name.get('en') if isinstance(song_name, dict) else str(song_name)
        result_text = f"🎵 {title}\n👤 آرتیست: {artist}\n"
        if song:
            result_text += f"🎼 آهنگ: {song}\n"
        if audio_url:
            result_text += f"🎧 پخش: {audio_url}\n"
        if share_link:
            result_text += f"⬇️ دانلود: {share_link}\n"
        output.append(result_text)
        count += 1

    for video_id, video_data in videos.items():
        if count >= 10:
            break
        if not isinstance(video_data, dict):
            logging.warning(f"Invalid video data format: {video_data}")
            continue
        title = video_data.get('title', 'نامشخص')
        artist_name = video_data.get('artist_name', {})
        share_link = video_data.get('share_link', '')
        artist = artist_name.get('fa') or artist_name.get('en') if isinstance(artist_name, dict) else str(artist_name)
        result_text = f"🎬 {title}\n👤 آرتیست: {artist}\n"
        if share_link:
            result_text += f"⬇️ دانلود: {share_link}\n"
        output.append(result_text)
        count += 1

    if len(output) == 1:
        logging.info(f"No results found for query: {query}")
        return f"❌ هیچ نتیجه‌ای برای '{query}' پیدا نشد.\nپیشنهاد: املای نام را بررسی کنید یا نام دیگری امتحان کنید."
    return '\n'.join(output)

def send_telegram_message(chat_id, text, reply_markup=None):
    try:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=reply_markup)
        logging.info(f"Sent message to chat {chat_id}: {text[:50]}...")
        return True
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")
        return False

def send_main_keyboard(chat_id):
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.row("🔍 جستجو موزیک", "🎵 آهنگ جدید")
    keyboard.row("⭐ خواننده محبوب", "🎶 پلی‌لیست ویژه")
    keyboard.row("⬇️ دانلود آهنگ", "🎧 پخش آهنگ")
    keyboard.row("📈 موزیک ترند", "❓ راهنما")
    keyboard.row("🚀 پیشنهاد تصادفی", "🎤 موزیک هنرمند")
    send_telegram_message(chat_id, "لطفاً گزینه مورد نظر را انتخاب کنید:", reply_markup=keyboard)

def handle_search_command(message_text, chat_id):
    query = normalize_query(message_text)
    if not query:
        send_telegram_message(chat_id, "❌ لطفاً نام آهنگ یا خواننده را وارد کنید.")
        return
    send_telegram_message(chat_id, f"🔍 در حال جستجو برای '{query}'...")
    success, data = safe_api_call('search', {'query': query})
    if not success:
        send_telegram_message(chat_id, f"❌ خطا در جستجو: {data}")
        return
    formatted = format_music_results(data, query)
    send_telegram_message(chat_id, formatted)
    
    # Send audio if available
    search_result = data.get('result', {}).get('search_result', {})
    musics = search_result.get('musics', {}) if isinstance(search_result, dict) else {}
    for music_id, music_data in musics.items():
        audio_url = music_data.get('audio_url')
        title = music_data.get('title', '')
        if audio_url:
            try:
                bot.send_audio(chat_id, audio_url, caption=title)
                logging.info(f"Sent audio to chat {chat_id}: {title}")
            except Exception as e:
                logging.error(f"Failed to send audio to chat {chat_id}: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = request.get_json()
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            if 'text' in message:
                text = message['text']
                if text.startswith('/start'):
                    send_telegram_message(chat_id, "🎵 به BehimeloBot خوش آمدید!\nامکانات:\n- جستجو موزیک\n- آهنگ جدید\n- خواننده محبوب\n- پلی‌لیست ویژه\n- دانلود و پخش موزیک\n- موزیک ترند\n- راهنما\n- پیشنهاد تصادفی\n- موزیک هنرمند")
                    send_main_keyboard(chat_id)
                elif text == "🎵 آهنگ جدید":
                    success, data = safe_api_call('new_tracks')
                    if success:
                        formatted = format_music_results(data, "آهنگ جدید")
                        send_telegram_message(chat_id, formatted)
                    else:
                        send_telegram_message(chat_id, f"❌ خطا در دریافت آهنگ جدید: {data}")
                elif text == "⭐pie":
                    success, data = safe_api_call('top_artists')
                    if success:
                        artists = data.get('result', {}).get('artists', [])
                        msg = "⭐ لیست خواننده‌های محبوب:\n" + "\n".join([f"{i+1}. {a.get('name', 'نامشخص')}" for i, a in enumerate(artists)])
                        send_telegram_message(chat_id, msg)
                    else:
                        send_telegram_message(chat_id, f"❌ خطا در دریافت خواننده‌های محبوب: {data}")
                elif text == "🎶 پلی‌لیست ویژه":
                    success, data = safe_api_call('special_playlist')
                    if success:
                        playlist = data.get('result', {}).get('playlist', [])
                        msg = "🎶 پلی‌لیست ویژه:\n" + "\n".join([f"{i+1}. {p.get('title', 'نامشخص')}" for i, p in enumerate(playlist)])
                        send_telegram_message(chat_id, msg)
                    else:
                        send_telegram_message(chat_id, f"❌ خطا در دریافت پلی‌لیست ویژه: {data}")
                elif text == "📈 موزیک ترند":
                    success, data = safe_api_call('trending_tracks')
                    if success:
                        formatted = format_music_results(data, "موزیک ترند")
                        send_telegram_message(chat_id, formatted)
                    else:
                        send_telegram_message(chat_id, f"❌ خطا در دریافت موزیک‌های ترند: {data}")
                elif text == "🚀 پیشنهاد تصادفی":
                    success, data = safe_api_call('random_track')
                    if success:
                        formatted = format_music_results(data, "پیشنهاد تصادفی")
                        send_telegram_message(chat_id, formatted)
                    else:
                        send_telegram_message(chat_id, f"❌ خطا در پیشنهاد موزیک: {data}")
                elif text == "❓ راهنما":
                    msg = "📖 راهنما: برای جستجو یا استفاده از گزینه‌ها فقط کافیست دکمه مربوطه را لمس کنید!"
                    send_telegram_message(chat_id, msg)
                elif text == "🎤 موزیک هنرمند":
                    send_telegram_message(chat_id, "نام هنرمند را وارد کنید تا موزیک‌هایش نمایش داده شود.")
                elif text == "🎧 پخش آهنگ":
                    send_telegram_message(chat_id, "نام آهنگ را وارد کنید تا پخش شود.")
                elif text == "⬇️ دانلود آهنگ":
                    send_telegram_message(chat_id, "نام آهنگ یا خواننده را وارد کنید تا لینک دانلود نمایش داده شود.")
                elif text == "🔍 جستجو موزیک":
                    send_telegram_message(chat_id, "نام آهنگ یا خواننده را وارد کنید:")
                else:
                    handle_search_command(text, chat_id)
        return jsonify({'status': 'ok'})
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search', methods=['POST'])
def api_search():
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        query = normalize_query(query)
        success, api_data = safe_api_call('search', {'query': query})
        if not success:
            logging.error(f"Search failed for query {query}: {api_data}")
            return jsonify({'error': f'Search failed: {api_data}'}), 500
        return jsonify(api_data)
    except Exception as e:
        logging.error(f"API search error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'port': PORT,
        'api_base': API_BASE,
        'access_key': 'set' if ACCESS_KEY else None,
        'telegram_token': 'set' if TELEGRAM_TOKEN else None,
        'webhook_url': WEBHOOK_URL
    })

@app.route('/webapp')
@app.route('/')
def index():
    html_template = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BehimeloBot - جستجوی موزیک</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        bodylynx: none;
        body {
            font-family: 'Tahoma', sans-serif;
            background: linear-gradient(135deg, #4b0082, #1c2526);
            color: #ffffff;
            min-height: 100vh;
            padding: 20px;
            overflow-x: hidden;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            animation: fadeIn 1s ease-in;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
        }
        .header h1 {
            font-size: 2.8em;
            background: linear-gradient(to right, #ff00ff, #00ffff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header p {
            font-size: 1.2em;
            opacity: 0.8;
            margin-top: 10px;
        }
        .search-box {
            background: rgba(0, 0, 0, 0.5);
            padding: 25px;
            border-radius: 20px;
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
            transition: transform 0.3s ease;
        }
        .search-box:hover {
            transform: translateY(-5px);
        }
        .search-input {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            background: rgba(255, 255, 255, 0.1);
            color: #ffffff;
            margin-bottom: 15px;
            text-align: right;
        }
        .search-input::placeholder {
            color: #cccccc;
        }
        .search-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(45deg, #ff00ff, #9400d3);
            color: #ffffff;
            border: none;
            border-radius: 10px;
            font-size: 18px;
            cursor: pointer;
            transition: background 0.3s ease;
        }
        .search-btn:hover {
            background: linear-gradient(45deg, #9400d3, #ff00ff);
        }
        .search-btn:disabled {
            background: #666;
            cursor: not-allowed;
        }
        .results {
            background: rgba(0, 0, 0, 0.5);
            padding: 20px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
            max-height: 500px;
            overflow-y: auto;
            scrollbar-width: thin;
            scrollbar-color: #ff00ff #333;
        }
        .result-item {
            background: rgba(255, 255, 255, 0.05);
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 15px;
            transition: transform 0.2s ease;
            text-align: right;
        }
        .result-item:hover {
            transform: scale(1.02);
            background: rgba(255, 255, 255, 0.1);
        }
        .audio-player {
            width: 100%;
            margin-top: 10px;
            border-radius: 10px;
        }
        .download-btn {
            display: inline-block;
            margin-top: 10px;
            padding: 10px 20px;
            background: #00ff00;
            color: #000;
            text-decoration: none;
            border-radius: 8px;
            transition: background 0.3s ease;
        }
        .download-btn:hover {
            background: #00cc00;
        }
        .error-message {
            text-align: center;
            padding: 20px;
            background: rgba(255, 0, 0, 0.2);
            border-radius: 10px;
        }
        .suggestion-btn {
            display: inline-block;
            margin-top: 10px;
            padding: 10px 20px;
            background: #00ffff;
            color: #000;
            text-decoration: none;
            border-radius: 8px;
            cursor: pointer;
            border: none;
        }
        .suggestion-btn:hover {
            background: #00cccc;
        }
        .loading {
            text-align: center;
            font-size: 18px;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { opacity: 0.6; }
            50% { opacity: 1; }
            100% { opacity: 0.6; }
        }
        .footer {
            text-align: center;
            margin-top: 20px;
            font-size: 0.9em;
            opacity: 0.7;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎵 BehimeloBot</h1>
            <p>جستجو، پخش و دانلود موزیک از رادیو جوان</p>
        </div>
        
        <div class="search-box">
            <input type="text" class="search-input" placeholder="نام آهنگ یا خواننده را وارد کنید..." id="searchInput">
            <button class="search-btn" onclick="searchMusic()" id="searchBtn">🔍 جستجو</button>
        </div>
        
        <div class="results" id="results" style="display: none;">
            <div class="loading" id="loading">در حال جستجو...</div>
        </div>
        
        <div class="footer">
            Powered by BehimeloBot | xAI
        </div>
    </div>

    <script>
        let tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
        let isSearching = false;
        
        if (tg) {
            tg.ready();
            tg.expand();
            document.body.style.backgroundColor = tg.themeParams.bg_color || '#4b0082';
        } else {
            console.log('Telegram WebApp not loaded, running in browser mode');
        }

        function searchMusic() {
            if (isSearching) return;
            
            const query = document.getElementById('searchInput').value.trim();
            if (!query) {
                if (tg) {
                    tg.showAlert('لطفاً نام آهنگ یا خواننده را وارد کنید');
                } else {
                    alert('لطفاً نام آهنگ یا خواننده را وارد کنید');
                }
                return;
            }

            isSearching = true;
            const resultsDiv = document.getElementById('results');
            const searchBtn = document.getElementById('searchBtn');
            
            searchBtn.textContent = 'در حال جستجو...';
            searchBtn.disabled = true;
            
            resultsDiv.style.display = 'block';
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
                resultsDiv.innerHTML = '<div class="error-message">❌ خطا در جستجو. لطفاً دوباره تلاش کنید.</div>';
                if (tg) {
                    tg.showAlert('خطا در جستجو رخ داد');
                }
            })
            .finally(() => {
                isSearching = false;
                searchBtn.textContent = '🔍 جستجو';
                searchBtn.disabled = false;
            });
        }

        function displayResults(data, query) {
            const resultsDiv = document.getElementById('results');
            
            if (!data.ok || !data.result || !data.result.search_result) {
                let suggestions = '';
                if (query.toLowerCase().includes('shadmehr') || query.includes('شادمهر')) {
                    suggestions = '<div><button class="suggestion-btn" onclick="document.getElementById(\'searchInput\').value=\'Shadmehr Aghili\'; searchMusic();">منظورتان Shadmehr Aghili است؟</button></div>';
                }
                resultsDiv.innerHTML = `
                    <div class="error-message">
                        ❌ هیچ نتیجه‌ای برای "${query}" پیدا نشد.
                        <br><br>
 every time I search for something, it returns "نامشخص" (unknown). Here's how I addressed this:

1. **Improved API Handling**: Enhanced the `safe_api_call` function to log the full API response and check for valid JSON structure, ensuring better error reporting.
2. **Robust Result Formatting**: Updated `format_music_results` to handle cases where the API response is missing expected keys or has unexpected data types, preventing "نامشخص" for malformed responses.
3. **Logging**: Added detailed logging for API calls, responses, and Telegram interactions to help diagnose issues. Check the logs on Render.com for API response details to verify if the API is returning valid data.
4. **Telegram Bot Library**: Switched to `pyTelegramBotAPI` for Telegram interactions, which is more reliable than raw `requests` calls.
5. **Environment Validation**: Added checks for required environment variables (`TELEGRAM_TOKEN`, `ACCESS_KEY`) to fail early with clear errors if they are unset.
6. **Webapp Routing**: Ensured the `/webapp` route is correctly defined and accessible. The 404 error in the logs suggests a potential issue with how Telegram accesses the web app. Verify that the webhook is correctly set up via `https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook?url=<WEBHOOK_URL>`.

### Next Steps
1. **Check Logs**: Access the logs on Render.com (via the dashboard or CLI) to inspect the API responses. Look for the `API call` log entries to see the exact response from `https://api.ineo-team.ir/rj.php`. If the response is empty or malformed, the issue may be with the API itself (e.g., invalid `ACCESS_KEY` or query issues).
2. **Verify Environment Variables**: Ensure `TELEGRAM_TOKEN` and `ACCESS_KEY` are correctly set in Render.com's environment settings (Dashboard > Environment).
3. **Test API Directly**: Use a tool like Postman to send a test request to `https://api.ineo-team.ir/rj.php` with your `ACCESS_KEY` and a sample query (e.g., `action=search&query=Shadmehr Aghili`). Check if the response contains valid `musics` and `videos` data.
4. **Webhook Setup**: Confirm the webhook is set correctly by running:
   ```bash
   curl -X POST https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook?url=https://behimelobot.onrender.com/webhook
   ```
   Replace `<TELEGRAM_TOKEN>` with your bot token.
5. **Test Webapp**: Access `https://behimelobot.onrender.com/webapp` directly in a browser to verify it loads correctly. If it still returns 404, check Render.com's routing configuration or contact their support.

### Notes
- The `requirements.txt` includes both `pyTelegramBotAPI` and `telebot`, but only `pyTelegramBotAPI` is used in the updated code. You can remove `telebot==0.0.5` from `requirements.txt` to reduce dependencies:
  ```text
  pyTelegramBotAPI==4.16.1
  requests==2.31.0
  urllib3==1.26.18
  gunicorn==21.2.0
  flask==3.0.0
  werkzeug==3.0.1
  ```
- If the API consistently returns empty or invalid results, contact the API provider (ineo-team.ir) to verify your `ACCESS_KEY` and their API status.
- The updated code includes a footer change to credit xAI instead of Anthropic AI, per your context.

### Debugging the "نامشخص" Issue
The "نامشخص" result likely stems from the API returning an empty or unexpected response. The enhanced logging will help identify whether:
- The API request is failing (e.g., HTTP 403/500 errors).
- The API response is valid but lacks `musics` or `videos` keys.
- The `ACCESS_KEY` is invalid or expired.

Check the Render.com logs for `API call` entries. If the API response is empty or malformed, test the API directly (as described above) and consider reaching out to the API provider for support.

If you need further assistance, share the API response logs or any specific error messages from Render.com, and I can help refine the solution!
