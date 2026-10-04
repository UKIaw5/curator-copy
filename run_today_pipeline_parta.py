from datetime import datetime
import glob
import json
import os
import re
import subprocess
import sys
import time

from fetchers.arxiv import fetch_arxiv
from fetchers.github_trending import fetch_github_trending
from fetchers.hacker_news import fetch_hacker_news
from fetchers.huggingface import fetch_huggingface_papers
from generators.curator import select_best_items
from generators.generate_x_posts import run_stage1
from generators.refiner import refine_to_x_post
from generators.reviewer import review_and_edit_post

HISTORY_FILE = "output/history.json"


def load_published_urls():
  published_urls = set()
  if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
      try:
        data = json.load(f)
        for url, meta in data.items():
          if meta.get("status") == "published":
            published_urls.add(url)
      except json.JSONDecodeError:
        pass

  archived_files = glob.glob("output/archive/*.md")
  url_pattern = re.compile(r'https?://[^\s<>"\\\)\]]+')
  for path in archived_files:
    with open(path, "r", encoding="utf-8") as f:
      for u in url_pattern.findall(f.read()):
        published_urls.add(re.sub(r"[\.\,\)\*\_\:]+$", "", u))

  return published_urls


def get_pending_raw_info():
  raw_dir = "output/raw"
  raw_files = sorted(
      glob.glob(os.path.join(raw_dir, "output_prex_posts_*.md"))
  )
  if not raw_files:
    return None, None

  latest_raw = raw_files[-1]
  filename = os.path.basename(latest_raw)
  timestamp = filename.replace("output_prex_posts_", "").replace(".md", "")

  draft_file = os.path.join("output", f"output_x_posts_{timestamp}.md")
  archived_draft = os.path.join(
      "output/archive", f"output_x_posts_{timestamp}.md"
  )

  if not os.path.exists(draft_file) and not os.path.exists(archived_draft):
    return latest_raw, timestamp

  return None, None


def git_pull():
  try:
    print("Step 1: Pulling latest changes from Git...")
    res = subprocess.run(
        ["git", "pull"], capture_output=True, text=True, check=False
    )
    if res.stdout.strip():
      print(f"  [Git] {res.stdout.strip()}")
  except Exception as e:
    print(f"⚠️ Git pull warning: {e}")


