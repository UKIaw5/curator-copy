import os
import json
import subprocess
from datetime import datetime
from fetchers.hacker_news import fetch_hacker_news
from fetchers.arxiv import fetch_arxiv
from fetchers.github_trending import fetch_github_trending
from fetchers.huggingface import fetch_huggingface_papers
from generators.generate_x_posts import run_stage1
from generators.refiner import refine_to_x_post

HISTORY_FILE = "output/history.json"

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

def git_commit_and_push():
    try:
        print("Step 5: Committing and pushing changes to Git...")
        subprocess.run(["git", "add", "."], check=False)
        res = subprocess.run(
            ["git", "commit", "-m", "Auto: Update multi-source (4 sources) prex and x post files"],
            capture_output=True,
            text=True
        )
        if res.returncode == 0:
            print("📦 Changes committed. Pushing to remote...")
            subprocess.run(["git", "push"], check=False)
            print("🚀 Successfully pushed to Git!")
        else:
            print("ℹ️ No changes to commit (working tree clean).")
    except Exception as e:
        print(f"Git sync error: {e}")

def main():
    git_pull()

    print("Step 2: Fetching data from multiple sources (HN, arXiv, GitHub, Hugging Face)...")
    all_items = []
    
    # 1. Hacker News
    try:
        hn_items = fetch_hacker_news(limit=10)
        all_items.extend(hn_items)
        print(f"- Fetched {len(hn_items)} items from Hacker News")
    except Exception as e:
        print(f"Error fetching Hacker News: {e}")

    # 2. arXiv (cs.AI)
    try:
        arxiv_items = fetch_arxiv(category="cs.AI", limit=3)
        all_items.extend(arxiv_items)
        print(f"- Fetched {len(arxiv_items)} items from arXiv (cs.AI)")
    except Exception as e:
        print(f"Error fetching arXiv: {e}")

    # 3. GitHub Trending
    try:
        gh_items = fetch_github_trending(limit=10)
        all_items.extend(gh_items)
        print(f"- Fetched {len(gh_items)} items from GitHub Trending")
    except Exception as e:
        print(f"Error fetching GitHub Trending: {e}")

    # 4. Hugging Face Daily Papers
    try:
        hf_items = fetch_huggingface_papers(limit=10)
        all_items.extend(hf_items)
        print(f"- Fetched {len(hf_items)} items from Hugging Face Papers")
    except Exception as e:
        print(f"Error fetching Hugging Face Papers: {e}")

    print(f"Total fetched items combined: {len(all_items)}")

    # 🌟 --- 履歴フィルター処理 開始 --- 🌟
    posted_history = load_history()
    new_items = []
    
    for item in all_items:
        # fetcherの返り値が辞書であり、'link'または'url'キーを持っている前提
        item_id = item.get('link') or item.get('url') or item.get('title')
        
        if not item_id:
            continue # IDとして使える情報がない場合はスキップ
            
        if item_id not in posted_history:
            new_items.append(item)
            posted_history.add(item_id) # 新規リストに追加

    print(f"🔍 After duplication check: {len(new_items)} new items to process.")

    if not new_items:
        print("ℹ️ No new items to process. Exiting.")
        return
    # 🌟 --- 履歴フィルター処理 終了 --- 🌟

    output_dir = "output"
    raw_dir = os.path.join(output_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("Step 3: Generating detailed tech summaries (Stage 1 - Qwen)...")
    stage1_filename = f"output_prex_posts_{timestamp}.md"
    
    # 💡 all_items ではなく new_items をLLMに渡す
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

    print("Step 4: Refining summaries into edgy viral X posts (Stage 2 - Gemma2)...")
    refined_posts = []
    for summary in summaries:
        x_post = refine_to_x_post(summary)
        refined_posts.append(x_post)

    final_content = "\n\n---\n\n".join(refined_posts)

    timestamped_file = os.path.join(output_dir, f"output_x_posts_{timestamp}.md")

    with open(timestamped_file, "w", encoding="utf-8") as f:
        f.write(final_content)

    # 🎉 全処理が成功した場合のみ履歴を保存する
    save_history(posted_history)
    print(f"💾 Updated history file with new items.")

    print(f"💾 Saved Stage 1 prex to `{latest_summaries_path}`")
    print(f"💾 Saved Stage 2 x posts to `{timestamped_file}`")

    git_commit_and_push()
    print("✅ Pipeline execution completed!")

if __name__ == "__main__":
    main()