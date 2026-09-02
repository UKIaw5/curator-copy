import os
import json
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_PATH = os.path.join(BASE_DIR, "note_cookies.json")
STATUS_PATH = os.path.join(BASE_DIR, "note_status.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ARCHIVE_DIR = os.path.join(OUTPUT_DIR, "archive")

def get_latest_article():
    if not os.path.exists(OUTPUT_DIR):
        return None
    files = [os.path.join(OUTPUT_DIR, f) for f in os.listdir(OUTPUT_DIR) if f.endswith(".md")]
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def parse_markdown(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    title = ""
    if lines:
        title = lines[0].replace("#", "").replace("■", "").strip()

    # 💡 <!-- PAYWALL --> も拾えるように正規表現を更新
    split_pattern = r'<!--\s*(?:PAYWALL|PAID_START)\s*-->|---PAID---|\[有料エリア\]|■有料エリア|### 有料エリア|有料エリア'
    parts = re.split(split_pattern, content)
    
    if len(parts) > 1:
        free_section = parts[0].replace(lines[0], "").strip() if lines else parts[0].strip()
        paid_section = parts[1].strip()
    else:
        print("⚠️ Warning: Paywall marker not found! Treating whole content as free.")
        free_section = content.replace(lines[0], "").strip() if lines else content
        paid_section = ""

    hashtags = re.findall(r'#[\w\u3000-\u9fff]+', content)
    hashtags = list(set(hashtags))[:5]

    return title, free_section, paid_section, hashtags

def main():
    print("=== Starting Note Auto-Publisher (v2.7 Fixed Workflow) ===")
    
    article_path = get_latest_article()
    if not article_path:
        print("❌ No markdown file found in output/")
        return

    print(f"📌 Target Article: {article_path}")
    title, free_section, paid_section, hashtags = parse_markdown(article_path)
    
    print(f"📌 Title: {title}")
    print(f"🏷️ Hashtags: {hashtags}")
    print(f"📊 Free section length: {len(free_section)} chars")
    print(f"📊 Paid section length: {len(paid_section)} chars")

    # アイキャッチ画像のパス確認
    base_name, _ = os.path.splitext(os.path.basename(article_path))
    eyecatch_filename = f"{base_name}.png"
    eyecatch_path = os.path.join(OUTPUT_DIR, eyecatch_filename)

    with sync_playwright() as p:
        # 💡 headless=Falseにしてブラウザの動きを目で見えるようにする
        browser = p.chromium.launch(headless=False, slow_mo=80)
        context = browser.new_context(viewport={"width": 1280, "height": 800})

        # クッキーの読み込み
        if os.path.exists(COOKIES_PATH):
            with open(COOKIES_PATH, "r", encoding="utf-8") as f:
                cookies = json.load(f)
                formatted_cookies = []
                for c in cookies:
                    cookie = {
                        "name": c.get("name"),
                        "value": c.get("value"),
                        "domain": c.get("domain"),
                        "path": c.get("path", "/"),
                    }
                    if "expires" in c and isinstance(c["expires"], (int, float)):
                        cookie["expires"] = c["expires"]
                    formatted_cookies.append(cookie)
                context.add_cookies(formatted_cookies)
            print("✅ Cookies loaded successfully!")

        page = context.new_page()
        print("🚀 Navigating to note editor...")
        page.goto("https://editor.note.com/new/")
        
        print("⏳ Waiting for editor to load...")
        page.wait_for_selector("div.ProseMirror", timeout=30000)
        print("✅ Editor loaded successfully!")
        
        # ------------------------------------------------------------------
        # 🖼️ 【初手】アイキャッチ画像のアップロード
        # ------------------------------------------------------------------
        if os.path.exists(eyecatch_path):
            print(f"🖼️ [Step 1] Uploading eyecatch image first: {eyecatch_path}")
            try:
                # noteのエディタにあるファイル入力要素を探して画像を設定
                file_input = page.locator("input[type='file']").first
                if file_input.count() > 0:
                    file_input.set_input_files(eyecatch_path)
                    print("✅ Eyecatch image attached successfully!")
                    page.wait_for_timeout(3000)
                else:
                    print("⚠️ File input not found directly, trying button click...")
                    eyecatch_btn = page.locator("button, div").filter(has_text="見出し画像").first
                    if eyecatch_btn.is_visible():
                        eyecatch_btn.click()
                        page.wait_for_timeout(1000)
                        page.locator("input[type='file']").first.set_input_files(eyecatch_path)
                        print("✅ Eyecatch image attached via button!")
                        page.wait_for_timeout(3000)
            except Exception as e:
                print(f"⚠️ Could not upload eyecatch image: {e}")
        else:
            print("⚠️ Eyecatch image not found in output/, skipping.")

        # ------------------------------------------------------------------
        # ✍️ タイトルの入力
        # ------------------------------------------------------------------
        print("✍️ [Step 2] Typing title...")
        title_input = page.locator("textarea.p-editor__titleInput, textarea").first
        title_input.click()
        title_input.fill(title)
        page.wait_for_timeout(1000)

        # ------------------------------------------------------------------
        # ✍️ 無料パートの入力
        # ------------------------------------------------------------------
        print("✍️ [Step 3] Typing free section...")
        body_editor = page.locator("div.ProseMirror").first
        body_editor.click()
        page.keyboard.type(free_section, delay=1)
        page.wait_for_timeout(1000)

        # ------------------------------------------------------------------
        # 💰 有料パート（ある場合）
        # ------------------------------------------------------------------
        if paid_section:
            print("💰 [Step 4] Inserting paid boundary and typing paid section...")
            page.keyboard.press("Enter")
            page.keyboard.type("/paid")
            page.wait_for_timeout(1500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)
            
            # カーソルを下に移動して有料テキストを入力
            page.keyboard.press("ArrowDown")
            page.keyboard.press("ArrowDown")
            page.keyboard.type(paid_section, delay=1)
            page.wait_for_timeout(1000)

        # ------------------------------------------------------------------
        # 🚀 公開設定・投稿フロー
        # ------------------------------------------------------------------
        print("🚀 [Step 5] Clicking '公開に進む' button...")
        publish_btn = page.locator("button").filter(has_text="公開に進む").first
        publish_btn.click()
        page.wait_for_timeout(3000)

        print("💰 Selecting '有料' option...")
        paid_radio = page.locator("label, span, div").filter(has_text="有料").first
        paid_radio.click()
        page.wait_for_timeout(1000)

        print("💴 Setting price to 100 yen...")
        price_input = page.locator("input[type='number'], input[name*='price']").first
        if price_input.count() > 0:
            price_input.click()
            price_input.fill("100")
            print("✅ Price set to 100 yen!")
        page.wait_for_timeout(1000)

        print("💾 Clicking '有料エリア設定' (Save/Confirm) button...")
        confirm_btn = page.locator("button").filter(has_text="有料エリア設定").first
        if confirm_btn.count() > 0 and confirm_btn.is_visible():
            confirm_btn.click()
            page.wait_for_timeout(2000)

        # ハッシュタグの追加
        if hashtags:
            print(f"🏷️ Adding hashtags: {hashtags}")
            try:
                tag_input = page.locator("input[placeholder*='ハッシュタグ'], input[type='text']").last
                for tag in hashtags:
                    tag_input.click()
                    tag_input.fill(tag)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(500)
            except Exception as e:
                print(f"⚠️ Could not add hashtags: {e}")

        print("📢 Clicking final '投稿' (Publish) button...")
        final_publish_btn = page.locator("button").filter(has_text="投稿").last
        if final_publish_btn.count() > 0:
            final_publish_btn.click()
            print("✅ Final publish button clicked!")
            # 💡 公開処理が確実に完了するよう余裕を持って待機
            page.wait_for_timeout(7000)
        else:
            print("❌ Final publish button not found!")

        # ステータスとアーカイブの処理
        if not os.path.exists(ARCHIVE_DIR):
            os.makedirs(ARCHIVE_DIR)

        # status.json の更新処理（必要に応じて）
        
        # ファイルの移動
        os.rename(article_path, os.path.join(ARCHIVE_DIR, os.path.basename(article_path)))
        if os.path.exists(eyecatch_path):
            os.rename(eyecatch_path, os.path.join(ARCHIVE_DIR, eyecatch_filename))
        print("📦 Moved article and eyecatch to archive successfully.")

    print("🎉 All automation steps completed!")
    input("Press Enter to close browser...")

if __name__ == "__main__":
    main()