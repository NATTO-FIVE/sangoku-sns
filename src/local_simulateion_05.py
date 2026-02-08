import json
import time
import datetime
import os
import random
import threading
import re
import urllib.request # タイムアウト付き通信用
import feedparser
import subprocess # Git操作用
from http.server import HTTPServer, SimpleHTTPRequestHandler
from llama_cpp import Llama

# 設定ファイル読み込み
try:
    from settings import CHARACTERS, MOBS, RIVALS, INITIAL_STATE, MODEL_PATH, DATA_FILE, HISTORY_FILE, PORT, SLEEP_TIME
except ImportError:
    from src.settings import CHARACTERS, MOBS, RIVALS, INITIAL_STATE, MODEL_PATH, DATA_FILE, HISTORY_FILE, PORT, SLEEP_TIME

print(f"--- 🏰 魏ホールディングス Stability & Auto-Push版 ({MODEL_PATH}) ---")

# --- 🔒 ロック & フラグ定義 ---
data_lock = threading.Lock()   # ファイル読み書き用
model_lock = threading.Lock()  # AIモデル生成用
reset_event = threading.Event() # リセット発生通知用

# --- 🤖 モデルロード ---
try:
    llm = Llama(model_path=MODEL_PATH, n_gpu_layers=25, n_ctx=4096, verbose=False)
    print("✅ Qwen2.5 起動完了")
except Exception as e:
    print(f"❌ モデルエラー: {e}")
    exit()

# --- 🛠️ ユーティリティ ---
def load_json_safe(path, default_data):
    if not os.path.exists(path): return default_data
    try:
        with data_lock:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return default_data

def save_json_safe(path, data):
    with data_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

def extract_json(text):
    try:
        text = re.sub(r'```json', '', text)
        text = re.sub(r'```', '', text)
        text = text.replace("万", "0000").replace("億", "00000000")
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
    except: pass
    return None

def chat_generate(messages, max_tokens=200):
    with model_lock:
        try:
            response = llm.create_chat_completion(messages=messages, max_tokens=max_tokens, temperature=0.8)
            return response['choices'][0]['message']['content'].strip()
        except: return ""

def safe_int(val):
    try:
        clean_val = str(val).replace(",", "").replace("+", "").replace(" ", "")
        return int(float(clean_val))
    except: return 0

