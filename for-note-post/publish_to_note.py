import os
import re
import json
from playwright.sync_api import sync_playwright

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
        print("✅ Cookies loaded and formatted successfully!")
        return True
    except Exception as e:
        print(f"⚠️ Failed to load cookies: {e}")
        return False

def get_latest_article():
    output_dir = "output"
    if not os.path.exists(output_dir):
        return None
    files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".md") or f.endswith(".txt")]
    if not files:
        return None
    latest_file = max(files, key=os.path.getmtime)
    with open(latest_file, "r", encoding="utf-8") as f:
        content = f.read()
    return latest_file, content

def parse_article_content(raw_content):
    lines = raw_content.splitlines()
    title = lines[0].replace("#", "").strip() if lines else "無題のタイトル"
    
    boundary_marker = "--- [NOTE PAID BOUNDARY] ---"
    
    parts = raw_content.split(boundary_marker)
    free_section = parts[0].replace(lines[0], "").strip() if len(parts) > 0 else raw_content
    paid_section = parts[1].strip() if len(parts) > 1 else ""
    return title, free_section, paid_section


def main():
    print("=== Starting Note Auto-Publisher (Final Polish) ===")
    
    res = get_latest_article()
    if not res:
        print("❌ No generated note articles found in output/")
        return
    
    file_path, raw_content = res
    title, free_section, paid_section = parse_article_content(raw_content)
    print(f"📌 Target Article: {file_path}")
    print(f"📌 Title: {title}")
    
    print(f"📊 Free section length: {len(free_section)} chars")
    if paid_section:
        print(f"📊 Paid section length: {len(paid_section)} chars")
    else:
        print("⚠️ 警告: '--- [NOTE PAID BOUNDARY] ---' が見つからなかったため、有料エリアは設定されません！")

    with sync_playwright() as p:
        print("🌐 Launching browser...")
        
        browser = p.chromium.launch(
            headless=False, 
            slow_mo=100, 
            args=["--window-size=1024,720"]
        )
        context = browser.new_context(viewport={"width": 1024, "height": 720})
        
        if not load_cookies_to_context(context):
            browser.close()
            return
        
        page = context.new_page()
        
        print("🚀 Navigating to note editor...")
        page.goto("https://editor.note.com/new/", timeout=60000)
        
        print("⏳ Waiting for editor to load...")
        try:
            page.wait_for_selector("textarea, div[contenteditable='true']", timeout=30000)
            print("✅ Editor loaded successfully!")
        except Exception as e:
            print(f"⚠️ Failed to detect editor: {e}")
            browser.close()
            return

        # 1. Input Title
        print("✍️ Typing title...")
        title_input = page.locator("textarea.p-editor__titleInput, textarea").first
        title_input.click()
        title_input.fill(title)
        
        # 2. Input Free Section
        print("✍️ Typing free section...")
        body_editor = page.locator("div.ProseMirror").first
        body_editor.click()
        page.keyboard.type(free_section, delay=2)
        
        page.wait_for_timeout(1000)

        # 3. Insert Paid Boundary via Keyboard Navigation
        if paid_section:
            print("💰 Inserting paid boundary via keyboard navigation...")
            try:
                page.keyboard.press("End")
                page.keyboard.press("Enter")
                page.wait_for_timeout(1000)
                
                print("⌨️ Pressing 'Tab' to focus '+' button...")
                page.keyboard.press("Tab")
                page.wait_for_timeout(500)
                
                print("⌨️ Pressing 'Enter' to open menu...")
                page.keyboard.press("Enter")
                page.wait_for_timeout(1000)
                
                print("⌨️ Pressing 'ArrowUp' then 'Enter' to select paid boundary...")
                page.keyboard.press("ArrowUp")
                page.wait_for_timeout(500)
                page.keyboard.press("Enter")
                
                page.wait_for_timeout(1500)
                
                print("⌨️ Pressing 'ArrowDown' x2 to move cursor below the line...")
                page.keyboard.press("ArrowDown")
                page.wait_for_timeout(300)
                page.keyboard.press("ArrowDown")
                page.wait_for_timeout(500)
                
                print("✅ Paid boundary line and cursor position fixed!")
                
            except Exception as e:
                print(f"⚠️ Could not insert paid line via keyboard: {e}")

            # 4. Input Paid Section
            print("✍️ Typing paid section into the paid area...")
            page.keyboard.type(paid_section, delay=2)

        # 5. Click "公開に進む"
        print("🚀 Clicking '公開に進む' button...")
        try:
            publish_btn = page.get_by_role("button", name=re.compile("公開に進む"))
            publish_btn.click()
            
            print("⏳ Waiting for publish configuration screen...")
            page.wait_for_timeout(4000)

            # 6. Select "有料" and set price
            if paid_section:
                print("💰 Selecting '有料' option...")
                paid_option = page.get_by_text("有料", exact=True)
                if paid_option.count() > 0:
                    paid_option.first.click()
                    page.wait_for_timeout(1000)
                    
                    # Set Price to 100 yen
                    print("💴 Setting price to 100 yen...")
                    price_input = page.locator("input[type='text'], input[type='tel'], input[type='number']").filter(has_not=page.locator("textarea")).first
                    if price_input.count() > 0:
                        price_input.click()
                        price_input.press("Control+A")
                        price_input.fill("100")
                        print("✅ Price set to 100 yen!")
                        page.wait_for_timeout(1000)
                    else:
                        print("⚠️ Price input field could not be targeted.")
                        
                    # 💡追加点1：右上にある「有料エリア設定」などの保存/確認ボタンを押す
                    print("💾 Clicking '有料エリア設定' (Save/Confirm) button...")
                    # 右上のボタンは「設定を保存」や「確認」などのテキストである可能性が高いため、ボタン要素で広く探します
                    # もし特定のテキスト（例：「保存」）であれば name="保存" に変更してください
                    setting_confirm_btn = page.get_by_role("button", name=re.compile("設定|保存|完了")).first
                    if setting_confirm_btn.is_visible():
                        setting_confirm_btn.click()
                        page.wait_for_timeout(2000)
                    else:
                        print("⚠️ '有料エリア設定' 保存ボタンが見つかりませんでした。画面の状態を確認してください。")

            # 💡追加点2：最終的な「投稿」ボタンを押す
            print("📢 Clicking final '投稿' (Publish) button...")
            final_publish_btn = page.get_by_role("button", name=re.compile("投稿|公開")).filter(has_text=re.compile("投稿|公開")).last
            
            if final_publish_btn.is_visible():
                final_publish_btn.click()
                print("✅ Final publish button clicked!")
                # 投稿完了画面に遷移するのを待つ
                page.wait_for_timeout(5000) 
            else:
                print("⚠️ 最終的な '投稿' ボタンが見つかりませんでした。")
                
        except Exception as e:
            print(f"⚠️ Error during publication settings automation: {e}")

        print("\n🎉 All automation steps completed!")
        input("Check the browser to confirm the article has been published successfully. Press Enter to close...")

        browser.close()
        print("✅ Session closed.")

if __name__ == "__main__":
    main()