import os
import json
import shutil
import subprocess
from datetime import datetime
from fetchers.hacker_news import fetch_hacker_news
from fetchers.arxiv import fetch_arxiv
from fetchers.github_trending import fetch_github_trending
from fetchers.huggingface import fetch_huggingface_papers
from generators.generate_x_posts import run_stage1
from generators.refiner import refine_to_x_post

# 本丸の重複管理ファイル
HISTORY_FILE = "output/seen_urls.json"
HISTORY_BAK = "output/seen_urls.json.bak"

def backup_history():
    """ロールバック用に履歴ファイルをバックアップする"""
    if os.path.exists(HISTORY_FILE):
        shutil.copy2(HISTORY_FILE, HISTORY_BAK)

def load_history():
    """履歴ファイルから過去に処理したURLのリストを読み込む"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()

def save_history(history_set):
    """新しいURLを含めて履歴ファイルを保存する"""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(history_set), f, ensure_ascii=False, indent=4)

def git_pull():
    try:
        print("Step 1: Pulling latest changes from Git...")
        subprocess.run(["git", "pull"], check=False)
    except Exception as e:
        print(f"Git pull warning: {e}")

def main():
    print("=== Starting Daily Curation Pipeline (Part A: Fetch & Refine) ===")
    git_pull()

    print("\nStep 2: Fetching data from multiple sources...")
    all_items = []
    
    try:
        hn_items = fetch_hacker_news(limit=10)
        all_items.extend(hn_items)
        print(f"- Fetched {len(hn_items)} items from Hacker News")
    except Exception as e: print(f"Error fetching Hacker News: {e}")

    try:
        arxiv_items = fetch_arxiv(category="cs.AI", limit=10)
        all_items.extend(arxiv_items)
        print(f"- Fetched {len(arxiv_items)} items from arXiv (cs.AI)")
    except Exception as e: print(f"Error fetching arXiv: {e}")

    try:
        gh_items = fetch_github_trending(limit=10)
        all_items.extend(gh_items)
        print(f"- Fetched {len(gh_items)} items from GitHub Trending")
    except Exception as e: print(f"Error fetching GitHub Trending: {e}")

    try:
        hf_items = fetch_huggingface_papers(limit=10)
        all_items.extend(hf_items)
        print(f"- Fetched {len(hf_items)} items from Hugging Face Papers")
    except Exception as e: print(f"Error fetching Hugging Face Papers: {e}")

    print(f"Total fetched items combined: {len(all_items)}")

    # 🌟 --- 履歴フィルター処理 --- 🌟
    backup_history()  # 新規追加の前に現在の履歴(seen_urls)をバックアップ
    posted_history = load_history()
    new_items = []
    
    for item in all_items:
        item_id = item.get('link') or item.get('url') or item.get('title')
        if not item_id: continue
        if item_id not in posted_history:
            new_items.append(item)
            posted_history.add(item_id)

    print(f"🔍 After duplication check: {len(new_items)} new items to process.")
    if not new_items:
        print("ℹ️ No new items to process. Exiting.")
        return

    output_dir = "output"
    raw_dir = os.path.join(output_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\nStep 3: Generating detailed tech summaries (Stage 1 - Qwen)...")
    stage1_filename = f"output_prex_posts_{timestamp}.md"
    run_stage1(new_items, raw_dir, filename=stage1_filename)

    latest_summaries_path = os.path.join(raw_dir, stage1_filename)
    if not os.path.exists(latest_summaries_path):
        print("ℹ️ No summaries generated.")
        return

    with open(latest_summaries_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    summaries = [s.strip() for s in raw_content.split("\n\n---\n\n") if s.strip()]
    if not summaries:
        print("ℹ️ No content to refine.")
        return

    # Step 4: Refine each summary using Gemma2 professional tone (従来の詳細なループとログを復元)
    print(f"\nStep 4: Refining {len(summaries)} summaries into professional X posts (Stage 2 - Gemma2)...")
    refined_posts = []
    for i, summary in enumerate(summaries, 1):
        print(f"[{i}/{len(summaries)}] Refining summary...")
        post = refine_to_x_post(summary)
        refined_posts.append(post)

    final_content = "\n\n---\n\n".join(refined_posts)

    timestamped_file = os.path.join(output_dir, f"output_x_posts_{timestamp}.md")

    with open(timestamped_file, "w", encoding="utf-8") as f:
        f.write(final_content)

    # 全処理成功後に履歴を保存
    save_history(posted_history)
    
    print(f"\n💾 Updated history file with new items.")
    print(f"💾 Saved Stage 1 prex to `{latest_summaries_path}`")
    print(f"💾 Saved Stage 2 x posts to `{timestamped_file}`")
    
    print("\n✅ Part A completed! Please review the Markdown files.")
    print("👉 If OK, run `part_b_publish.py` to schedule and sync.")
    print("👉 If you want to tune and retry, run `rollback_part_a.py` first.")

if __name__ == "__main__":
    main()