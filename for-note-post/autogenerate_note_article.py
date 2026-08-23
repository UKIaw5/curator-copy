# autogenerate_note_article_with_review.py
import os
import shutil
import glob
import json
import requests
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
WRITER_MODEL = "qwen2.5-coder:14b"
REVIEWER_MODEL = "gemma4:12b"
STATUS_FILE = "note_status.json"

def call_llm(model_name: str, prompt: str) -> str:
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 3000}
    }
    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=400)
        res.raise_for_status()
        return res.json().get("response", "").strip()
    except Exception as e:
        print(f"❌ LLM Error ({model_name}): {e}")
        return ""

def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except json.JSONDecodeError: return {}
    return {}

def save_status(data):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_active_raw_file():
    raw_dir = "../output/raw"
    status = load_status()
    raw_files = sorted(
        glob.glob(os.path.join(raw_dir, "output_prex_posts_*.md")),
        key=os.path.getmtime,
        reverse=True
    )
    for latest_file in raw_files:
        basename = os.path.basename(latest_file)
        with open(latest_file, "r", encoding="utf-8") as f:
            items = [s.strip() for s in f.read().split("\n\n---\n\n") if s.strip()]
        if basename not in status:
            status[basename] = {}
        if any(not status[basename].get(str(i), {}).get("note_used", False) for i in range(len(items))):
            return latest_file, items, status
    return None, [], status

def main():
    print("=== Note Article AI Pipeline (Write & Review) ===")
    
    while True:
        latest_file, items, status = get_active_raw_file()
        if not items:
            print("ℹ️ No active raw files found. All items processed!")
            break

        basename = os.path.basename(latest_file)
        available = [(i, t) for i, t in enumerate(items) if not status[basename].get(str(i), {}).get("note_used", False)]

        if not available:
            archive_path = os.path.join("../output/raw/archive_note_used", basename)
            shutil.move(latest_file, archive_path)
            continue

        orig_idx, selected_text = available[0]
        preview = selected_text.split('\n')[0][:70]
        print(f"\n🚀 Processing: (Item #{orig_idx + 1}) {preview}...")

        # Step 1: Writer Agent (Qwen)
        writer_prompt = f"""
You are a professional tech writer. Write a 100-yen paid note article in Japanese based on this English raw data.
Target audience: Japanese developers who want to save time reading English tech news.
Raw Data:
{selected_text}

Structure strictly in Markdown:
1. Catchy Title
2. Free Section (Intro, Overview, What problem it solves)
3. Exactly this line: `--- [NOTE PAID BOUNDARY] ---`
4. Paid Section (Deep dive, Implementation, Original English links)
Output only the markdown.
"""
        print(f"🤖 Step 1: Generating draft with {WRITER_MODEL}...")
        draft = call_llm(WRITER_MODEL, writer_prompt)
        if not draft:
            print("❌ Draft generation failed. Skipping.")
            break

        # Step 2: Reviewer Agent (Gemma)
        reviewer_prompt = f"""
You are a senior tech editor. Review and improve the following draft for a Japanese blog post.
The post uses a "Freemium" model. The free section must hook the reader, and the paid section must deliver technical value.

Draft:
{draft}

Instructions:
1. Make the Title more engaging (suitable for a Twitter post).
2. Enhance the Free Section to build curiosity. Tell them *why* it's amazing.
3. Keep the exact line `--- [NOTE PAID BOUNDARY] ---` untouched.
4. Ensure the Paid Section provides concrete technical value or detailed summaries.
5. Output ONLY the finalized Markdown content in Japanese.
"""
        print(f"🧐 Step 2: Reviewing and polishing with {REVIEWER_MODEL}...")
        final_article = call_llm(REVIEWER_MODEL, reviewer_prompt)
        
        # Fallback in case reviewer fails or removes boundary
        if not final_article or "--- [NOTE PAID BOUNDARY] ---" not in final_article:
            print("⚠️ Reviewer failed or removed boundary. Falling back to original draft.")
            final_article = draft

        os.makedirs("output", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = f"output/note_article_{ts}.md"
        
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(final_article)

        status[basename][str(orig_idx)] = {
            "note_used": True,
            "generated_at": ts,
            "generated_file": out_path,
            "published_to_note": False,
            "published_at": None
        }
        save_status(status)
        print(f"💾 Saved Final Article: {out_path}")

        if all(status[basename].get(str(i), {}).get("note_used", False) for i in range(len(items))):
            shutil.move(latest_file, os.path.join("../output/raw/archive_note_used", basename))
            print(f"📦 Fully consumed. Moved {basename} to archive.")

    print("✅ All batch generation tasks completed successfully!")

if __name__ == "__main__":
    main()