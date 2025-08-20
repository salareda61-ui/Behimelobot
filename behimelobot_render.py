import os
import json
import logging
import requests
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from datetime import datetime
import re

# تعریف اپلیکیشن Flask
app = Flask(__name__)

# متغیرهای محیطی
TELEGRAM_TOKEN = None
ACCESS_KEY = None
API_BASE = None
WEBHOOK_URL = None
PORT = None

def load_env_from_secrets():
    global TELEGRAM_TOKEN, ACCESS_KEY, API_BASE, WEBHOOK_URL, PORT
    try:
        env_path = '/etc/secrets/.env'
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
    except Exception as e:
        pass
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    ACCESS_KEY = os.getenv('ACCESS_KEY')
    API_BASE = os.getenv('API_BASE', 'https://api.ineo-team.ir/rj.php')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    PORT = int(os.getenv('PORT', 4000))
load_env_from_secrets()

# توابع API
def safe_api_call(action: str, params: dict = None):
    try:
        if not ACCESS_KEY:
            return False, "ACCESS_KEY تنظیم نشده"
        post_data = {'accessKey': ACCESS_KEY, 'action': action}
        if params: post_data.update(params)
        response = requests.post(API_BASE, data=post_data, timeout=15)
        if response.status_code == 200:
            try:
                return True, response.json()
            except Exception:
                return False, "Invalid JSON response"
        else:
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

def normalize_query(query: str) -> str:
    if not query: return ""
    return re.sub(r'\s+', ' ', query.strip())

def format_music_results(data, query):
    if not isinstance(data, dict) or not data.get('ok'):
        return f"❌ هیچ نتیجه‌ای برای '{query}' پیدا نشد."
    result = data.get('result', {})
    search_result = result.get('search_result', {})
    musics = search_result.get('musics', {})
    videos = search_result.get('videos', {})
    output = [f"🎵 نتایج جستجو برای '{query}':\n"]
    count = 0
    for music_id, music_data in musics.items():
        if count >= 10: break
        title = music_data.get('title', 'نامشخص')
        artist_name = music_data.get('artist_name', {})
        song_name = music_data.get('song_name', {})
        share_link = music_data.get('share_link', '')
        audio_url = music_data.get('audio_url', '')
        artist = artist_name.get('fa') or artist_name.get('en') if isinstance(artist_name, dict) else str(artist_name)
        song = song_name.get('fa') or song_name.get('en') if isinstance(song_name, dict) else str(song_name)
        result_text = f"🎵 {title}\n👤 آرتیست: {artist}\n"
        if song: result_text += f"🎼 آهنگ: {song}\n"
        if audio_url: result_text += f"🎧 پخش: {audio_url}\n"
        if share_link: result_text += f"⬇️ دانلود: {share_link}\n"
        output.append(result_text)
        count += 1
    for video_id, video_data in videos.items():
        if count >= 10: break
        title = video_data.get('title', 'نامشخص')
        artist_name = video_data.get('artist_name', {})
        share_link = video_data.get('share_link', '')
        artist = artist_name.get('fa') or artist_name.get('en') if isinstance(artist_name, dict) else str(artist_name)
        result_text = f"🎬 {title}\n👤 آرتیست: {artist}\n"
        if share_link: result_text += f"⬇️ دانلود: {share_link}\n"
        output.append(result_text)
        count += 1
    if len(output) == 1:
        return f"❌ هیچ نتیجه‌ای برای '{query}' پیدا نشد."
    return '\n'.join(output)

def send_telegram_message(chat_id, text, reply_markup=None):
    if not TELEGRAM_TOKEN: return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup: data['reply_markup'] = json.dumps(reply_markup)
    requests.post(url, data=data, timeout=10)
    return True

