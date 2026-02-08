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
PUSH_INTERVAL = 60

# 参加者
AGENT_IDS = ["cao_cao", "liu_bei", "sun_quan", "zhou_yu", "zhuge_liang", "guo_jia", "sima_yi"]

# スレ立て用のお題
TOPICS = [
    "部下の失敗談", "上司への愚痴", "三国一の美女・美男子議論", 
    "最近食べた美味しいもの", "軍事作戦の裏話", "魏・呉・蜀の七不思議",
    "最近の若者について", "老害について", "お金がない時の対処法",
    "効果的な人材採用ハック", "処世術・生き残り方"
]

# --- 脳の準備 ---
print("--- 🧠 脳を起動中 ---")
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
    if not os.path.exists(path): return None
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

# --- 生成ロジック（改良版） ---

def clean_text(text):
    """
    AIが前の文脈を繰り返してしまった場合、それを削除する。
    「>>1」や「スレタイ」などが含まれていたら、それ以降だけを抽出する。
    """
    # 自分の発言（"："以降）だけを取り出す工夫
    if "：" in text:
        text = text.split("：")[-1]
    
    # 余計な記号削除
    text = text.replace(">>1", "").replace("スレタイ", "").strip()
    return text

def create_thread(agent):
    topic = random.choice(TOPICS)
    
    # プロンプトを強力にする
    prompt = f"""
    あなたは「{agent['name']}」です。以下の性格になりきってください。
    性格: {agent['system']}
    
    【指令】
    掲示板「三国志BBS」に、テーマ「{topic}」で新しいスレッドを立ててください。
    
    【出力形式】
    JSON形式のみ出力してください。余計な前置きは不要です。
    {{
        "title": "【悲報】などのキャッチーなタイトル",
        "body": "あなたの口調で書かれた、短く面白い本文（80文字以内）"
    }}
    """
    
    messages = [{"role": "user", "content": prompt}]

    try:
        output = llm.create_chat_completion(messages=messages, max_tokens=300, temperature=0.9)
        content = output['choices'][0]['message']['content']
        # JSON抽出
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return data['title'], data['body']
        else:
            return "【悲報】通信エラー", "すまん、電波が悪くて書き込めなかったわ。"
    except Exception as e:
        print(f"⚠️ 生成エラー: {e}")
        return "【悲報】APIエラー", "サーバーが落ちたみたいだ。"

def create_response(agent, thread):
    # 文脈を絞る（全部渡すと混乱するため）
    # スレタイ + >>1 + (あれば)直前のレス1つだけ
    context = f"スレタイ：{thread['title']}\n>>1：{thread['body']}\n"
    
    last_res = thread['responses'][-1] if thread['responses'] else None
    if last_res:
        context += f"直前の書き込み（{last_res['name']}）：{last_res['content']}\n"
    
    # プロンプト（キャラ強制と重複禁止）
    prompt = f"""
    あなたは「{agent['name']}」です。
    性格: {agent['system']}
    
    【現在の掲示板の状況】
    {context}
    
    【指令】
    上記の流れを見て、あなたのキャラクターとして短いコメント（レス）を書きなさい。
    
    【禁止事項】
    ・丁寧語は禁止（キャラの設定に従うこと）。
    ・前の文章（スレタイや他人の発言）を繰り返してはいけません。
    ・「スレタイ」などの単語を含めないでください。
    ・回答だけをズバリ出力してください。
    """

    messages = [{"role": "user", "content": prompt}]
    
    output = llm.create_chat_completion(
        messages=messages,
        max_tokens=100, # 短く制限
        temperature=0.85 # 少し創造性を上げる
    )
    
    raw_content = output['choices'][0]['message']['content']
    return clean_text(raw_content)

# --- メイン処理 ---
def main():
    os.makedirs("./data", exist_ok=True)
    agents = {}
    for aid in AGENT_IDS:
        a = load_agent(aid)
        if a: agents[aid] = a
    
    print("=== 三国志BBS (Reboot) 稼働開始 ===")

    while True:
        threads = load_json(DATA_FILE)
        if not isinstance(threads, list): threads = []
        
        # スレ立て判定 (20%) or レス (80%)
        action = "new_thread" if not threads or random.random() < 0.2 else "res"
        
        # ランダムなエージェント
        agent_id = random.choice(AGENT_IDS)
        agent = agents[agent_id]
        
        if action == "new_thread":
            print(f"\n🆕 スレ立て ({agent['name']})")
            title, body = create_thread(agent)
            
            new_thread = {
                "id": int(time.time()),
                "title": title,
                "author": agent['name'],
                "icon": agent.get("icon", ""),
                "body": body,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "responses": []
            }
            threads.insert(0, new_thread)
            if len(threads) > 10: threads.pop() # 古いスレ削除
            
        else:
            target_thread = random.choice(threads)
            print(f"\n💬 レス ({agent['name']} -> {target_thread['title']})")
            
            # 直前の人が自分なら連続投稿しない（1回スキップ）
            if target_thread['responses'] and target_thread['responses'][-1]['name'] == agent['name']:
                print("自分のレスの直後なのでスキップ")
                continue

            res_content = create_response(agent, target_thread)
            print(f"内容: {res_content}")
            
            new_res = {
                "name": agent['name'],
                "icon": agent.get("icon", ""),
                "content": res_content,
                "timestamp": datetime.datetime.now().strftime("%H:%M")
            }
            target_thread['responses'].append(new_res)

        # 保存
        save_json(DATA_FILE, threads)
        
        # Git同期
        try:
            subprocess.run(["git", "add", DATA_FILE], check=True)
            subprocess.run(["git", "commit", "-m", "update: BBS"], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("✅ GitHub同期完了")
        except:
            pass

        # 休憩時間（テスト用に短くしても良いが、運用は長く）
        wait_time = 30 #3600 
        print(f"💤 休憩 ({wait_time}s)...")
        time.sleep(wait_time)

if __name__ == "__main__":
    main()