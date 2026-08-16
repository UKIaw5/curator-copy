import os
import glob
import shutil
import time
import random
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

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

def human_type(page, selector, text):
    """Simulate human typing cadence."""
    page.click(selector)
    for char in text:
        page.keyboard.type(char)
        time.sleep(random.uniform(0.01, 0.04))

def schedule_post_on_x(page, text: str, target_time: datetime):
    """Fill in post content and schedule it via X's scheduling UI."""
    tweet_box_selector = '[data-testid="tweetTextarea_0"]'
    
    print(f"✍️ Typing post content (Target Schedule: {target_time.strftime('%Y-%m-%d %H:%M')})...")
    page.wait_for_selector(tweet_box_selector, timeout=10000)
    human_type(page, tweet_box_selector, text)
    time.sleep(random.uniform(1.0, 2.0))
    
    # 1. カレンダーアイコンをクリック
    schedule_icon_selector = '[data-testid="scheduleOption"]'
    page.click(schedule_icon_selector)
    print("📅 Clicked schedule icon, waiting for modal...")
    
    time.sleep(2.5)
    
    try:
        # 2. モーダル内のSelect要素を取得
        selects = page.locator('select')
        selects.first.wait_for(state="attached", timeout=5000)
        count = selects.count()
        
        if count < 5:
            raise Exception(f"Schedule dropdowns not found! Found {count} selects.")

        selects.nth(0).select_option(str(target_time.month))
        selects.nth(1).select_option(str(target_time.day))
        selects.nth(2).select_option(str(target_time.year))
        
        # 💡 修正: 時間の処理 (12時間 / 24時間表記の自動判定)
        hour_select = selects.nth(3)
        # ドロップダウン内に「13」以上の値があるかチェック
        is_24h = hour_select.evaluate("node => Array.from(node.options).some(opt => parseInt(opt.value) >= 13)")
        
        h24 = target_time.hour
        if is_24h:
            hour_select.select_option(str(h24))
        else:
            # 12時間表記UIの場合
            h12 = h24 % 12
            if h12 == 0:
                h12 = 12
            hour_select.select_option(str(h12))
            
            # AM/PM（午前/午後）のセレクトボックス（通常6番目）を設定
            if count >= 6:
                is_pm = h24 >= 12
                # index=0 が AM(午前)、index=1 が PM(午後)
                selects.nth(5).select_option(index=1 if is_pm else 0)

        # 分は5分刻みに丸める
        rounded_minute = (target_time.minute // 5) * 5
        selects.nth(4).select_option(str(rounded_minute))
        time.sleep(1.5)
        
        # 3. モーダル内の「確認」ボタンをクリック
        confirm_btn = page.locator(
            '[data-testid="scheduledConfirmationPrimaryButton"], '
            '[data-testid="confirmationSheetConfirm"], '
            '[role="dialog"] [role="button"]:has-text("更新"), '
            '[role="dialog"] [role="button"]:has-text("Update"), '
            '[role="dialog"] [role="button"]:has-text("確認"), '
            '[role="dialog"] [role="button"]:has-text("Confirm")'
        ).first
        
        confirm_btn.wait_for(state="visible", timeout=5000)
        confirm_btn.click()
        print("🔘 Clicked confirm in modal...")
        
        # モーダル（背景マスク）が完全に消えるのを待機
        mask = page.locator('[data-testid="mask"]')
        try:
            mask.last.wait_for(state="hidden", timeout=4000)
        except Exception:
            print("⚠️ Modal might still be open, retrying confirm click...")
            if confirm_btn.is_visible():
                confirm_btn.click(force=True)
            try:
                mask.last.wait_for(state="hidden", timeout=4000)
            except Exception:
                pass
                
        time.sleep(2.0)
        
        # 4. タイムライン上の「予約投稿(Schedule)」ボタンをクリック
        post_btn = page.locator('[data-testid="tweetButtonInline"]:visible, [data-testid="tweetButton"]:visible').first
        try:
            post_btn.click(force=True, timeout=5000)
        except Exception:
            print("⚠️ standard click failed, trying JS evaluation fallback...")
            post_btn.evaluate("node => node.click()")
            
        print(f"✅ Successfully scheduled post for {target_time.strftime('%Y-%m-%d %H:%M')}!")
        time.sleep(3.0)
        
    except Exception as e:
        print(f"❌ Failed during schedule modal interaction: {e}")
        page.keyboard.press("Escape")
        time.sleep(1.0)
        raise e

def process_batch_scheduling(interval_hours: int = 3):
    ensure_archive_dir()
    file_path = get_latest_x_post_file()
    if not file_path:
        return

    posts = parse_posts_from_file(file_path)
    if not posts:
        print("⚠️ File contains no posts.")
        return

    print(f"🚀 Found {len(posts)} posts to schedule.")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            channel="chrome",
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()
        page.goto("https://x.com/home")
        time.sleep(4.0)

        # 2時間後からスケジュールを開始
        current_schedule_time = datetime.now() + timedelta(hours=2)

        for idx, post_text in enumerate(posts, start=1):
            print(f"\n--- Processing Post {idx}/{len(posts)} ---")
            try:
                schedule_post_on_x(page, post_text, current_schedule_time)
                current_schedule_time += timedelta(hours=interval_hours)
                time.sleep(random.uniform(2.0, 4.0))
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
    process_batch_scheduling(interval_hours=3)