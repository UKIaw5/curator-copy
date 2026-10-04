import os
import re
import glob
import json
import random
import shutil
import sys
import time
from datetime import datetime, timedelta
from cloakbrowser import launch_persistent_context

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "socialdog_cookies.json")
USER_DATA_DIR = os.path.join(BASE_DIR, "socialdog_user_data")

# 💡 チームIDを含む固定URL。アカウント構成が変わったら要更新
QUEUE_URL = "https://web.social-dog.net/teams/1418529/publish/queue/list"

OUTPUT_DIR = "output"
ARCHIVE_DIR = os.path.join(OUTPUT_DIR, "archive")


def load_cookies_to_context(context):
    if not os.path.exists(COOKIE_FILE):
        print(f"⚠️ {COOKIE_FILE} not found. Run the cookie export first.")
        return False

    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            raw_cookies = json.load(f)

        formatted_cookies = []
        for c in raw_cookies:
            fc = {}
            if "name" in c: fc["name"] = c["name"]
            if "value" in c: fc["value"] = c["value"]
            if "domain" in c: fc["domain"] = c["domain"]
            if "path" in c: fc["path"] = c["path"]
            if "secure" in c: fc["secure"] = c["secure"]
            if "httpOnly" in c: fc["httpOnly"] = c["httpOnly"]

            if "expirationDate" in c:
                fc["expires"] = int(c["expirationDate"])
            elif "expires" in c:
                fc["expires"] = int(c["expires"])

            if "sameSite" in c:
                ss = str(c["sameSite"]).lower()
                if ss == "lax": fc["sameSite"] = "Lax"
                elif ss == "strict": fc["sameSite"] = "Strict"
                elif ss in ["none", "no_restriction"]: fc["sameSite"] = "None"

            formatted_cookies.append(fc)

        context.add_cookies(formatted_cookies)
        print("✅ SocialDog cookies loaded!")
        return True
    except Exception as e:
        print(f"⚠️ Failed to load cookies: {e}")
        return False


def get_latest_x_post_file():
    """output/ 直下の未アーカイブ(最も古い)Xポストファイルを取得する。"""
    files = [f for f in glob.glob(f"{OUTPUT_DIR}/output_x_posts_*.md") if os.path.isfile(f)]
    if not files:
        print("⚠️ No pending X post files found in the output directory.")
        return None
    files.sort(key=os.path.getmtime)
    return files[0]


def parse_posts_from_file(file_path):
    print(f"📖 Reading file: `{file_path}`")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    # 💡 Stage2(X投稿文)の区切りは "\n\n---\n\n" のまま(Stage1の生データとは別物)
    return [p.strip() for p in content.split("\n\n---\n\n") if p.strip()]


def set_schedule_datetime(page, target_time: datetime):
    """投稿予約の日時ピッカーで日時を設定する。

    💡 DevToolsで確認: Blueprint.js(bp3-)のDateInputコンポーネントで、
    <input aria-label="日付" placeholder="YYYY/MM/DD H:mm"> に日時文字列を
    直接入力するだけで設定できる。カレンダーの日付セルクリックや時・分の
    個別スピンボックス操作は不要。
    """
    # 💡 日付ボタンのテキスト("2026/10/04 19:35"等)は毎回値が変わる上に
    # get_by_textでの直接クリックが不安定だった。DevToolsで確認した
    # "bp3-popover-wrapper datetime_picker_blueprint" という安定した
    # Blueprint.js側のクラス名を使って、popoverのトリガー要素を直接狙う
    date_button = page.locator(".datetime_picker_blueprint .bp3-popover-target").first
    date_button.click()
    time.sleep(1.0)

    datetime_input = page.get_by_label("日付")
    datetime_input.click()
    page.keyboard.press("Control+A")
    page.keyboard.type(target_time.strftime("%Y/%m/%d %H:%M"))
    page.keyboard.press("Enter")
    time.sleep(0.5)


def schedule_post_on_socialdog(page, text: str, target_time: datetime):
    print(f"📋 Composing post (Target Schedule: {target_time.strftime('%Y-%m-%d %H:%M')})...")

    # 💡 DevToolsで確認: <textarea placeholder="投稿内容を入力"> という
    # 本物のplaceholder属性を持つtextarea。contenteditableではない。
    # クラス名(sc-xxxxx-N)はstyled-components由来の自動生成なので使わない
    compose_box = page.get_by_placeholder("投稿内容を入力")
    compose_box.click()
    time.sleep(0.5)
    # 💡 前回実行時の下書きが残っている場合があるため、念のため全選択して
    # 削除してから入力する(2重入力を防ぐ)
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    time.sleep(0.3)
    page.keyboard.insert_text(text)
    time.sleep(1.0)

    set_schedule_datetime(page, target_time)

    confirm_btn = page.get_by_role("button", name=re.compile("投稿を予約"))
    confirm_btn.click()
    print(f"✅ Scheduled for {target_time.strftime('%Y-%m-%d %H:%M')}!")
    time.sleep(2.5)


def process_batch_scheduling(base_interval_hours: int = 3, limit: int = None):
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    file_path = get_latest_x_post_file()
    if not file_path:
        return

    posts = parse_posts_from_file(file_path)
    if not posts:
        print("⚠️ File contains no posts.")
        return

    if limit is not None:
        posts = posts[:limit]
        print(f"🧪 TEST MODE: only processing {len(posts)} post(s), file will NOT be archived.")

    print(f"🚀 Found {len(posts)} post(s) to schedule via SocialDog.")

    # 💡 x_poster.pyと同じくCloakBrowser(ステルス版Playwright)+永続プロファイルを使う。
    # SocialDog自体はXほどボット検知を敵視していないと思われるが、投稿代行する
    # 自動化である以上、既存のX投稿自動化と同じ安全マージンで揃えておく
    context = launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=False,
        humanize=True,
        viewport={"width": 1280, "height": 900}
    )

    if not load_cookies_to_context(context):
        context.close()
        return

    page = context.new_page()
    print(f"🌐 Navigating to {QUEUE_URL} ...")
    page.goto(QUEUE_URL, timeout=60000)
    time.sleep(3.0)

    current_schedule_time = datetime.now() + timedelta(minutes=30)

    for idx, post_text in enumerate(posts, start=1):
        print(f"\n--- Processing Post {idx}/{len(posts)} ---")
        try:
            schedule_post_on_socialdog(page, post_text, current_schedule_time)
            jitter_minutes = random.randint(-40, 40)
            current_schedule_time += timedelta(hours=base_interval_hours, minutes=jitter_minutes)
            time.sleep(random.uniform(2.0, 4.0))
        except Exception as e:
            print(f"⚠️ Aborting batch due to error on post {idx}: {e}")
            print("🔍 Leaving the browser open for inspection. Close it manually when done.")
            input("Press Enter to close the browser...")
            context.close()
            return

    if limit is None:
        archive_path = os.path.join(ARCHIVE_DIR, os.path.basename(file_path))
        shutil.move(file_path, archive_path)
        print(f"\n🎉 All posts scheduled! Archived file to `{archive_path}`!")
    else:
        print("\n🧪 Test run complete. File left in place (not archived).")

    input("Press Enter to close the browser...")
    context.close()


if __name__ == "__main__":
    test_limit = 1 if "--test" in sys.argv else None
    process_batch_scheduling(base_interval_hours=3, limit=test_limit)