def send_main_keyboard(chat_id):
    keyboard = {
        "keyboard": [
            [{"text": "🔍 جستجو موزیک"}, {"text": "🎵 آهنگ جدید"}],
            [{"text": "⭐ خواننده محبوب"}, {"text": "🎶 پلی‌لیست ویژه"}],
            [{"text": "⬇️ دانلود آهنگ"}, {"text": "🎧 پخش آهنگ"}],
            [{"text": "📈 موزیک ترند"}, {"text": "❓ راهنما"}],
            [{"text": "🚀 پیشنهاد تصادفی"}, {"text": "🎤 موزیک هنرمند"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }
    send_telegram_message(chat_id, "لطفاً گزینه مورد نظر را انتخاب کنید:", keyboard)

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
    # پخش آهنگ با sendAudio اگر audio_url موجود بود
    search_result = data.get('result', {}).get('search_result', {})
    musics = search_result.get('musics', {})
    for music_id, music_data in musics.items():
        audio_url = music_data.get('audio_url')
        title = music_data.get('title', '')
        if audio_url:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendAudio"
            payload = {"chat_id": chat_id, "audio": audio_url, "caption": title}
            requests.post(url, data=payload)
    # دانلود لینک‌ها به صورت پیام جداگانه هم قابل ارسال است

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
                        send_telegram_message(chat_id, "❌ خطا در دریافت آهنگ جدید.")
                elif text == "⭐ خواننده محبوب":
                    success, data = safe_api_call('top_artists')
                    if success:
                        artists = data.get('result', {}).get('artists', [])
                        msg = "⭐ لیست خواننده‌های محبوب:\n" + "\n".join([f"{i+1}. {a.get('name')}" for i, a in enumerate(artists)])
                        send_telegram_message(chat_id, msg)
                    else:
                        send_telegram_message(chat_id, "❌ خطا در دریافت خواننده‌های محبوب.")
                elif text == "🎶 پلی‌لیست ویژه":
                    success, data = safe_api_call('special_playlist')
                    if success:
                        playlist = data.get('result', {}).get('playlist', [])
                        msg = "🎶 پلی‌لیست ویژه:\n" + "\n".join([f"{i+1}. {p.get('title')}" for i, p in enumerate(playlist)])
                        send_telegram_message(chat_id, msg)
                    else:
                        send_telegram_message(chat_id, "❌ خطا در دریافت پلی‌لیست ویژه.")
                elif text == "📈 موزیک ترند":
                    success, data = safe_api_call('trending_tracks')
                    if success:
                        formatted = format_music_results(data, "موزیک ترند")
                        send_telegram_message(chat_id, formatted)
                    else:
                        send_telegram_message(chat_id, "❌ خطا در دریافت موزیک‌های ترند.")
                elif text == "🚀 پیشنهاد تصادفی":
                    success, data = safe_api_call('random_track')
                    if success:
                        formatted = format_music_results(data, "پیشنهاد تصادفی")
                        send_telegram_message(chat_id, formatted)
                    else:
                        send_telegram_message(chat_id, "❌ خطا در پیشنهاد موزیک.")
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
            return jsonify({'error': f'Search failed: {api_data}'}), 500
        return jsonify(api_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat(), 'port': PORT})

@app.route('/')
def index():
    html_template = """
    <html>
    <head>
        <title>BehimeloBot - جستجوی موزیک</title>
    </head>
    <body>
        <h1>🎵 BehimeloBot</h1>
        <p>جستجو و دانلود موزیک در رادیو جوان</p>
        <input type="text" id="searchInput" placeholder="نام آهنگ یا خواننده..."/>
        <button onclick="searchMusic()">جستجو</button>
        <div id="results"></div>
        <script>
        function searchMusic() {
            let q = document.getElementById('searchInput').value;
            fetch('/api/search', {method: 'POST', headers: {'Content-Type':'application/json'}, body:JSON.stringify({query:q})})
            .then(r=>r.json()).then(data=>{
                let res = document.getElementById('results');
                if (!data.ok || !data.result || !data.result.search_result) {
                    res.innerHTML = "❌ نتیجه‌ای پیدا نشد.";
                    return;
                }
                let musics = data.result.search_result.musics || {};
                let html = '';
                Object.values(musics).forEach(m=>{
                    html += `<div><b>${m.title}</b> <br>👤 ${m.artist_name.fa||m.artist_name.en||''}<br>
                    ${m.song_name.fa||m.song_name.en||''}<br>
                    ${m.audio_url ? `<audio controls src="${m.audio_url}"></audio>` : ''}
                    ${m.share_link ? `<a href="${m.share_link}" target="_blank">⬇️ دانلود</a>` : ''}</div><hr>`;
                });
                res.innerHTML = html ? html : "❌ نتیجه‌ای پیدا نشد.";
            });
        }
        </script>
    </body>
    </html>
    """
    return render_template_string(html_template)

@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except:
        return '', 204

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
