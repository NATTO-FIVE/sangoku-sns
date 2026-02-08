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

# --- 議論の質を高める「高尚なテーマ」リスト ---
TOPICS = [
    "「血筋」と「能力」、乱世で重要なのはどちらか？",
    "「徳」による統治は偽善か、それとも真理か？",
    "裏切りは戦略として許容されるべきか？",
    "リーダーに必要なのは「恐怖」か「愛」か？",
    "100万の兵より1人の天才軍師の方が価値があるか？",
    "平和のためなら、多少の犠牲（虐殺）は正当化されるか？",
    "酒は百薬の長か、身を滅ぼす毒か？（孫権・郭嘉用）",
    "「運」も実力のうちか、それともただの確率か？",
    "死後の名誉に意味はあるか？",
    "組織において「古参」と「新参」、どちらを重用すべきか？"
]

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

# --- テキスト浄化 ---
def clean_text(text):
    # 余計な思考プロセスや引用を削除
    text = re.sub(r'【.*?】', '', text) # 【思考】などを消す
    text = re.sub(r'スレタイ[:：].*', '', text)
    text = re.sub(r'>>\d+.*', '', text)
    if "：" in text:
        text = text.split("：")[-1]
    return text.strip()

# --- 生成ロジック（思考ステップ導入版） ---

def create_thread(agent):
    topic = random.choice(TOPICS)
    
    # 思考誘導プロンプト
    prompt = f"""
    あなたは「{agent['name']}」として、以下のテーマについて深い議論を提起してください。
    
    テーマ: {topic}
    あなたの性格: {agent['system']}
    
    【指令】
    単なる感想ではなく、あなたの「哲学」や「信念」に基づいた強い主張（問題提起）を行ってください。
    読者を挑発するような内容が望ましいです。
    
    【出力形式】
    JSON形式のみ出力（余計な前置き禁止）:
    {{
        "title": "【議論】などのタグをつけた、刺激的なタイトル",
        "body": "あなたの主張（100文字〜150文字程度）"
    }}
    """
    
    messages = [{"role": "user", "content": prompt}]

    try:
        output = llm.create_chat_completion(messages=messages, max_tokens=400, temperature=0.8)
        content = output['choices'][0]['message']['content']
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return data['title'], data['body']
        else:
            return f"【議論】{topic}について", "議論しようぜ。"
    except Exception as e:
        print(f"⚠️ 生成エラー: {e}")
        return "【悲報】思考回路停止", "エラー発生。"

def create_response(agent, thread):
    # 文脈：スレタイ + >>1 + 最新レス3つ（流れを読ませる）
    context = f"【議題】{thread['title']}\n【提唱者】{thread['body']}\n"
    
    recent_responses = thread['responses'][-3:]
    if recent_responses:
        context += "【直近の議論】\n"
        for res in recent_responses:
            context += f"- {res['name']}: {res['content']}\n"
    
    # ここが重要：AIに「役割」と「議論の目的」を叩き込む
    prompt = f"""
    あなたは「{agent['name']}」です。
    あなたの性格・哲学: {agent['system']}
    
    現在は、以下の議題について激論が交わされています。
    
    {context}
    
    【指令】
    1. 直前の発言者の主張を分析し、あなたの哲学と「対立」するか「同意」するか判断してください。
    2. 単なる相槌（「そうですね」等）は禁止です。必ず「理由」や「歴史的背景」、「独自の視点」を加えて論破または補強してください。
    3. 自分の経験（過去の戦いや政策）を例に出すとより良いです。
    4. 口調はキャラ設定を厳守してください。
    
    短いレス（100文字前後）を書きなさい。返信先へのアンカー等は不要です。
    """

    messages = [{"role": "user", "content": prompt}]
    
    output = llm.create_chat_completion(
        messages=messages,
        max_tokens=200, # 少し長めに許容
        temperature=0.75 # 創造性を少し下げて論理性を高める
    )
    
    raw_content = output['choices'][0]['message']['content']
    return clean_text(raw_content)

# --- メインループ ---
def main():
    os.makedirs("./data", exist_ok=True)
    agents = {}
    for aid in AGENT_IDS:
        a = load_agent(aid)
        if a: agents[aid] = a
    
    print("=== 三国志BBS (Debate Mode) 稼働開始 ===")

    while True:
        threads = load_json(DATA_FILE)
        if not isinstance(threads, list): threads = []
        
        # スレ立て判定 (20%) or レス (80%)
        action = "new_thread" if not threads or random.random() < 0.2 else "res"
        
        agent_id = random.choice(AGENT_IDS)
        agent = agents[agent_id]
        
        if action == "new_thread":
            print(f"\n🆕 議論開始 ({agent['name']})")
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
            if len(threads) > 10: threads.pop()
            
        else:
            target_thread = random.choice(threads)
            
            # 連続投稿防止
            if target_thread['responses'] and target_thread['responses'][-1]['name'] == agent['name']:
                continue

            print(f"\n💬 論客登場 ({agent['name']} -> {target_thread['title']})")
            res_content = create_response(agent, target_thread)
            print(f"発言: {res_content}")
            
            new_res = {
                "name": agent['name'],
                "icon": agent.get("icon", ""),
                "content": res_content,
                "timestamp": datetime.datetime.now().strftime("%H:%M")
            }
            target_thread['responses'].append(new_res)

        save_json(DATA_FILE, threads)
        
        try:
            subprocess.run(["git", "add", DATA_FILE], check=True)
            subprocess.run(["git", "commit", "-m", "update: 議論進行"], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("✅ GitHub同期完了")
        except:
            pass

        # テスト確認用に一旦60秒。満足したら3600に戻してくれ。
        wait_time = 60 
        print(f"💤 思考整理中 ({wait_time}s)...")
        time.sleep(wait_time)

if __name__ == "__main__":
    main()