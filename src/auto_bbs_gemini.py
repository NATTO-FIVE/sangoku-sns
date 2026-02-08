import json
import time
import datetime
import subprocess
import os
import random
import re
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- 🔑 APIキー設定 ---
API_KEY = "AIzaSyDkx-Mbz3tOYisOX9L3cFOCaM87koHftxo"
genai.configure(api_key=API_KEY)

# --- 設定 ---
# 安定の1.5 Flashを使用
MODEL_NAME = "models/gemini-flash-latest"

AGENTS_DIR = "./src/agents/"
DATA_FILE = "./data/threads.json"

# スレッド更新間隔：1時間 (3600秒)
SLEEP_TIME = 3600 

AGENT_IDS = ["cao_cao", "liu_bei", "sun_quan", "zhou_yu", "zhuge_liang", "guo_jia", "sima_yi"]

AUTO_TOPICS = [
    "【議論】弊社における「働き方改革」が完全に形骸化している件について",
    "【技術】レガシーシステム（魏システム）の完全撤廃とクラウド移行の是非",
    "【告発】上層部（曹操派）の経費使い込み疑惑と、監査体制の不備",
    "【悲報】新人エンジニアの離職率が80%を超えた原因を分析する",
    "【提案】全社的なリモートワーク廃止命令に対する反対署名運動",
    "【事故】本番DBが誤って削除された件のポストモーテム（事後検証）",
    "【相談】パワハラ上司（司馬懿）の音声を録音したが、どこに提出すべきか",
    "【経営】次期CTO選出選挙における派閥争いの現状まとめ",
    "【炎上】公式SNSの不適切発言による株価暴落と、広報の責任",
    "【質問】競合他社（蜀・呉）への転職活動がバレた場合の処遇について"
]

print(f"--- ☁️ 三国ホールディングス 不死鳥モード (Auto Retry / SafeFilter OFF) ---")

# --- ⚙️ モデル設定 ---
generation_config = {
    "temperature": 1.0,
    "response_mime_type": "application/json",
}

safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    generation_config=generation_config,
    safety_settings=safety_settings
)

# --- 🛠️ ヘルパー関数 ---

def load_json(path):
    if not os.path.exists(path): return []
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_agent(agent_id):
    path = f"{AGENTS_DIR}{agent_id}.json"
    if not os.path.exists(path): return None
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

def git_sync():
    try:
        subprocess.run(["git", "add", DATA_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "update: Heavy Discussion"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("✅ GitHub同期完了")
    except:
        pass

# --- 🛡️ ゾンビ機能（リトライ処理） ---
def generate_safe(prompt_func, max_retries=5):
    """429エラーが出たら待機してリトライするラッパー関数"""
    for attempt in range(max_retries):
        try:
            return prompt_func()
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                wait_time = 60 * (attempt + 1) # 60秒, 120秒, 180秒...と待機時間を増やす
                print(f"\n⏳ 速度制限(429)検知。{wait_time}秒 冷却します... (Re-try {attempt+1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"⚠️ 生成エラー: {e}")
                return None
    return None

# --- 生成ロジック ---

def create_thread_content(agent, topic):
    prompt = f"""
あなたは「{agent['name']}」です。
役割: {agent['system']}
【指令】
社内掲示板に新しいスレッドを立ててください。
お題: {topic}
今回は「深刻な相談」または「熱い議論の提案」です。
400文字〜600文字程度の長文で、現状の課題、具体的な数字、過去の経緯、感情を盛り込んでください。
出力スキーマ: {{ "title": "str", "body": "str" }}
"""
    response = model.generate_content(prompt)
    return json.loads(response.text)

def create_response_content(agent, thread):
    context = f"スレ主（{thread['author']}）: {thread['body'][:300]}...\n"
    for res in thread['responses'][-3:]:
        context += f"{res['name']}: {res['content'][:100]}...\n"

    prompt = f"""
あなたは「{agent['name']}」です。
役割: {agent['system']}
【文脈】
{context}
【指令】
この議論に対して、あなたの立場から「長文レス（200文字〜400文字）」を返してください。
論理的、または感情的に深く掘り下げてください。
専門用語（KPI、ROI、コンプラ、技術的負債など）を多用してください。
出力スキーマ: {{ "content": "str" }}
"""
    response = model.generate_content(prompt)
    return json.loads(response.text)['content']

# --- メインループ ---
def main():
    os.makedirs("./data", exist_ok=True)
    agents = {}
    for aid in AGENT_IDS:
        a = load_agent(aid)
        if a: agents[aid] = a
    
    while True:
        author_id = random.choice(AGENT_IDS)
        author = agents[author_id]
        topic = random.choice(AUTO_TOPICS)
        
        print(f"\n🆕 {author['name']} が長文スレを投稿しようとしています...")
        
        # リトライ付きで実行
        data = generate_safe(lambda: create_thread_content(author, topic))
        
        if not data:
            print("❌ スレ立て失敗。スキップします。")
            time.sleep(10)
            continue

        title, body = data['title'], data['body']
        
        threads = load_json(DATA_FILE)
        if not isinstance(threads, list): threads = []
        
        new_thread = {
            "id": int(time.time()),
            "title": title,
            "author": author['name'],
            "icon": author.get("icon", ""),
            "body": body,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "responses": []
        }
        threads.insert(0, new_thread)
        if len(threads) > 10: threads.pop()
        
        print(f"📌 {title}")
        print(f"📝 本文文字数: {len(body)}文字")
        
        res_count = random.randint(8, 12)
        print(f"💬 {res_count}件の激論を開始します...")
        
        potential_responders = [aid for aid in AGENT_IDS if aid != author_id]
        
        for i in range(res_count):
            responder_id = random.choice(potential_responders)
            responder = agents[responder_id]
            
            if new_thread['responses'] and new_thread['responses'][-1]['name'] == responder['name']:
                continue

            # リトライ付きで実行
            res_content = generate_safe(lambda: create_response_content(responder, new_thread))
            
            if not res_content:
                res_content = "......"

            new_res = {
                "name": responder['name'],
                "icon": responder.get("icon", ""),
                "content": res_content,
                "timestamp": datetime.datetime.now().strftime("%H:%M")
            }
            new_thread['responses'].append(new_res)
            
            print(f"   {responder['name']}: {res_content[:30]}...")
            
            # 20秒待つ（これでRPM制限を確実に回避）
            time.sleep(20)

        save_json(DATA_FILE, threads)
        git_sync()
        
        print(f"\n💤 次回の定例会議（更新）は {SLEEP_TIME/60}分後 です...")
        time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    main()