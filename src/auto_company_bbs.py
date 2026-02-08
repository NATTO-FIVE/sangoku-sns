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
SLEEP_TIME = 60 

AGENT_IDS = ["cao_cao", "liu_bei", "sun_quan", "zhou_yu", "zhuge_liang", "guo_jia", "sima_yi"]

# ランダムなお題
AUTO_TOPICS = [
    "【悲報】オフィスのエアコンが設定温度28度固定になる",
    "【通達】来月から週休0日制を導入します（by CEO）",
    "【事故】サーバー室で誰かがカップ麺こぼした",
    "【目撃】社長が経費で高級車（フェラーリ）買ってた件",
    "【募集】デスマーチに耐えられる新人（給与は夢払い）",
    "【議論】Windows vs Mac 戦争、決着つかず",
    "【速報】女子トイレがずっと埋まっている",
    "【相談】上司のパワハラ音声を録音しました",
    "【朗報】今月の給料、現物支給（米5kg）",
    "【質問】魏グループへの転職ってどうなの？ブラック？",
    "【愚痴】飲み会が多すぎて肝臓が悲鳴を上げている",
    "【炎上】公式SNSが誤爆して大荒れｗｗｗ"
]

print("--- 🧠 全自動・企業戦士AI (Ver.2.0) 起動 ---")
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
    if "：" in text: text = text.split("：")[-1]
    return text.strip()

# --- 生成ロジック ---

def create_thread(agent):
    topic = random.choice(AUTO_TOPICS)
    
    prompt = f"""
    あなたは「{agent['name']}」です。
    役割: {agent['system']}
    
    【指令】
    社内SNS（掲示板）に新しいスレッドを立ててください。
    お題: 「{topic}」
    
    上記のお題について、あなたの立場から愚痴、または自慢を書いてください。
    タイトルは【】タグを使い、本文はネットスラングを交えて少し具体的に（50文字程度）書いてください。
    
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
            return f"【話題】{topic}", "みんな聞いてくれ。"
    except:
        return f"【話題】{topic}", "..."

def create_response(agent, thread):
    # 文脈をリッチにする
    context = f"スレタイ：{thread['title']}\n本文：{thread['body']}\n"
    
    # 直前の発言者を取得（アンカー用）
    last_res = thread['responses'][-1] if thread['responses'] else None
    
    if last_res:
        target_name = last_res['name']
        target_content = last_res['content']
        target_info = f"直前の発言（{target_name}）：{target_content}"
    else:
        target_name = thread['author']
        target_content = thread['body']
        target_info = f"スレ主（{target_name}）：{target_content}"
    
    prompt = f"""
    あなたは「{agent['name']}」です。
    役割: {agent['system']}
    
    社内掲示板で、以下の発言に対してレス（返信）をしてください。
    
    【ターゲット】
    {target_info}
    
    【指令】
    1. 相手の発言内容を具体的に拾って、反論またはツッコミを入れてください。
    2. 単なる口癖（「仕様です」「コンプラ違反」など一言だけ）は禁止。
    3. 「なぜそう思うか」を一言付け加えて、文章（20文字〜40文字）にしてください。
    4. 相手の名前（{target_name}）を呼んでも構いません。
    5. ネットスラング（草、ｗ、それな）を適度に使ってください。
    
    【回答】
    レスの内容だけを出力してください。
    """
    
    messages = [{"role": "user", "content": prompt}]
    
    # 温度を少し上げて(0.85)バラつきを出す
    output = llm.create_chat_completion(messages=messages, max_tokens=150, temperature=0.85)
    return clean_text(output['choices'][0]['message']['content'])

def git_sync():
    try:
        subprocess.run(["git", "add", DATA_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "update: 社内BBS"], check=True)
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
    
    print("\n=== 🏢 三国ホールディングス 全自動稼働モード (Ver.2) ===")

    while True:
        author_id = random.choice(AGENT_IDS)
        author = agents[author_id]
        
        print(f"\n🆕 {author['name']} が新しいスレを立てています...")
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
        
        print(f"📌 タイトル: {title}")
        print(f"📝 本文: {body}")
        
        # レス数もランダムに変動
        res_count = random.randint(4, 8)
        print(f"💬 {res_count}件のレスバトルを開始します...")
        
        # 参加者リスト（自分以外）
        potential_responders = [aid for aid in AGENT_IDS if aid != author_id]
        
        for i in range(res_count):
            responder_id = random.choice(potential_responders)
            responder = agents[responder_id]
            
            # 直前の人が自分ならスキップ（連投防止）
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
            print(f"   {responder['name']}: {res_content}")
            
            time.sleep(2)

        save_json(DATA_FILE, threads)
        git_sync()
        
        print(f"\n💤 {SLEEP_TIME}秒 休憩中...")
        time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    main()