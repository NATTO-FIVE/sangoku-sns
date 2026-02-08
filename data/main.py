import json
import time
import datetime
import os
import random
import threading
import re
import feedparser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from llama_cpp import Llama

from settings import CHARACTERS, MOBS, RIVALS, INITIAL_STATE, MODEL_PATH, DATA_FILE, HISTORY_FILE, PORT, SLEEP_TIME

print(f"--- 🏰 魏ホールディングス Sync版 ({MODEL_PATH}) ---")

# ★ ロック定義
model_lock = threading.Lock() # AI生成中のロック
data_lock = threading.Lock()  # JSON読み書き中のロック（これ重要！）

try:
    llm = Llama(model_path=MODEL_PATH, n_gpu_layers=25, n_ctx=8192, verbose=False)
    print("✅ Qwen2.5 起動完了")
except Exception as e:
    print(f"❌ モデルエラー: {e}")
    exit()

# --- 🛠️ ユーティリティ ---
def load_json_safe(path, default_data):
    """排他制御付きロード"""
    with data_lock:
        if not os.path.exists(path): return default_data
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: return default_data

def save_json_safe(path, data):
    """排他制御付きセーブ"""
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

# --- 📰 ニュース取得 ---
def get_ai_news():
    rss_url = "https://news.google.com/rss/search?q=AI技術+when:1d&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            entry = random.choice(feed.entries[:5])
            summary = entry.summary[:150] + "..." if 'summary' in entry else "詳細不明"
            return {"title": entry.title, "link": entry.link, "summary": summary}
    except: pass
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

# --- 🧠 生成ロジック ---

def generate_event(state):
    print("🎲 自動イベント生成中...")
    news = get_ai_news()
    news_context = ""
    news_url = ""
    
    # プロンプトを強化：ニュースをそのまま書くなと指示
    if news:
        print(f"📰 News: {news['title']}")
        news_context = f"""
【重要：以下のニュースを利用せよ】
記事タイトル: {news['title']}
概要: {news['summary']}

【指令】
このニュース記事を見て、魏ホールディングスがとった「具体的な施策」や「便乗ビジネス」を考案してください。
※イベント名や説明文に、ニュースのタイトルをそのままコピーするのは禁止です。
「誰が、ニュースを利用して、何をしたか」を記述してください。
"""
        news_url = news['link']
    else:
        news_context = "社内で起きたユニークなトラブルや成功イベントを作成してください。"

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
    
    # (中略：プロンプトは前回と同じなので省略なしで記述します)
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
            return {"title": "定期監査", "description": "荀彧による監査は完璧だった。", "changes": {"funds": -100, "morale": 5, "risk": -20}}
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
            {"role": "system", "content": f"あなたは{name}。役割:{char_data['desc']} 口調:{char_data['style']} スタンス:{stance}。30文字以内でコメントして。"},
            {"role": "user", "content": f"イベント: {event_data['title']}\n詳細: {event_data['description']}"}
        ]
        text = chat_generate(messages, max_tokens=60).replace("「", "").replace("」", "")
        new_comments[name] = text
    return new_comments

def generate_sns_reactions(event_data, current_sns_log, comments):
    print("📱 SNS反応...")
    targets = random.sample(MOBS, 3)
    if random.random() < 0.3: targets.append(random.choice(RIVALS))
    
    pickup = random.sample(list(comments.items()), min(2, len(comments)))
    context = "\n".join([f"- {name}: {cmt}" for name, cmt in pickup])
    
    new_tweets = []
    for user in targets:
        messages = [
            {"role": "system", "content": f"あなたはSNSユーザー「{user['name']}」。{user['desc']}。タメ口30文字以内で反応して。"},
            {"role": "user", "content": f"ニュース: {event_data['description']}\n経営陣:\n{context}"}
        ]
        text = chat_generate(messages, max_tokens=60).replace("「", "").replace("」", "")
        new_tweets.append({"name": user['name'], "id": user['id'], "content": text, "is_vip": user in RIVALS, "timestamp": datetime.datetime.now().strftime("%H:%M")})
    
    return (new_tweets + current_sns_log)[:30]

