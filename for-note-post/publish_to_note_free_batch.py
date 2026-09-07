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
        return True
    except Exception as e:
        print(f"⚠️ Failed to load cookies: {e}")
        return False

def get_next_unpublished_article():
    """note_status.json を走査して、未投稿の記事ファイルを1つ見つけて返す"""
    status_data = load_status()
    for raw_file, items in status_data.items():
        if not isinstance(items, dict):
            continue
        for idx, info in items.items():
            if isinstance(info, dict) and not info.get("published_to_note", False):
                md_path = info.get("generated_file")
                if md_path and os.path.exists(md_path):
                    return raw_file, idx, md_path, status_data
    return None, None, None, status_data

def parse_article_content_as_free(raw_content):
    """ペイウォールマーカーを削除し、すべての文章を1つの無料本文として結合・整形する"""
    lines = raw_content.splitlines()
    title = lines[0].replace("#", "").replace("■", "").strip() if lines else "無題のタイトル"
    
    # ペイウォールマーカー（<!-- PAYWALL --> または --- [NOTE PAID BOUNDARY] ---）をすべて除去する
    cleaned_content = raw_content
    cleaned_content = cleaned_content.replace("<!-- PAYWALL -->", "")
    cleaned_content = cleaned_content.replace("--- [NOTE PAID BOUNDARY] ---", "")
    
    # タイトル行を除いた残りの本文部分を取得
    body_lines = [line for line in cleaned_content.splitlines() if line.strip() != lines[0].strip()]
    full_body = "\n".join(body_lines).strip()
    
    return title, full_body

def update_status_and_archive(file_path, raw_file, idx, status_data):
    filename = os.path.basename(file_path)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    destination_path = os.path.join(ARCHIVE_DIR, filename)
    
    if os.path.exists(destination_path):
        base, ext = os.path.splitext(filename)
        destination_path = os.path.join(ARCHIVE_DIR, f"{base}_{datetime.now().strftime('%H%M%S')}{ext}")
        
    shutil.move(file_path, destination_path)
    print(f"📦 Moved published file to: {destination_path}")

    # ステータス更新
    if raw_file in status_data and idx in status_data[raw_file]:
        status_data[raw_file][idx]["published_to_note"] = True
        status_data[raw_file][idx]["published_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_status(status_data)
        print(f"📝 Updated {STATUS_FILE} with published record.")

def main():
    print("=== Starting Note Free Batch Auto-Publisher == Selector Loop ===")
    
    while True:
        raw_file, idx, file_path, status_data = get_next_unpublished_article()
        
        if not file_path:
            print("\n✅ All articles have been successfully published as FREE posts!")
            break
            
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
            
        title, full_body = parse_article_content_as_free(raw_content)
        print(f"\n==============================================")
        print(f"📌 Target Article (FREE): {file_path}")
        print(f"📌 Title: {title}")
        print(f"📊 Total body length: {len(full_body)} chars")
        print(f"==============================================")

        publish_success = False

        with sync_playwright() as p:
            print("🌐 Launching browser for this article...")
            browser = p.chromium.launch(
                headless=False,  # 動作確認のためFalse。安定したらTrueにしてもOK
                slow_mo=100, 
                args=["--window-size=1024,720"]
            )
            context = browser.new_context(viewport={"width": 1024, "height": 720})
            
            if not load_cookies_to_context(context):
                print("❌ Failed to load cookies. Aborting batch.")
                browser.close()
                break
            
            page = context.new_page()
            print("🚀 Navigating to note editor...")
            
            try:
                page.goto("https://editor.note.com/new/", timeout=60000)
                page.wait_for_selector("textarea, div[contenteditable='true']", timeout=30000)
                print("✅ Editor loaded successfully!")

                # --- 1. タイトル入力 ---
                print("✍️ Typing title...")
                title_input = page.locator("textarea.p-editor__titleInput, textarea").first
                title_input.click()
                title_input.fill(title)
                
                # --- 2. 本文一括入力（すべて無料エリアとして流し込む） ---
                print("✍️ Typing full free body content...")
                body_editor = page.locator("div.ProseMirror").first
                body_editor.click()
                page.keyboard.type(full_body, delay=1)
                page.wait_for_timeout(1500)

                # --- 3. 公開設定画面へ進む ---
                print("🚀 Clicking '公開に進む' button...")
                publish_btn = page.get_by_role("button", name=re.compile("公開に進む"))
                publish_btn.click()
                page.wait_for_timeout(4000)

                # （※有料設定や金額設定の処理は一切行わず、無料のまま進める）

                # --- 4. 最終投稿ボタン ---
                print("📢 Clicking final '投稿' (Publish) button...")
                final_publish_btn = page.get_by_role("button", name=re.compile("投稿|公開")).filter(has_text=re.compile("投稿|公開")).last
                
                if final_publish_btn.is_visible():
                    final_publish_btn.click()
                    print("✅ Final publish button clicked successfully!")
                    page.wait_for_timeout(5000) 
                    publish_success = True
                else:
                    print("⚠️ 最終的な '投稿' ボタンが見つかりませんでした。")
                    
            except Exception as e:
                print(f"⚠️ Error during automation process: {e}")

            print("🔒 Closing browser session for this article...")
            browser.close()

        # 投稿成功したらステータスを更新してアーカイブし、次のループへ
        if publish_success:
            update_status_and_archive(file_path, raw_file, idx, status_data)
            print("🎉 Article successfully posted as FREE! Moving to next item...")
            import time
            time.sleep(3)
        else:
            print("❌ Publication failed for this article. Stopping batch to prevent cascade errors.")
            break

    print("✅ All free batch publication tasks finished!")

if __name__ == "__main__":
    main()
