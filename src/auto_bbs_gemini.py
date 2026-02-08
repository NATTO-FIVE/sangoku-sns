import json
import time
import datetime
import subprocess
import os
import random
import re
import google.generativeai as genai

# --- 🔑 APIキー設定 ---
API_KEY = "AIzaSyDkx-Mbz3tOYisOX9L3cFOCaM87koHftxo"
genai.configure(api_key=API_KEY)

# --- 設定 ---
# MODEL_NAME = "models/gemini-2.0-flash"  # そのまま
MODEL_NAME = "models/gemini-flash-latest"

AGENTS_DIR = "./src/agents/"
DATA_FILE = "./data/threads.json"

# ⏱️ ここを変更：1時間（3600秒）に1回
SLEEP_TIME = 3600 

AGENT_IDS = ["cao_cao", "liu_bei", "sun_quan", "zhou_yu", "zhuge_liang", "guo_jia", "sima_yi"]

# お題も少し「議論向き」に重くする
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

print(f"--- ☁️ 三国ホールディングス 重厚長大モード ({MODEL_NAME}) ---")

model = genai.GenerativeModel(MODEL_NAME)

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

def clean_text(text):
    text = re.sub(r'【.*?】', '', text)
    text = re.sub(r'スレタイ[:：].*', '', text)
    text = re.sub(r'```json', '', text)
    text = re.sub(r'```', '', text)
    if "：" in text: text = text.split("：")[-1]
    return text.strip()

# --- 生成ロジック (長文特化) ---

def create_thread(agent):
    topic = random.choice(AUTO_TOPICS)
    
    prompt = f"""
あなたは「{agent['name']}」になりきってください。
役割設定: {agent['system']}

【指令】
社内掲示板に新しいスレッドを立ててください。
お題: {topic}

今回は「深刻な相談」または「熱い議論の提案」です。
以下のJSON形式のみを出力してください。

{{
  "title": "【議論】などのタイトル",
  "body": "400文字〜600文字程度の長文を書いてください。現状の課題、具体的な数字、過去の経緯、あなたの強い感情（怒り、諦め、野心など）を盛り込んで、読み応えのある内容にしてください。"
}}
"""
    try:
        response = model.generate_content(prompt)
        text = clean_text(response.text)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return data['title'], data['body']
        else:
            return f"【話題】{topic}", "詳細を語る気力もない..."
    except Exception as e:
        print(f"⚠️ APIエラー: {e}")
        return f"【話題】{topic}", "..."

def create_response(agent, thread):
    # 文脈を全部渡す（長文議論には流れが重要）
    context = f"スレ主（{thread['author']}）: {thread['body'][:200]}...\n"
    for res in thread['responses'][-3:]: # 直近3件の流れを読む
        context += f"{res['name']}: {res['content'][:100]}...\n"

    prompt = f"""
あなたは「{agent['name']}」になりきってください。
役割設定: {agent['system']}

【文脈】
{context}

【指令】
この議論に対して、あなたの立場から「長文レス（200文字〜400文字）」を返してください。

【ルール】
1. 短い一言レスは禁止。論理的、または感情的に深く掘り下げてください。
2. 専門用語（KPI、ROI、コンプラ、技術的負債など）を多用してください。
3. 相手の意見に対して「それは違う」「甘い」「面白い」と明確なスタンスを取ってください。
4. 箇条書きを使っても構いません。

出力はレスの本文だけにしてください。
"""
    try:
        response = model.generate_content(prompt)
        return clean_text(response.text)
    except:
        return "..."

def git_sync():
    try:
        subprocess.run(["git", "add", DATA_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "update: Heavy Discussion"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("✅ GitHub同期完了")
    except:
        pass

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
        
        print(f"\n🆕 {author['name']} が長文スレを投稿中...")
        title, body = create_thread(author)
        
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
        
        # レス数を増やす（議論を白熱させる）
        res_count = random.randint(8, 12)
        print(f"💬 {res_count}件の激論を開始します...")
        
        potential_responders = [aid for aid in AGENT_IDS if aid != author_id]
        
        for i in range(res_count):
            responder_id = random.choice(potential_responders)
            responder = agents[responder_id]
            
            if new_thread['responses'] and new_thread['responses'][-1]['name'] == responder['name']:
                continue

            res_content = create_response(responder, new_thread)
            
            new_res = {
                "name": responder['name'],
                "icon": responder.get("icon", ""),
                "content": res_content,
                "timestamp": datetime.datetime.now().strftime("%H:%M")
            }
            new_thread['responses'].append(new_res)
            
            # コンソールには長いので最初の1行だけ表示
            print(f"   {responder['name']}: {res_content[:30]}...")
            
            # API制限回避のため、少し長めに待つ（3秒）
            time.sleep(3)

        save_json(DATA_FILE, threads)
        git_sync()
        
        print(f"\n💤 次回の定例会議（更新）は {SLEEP_TIME/60}分後 です...")
        time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    main()