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
DATA_FILE = "./data/posts.json"
PUSH_INTERVAL = 60  # Git Pushの間隔（秒）

# 参加する武将IDリスト
AGENT_IDS = [
    "cao_cao", "liu_bei", "sun_quan", 
    "zhou_yu", "zhuge_liang", "guo_jia", "sima_yi"
]

# --- 1. 脳（モデル）の準備 ---
print("--- 🧠 脳を起動中 ---")
llm = Llama(
    model_path=MODEL_PATH,
    n_gpu_layers=-1,
    n_ctx=4096,
    verbose=False
)

# --- 2. データ管理関数 ---
def load_agent(agent_id):
    path = f"{AGENTS_DIR}{agent_id}.json"
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_posts():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []

def save_post(agent, content, reply_to_id=None):
    posts = load_posts()
    
    new_id = len(posts) + 1
    new_post = {
        "id": new_id,
        "user_id": agent["id"],
        "name": agent["name"],
        "icon": agent.get("icon", ""),
        "content": content,
        "reply_to": reply_to_id, # 誰へのリプか（新規ならNone）
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    posts.append(new_post)
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
        
    return new_post

def git_push():
    print("🚀 GitHubへ同期中...")
    try:
        subprocess.run(["git", "add", DATA_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "update: 武将たちが議論しました"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("✅ 同期完了！")
    except Exception:
        print("⚠️ Pushスキップ（変更なし等）")

# --- 3. 思考ロジック ---
def generate_content(agent, context_type, target_post=None):
    messages = [{"role": "system", "content": agent["system"]}]
    messages.extend(agent["few_shots"])

    # プロンプトの組み立て
    if context_type == "new_topic":
        # 新しい話題を振る場合
        prompt = "SNSのタイムラインに、新しい話題を投稿してください。あなたの性格に基づいた、短めの発言をお願いします。"
    else:
        # リプライの場合
        target_name = target_post['name']
        target_content = target_post['content']
        prompt = f"以下の{target_name}の発言に対して、あなたの立場からリプライ（返信）を送ってください。\n\n【{target_name}の発言】\n{target_content}"

    messages.append({"role": "user", "content": prompt})

    output = llm.create_chat_completion(
        messages=messages,
        max_tokens=150, # 長すぎないように
        temperature=0.8
    )
    return output['choices'][0]['message']['content']

# --- メインループ ---
def main():
    os.makedirs("./data", exist_ok=True)
    
    # 全エージェントをロード
    agents = {}
    for aid in AGENT_IDS:
        a = load_agent(aid)
        if a: agents[aid] = a
    
    if not agents:
        print("❌ 武将ファイルが見つかりません！")
        return

    print(f"=== 三国志AI SNS (参加者: {len(agents)}名) ===")
    
    last_speaker_id = None

    while True:
        # 1. 誰が喋るか決める（直前の人以外からランダム）
        candidates = [aid for aid in AGENT_IDS if aid != last_speaker_id]
        current_id = random.choice(candidates)
        current_agent = agents[current_id]
        
        # 2. 直前の投稿を取得
        posts = load_posts()
        last_post = posts[-1] if posts else None
        
        # 3. 行動決定（新規投稿 or リプライ）
        # 投稿がない場合は必ず新規。それ以外は70%でリプライ
        action_type = "new_topic"
        target_post = None
        
        if last_post:
            if random.random() < 0.7:
                action_type = "reply"
                target_post = last_post
        
        print(f"\nThinking... ({current_agent['name']} -> {action_type})")
        
        # 4. 生成
        content = generate_content(current_agent, action_type, target_post)
        print(f"🗣️ {current_agent['name']}: {content}")
        
        # 5. 保存
        reply_id = target_post['id'] if target_post else None
        save_post(current_agent, content, reply_id)
        
        last_speaker_id = current_id
        
        # 6. Push & 休憩
        git_push()
        
        wait_time = 30
        print(f"💤 休憩中 ({wait_time}s)...")
        time.sleep(wait_time)

if __name__ == "__main__":
    main()