# --- 📤 GitHub送信関数 ---
def git_push_result():
    """保存されたJSONデータをGitHubへ自動送信する"""
    try:
        # 変更があるかチェック
        status = subprocess.run(["git", "status", "--porcelain", "data/"], capture_output=True, text=True).stdout
        if not status:
            print("✨ データに変化がないためGitHub送信をスキップします。")
            return

        print("📤 GitHubへ最新データを送信中...")
        subprocess.run(["git", "add", "data/*.json"], check=True)
        # 変更がない場合にエラーにならないよう || true を入れるか、statusチェックで弾く
        subprocess.run(["git", "commit", "-m", "📊 魏ホールディングス 定期更新"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("✅ GitHubへのアップロードが完了しました。")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Git操作失敗 (変更がないか設定不備): {e}")
    except Exception as e:
        print(f"⚠️ 予期せぬGitエラー: {e}")

# --- 📰 ニュース取得 ---
def get_ai_news():
    if random.random() > 0.4: return None
    rss_url = "https://news.google.com/rss/search?q=AI技術+when:1d&hl=ja&gl=JP&ceid=JP:ja"
    try:
        with urllib.request.urlopen(rss_url, timeout=5) as response:
            xml = response.read()
            feed = feedparser.parse(xml)
            if feed.entries:
                entry = random.choice(feed.entries[:5])
                return {"title": entry.title, "link": entry.link, "summary": entry.summary}
    except Exception as e:
        print(f"⚠️ ニュース取得失敗: {e}")
    return None

# --- 📊 経営評価 ---
def evaluate_status(state):
    f = safe_int(state['funds'])
    risk = safe_int(state['risk'])
    morale = safe_int(state['morale'])
    
    if risk > 60: state['reputation'] = "炎上中🔥"; state['rating'] = "危険"
    elif morale < 30: state['reputation'] = "ブラック"; state['rating'] = "悪化"
    elif f > 5000: state['reputation'] = "優良企業"; state['rating'] = "安泰"
    else: state['reputation'] = "様子見"; state['rating'] = "安定"
    return state

# --- 🧠 生成ロジック群 ---
def generate_event(state):
    print("🎲 イベント生成中...")
    news = get_ai_news()
    news_context = ""
    news_url = ""

    if news:
        print(f"📰 News採用: {news['title']}")
        news_context = f"【ニュース記事】\nタイトル: {news['title']}\n概要: {news['summary']}\n\nこのニュースを利用して、魏がとった施策を考案せよ。"
        news_url = news['link']
    else:
        print("🏢 社内イベント生成")
        news_context = "社内の出来事（派閥争い、突飛な新規事業、宴会、トラブル等）を作成せよ。"

    situation = f"資金{state['funds']}、士気{state['morale']}、リスク{state['risk']}"
    members_str = ", ".join(CHARACTERS.keys())

    messages = [
        {"role": "system", "content": f"あなたは魏のGM。メンバー({members_str})から1名を選び、JSONでイベント作成せよ。項目:title, proposer, description, changes(funds, morale, risk)"},
        {"role": "user", "content": f"状況: {situation}\n{news_context}"}
    ]

    data = extract_json(chat_generate(messages, max_tokens=500))
    if data and "changes" in data:
        if data.get('proposer') not in CHARACTERS: data['proposer'] = "曹操"
        data['news_url'] = news_url
        return data
    return {"title": "平穏な一日", "description": "特になし。", "proposer": "荀攸", "changes": {"funds": -10, "morale": 0, "risk": -5}, "news_url": ""}

def generate_intervention(action_type, state):
    print(f"⚡ 介入イベント生成中: {action_type}")
    system_prompt = {
        'rumor': 'あなたは悪徳広告代理店。魏のための嘘八百なヤラセ広告をJSONで考えろ。',
        'audit': 'あなたは内部監査員。誰かの笑える不正を報告せよ。',
        'edict': 'あなたは気まぐれな皇帝。理不尽な命令を与えよ。'
    }.get(action_type, '')

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": "生成せよ"}]
    data = extract_json(chat_generate(messages, max_tokens=500))
    if data and "changes" in data:
        data['proposer'] = "天の声"
        return data
    return {"title": "エラー", "description": "失敗", "proposer": "システム", "changes": {}}

def update_ministers_comments(state, event_data):
    print("💬 武将コメント...")
    new_comments = {}
    for name, char_data in CHARACTERS.items():
        stance = random.choice(char_data['bias'])
        messages = [
            {"role": "system", "content": f"あなたは{name}。{char_data['style']} スタンス:{stance}。ネットスラング等を使い20文字以内で発言せよ。"},
            {"role": "user", "content": f"イベント: {event_data['title']}\n詳細: {event_data['description']}"}
        ]
        text = chat_generate(messages, max_tokens=60).replace("「", "").replace("」", "")
        new_comments[name] = text
    return new_comments

def generate_sns_reactions(event_data, current_sns_log, comments):
    print("📱 SNS反応...")
    targets = random.sample(MOBS, 3)
    if random.random() < 0.3: targets.append(random.choice(RIVALS))
    
    new_tweets = []
    for user in targets:
        messages = [
            {"role": "system", "content": f"あなたはSNSユーザー「{user['name']}」。ネットのノリで30文字以内で書け。"},
            {"role": "user", "content": f"話題: {event_data['description'] if event_data else '最近の魏について'}"}
        ]
        text = chat_generate(messages, max_tokens=60).replace("「", "").replace("」", "")
        new_tweets.append({"name": user['name'], "id": user['id'], "content": text, "is_vip": user in RIVALS, "timestamp": datetime.datetime.now().strftime("%H:%M")})
    
    return (new_tweets + current_sns_log)[:30]

# --- 🔄 メインループ ---
def simulation_loop():
    os.makedirs("./data", exist_ok=True)
    if not os.path.exists(DATA_FILE): save_json_safe(DATA_FILE, INITIAL_STATE)
    if not os.path.exists(HISTORY_FILE): 
        save_json_safe(HISTORY_FILE, [{"timestamp": datetime.datetime.now().strftime("%H:%M"), "title": "魏創業", "description": "システム稼働。", "proposer": "システム", "changes": {}}])

    # ★ 追加：起動直後に一度強制的に送信して、404エラー（真っ白）を防ぐ
    print("🚀 初回データを同期中...")
    subprocess.run(["git", "add", "data/*.json"], check=False)
    subprocess.run(["git", "commit", "-m", "🚀 System Started"], check=False)
    subprocess.run(["git", "push", "origin", "main"], check=False)

    print("🚀 シミュレーション開始！")
    
    while True:
        # A. 現状読み込み
        state_snapshot = load_json_safe(DATA_FILE, INITIAL_STATE)
        
        # B. 各種生成
        event_data = generate_event(state_snapshot)
        comments = update_ministers_comments(state_snapshot, event_data)
        sns_log = generate_sns_reactions(event_data, state_snapshot.get('sns', []), comments)

        if reset_event.is_set():
            reset_event.clear(); continue

        # C. 書き込み
        with data_lock:
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f: current_state = json.load(f)
                with open(HISTORY_FILE, "r", encoding="utf-8") as f: current_history = json.load(f)
            except:
                current_state = state_snapshot; current_history = []

            changes = event_data['changes']
            current_state['funds'] += safe_int(changes.get('funds', 0))
            current_state['morale'] += safe_int(changes.get('morale', 0))
            current_state['risk'] += safe_int(changes.get('risk', 0))
            current_state = evaluate_status(current_state)
            current_state['comments'] = comments
            current_state['sns'] = sns_log 

            log_entry = {"timestamp": datetime.datetime.now().strftime("%H:%M"), "title": event_data['title'], "description": event_data['description'], "proposer": event_data.get("proposer"), "news_url": event_data.get("news_url", ""), "changes": changes}
            current_history.insert(0, log_entry)
            if len(current_history) > 30: current_history.pop()

            with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(current_state, f, indent=2, ensure_ascii=False)
            with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(current_history, f, indent=2, ensure_ascii=False)

            # --- 💾 自動送信 (判定を甘くして確実に送る) ---
            print("📤 更新データを送信中...")
            subprocess.run(["git", "add", "data/*.json"], check=False)
            subprocess.run(["git", "commit", "-m", f"📊 Update {datetime.datetime.now().strftime('%H:%M')}"], check=False)
            subprocess.run(["git", "push", "origin", "main"], check=False)
        
        print(f"✅ 更新完了。次の更新まで {SLEEP_TIME // 60} 分待機します。")
        time.sleep(SLEEP_TIME)

# --- 🌍 Webサーバー ---
class CustomHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        super().end_headers()

    def do_POST(self):
        action_type = self.path.split('/')[-1]
        try:
            if action_type == 'reset':
                with data_lock:
                    save_json_safe(DATA_FILE, INITIAL_STATE.copy())
                    save_json_safe(HISTORY_FILE, [{"timestamp": datetime.datetime.now().strftime("%H:%M"), "title": "リセット", "description": "無に帰した。", "proposer": "システム", "changes": {}}])
                    reset_event.set()
                self.send_response(200); self.end_headers(); self.wfile.write(b'OK'); return

            if action_type in ['edict', 'audit', 'rumor']:
                state_snapshot = load_json_safe(DATA_FILE, INITIAL_STATE)
                event_data = generate_intervention(action_type, state_snapshot)
                comments = update_ministers_comments(state_snapshot, event_data)
                
                with data_lock:
                    if reset_event.is_set(): self.send_response(200); self.end_headers(); return
                    
                    state = load_json_safe(DATA_FILE, INITIAL_STATE)
                    history = load_json_safe(HISTORY_FILE, [])
                    
                    changes = event_data['changes']
                    state['funds'] += safe_int(changes.get('funds', 0))
                    state['morale'] += safe_int(changes.get('morale', 0))
                    state['risk'] += safe_int(changes.get('risk', 0))
                    state = evaluate_status(state); state['comments'] = comments
                    state['sns'] = generate_sns_reactions(event_data, state.get('sns', []), comments)

                    log_entry = {"timestamp": datetime.datetime.now().strftime("%H:%M"), "title": event_data['title'], "description": event_data['description'], "proposer": "天の声", "news_url": "", "changes": changes}
                    history.insert(0, log_entry)
                    if len(history) > 30: history.pop()

                    with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(state, f, indent=2, ensure_ascii=False)
                    with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(history, f, indent=2, ensure_ascii=False)
                    
                    # --- 💾 自動送信 (介入イベント版) ---
                    git_push_result()

                self.send_response(200); self.end_headers(); self.wfile.write(b'OK'); return
            self.send_response(400)
        except Exception as e:
            print(f"Error: {e}"); self.send_response(500)

if __name__ == "__main__":
    t_server = threading.Thread(target=lambda: HTTPServer(('0.0.0.0', PORT), CustomHandler).serve_forever(), daemon=True)
    t_server.start()
    simulation_loop()