import json
import time
import datetime
import subprocess
import os
import random
import re
from llama_cpp import Llama

# --- 設定 ---
MODEL_PATH = "./models/qwen2.5-3b-instruct-q4_k_m.gguf"
AGENTS_DIR = "./src/agents/"
DATA_FILE = "./data/threads.json"

AGENT_IDS = ["cao_cao", "liu_bei", "sun_quan", "zhou_yu", "zhuge_liang", "guo_jia", "sima_yi"]

# ランダム用ネタ（入力がない時用）
BACKUP_TOPICS = [
    "【悲報】オフィスのエアコンが壊れる",
    "【通達】来月から週休0日制を導入します（by CEO）",
    "【事故】サーバー室でカップ麺こぼした",
    "【目撃】社長が経費で高級車買ってた件",
    "【募集】デスマーチに耐えられる新人",
    "【議論】Windows vs Mac 戦争",
    "【速報】トイレがずっと埋まっている",
]

print("--- 🧠 企業戦士AIを起動中 ---")
llm = Llama(
    model_path=MODEL_PATH,
    n_gpu_layers=-1,
    n_ctx=4096,
    verbose=False
)

def load_json(path):
    if not os.path.exists(path): return []
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_agent(agent_id):
    path = f"{AGENTS_DIR}{agent_id}.json"
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

def clean_text(text):
    text = re.sub(r'【.*?】', '', text)
    text = re.sub(r'スレタイ[:：].*', '', text)
    if "：" in text: text = text.split("：")[-1]
    return text.strip()

# --- 生成ロジック ---

def create_thread(agent, user_topic=None):
    # ユーザー入力があればそれを優先、なければランダム
    topic = user_topic if user_topic else random.choice(BACKUP_TOPICS)
    
    prompt = f"""
    あなたは「{agent['name']}」です。
    役割: {agent['system']}
    
    【指令】
    社内SNS（掲示板）にスレッドを立ててください。
    話題: 「{topic}」
    
    上記の話題について、あなたの立場（CEO、社畜、監査など）から、
    【悲報】や【通達】などのタグを付けたタイトルと、短い本文を作成してください。
    
    【出力形式】
    JSONのみ:
    {{
        "title": "タイトル",
        "body": "本文"
    }}
    """
    
    messages = [{"role": "user", "content": prompt}]
    try:
        output = llm.create_chat_completion(messages=messages, max_tokens=300, temperature=0.9)
        content = output['choices'][0]['message']['content']
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return data['title'], data['body']
        else:
            return f"【話題】{topic}", "どう思う？"
    except:
        return f"【話題】{topic}", "みんな聞いてくれ。"

def create_response(agent, thread):
    context = f"スレタイ：{thread['title']}\n本文：{thread['body']}\n"
    for res in thread['responses'][-3:]:
        context += f"{res['name']}：{res['content']}\n"
    
    prompt = f"""
    あなたは「{agent['name']}」です。
    役割: {agent['system']}
    
    社内掲示板の以下の流れに、短いレス（反応）を返してください。
    
    {context}
    
    【ルール】
    ・ビジネス用語、ネットスラングを多用。
    ・立場（上司・部下・外注）を意識した発言。
    ・前の文の繰り返し禁止。
    """
    
    messages = [{"role": "user", "content": prompt}]
    output = llm.create_chat_completion(messages=messages, max_tokens=150, temperature=0.8)
    return clean_text(output['choices'][0]['message']['content'])

def git_sync():
    try:
        subprocess.run(["git", "add", DATA_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "update: 社内BBS"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("✅ 社内報を更新しました（GitHub同期完了）")
    except:
        pass

# --- メインループ（インタラクティブ版） ---
def main():
    os.makedirs("./data", exist_ok=True)
    agents = {aid: load_agent(aid) for aid in AGENT_IDS}
    
    print("\n=== 🏢 三国ホールディングス 社内掲示板システム ===")
    print("神（あなた）の入力を待っています...\n")

    while True:
        # ユーザー入力を待つ
        user_input = input("🎤 ネタを投下してください (Enterのみでランダム生成): ").strip()
        
        # スレ主をランダム決定
        author_id = random.choice(AGENT_IDS)
        author = agents[author_id]
        
        # スレ立て
        print(f"\n🆕 {author['name']} がスレを立てています...")
        title, body = create_thread(author, user_input)
        
        # データ保存
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
        
        print(f"📌 タイトル: {title}")
        print(f"📝 本文: {body}")
        
        # レスを5〜7個自動生成
        res_count = random.randint(5, 7)
        print(f"\n💬 {res_count}件のクソリプが届いています...")
        
        # スレ主以外のメンバーからランダムに選出
        potential_responders = [aid for aid in AGENT_IDS if aid != author_id]
        
        for i in range(res_count):
            responder_id = random.choice(potential_responders)
            responder = agents[responder_id]
            
            res_content = create_response(responder, new_thread)
            
            new_res = {
                "name": responder['name'],
                "icon": responder.get("icon", ""),
                "content": res_content,
                "timestamp": datetime.datetime.now().strftime("%H:%M")
            }
            new_thread['responses'].append(new_res)
            print(f"   {responder['name']}: {res_content}")
            
            # 少しウェイトを入れるとそれっぽい
            time.sleep(1)

        # 保存と同期
        save_json(DATA_FILE, threads)
        git_sync()
        
        print("\n✨ 議論終了。次のネタをどうぞ。")

if __name__ == "__main__":
    main()