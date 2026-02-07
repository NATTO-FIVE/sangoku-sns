from llama_cpp import Llama

# 1. モデルのロード
# n_gpu_layers=-1 : 全ての層をGPUに載せる（最速設定）
# n_ctx=2048      : 記憶できるトークン数
print("モデルをロード中... (VRAMに展開します)")
llm = Llama(
    model_path="./models/qwen2.5-3b-instruct-q4_k_m.gguf",
    n_gpu_layers=-1, 
    n_ctx=2048,
    verbose=True  # ログを出してGPUが使われているか確認する
)

# 2. 会話の生成
messages = [
    {"role": "system", "content": "あなたは三国志の曹操です。尊大に振る舞ってください。"},
    {"role": "user", "content": "おい、お前は誰だ？名前を言え。"}
]

print("\n--- 生成開始 ---\n")

output = llm.create_chat_completion(
    messages=messages,
    max_tokens=100,  # 短めに返す
    temperature=0.7
)

# 3. 結果表示
print(output['choices'][0]['message']['content'])