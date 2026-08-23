from datetime import datetime
import json
import os
import shutil
import subprocess
import time  # 💡 timeモジュールを追加しました
from fetchers.arxiv import fetch_arxiv
from fetchers.github_trending import fetch_github_trending
from fetchers.hacker_news import fetch_hacker_news
from fetchers.huggingface import fetch_huggingface_papers
from generators.curator import select_best_items
from generators.generate_x_posts import run_stage1
from generators.refiner import refine_to_x_post
from generators.reviewer import review_and_edit_post

HISTORY_FILE = "output/seen_urls.json"
HISTORY_BAK = "output/seen_urls.json.bak"


def backup_history():
  if os.path.exists(HISTORY_FILE):
    shutil.copy2(HISTORY_FILE, HISTORY_BAK)


def load_history():
  if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
      try:
        return set(json.load(f))
      except json.JSONDecodeError:
        return set()
  return set()


def save_history(history_set):
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
  except Exception as e:
    print(f"Error fetching Hacker News: {e}")

  try:
    arxiv_items = fetch_arxiv(category="cs.AI", limit=10)
    all_items.extend(arxiv_items)
    print(f"- Fetched {len(arxiv_items)} items from arXiv (cs.AI)")
  except Exception as e:
    print(f"Error fetching arXiv: {e}")

  try:
    gh_items = fetch_github_trending(limit=10)
    all_items.extend(gh_items)
    print(f"- Fetched {len(gh_items)} items from GitHub Trending")
  except Exception as e:
    print(f"Error fetching GitHub Trending: {e}")

  try:
    hf_items = fetch_huggingface_papers(limit=10)
    all_items.extend(hf_items)
    print(f"- Fetched {len(hf_items)} items from Hugging Face Papers")
  except Exception as e:
    print(f"Error fetching Hugging Face Papers: {e}")

  print(f"Total fetched items combined: {len(all_items)}")

  backup_history()
  posted_history = load_history()
  candidate_items = []

  for item in all_items:
    item_id = item.get("link") or item.get("url") or item.get("title")
    if not item_id:
      continue
    if item_id not in posted_history:
      candidate_items.append(item)

  print(
      f"🔍 After duplication check: {len(candidate_items)} new candidate items"
      " to process."
  )
  if not candidate_items:
    print("ℹ️ No new items to process. Exiting.")
    return

  curated_items = select_best_items(candidate_items, max_select=8)
  print(
      f"🎯 After Qwen curation: {len(curated_items)} items selected for"
      " generation."
  )

  for item in curated_items:
    item_id = item.get("link") or item.get("url") or item.get("title")
    if item_id:
      posted_history.add(item_id)

  output_dir = "output"
  raw_dir = os.path.join(output_dir, "raw")
  os.makedirs(raw_dir, exist_ok=True)
  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

  print("\nStep 3: Generating detailed tech summaries (Stage 1 - Qwen)...")
  stage1_filename = f"output_prex_posts_{timestamp}.md"
  run_stage1(curated_items, raw_dir, filename=stage1_filename)

  latest_summaries_path = os.path.join(raw_dir, stage1_filename)
  if not os.path.exists(latest_summaries_path):
    print("ℹ️ No summaries generated.")
    return

  with open(latest_summaries_path, "r", encoding="utf-8") as f:
    raw_content = f.read()

  summaries = [
      s.strip() for s in raw_content.split("\n\n---\n\n") if s.strip()
  ]
  if not summaries:
    print("ℹ️ No content to refine.")
    return

  print(
      f"\nStep 4: Refining {len(summaries)} summaries into professional X posts"
      " (Stage 2 - gemma4:12b & Qwen Review)..."
  )
  refined_posts = []
  for i, summary in enumerate(summaries, 1):
    print(f"[{i}/{len(summaries)}] Generating draft with gemma4:12b...")
    gemma_draft = refine_to_x_post(summary)

    print(f"[{i}/{len(summaries)}] Reviewing & editing with Qwen...")
    final_post = review_and_edit_post(gemma_draft, summary)

    refined_posts.append(final_post)

    # 💡 変更点: ループの合間に3秒のウェイトを挿入（必要に応じて秒数は変更可能）
    if i < len(summaries):
      print("⏳ Cooling down for 3 seconds before the next item...")
      time.sleep(3)

  final_content = "\n\n---\n\n".join(refined_posts)

  timestamped_file = os.path.join(output_dir, f"output_x_posts_{timestamp}.md")

  with open(timestamped_file, "w", encoding="utf-8") as f:
    f.write(final_content)

  save_history(posted_history)

  print(f"\n💾 Updated history file with curated items.")
  print(f"💾 Saved Stage 1 prex to `{latest_summaries_path}`")
  print(f"💾 Saved Stage 2 x posts to `{timestamped_file}`")

  print("\n✅ Part A completed! Please review the Markdown files.")
  print("👉 If OK, run `part_b_publish.py` to schedule and sync.")
  print("👉 If you want to tune and retry, run `rollback_part_a.py` first.")


if __name__ == "__main__":
  main()