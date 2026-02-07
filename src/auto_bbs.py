import json
import time
import datetime
import subprocess
import os
import random
from llama_cpp import Llama

# --- 設定 ---
MODEL_PATH = "./models/qwen2.5-3b-instruct-q4_k_m.gguf"
AGENTS_DIR = "./src/agents/"
DATA_FILE = "./data/threads.json" # 保存先を変更
PUSH_INTERVAL = 60

# 参加者
AGENT_IDS = ["cao_cao", "liu_bei", "sun_quan", "zhou_yu", "zhuge_liang", "guo_jia", "sima_yi"]

# スレ立て用のお題（ネタ切れ防止）
TOPICS = [
    "部下の失敗談", "上司への愚痴", "三国一の美女・美男子議論", 
    "最近食べた美味しいもの", "軍事作戦の裏話", "魏・呉・蜀の七不思議",
    "最近の若者について", "老害について", "お金がない時の対処法",
    "効果的な人材採用ハック", "処世術・生き残り方"
]

# --- 脳の準備 ---
print("--- 🧠 脳を起動中 ---")
llm = Llama(model_path=MODEL_PATH, n_gpu_layers=-1, n_ctx=4096, verbose=False)

def load_json(path):
    if not os.path.exists(path): return [] if "threads" in path else {}
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_agent(agent_id):
    path = f"{AGENTS_DIR}{agent_id}.json"
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

# --- 生成ロジック ---

# 1. スレッド作成（タイトル + 本文）
def create_thread(agent):
    topic = random.choice(TOPICS)
    
    # システムプロンプト作成
    system_prompt = f"{agent['system']}\nあなたは匿名掲示板（2ちゃんねる風）にスレッドを立てます。"
    
    # ユーザープロンプト
    prompt = f"""
    テーマ「{topic}」について、ネット掲示板のスレッドを立ててください。
    
    以下のJSON形式で出力してください（マークダウンは不要）：
    {{
        "title": "【悲報】などの隅付き括弧を使った、キャッチーで釣り気味なスレタイ",
        "body": "テーマに沿った、具体的で面白いエピソードや主張（100〜150文字程度）"
    }}
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    try:
        output = llm.create_chat_completion(messages=messages, max_tokens=300, temperature=0.9)
        content = output['choices'][0]['message']['content']
        # JSON部分だけ無理やり抽出（LLMが余計なこと言った時用）
        content = content[content.find('{'):content.rfind('}')+1]
        data = json.loads(content)
        return data['title'], data['body']
    except Exception as e:
        print(f"⚠️ 生成失敗: {e}")
        return "【悲報】AIがバグった件", "すまん、エラー吐いたわ。"

# 2. レス投稿
def create_response(agent, thread):
    # 文脈を作る（タイトル + 本文 + 最新のレス3つ）
    context = f"スレタイ：{thread['title']}\n>>1：{thread['body']}\n"
    
    # 直近のレスを数件追加
    recent_res = thread['responses'][-3:]
    for res in recent_res:
        context += f"{res['name']}：{res['content']}\n"
    
    prompt = f"""
    上記のスレッドの流れを読んで、あなたのキャラで短いレス（反応）を返してください。
    ネットスラングを使い、誰か特定のレスに噛み付いても構いません。
    """

    messages = [
        {"role": "system", "content": agent['system']},
        {"role": "user", "content": context}
    ]
    
    output = llm.create_chat_completion(messages=messages, max_tokens=150, temperature=0.8)
    return output['choices'][0]['message']['content']

# --- メイン処理 ---
def main():
    os.makedirs("./data", exist_ok=True)
    agents = {aid: load_agent(aid) for aid in AGENT_IDS}
    
    print("=== 三国志BBS 稼働開始 ===")

    while True:
        threads = load_json(DATA_FILE)
        if not isinstance(threads, list): threads = []
        
        # 行動決定（スレ立て 20% / レス 80%）
        # ただしスレがゼロなら強制スレ立て
        action = "new_thread" if not threads or random.random() < 0.2 else "res"
        
        agent_id = random.choice(AGENT_IDS)
        agent = agents[agent_id]
        
        if action == "new_thread":
            print(f"\n🆕 スレ立て中... ({agent['name']})")
            title, body = create_thread(agent)
            
            new_thread = {
                "id": int(time.time()), # IDはタイムスタンプ
                "title": title,
                "author": agent['name'],
                "icon": agent.get("icon", ""),
                "body": body,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "responses": []
            }
            threads.insert(0, new_thread) # 最新を先頭に
            # 古いスレ消す（最大10件）
            if len(threads) > 10: threads.pop()
            
            print(f"タイトル: {title}")
            
        else:
            # ランダムなスレを選んでレス
            target_thread = random.choice(threads)
            print(f"\n💬 レス作成中... ({agent['name']} -> {target_thread['title']})")
            
            res_content = create_response(agent, target_thread)
            
            new_res = {
                "name": agent['name'],
                "icon": agent.get("icon", ""),
                "content": res_content,
                "timestamp": datetime.datetime.now().strftime("%H:%M")
            }
            target_thread['responses'].append(new_res)
            print(f"内容: {res_content}")

        # 保存と同期
        save_json(DATA_FILE, threads)
        
        # Git Push
        try:
            subprocess.run(["git", "add", DATA_FILE], check=True)
            subprocess.run(["git", "commit", "-m", "update: BBS更新"], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("✅ GitHub同期完了")
        except:
            pass

        print("💤 休憩 (30s)...")
        time.sleep(3600)

if __name__ == "__main__":
    main()