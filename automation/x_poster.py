import os
import glob
import shutil
import time
import random
from datetime import datetime, timedelta
from cloakbrowser import launch_persistent_context

USER_DATA_DIR = os.path.abspath("./x_user_data")
OUTPUT_DIR = "output"
ARCHIVE_DIR = os.path.join(OUTPUT_DIR, "archive")

def ensure_archive_dir():
    """Ensure the archive directory exists."""
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)

def get_latest_x_post_file():
    """Retrieve the oldest unarchived Markdown file in output/ directory."""
    files = [f for f in glob.glob(f"{OUTPUT_DIR}/output_x_posts_*.md") if os.path.isfile(f)]
    if not files:
        print("⚠️ No pending X post files found in the output directory.")
        return None
    
    files.sort(key=os.path.getmtime)
    return files[0]

def parse_posts_from_file(file_path):
    """Parse markdown content into individual post strings."""
    print(f"📖 Reading file: `{file_path}`")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    posts = [p.strip() for p in content.split("\n\n---\n\n") if p.strip()]
    return posts

def paste_text(page, selector, text):
    """Simulate human pasting action (Clipboard style)."""
    page.click(selector)
    time.sleep(0.5)
    # insert_text は クリップボード貼り付け（Ctrl+V）と同等の処理を一瞬で行います
    page.keyboard.insert_text(text)
    time.sleep(1.0)

def schedule_post_on_x(page, text: str, target_time: datetime):
    """Fill in post content via paste and schedule it via X's scheduling UI."""
    tweet_box_selector = '[data-testid="tweetTextarea_0"]'
    
    print(f"📋 Pasting post content (Target Schedule: {target_time.strftime('%Y-%m-%d %H:%M')})...")
    page.wait_for_selector(tweet_box_selector, timeout=10000)
    
    # 1. テキスト挿入（コピペ方式）
    paste_text(page, tweet_box_selector, text)
    time.sleep(2.0)
    
    # 2. カレンダーアイコンをクリック
    schedule_icon_selector = '[data-testid="scheduleOption"]'
    schedule_icon = page.locator(schedule_icon_selector)
    schedule_icon.wait_for(state="attached", timeout=5000)
    schedule_icon.evaluate("node => node.click()")
    print("📅 Clicked schedule icon, waiting for modal...")
    
    time.sleep(2.0)
    
    try:
        # 3. モーダル内のSelect要素を取得（dialogの待機を挟まず直接待ちます）
        selects = page.locator('select')
        selects.first.wait_for(state="attached", timeout=8000)
        count = selects.count()
        
        if count < 5:
            raise Exception(f"Schedule dropdowns not found! Found {count} selects.")

        selects.nth(0).select_option(str(target_time.month))
        selects.nth(1).select_option(str(target_time.day))
        selects.nth(2).select_option(str(target_time.year))
        
        # 時間の処理 (12時間 / 24時間表記の自動判定)
        hour_select = selects.nth(3)
        is_24h = hour_select.evaluate("node => Array.from(node.options).some(opt => parseInt(opt.value) >= 13)")
        
        h24 = target_time.hour
        if is_24h:
            hour_select.select_option(str(h24))
        else:
            h12 = h24 % 12
            if h12 == 0:
                h12 = 12
            hour_select.select_option(str(h12))
            
            if count >= 6:
                is_pm = h24 >= 12
                selects.nth(5).select_option(index=1 if is_pm else 0)

        # 分は5分刻みに丸める
        rounded_minute = (target_time.minute // 5) * 5
        selects.nth(4).select_option(str(rounded_minute))
        time.sleep(1.5)
        
        # 4. モーダル内の「確認 / Update」ボタンをクリック
        confirm_btn = page.locator(
            '[data-testid="scheduledConfirmationPrimaryButton"], '
            '[role="dialog"] button:has-text("確認"), '
            '[role="dialog"] button:has-text("Confirm"), '
            '[role="dialog"] button:has-text("更新"), '
            '[role="dialog"] button:has-text("Update")'
        ).first
        
        confirm_btn.wait_for(state="attached", timeout=8000)
        confirm_btn.evaluate("node => node.click()")
        print("🔘 Clicked confirm in modal...")
        
        time.sleep(2.5)
        
        # 5. タイムライン上の「予約投稿(Schedule)」ボタンをクリック
        post_btn = page.locator('[data-testid="tweetButtonInline"]:visible, [data-testid="tweetButton"]:visible').first
        post_btn.wait_for(state="attached", timeout=8000)
        
        try:
            post_btn.evaluate("node => node.click()")
        except Exception:
            post_btn.click(force=True, timeout=5000)
            
        print(f"✅ Successfully scheduled post for {target_time.strftime('%Y-%m-%d %H:%M')}!")
        time.sleep(5.0)
        
    except Exception as e:
        print(f"❌ Failed during schedule modal interaction: {e}")
        page.keyboard.press("Escape")
        time.sleep(1.0)
        raise e

def process_batch_scheduling(base_interval_hours: int = 3):
    ensure_archive_dir()
    file_path = get_latest_x_post_file()
    if not file_path:
        return

    posts = parse_posts_from_file(file_path)
    if not posts:
        print("⚠️ File contains no posts.")
        return

    print(f"🚀 Found {len(posts)} posts to schedule.")

    # CloakBrowser でセッション保持して起動
    context = launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=False,
        humanize=True,
        viewport={"width": 1280, "height": 800}
    )
    
    page = context.new_page()
    page.goto("https://x.com/home")
    time.sleep(5.0)

    # 1発目: 30分後の予約時間からスタート
    current_schedule_time = datetime.now() + timedelta(minutes=30)

    for idx, post_text in enumerate(posts, start=1):
        print(f"\n--- Processing Post {idx}/{len(posts)} ---")
        try:
            schedule_post_on_x(page, post_text, current_schedule_time)
            
            # 2件目以降: 3時間 ± 40分のランダムゆらぎ
            jitter_minutes = random.randint(-40, 40)
            current_schedule_time += timedelta(hours=base_interval_hours, minutes=jitter_minutes)
            
            time.sleep(random.uniform(3.0, 6.0))
        except Exception as e:
            print(f"⚠️ Aborting batch due to error on post {idx}: {e}")
            context.close()
            return

    context.close()

    file_name = os.path.basename(file_path)
    archive_path = os.path.join(ARCHIVE_DIR, file_name)
    shutil.move(file_path, archive_path)
    print(f"\n🎉 All posts scheduled! Archived file to `{archive_path}`!")

if __name__ == "__main__":
    process_batch_scheduling(base_interval_hours=3)