# --- 🔄 メインループ ---
def simulation_loop():
    os.makedirs("./data", exist_ok=True)
    while True:
        # 1. データの読み込み（生成に必要な情報だけ取る）
        initial_load_state = load_json_safe(DATA_FILE, INITIAL_STATE)
        
        # 2. イベント生成（時間がかかる処理。ロックはしない）
        event_data = generate_event(initial_load_state)
        
        # 3. データの更新（ここでロックして、最新の状態に対して書き込む）
        #    生成中にAPIが書き込んでいても、ここで最新版を再ロードして追記するので消えません。
        with data_lock:
            state = load_json_safe(DATA_FILE, INITIAL_STATE) # 最新をリロード
            history = load_json_safe(HISTORY_FILE, [])
            
            changes = event_data['changes']
            state['funds'] += safe_int(changes.get('funds', 0))
            state['morale'] += safe_int(changes.get('morale', 0))
            state['risk'] += safe_int(changes.get('risk', 0))
            state = evaluate_status(state)
            
            # コメント生成などはLLMを使うのでロック内でやると重いが、
            # データの整合性を優先するため、コメント生成は「イベント確定後」に行う
            # ただしLLMロックは別にあるので、ここでは「データロック」は一度離してもいいかもしれないが、
            # 簡易実装として、コメント生成後にまとめて保存するフローにする（ただし上書きリスクはある）
            
            # --- 修正フロー ---
            # データロックはいったん解除して、コメントとSNSを作る（時間がかかるから）
        
        # 4. 付帯情報生成（コメント・SNS）
        comments = update_ministers_comments(state, event_data)
        sns_log = generate_sns_reactions(event_data, state.get('sns', []), comments)

        # 5. 最終保存（もう一度ロックして書き込む）
        with data_lock:
            # 再度リロード（念には念を）
            state = load_json_safe(DATA_FILE, INITIAL_STATE)
            history = load_json_safe(HISTORY_FILE, [])
            
            # 数値変動を再適用（重複適用しないよう、本当はDiffでやるべきだが、簡易的に上書き）
            # 今回は「イベント生成時点の変動」を適用する
            state['funds'] += safe_int(changes.get('funds', 0))
            state['morale'] += safe_int(changes.get('morale', 0))
            state['risk'] += safe_int(changes.get('risk', 0))
            state = evaluate_status(state)
            
            state['comments'] = comments
            state['sns'] = sns_log

            log_entry = {
                "timestamp": datetime.datetime.now().strftime("%H:%M"),
                "title": event_data['title'],
                "description": event_data['description'],
                "proposer": event_data.get("proposer", "不明"),
                "news_url": event_data.get("news_url", ""),
                "changes": changes
            }
            history.insert(0, log_entry)
            if len(history) > 30: history.pop()
            
            save_json_safe(DATA_FILE, state)
            save_json_safe(HISTORY_FILE, history)
        
        print(f"💤 {SLEEP_TIME}秒 待機...")
        time.sleep(SLEEP_TIME)

# --- 🌍 Webサーバー ---
class CustomHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        action_type = self.path.split('/')[-1]
        try:
            if action_type == 'reset':
                save_json_safe(DATA_FILE, INITIAL_STATE.copy())
                save_json_safe(HISTORY_FILE, [{"timestamp": datetime.datetime.now().strftime("%H:%M"), "title": "再創業", "description": "リセット完了", "proposer": "システム", "changes": {}}])
                self.send_response(200); self.end_headers(); self.wfile.write(b'OK'); return

            # 介入イベント生成（LLM使用）
            state_snapshot = load_json_safe(DATA_FILE, INITIAL_STATE)
            event_data = generate_intervention(action_type, state_snapshot)
            
            # 付帯情報生成
            comments = update_ministers_comments(state_snapshot, event_data)
            
            # ★ ここでロックして保存
            with data_lock:
                state = load_json_safe(DATA_FILE, INITIAL_STATE)
                history = load_json_safe(HISTORY_FILE, [])
                
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

                save_json_safe(DATA_FILE, state)
                save_json_safe(HISTORY_FILE, history)
                
            self.send_response(200); self.end_headers(); self.wfile.write(b'OK')
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