def main():
  dry_run = "--dry-run" in sys.argv

  print("=== Starting Daily Curation Pipeline (Part A: Fetch & Refine) ===")
  if dry_run:
    print(
        "🧪 DRY RUN MODE: output goes to `output/dry_run/`, and"
        " `seen_urls.json`/history files are NOT touched. Nothing here is"
        " picked up by Part B or x_poster.py."
    )
  git_pull()

  # 💡 dry-runでは本番の output/ ではなく output/dry_run/ に書き込む。
  # これにより seen_urls.json や下書きファイルなど、本番の状態を一切汚さずに
  # パイプラインの動作・出力品質を確認できる。
  output_dir = "output/dry_run" if dry_run else "output"
  raw_dir = os.path.join(output_dir, "raw")
  os.makedirs(raw_dir, exist_ok=True)

  pending_raw_path, timestamp = None, None  # 💡 常に新規取得からやり直す

  if pending_raw_path:
    print(f"\n⏩ Found pending Raw file: `{pending_raw_path}`")
    print("⏩ Resuming directly from Step 4 (Refining)...")
    with open(pending_raw_path, "r", encoding="utf-8") as f:
      raw_content = f.read()
  else:
    published_history = load_published_urls()
    print(
        f"📊 Loaded {len(published_history)} published URLs from"
        " history/archive."
    )

    print("\nStep 2: Fetching data from multiple sources...")
    all_items = []

    for fetcher, name in [
        (fetch_hacker_news, "Hacker News"),
        (lambda: fetch_arxiv(category="cs.AI"), "arXiv"),
        (fetch_github_trending, "GitHub Trending"),
        (fetch_huggingface_papers, "Hugging Face Papers"),
    ]:
      try:
        items = fetcher() or []
        all_items.extend(items)
        print(f"  - Fetched {len(items)} items from {name}")
      except Exception as e:
        print(f"❌ Error fetching {name}: {e}")

    candidate_items = [
        item
        for item in all_items
        if (item.get("link") or item.get("url") or item.get("title"))
        not in published_history
    ]
    print(
        "🔍 Candidates after deduplication:"
        f" {len(candidate_items)} / {len(all_items)} items."
    )

    if not candidate_items:
      print("ℹ️ No new items to process. Exiting.")
      return

    curated_items = select_best_items(candidate_items, max_select=6)
    print(f"🎯 Curated {len(curated_items)} items for output.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stage1_filename = f"output_prex_posts_{timestamp}.md"

    print("\nStep 3: Generating detailed tech summaries (Stage 1 - Qwen)...")
    run_stage1(curated_items, raw_dir, filename=stage1_filename)

    pending_raw_path = os.path.join(raw_dir, stage1_filename)
    if not os.path.exists(pending_raw_path):
      print(
          f"❌ Stage 1 output file not created: `{pending_raw_path}`. Exiting."
      )
      return

    with open(pending_raw_path, "r", encoding="utf-8") as f:
      raw_content = f.read()

  # 💡 "---"ではなく専用の境界文字列で分割する(Qwenが要約内で"---"を
  # 区切り線として自然に使い、1件の要約が誤って複数件に分割されるのを防ぐ)。
  # 2026-10-04より前に生成された既存ファイルは旧形式("---"区切り)のままの
  # ため、新トークンが見つからない場合は旧形式にフォールバックする
  stripped_content = raw_content.strip()
  if "<<<CURATOR_ITEM_BOUNDARY>>>" in stripped_content:
    raw_parts = stripped_content.split("<<<CURATOR_ITEM_BOUNDARY>>>")
  else:
    raw_parts = re.split(r"\n+\s*---\s*\n+", stripped_content)
  summaries = [s.strip() for s in raw_parts if s.strip()]

  print(
      f"\nStep 4: Refining {len(summaries)} summaries into professional X"
      " posts (Gemma 12B + Qwen review)..."
  )

  if not summaries:
    print("ℹ️ No summaries extracted from Raw content. Exiting.")
    print(f"🔍 [DEBUG Raw Text Preview]\n{raw_content[:300]}\n...")
    return

  refined_posts = []

  for i, summary in enumerate(summaries, 1):
    print(f"\n--- [{i}/{len(summaries)}] Processing Item ---")
    preview_in = summary.replace("\n", " ")[:70]
    print(f"📥 Input Preview: {preview_in}...")

    try:
      post = refine_to_x_post(summary)
      if post:
        preview_out = post.replace("\n", " ")[:70]
        print(f"✨ Refined Output: {preview_out}...")

        post = review_and_edit_post(post, summary)
        preview_reviewed = post.replace("\n", " ")[:70]
        print(f"🔍 Reviewed Output: {preview_reviewed}...")

        refined_posts.append(post)
      else:
        print("⚠️ Refine returned empty string. (Check Ollama connection)")
    except Exception as e:
      print(f"❌ Error in refine_to_x_post: {e}")

    if i < len(summaries):
      time.sleep(4)

  if not refined_posts:
    print(
        "\n❌ No posts generated. Check if Ollama is running or returning"
        " valid text."
    )
    return

  final_content = "\n\n---\n\n".join(refined_posts)
  timestamped_file = os.path.join(output_dir, f"output_x_posts_{timestamp}.md")

  with open(timestamped_file, "w", encoding="utf-8") as f:
    f.write(final_content)

  print(f"\n💾 Saved Stage 1 prex to `{pending_raw_path}`")
  print(
      f"💾 Saved Stage 2 x posts to `{timestamped_file}` (Total"
      f" {len(refined_posts)} posts)"
  )
  if dry_run:
    print(
        "\n🧪 Dry run complete. Review the output above/in `output/dry_run/`,"
        " then delete that folder when done - it's gitignored and never"
        " touched by production runs."
    )
  print("\n✅ Part A completed successfully!")


if __name__ == "__main__":
  main()