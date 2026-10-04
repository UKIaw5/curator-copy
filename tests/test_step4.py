import os
import glob
from generators.refiner import refine_to_x_post

# Qwenレビューを有効化（Falseにするとレビューを実行します）
SKIP_QWEN_REVIEW = False

def review_with_qwen(draft_post: str) -> str:
    if SKIP_QWEN_REVIEW:
        return draft_post

    import requests
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
    # モデル名を qwen2.5-coder:14b に変更
    qwen_model = os.getenv("QWEN_MODEL", "qwen2.5-coder:14b")

    prompt = f"以下のX投稿案を確認し、誤字脱字や不自然な日本語があれば修正してください。問題なければそのまま出力してください。\n\n{draft_post}"
    
    payload = {
        "model": qwen_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }

    try:
        # タイムアウトを300秒に戻し、巨大モデルのロード・推論時間を確保
        res = requests.post(OLLAMA_URL, json=payload, timeout=300)
        res.raise_for_status()
        reviewed = res.json().get("message", {}).get("content", "").strip()
        return reviewed if reviewed else draft_post
    except Exception as e:
        print(f"⚠️ Review error: {e}. Keeping original Gemma draft.")
        return draft_post

def main():
    input_files = sorted(glob.glob("output/raw/output_prex_posts_*.md"))
    if not input_files:
        print("❌ No input files found.")
        return
        
    latest_file = input_files[-1]
    print(f"📂 Loading: {latest_file}")

    with open(latest_file, "r", encoding="utf-8") as f:
        content = f.read()

    summaries = [
        s.strip() for s in content.split("<<<CURATOR_ITEM_BOUNDARY>>>") if s.strip()
    ]
    print(f"🎯 Summaries detected: {len(summaries)}\n")

    final_posts = []

    for idx, summary in enumerate(summaries, 1):
        print(f"--- [{idx}/{len(summaries)}] Generating draft with Gemma ---")
        gemma_draft = refine_to_x_post(summary)
        print(f"📝 Gemma Draft:\n{gemma_draft}\n")

        if not SKIP_QWEN_REVIEW:
            print("🔍 Reviewing with Qwen (qwen2.5-coder:14b)...")
            final_post = review_with_qwen(gemma_draft)
        else:
            final_post = gemma_draft

        print(f"✨ Final Post:\n{final_post}\n")
        final_posts.append(final_post)

    output_path = "output/latest_x_posts_test.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(final_posts))

    print(f"🎉 Done! Saved to `{output_path}`.")

if __name__ == "__main__":
    main()