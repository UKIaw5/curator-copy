# batch_publish_to_note.py
import os
import re
import json
import shutil
from datetime import datetime
from playwright.sync_api import sync_playwright

STATUS_FILE = "note_status.json"
ARCHIVE_DIR = "output/archive_published"

def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except json.JSONDecodeError: return {}
    return {}

def save_status(data):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_cookies_to_context(context):
    cookie_path = "note_cookies.json"
    if not os.path.exists(cookie_path):
        print(f"⚠️ {cookie_path} not found.")
        return False
        
    try:
        with open(cookie_path, "r", encoding="utf-8") as f:
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
            
            if "expirationDate" in c: fc["expires"] = int(c["expirationDate"])
            elif "expires" in c: fc["expires"] = int(c["expires"])
                
            if "sameSite" in c:
                ss = str(c["sameSite"]).lower()
                if ss == "lax": fc["sameSite"] = "Lax"
                elif ss == "strict": fc["sameSite"] = "Strict"
                elif ss in ["none", "no_restriction"]: fc["sameSite"] = "None"
            
            formatted_cookies.append(fc)
            
        context.add_cookies(formatted_cookies)
        return True
    except Exception as e:
        print(f"⚠️ Failed to load cookies: {e}")
        return False

def get_unpublished_article(status_data):
    # JSONを走査して、未投稿のファイルを1つ見つける
    for raw_file, items in status_data.items():
        for idx, info in items.items():
            if not info.get("published_to_note", False):
                md_path = info.get("generated_file")
                if md_path and os.path.exists(md_path):
                    return raw_file, idx, md_path
    return None, None, None

def parse_article_content(raw_content):
    lines = raw_content.splitlines()
    title = lines[0].replace("#", "").strip() if lines else "無題のタイトル"
    boundary_marker = "--- [NOTE PAID BOUNDARY] ---"
    parts = raw_content.split(boundary_marker)
    free_section = parts[0].replace(lines[0], "").strip() if len(parts) > 0 else raw_content
    paid_section = parts[1].strip() if len(parts) > 1 else ""
    return title, free_section, paid_section

def main():
    print("=== Note Batch Auto-Publisher ===")
    
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    status_data = load_status()
    
    raw_file, idx, file_path = get_unpublished_article(status_data)
    if not file_path:
        print("✅ No unpublished articles found. All caught up!")
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    title, free_section, paid_section = parse_article_content(raw_content)
    print(f"📌 Target Article: {file_path}")
    print(f"📌 Title: {title}")

    publish_success = False

    with sync_playwright() as p:
        print("🌐 Launching browser...")
        browser = p.chromium.launch(headless=True, slow_mo=50) # 定期実行時はheadless=Trueを推奨
        context = browser.new_context(viewport={"width": 1024, "height": 720})
        
        if not load_cookies_to_context(context):
            browser.close()
            return
        
        page = context.new_page()
        print("🚀 Navigating to note editor...")
        page.goto("https://editor.note.com/new/", timeout=60000)
        
        try:
            page.wait_for_selector("textarea, div[contenteditable='true']", timeout=30000)
            
            # 1. Input Title
            title_input = page.locator("textarea.p-editor__titleInput, textarea").first
            title_input.click()
            title_input.fill(title)
            
            # 2. Input Free Section
            body_editor = page.locator("div.ProseMirror").first
            body_editor.click()
            page.keyboard.type(free_section, delay=2)
            page.wait_for_timeout(1000)

            # 3. Insert Paid Boundary & Paid Section
            if paid_section:
                page.keyboard.press("End")
                page.keyboard.press("Enter")
                page.wait_for_timeout(1000)
                page.keyboard.press("Tab")
                page.wait_for_timeout(500)
                page.keyboard.press("Enter")
                page.wait_for_timeout(1000)
                page.keyboard.press("ArrowUp")
                page.wait_for_timeout(500)
                page.keyboard.press("Enter")
                page.wait_for_timeout(1500)
                page.keyboard.press("ArrowDown")
                page.wait_for_timeout(300)
                page.keyboard.press("ArrowDown")
                page.wait_for_timeout(500)
                page.keyboard.type(paid_section, delay=2)

            # 4. Publish Process
            publish_btn = page.get_by_role("button", name=re.compile("公開に進む"))
            publish_btn.click()
            page.wait_for_timeout(4000)

            if paid_section:
                paid_option = page.get_by_text("有料", exact=True)
                if paid_option.count() > 0:
                    paid_option.first.click()
                    page.wait_for_timeout(1000)
                    price_input = page.locator("input[type='text'], input[type='tel'], input[type='number']").filter(has_not=page.locator("textarea")).first
                    if price_input.count() > 0:
                        price_input.click()
                        price_input.press("Control+A")
                        price_input.fill("100")
                        page.wait_for_timeout(1000)
                    setting_confirm_btn = page.get_by_role("button", name=re.compile("設定|保存|完了")).first
                    if setting_confirm_btn.is_visible():
                        setting_confirm_btn.click()
                        page.wait_for_timeout(2000)

            final_publish_btn = page.get_by_role("button", name=re.compile("投稿|公開")).filter(has_text=re.compile("投稿|公開")).last
            if final_publish_btn.is_visible():
                final_publish_btn.click()
                page.wait_for_timeout(5000)
                publish_success = True
                print("✅ Final publish button clicked!")
                
        except Exception as e:
            print(f"⚠️ Error during publication: {e}")

        browser.close()

    # 投稿成功時の後処理（JSON更新とファイル移動）
    if publish_success:
        basename = os.path.basename(file_path)
        archive_path = os.path.join(ARCHIVE_DIR, basename)
        shutil.move(file_path, archive_path)
        
        status_data[raw_file][idx]["published_to_note"] = True
        status_data[raw_file][idx]["published_at"] = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_status(status_data)
        print(f"📦 Successfully published and moved to {archive_path}")
    else:
        print("❌ Publication failed. File was not moved or updated.")

if __name__ == "__main__":
    main()
