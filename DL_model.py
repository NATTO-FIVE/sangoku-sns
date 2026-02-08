from huggingface_hub import hf_hub_download
import os

print("🚀 ダウンロードを開始します...")

# 保存先フォルダを作成
os.makedirs("models", exist_ok=True)

# 確実に存在するリポジトリとファイル名に変更しました
# Repo: bartowski/Qwen2.5-7B-Instruct-GGUF
# File: Qwen2.5-7B-Instruct-Q4_K_M.gguf
try:
    model_path = hf_hub_download(
        repo_id="bartowski/Qwen2.5-7B-Instruct-GGUF",
        filename="Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        local_dir="models",
        local_dir_use_symlinks=False
    )
    print(f"✅ ダウンロード完了！場所: {model_path}")
    
    # 元のプログラムで使いやすいように、小文字の名前にリネームしておきます
    old_path = os.path.join("models", "Qwen2.5-7B-Instruct-Q4_K_M.gguf")
    new_path = os.path.join("models", "qwen2.5-7b-instruct-q4_k_m.gguf")
    
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        print(f"🔄 ファイル名をリネームしました: {new_path}")

except Exception as e:
    print(f"❌ エラーが発生しました: {e}")