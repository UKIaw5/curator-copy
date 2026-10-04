import os
import glob
from datetime import datetime
from generators.refiner import refine_to_x_post
from generators.reviewer import review_and_edit_post

def main():
    print("=== Running Stage 2 Only (From Latest Raw Summaries) ===")

    # output/raw/ の中から最新の生データファイルを自動検出
    raw_dir = "output/raw"
    if not os.path.exists(raw_dir):
        print(f"❌ Directory not found: {raw_dir}")
        return

    raw_files = glob.glob(os.path.join(raw_dir, "output_prex_posts_*.md"))
    if not raw_files:
        print(f"❌ No raw summary files found in {raw_dir}")
        return

    # タイムスタンプが一番新しいファイルを選択
    latest_raw_file = max(raw_files, key=os.path.getmtime)
    print(f"📂 Loading latest raw summaries from: {latest_raw_file}")

    with open(latest_raw_file, "r", encoding="utf-8") as f:
        raw_content = f.read()

    # サマリーの分割
    summaries = [
        s.strip()
        for s in raw_content.split("<<<CURATOR_ITEM_BOUNDARY>>>")
        if s.strip()
    ]

    if not summaries:
        print("ℹ️ No content summaries detected in the file.")
        return

    print(f"🎯 Summaries detected: {len(summaries)}")

    print(f"\nStep: Refining {len(summaries)} summaries into X posts (gemma4:12b & Qwen Review)...")
    refined_posts = []
    for i, summary in enumerate(summaries, 1):
        print(f"\n--- [{i}/{len(summaries)}] Generating draft with gemma4:12b ---")
        gemma_draft = refine_to_x_post(summary)
        print(f"📝 Gemma Draft:\n{gemma_draft}")
        
        print(f"🔍 Reviewing & editing with Qwen...")
        final_post = review_and_edit_post(gemma_draft, summary)
        print(f"✨ Final Post:\n{final_post}")
        
        refined_posts.append(final_post)

    final_content = "\n\n---\n\n".join(refined_posts)

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_file = os.path.join(output_dir, f"output_x_posts_{timestamp}.md")

    with open(timestamped_file, "w", encoding="utf-8") as f:
        f.write(final_content)

    print(f"\n💾 Saved Stage 2 x posts to `{timestamped_file}`")
    print("\n✅ Stage 2 completed successfully!")
    print("👉 Next, you can proceed to Part B to publish/sync.")

if __name__ == "__main__":
    main()
