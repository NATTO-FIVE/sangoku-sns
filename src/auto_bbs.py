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

# --- 史実ネタ・ゴシップネタの種 ---
# ここをランダムに選んで、さらにAIに膨らませさせる
TOPICS = [
    "【実況】官渡の戦い、袁紹軍の兵糧庫が燃えてる件ｗｗｗ",
    "【悲報】赤壁の戦い、火力が強すぎてワロタ",
    "【疑問】曹操ってサイコパスすぎない？",
    "【相談】上司（劉備）がまた泣き出したんだが...",
    "【目撃】呂布がまた裏切ってるぞｗｗｗ",
    "【朗報】諸葛亮の「空城の計」、マジで誰もいなくて草",
    "【愚痴】孫権様がまた机の角を斬った件について",
    "【議論】三国一のイケメンは周瑜で確定な",
    "【速報】関羽、顔が赤すぎる",
    "【悲報】魏の給料、まだ振り込まれてない",
    "【特定】「鶏肋」とか言ったやつの住所特定したわ",
    "【実況】長坂の戦い、張飛が橋の上で仁王立ちしてるｗｗｗ"
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

def clean_text(text):
    text = re.sub(r'【.*?】', '', text) 
    text = re.sub(r'スレタイ[:：].*', '', text)
    text = re.sub(r'>>\d+.*', '', text)
    if "：" in text:
        text = text.split("：")[-1]
    return text.strip()

# --- 生成ロジック ---

def create_thread(agent):
    # ネタをランダムに選ぶ
    base_topic = random.choice(TOPICS)
    
    prompt = f"""
    あなたは「{agent['name']}」です。
    性格: {agent['system']}
    
    【指令】
    ネット掲示板（2ちゃんねる風）にスレッドを立ててください。
    ネタ: 「{base_topic}」
    
    上記のネタを元に、あなたの視点で少しアレンジしたタイトルと、短い本文(1行〜2行)を書いてください。
    史実を「今起きていること」として実況するか、現代風のゴシップとして語ってください。
    
    【出力形式】
    JSON形式のみ出力:
    {{
        "title": "【悲報】などのタグ付きタイトル",
        "body": "本文（ネットスラング推奨）"
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
            return base_topic, "これマジ？"
    except:
        return base_topic, "誰か詳しく教えてくれ。"

def create_response(agent, thread):
    context = f"スレタイ：{thread['title']}\n>>1：{thread['body']}\n"
    
    # 直近のレス（流れを読む）
    recent = thread['responses'][-2:]
    for res in recent:
        context += f"{res['name']}：{res['content']}\n"
    
    prompt = f"""
    あなたは「{agent['name']}」です。
    性格: {agent['system']}
    
    このスレッドに、短いレス（反応）を返してください。
    
    【状況】
    {context}
    
    【ルール】
    ・「史実の出来事」を「今起きているネタ」として扱ってください。
    ・ネットスラング（草、ｗ、嘘松、特定した）を使ってください。
    ・前の文章のコピペ禁止。
    ・1行でズバッと言い切る。
    """

    messages = [{"role": "user", "content": prompt}]
    
    output = llm.create_chat_completion(messages=messages, max_tokens=100, temperature=0.85)
    return clean_text(output['choices'][0]['message']['content'])

# --- メインループ ---
def main():
    os.makedirs("./data", exist_ok=True)
    agents = {}
    for aid in AGENT_IDS:
        a = load_agent(aid)
        if a: agents[aid] = a
    
    print("=== 三国志BBS (Realtime Live Mode) ===")

    while True:
        threads = load_json(DATA_FILE)
        if not isinstance(threads, list): threads = []
        
        # --- 行動判定ロジックの変更 ---
        # 1. スレがまだ無いなら作る
        # 2. 最新スレのレスが5件以上なら、強制的に新スレを作る（話題を変える）
        # 3. それ以外なら、30%で新スレ、70%でレス
        
        latest_thread = threads[0] if threads else None
        
        if not threads:
            action = "new_thread"
        elif len(latest_thread['responses']) >= 5:
            action = "new_thread"
        elif random.random() < 0.3:
            action = "new_thread"
        else:
            action = "res"
        
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
            if len(threads) > 10: threads.pop()
            
        else:
            # 最新のスレにレスする（古いスレは過去ログ扱い）
            target_thread = threads[0] 
            
            # 連続投稿防止
            if target_thread['responses'] and target_thread['responses'][-1]['name'] == agent['name']:
                continue

            print(f"\n💬 レス ({agent['name']} -> {target_thread['title']})")
            res_content = create_response(agent, target_thread)
            print(f"内容: {res_content}")
            
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
            subprocess.run(["git", "commit", "-m", "update: BBS"], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("✅ GitHub同期完了")
        except:
            pass

        # テスト確認用に60秒。満足したら3600に戻してくれ。
        wait_time = 60 
        print(f"💤 待機中 ({wait_time}s)...")
        time.sleep(wait_time)

if __name__ == "__main__":
    main()