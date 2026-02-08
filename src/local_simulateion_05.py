import json
import time
import datetime
import os
import random
import threading
import re
import urllib.request # タイムアウト付き通信用
import feedparser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from llama_cpp import Llama

# 設定ファイル読み込み
try:
    from settings import CHARACTERS, MOBS, RIVALS, INITIAL_STATE, MODEL_PATH, DATA_FILE, HISTORY_FILE, PORT, SLEEP_TIME
except ImportError:
    from src.settings import CHARACTERS, MOBS, RIVALS, INITIAL_STATE, MODEL_PATH, DATA_FILE, HISTORY_FILE, PORT, SLEEP_TIME

print(f"--- 🏰 魏ホールディングス Stability版 ({MODEL_PATH}) ---")

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

# --- 📰 ニュース取得 (タイムアウト付き修正) ---
def get_ai_news():
    if random.random() > 0.4: return None
    
    rss_url = "https://news.google.com/rss/search?q=AI技術+when:1d&hl=ja&gl=JP&ceid=JP:ja"
    try:
        # ★修正: 5秒で諦めるタイムアウト設定を追加
        with urllib.request.urlopen(rss_url, timeout=5) as response:
            xml = response.read()
            feed = feedparser.parse(xml)
            if feed.entries:
                entry = random.choice(feed.entries[:5])
                return {"title": entry.title, "link": entry.link, "summary": entry.summary}
    except Exception as e:
        print(f"⚠️ ニュース取得スキップ: {e}")
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
        news_context = f"""
【ニュース記事】
タイトル: {news['title']}
概要: {news['summary']}

【指令】
このニュースを利用して、魏ホールディングスがとった「具体的な施策」や「便乗ビジネス」を考案してください。
"""
        news_url = news['link']
    else:
        print("🏢 社内イベント生成")
        news_context = "外部ニュースには頼らず、純粋な「社内の出来事（派閥争い、突飛な新規事業、宴会、トラブルなど）」を作成してください。"

    situation = f"資金{state['funds']}、士気{state['morale']}、リスク{state['risk']}"
    members_str = ", ".join(CHARACTERS.keys())

    messages = [
        {"role": "system", "content": f"""あなたは魏ホールディングスのGMです。
メンバー({members_str})から1名を実行者に選び、イベントを作成してください。

出力はJSONのみ:
{{
  "title": "イベント名(15文字)",
  "proposer": "実行者名(リストから選択)",
  "description": "内容(100文字)。ニュースのコピペ禁止。武将がどう動いたかを書くこと。",
  "changes": {{ "funds": 整数, "morale": 整数, "risk": 整数 }}
}}"""},
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
    members_str = ", ".join(CHARACTERS.keys())
    
    system_prompt = ""
    if action_type == 'rumor':
        system_prompt = """あなたは悪徳広告代理店です。魏ホールディングスのために「嘘八百のヤラセ広告」を考えてください。
出力JSON: {"title": "広告コピー", "description": "具体的な広告内容", "changes": {"funds": -500, "morale": 30, "risk": 30}}"""
    elif action_type == 'audit':
        is_fraud = random.random() < 0.6
        if is_fraud:
            system_prompt = f"""あなたは内部監査員です。メンバー({members_str})の誰かの笑える不正を報告してください。
出力JSON: {{"title": "不正発覚", "description": "誰が何をしたか", "changes": {{"funds": -1000, "morale": -20, "risk": 20}}}}"""
        else:
            return {"title": "定期監査", "description": "荀彧による監査は完璧だった。一点の曇りもない。", "changes": {"funds": -100, "morale": 5, "risk": -20}}
    elif action_type == 'edict':
        system_prompt = """あなたは気まぐれな皇帝です。理不尽な命令や災害を与えてください。
出力JSON: {"title": "勅命", "description": "内容", "changes": {"funds": 変動値, "morale": 変動値, "risk": 変動値}}"""

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
        if random.random() < 0.7: stance = random.choice(char_data['bias'])
        else: stance = random.choice(["賛成", "反対", "懸念", "中立"])
        
        messages = [
            {"role": "system", "content": f"""
あなたは魏の「{name}」です。
キャラ設定: {char_data['desc']}
口調の指示: {char_data['style']}
現在のスタンス: {stance}

【重要】
・歴史的な堅苦しい言葉遣いは禁止。
・現代のネットスラング、若者言葉、ビジネス用語、煽りを多用せよ。
・20文字以内で、短く、キャラを立てて発言せよ。
"""},
            {"role": "user", "content": f"イベント: {event_data['title']}\n詳細: {event_data['description']}"}
        ]
        text = chat_generate(messages, max_tokens=60).replace("「", "").replace("」", "")
        new_comments[name] = text
    return new_comments

def generate_sns_reactions(event_data, current_sns_log, comments):
    print("📱 SNS反応...")
    
    targets = random.sample(MOBS, 3)
    if random.random() < 0.3: targets.append(random.choice(RIVALS))
    
    context = ""
    if event_data:
        pickup = random.sample(list(comments.items()), min(2, len(comments)))
        comment_str = "\n".join([f"- {name}: {cmt}" for name, cmt in pickup])
        context = f"最新ニュース: {event_data['description']}\n経営陣の反応:\n{comment_str}"
    else:
        target_char = random.choice(list(CHARACTERS.keys()))
        context = f"特にニュースはない。暇だ。{target_char}について噂話をして。"

    new_tweets = []
    for user in targets:
        messages = [
            {"role": "system", "content": f"""
あなたはSNSユーザー「{user['name']}」。{user['desc']}
【重要】
・Twitter(X)や匿名掲示板のノリで書け。
・「草」「ワロタ」「〜な件」「神」「クソ」などのスラングを使え。
・30文字以内の短文で投稿せよ。
"""},
            {"role": "user", "content": context}
        ]
        text = chat_generate(messages, max_tokens=60).replace("「", "").replace("」", "")
        new_tweets.append({"name": user['name'], "id": user['id'], "content": text, "is_vip": user in RIVALS, "timestamp": datetime.datetime.now().strftime("%H:%M")})
    
    return (new_tweets + current_sns_log)[:30]

# --- 🔄 メインループ ---
# --- 🔄 メインループ (毎時更新・省エネ版) ---
def simulation_loop():
    os.makedirs("./data", exist_ok=True)
    
    # 初回起動時のファイル作成（変更なし）
    if not os.path.exists(DATA_FILE):
        print("⚡ 初期ステータスファイルを作成します...")
        save_json_safe(DATA_FILE, INITIAL_STATE)
    
    if not os.path.exists(HISTORY_FILE):
        print("⚡ 初期履歴ファイルを作成します...")
        init_log = [{
            "timestamp": datetime.datetime.now().strftime("%H:%M"),
            "title": "魏ホールディングス創業",
            "description": "システム稼働。現在は1時間ごとの省エネモードです。",
            "proposer": "システム",
            "news_url": "",
            "changes": {}
        }]
        save_json_safe(HISTORY_FILE, init_log)

    print("🚀 魏ホールディングス・省エネ運用モード開始！")
    
    # 待機時間の設定（1時間 = 3600秒）
    # 動作テストをしたい場合は、一時的に 60 などに下げてください
    RELAX_TIME = 3600 

    while True:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n--- 🕒 定期更新開始: {now_str} ---")

        # リセットチェック
        if reset_event.is_set():
             print("♻️ リセット検知: 待機")
             reset_event.clear()
             time.sleep(5)
             continue

        # A. 現状読み込み
        with data_lock:
            with open(DATA_FILE, "r", encoding="utf-8") as f: state_snapshot = json.load(f)

        # B. イベント生成（ニュース取得あり）
        # 1時間に1回なので、ここでは確実にニュースを取得してイベントを生成します
        event_data = generate_event(state_snapshot)
        changes = event_data['changes']
        
        # C. 武将コメント生成
        comments = update_ministers_comments(state_snapshot, event_data)
        
        # D. SNS反応生成
        # イベントに対する反応をじっくり生成
        sns_log = generate_sns_reactions(event_data, state_snapshot.get('sns', []), comments)

        # 保存直前のリセット割り込みチェック
        if reset_event.is_set():
            print("♻️ 生成中にリセットされたため、今回の結果は破棄します")
            reset_event.clear()
            continue

        # E. 書き込み
        with data_lock:
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f: current_state = json.load(f)
                with open(HISTORY_FILE, "r", encoding="utf-8") as f: current_history = json.load(f)
            except:
                current_state = state_snapshot; current_history = []

            # ステータス更新
            current_state['funds'] += safe_int(changes.get('funds', 0))
            current_state['morale'] += safe_int(changes.get('morale', 0))
            current_state['risk'] += safe_int(changes.get('risk', 0))
            current_state = evaluate_status(current_state)
            current_state['comments'] = comments
            current_state['sns'] = sns_log 

            # 履歴保存
            log_entry = {
                "timestamp": datetime.datetime.now().strftime("%H:%M"),
                "title": event_data['title'],
                "description": event_data['description'],
                "proposer": event_data.get("proposer", "不明"),
                "news_url": event_data.get("news_url", ""),
                "changes": changes
            }
            current_history.insert(0, log_entry)
            if len(current_history) > 30: current_history.pop()

            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(current_state, f, indent=2, ensure_ascii=False)
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(current_history, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 更新完了。次の更新まで {RELAX_TIME // 60} 分間スリープします。")
        # 次のターンまで1時間待機
        time.sleep(RELAX_TIME)

# --- 🌍 Webサーバー (キャッシュ無効化付き) ---
class CustomHandler(SimpleHTTPRequestHandler):
    # ★修正: ブラウザに「キャッシュするな」と伝えるヘッダーを追加
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_POST(self):
        action_type = self.path.split('/')[-1]
        try:
            if action_type == 'reset':
                print("🚨 リセットリクエスト受信")
                with data_lock:
                    save_json_safe(DATA_FILE, INITIAL_STATE.copy())
                    init_log = [{"timestamp": datetime.datetime.now().strftime("%H:%M"), "title": "世界線リセット", "description": "全てが無に帰した。", "proposer": "管理者", "changes": {}}]
                    save_json_safe(HISTORY_FILE, init_log)
                    reset_event.set()
                self.send_response(200); self.end_headers(); self.wfile.write(b'OK'); return

            if action_type in ['edict', 'audit', 'rumor']:
                with data_lock:
                    with open(DATA_FILE, "r", encoding="utf-8") as f: state_snapshot = json.load(f)

                event_data = generate_intervention(action_type, state_snapshot)
                comments = update_ministers_comments(state_snapshot, event_data)
                
                with data_lock:
                    if reset_event.is_set():
                        self.send_response(200); self.end_headers(); self.wfile.write(b'Reset_Interrupted'); return
                    
                    with open(DATA_FILE, "r", encoding="utf-8") as f: state = json.load(f)
                    with open(HISTORY_FILE, "r", encoding="utf-8") as f: history = json.load(f)
                    
                    changes = event_data['changes']
                    state['funds'] += safe_int(changes.get('funds', 0))
                    state['morale'] += safe_int(changes.get('morale', 0))
                    state['risk'] += safe_int(changes.get('risk', 0))
                    state = evaluate_status(state)
                    state['comments'] = comments
                    state['sns'] = generate_sns_reactions(event_data, state.get('sns', []), comments)

                    log_entry = {
                        "timestamp": datetime.datetime.now().strftime("%H:%M"),
                        "title": event_data['title'],
                        "description": event_data['description'],
                        "proposer": "天の声",
                        "news_url": "",
                        "changes": changes
                    }
                    history.insert(0, log_entry)
                    if len(history) > 30: history.pop()

                    with open(DATA_FILE, "w", encoding="utf-8") as f:
                        json.dump(state, f, indent=2, ensure_ascii=False)
                    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                        json.dump(history, f, indent=2, ensure_ascii=False)
                
                self.send_response(200); self.end_headers(); self.wfile.write(b'OK')
                return
            
            self.send_response(400)
        except Exception as e:
            print(f"Server Error: {e}")
            self.send_response(500)

class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

def server_loop():
    print(f"🌍 http://localhost:{PORT}")
    httpd = ReusableHTTPServer(('0.0.0.0', PORT), CustomHandler)
    httpd.serve_forever()

if __name__ == "__main__":
    t_server = threading.Thread(target=server_loop, daemon=True)
    t_server.start()
    simulation_loop()