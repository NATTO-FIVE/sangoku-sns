import json
import time
from llama_cpp import Llama

# --- 設定 ---
MODEL_PATH = "./models/qwen2.5-3b-instruct-q4_k_m.gguf"
AGENTS_DIR = "./src/agents/"

# 1. モデルのロード（ここが一番重いので最初だけやる）
print("--- 脳を起動中 ---")
llm = Llama(
    model_path=MODEL_PATH,
    n_gpu_layers=-1,
    n_ctx=4096, # 会話が長引くので少し広めに
    verbose=False
)

# 2. 武将データの読み込み関数
def load_agent(agent_id):
    with open(f"{AGENTS_DIR}{agent_id}.json", "r", encoding="utf-8") as f:
        return json.load(f)

# 3. 思考・発言関数
def generate_reply(agent, context_history):
    """
    agent: 武将のJSONデータ
    context_history: これまでの会話ログ [{"role": "user", "content": "..."}, ...]
    """
    
    # プロンプトの構築（ここがミソ）
    # System(人格) + Few-shots(例示) + History(文脈) を結合する
    messages = [{"role": "system", "content": agent["system"]}]
    
    # 例示を注入（Few-shot）
    messages.extend(agent["few_shots"])
    
    # 実際の会話履歴を注入
    # ※ 直近の会話だけ渡す（メモリ節約のため、とりあえず最新5往復分とかにする）
    messages.extend(context_history[-5:]) 

    # 生成実行
    output = llm.create_chat_completion(
        messages=messages,
        max_tokens=200, # 長すぎないように
        temperature=0.7 # 創造性
    )
    
    return output['choices'][0]['message']['content']

# --- メインループ ---
def main():
    # 武将を召喚
    cao = load_agent("cao_cao")
    liu = load_agent("liu_bei")
    
    # 会話の履歴（共有の場）
    # 最初は劉備から話しかけることにする
    history = [
        {"role": "user", "name": liu["name"], "content": "曹公、久しぶりですね。最近の世の中をどう見ておられますか？"}
    ]
    
    print(f"{liu['icon']} {liu['name']}: {history[0]['content']}")

    # 5ターンだけ会話させる
    for i in range(5):
        # --- 曹操のターン ---
        # 曹操から見て、直前の劉備の発言は "user" の発言として扱う
        last_message = history[-1]["content"]
        
        # 履歴をLLM形式（role: user/assistant）に変換して渡す必要がある
        # 簡易的に「相手の言葉」だけを input として渡す
        context = [{"role": "user", "content": last_message}]
        
        reply_text = generate_reply(cao, context)
        
        print(f"\n{cao['icon']} {cao['name']}: {reply_text}")
        
        # 履歴に保存
        history.append({"role": "assistant", "name": cao["name"], "content": reply_text})
        
        # --- 劉備のターン ---
        # 劉備から見て、直前の曹操の発言は "user"
        context = [{"role": "user", "content": reply_text}]
        
        reply_text = generate_reply(liu, context)
        
        print(f"\n{liu['icon']} {liu['name']}: {reply_text}")
        
        history.append({"role": "assistant", "name": liu["name"], "content": reply_text})
        
        time.sleep(1) # 読みやすくするため少し待つ

if __name__ == "__main__":
    main()