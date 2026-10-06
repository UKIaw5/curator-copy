import os
import re
import json
import shutil
from datetime import datetime
from playwright.sync_api import sync_playwright

# 💡 カレントディレクトリに依存する相対パスだと、リポジトリルートから
# `python3 for-note-post/publish_to_note.py` のように実行された際に
# note_status.json/cookieが見つからず、エラーも出さずに誤動作する恐れが
# ある(publish_to_note_batch.pyで実例を確認)。スクリプト自身の場所からの
# 絶対パスにする
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(BASE_DIR, "note_status.json")

def load_cookies_to_context(context):
    cookie_path = os.path.join(BASE_DIR, "note_cookies.json")
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
    output_dir = os.path.join(BASE_DIR, "output")
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
    # 💡 モデルがタイトル中のツール名等をMarkdownのコード書式(`name`)や太字(**name**)
    # で装飾することがあり、#/■だけ除去してもバッククォートがタイトルに残ってしまう
    # (実例: "■ `universal-modder`: ..." → note.comのタイトル欄にバッククォートが
    # そのまま表示される事故を確認)
    title = lines[0].replace("#", "").replace("■", "").replace("`", "").replace("**", "").replace("[", "").replace("]", "").strip() if lines else "無題のタイトル"
    
    boundary_marker = "<!-- PAYWALL -->"

    parts = raw_content.split(boundary_marker)
    # 💡 先頭行(タイトル)だけを除去する。文字列全体へのreplace()は、本文中に
    # タイトルと同じ文言が再出現した場合そこも誤って削除してしまうため使わない
    free_lines = parts[0].splitlines() if len(parts) > 0 else raw_content.splitlines()
    free_section = "\n".join(free_lines[1:]).strip() if free_lines else ""
    paid_section = parts[1].strip() if len(parts) > 1 else ""
    return title, free_section, paid_section

def relink_urls_in_editor(page, urls: list):
    """insert_textで入力済みの本文中から各URLを見つけ、選択→削除→
    1文字ずつ再入力することでクリック可能なリンクに変換する。
    本文編集の最後の操作として行い、この後は何も挿入しない
    (以前URLをtype()で混在入力して事故を起こした教訓を踏まえた設計)。

    💡 URLを再入力するだけではリンク化(自動カード生成)は発火しない
    (実例で確認: ドラフト保存後もプレーンテキストのままだった)。
    note.comのリンク自動検出はEnter入力をトリガーにしており、スペース
    よりEnterの方がきれいにリンク化されることをユーザーが実機で確認済み。
    再入力の直後にEnterを押して確定させる(これが本文編集の最後の
    操作であることは変わらないので安全)。
    """
    for url in urls:
        try:
            target = page.get_by_text(url, exact=True).first
            target.click(click_count=3)
            page.wait_for_timeout(300)
            page.keyboard.press("Backspace")
            page.wait_for_timeout(300)
            page.keyboard.type(url, delay=20)
            page.keyboard.press("Enter")  # リンク自動検出のトリガー
            page.wait_for_timeout(1500)
            print(f"🔗 Relinked URL: {url}")
        except Exception as e:
            print(f"⚠️ Failed to relink URL {url}: {e}")

def extract_urls(text):
    # 💡 同じURLが本文中に複数回出現すると、1回目のリンク化成功後に
    # 2回目以降は既にリンクカード化されていて見つからずタイムアウトする
    # (実例で確認: 30秒のムダ待ちになるだけで実害はないが非効率)。
    # 重複を除去して1URLにつき1回だけ処理する
    seen = set()
    urls = []
    for u in re.findall(r'https?://[^\s)]+', text):
        if u not in seen:
            seen.add(u)
            urls.append(u)
    return urls

def update_status_and_archive(file_path):
    """投稿完了後に status ファイルを更新し、ファイルを archive ディレクトリへ移動する"""
    filename = os.path.basename(file_path)
    
    # 1. note_status.json の更新
    status_data = {}
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                status_data = json.load(f)
        except json.JSONDecodeError:
            status_data = {}
            
    if "published_articles" not in status_data:
        status_data["published_articles"] = []
        
    status_data["published_articles"].append({
        "filename": filename,
        "published_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_data, f, ensure_ascii=False, indent=4)
    print(f"📝 Updated {STATUS_FILE} with published record.")

    # 2. output/archive への移動
    archive_dir = os.path.join(BASE_DIR, "output", "archive")
    os.makedirs(archive_dir, exist_ok=True)
    destination_path = os.path.join(archive_dir, filename)
    
    # 万が一同名ファイルがある場合はタイムスタンプで退避
    if os.path.exists(destination_path):
        base, ext = os.path.splitext(filename)
        destination_path = os.path.join(archive_dir, f"{base}_{datetime.now().strftime('%H%M%S')}{ext}")
        
    shutil.move(file_path, destination_path)
    print(f"📦 Moved published file to: {destination_path}")

def main(draft_only=False):
    print("=== Starting Note Auto-Publisher (Final Polish + Archiver) ===")
    if draft_only:
        print("🧪 DRAFT-ONLY MODE: will stop at '下書き保存', nothing will be published.")

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
        print("⚠️ 警告: '<!-- PAYWALL -->' が見つからないため、有料エリアは設定されません！")

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
        # 💡 URL部分だけ1文字ずつ入力してリンク化を狙うハイブリッド方式を
        # 試したが、note.comのリンクカード生成とカーソル位置がずれ、
        # 本文の途中にURL/ハッシュタグが割り込む重大な文章破損が実際の
        # 公開記事で発生した。安全なinsert_text()一本に戻す
        # (URLはクリック不可のプレーンテキストのままだが、文章は壊れない)
        page.keyboard.insert_text(free_section)
        
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
            page.keyboard.insert_text(paid_section)
            page.wait_for_timeout(1000)

        # --- URLをクリック可能なリンクに変換(本文編集の最後の操作) ---
        urls = extract_urls(free_section + "\n" + paid_section)
        if urls:
            print(f"🔗 Relinking {len(urls)} URL(s) in editor...")
            relink_urls_in_editor(page, urls)

        if draft_only:
            print("🧪 Clicking '下書き保存' (draft-only mode, will NOT publish)...")
            try:
                draft_btn = page.get_by_role("button", name=re.compile("下書き保存"))
                draft_btn.click()
                page.wait_for_timeout(3000)
                print("🧪 Saved as draft. Check note.com now to confirm no corruption and that the link is clickable.")
            except Exception as e:
                print(f"⚠️ Could not click draft save button: {e}")
            # 💡 `!`モード等、標準入力がTTYでない場合はinput()がEOFErrorで
            # 落ちる(socialdog_poster.pyで実例あり)。ここで落ちると目視
            # 確認の前にブラウザが強制終了してしまうので握りつぶす
            try:
                input("Press Enter here to close the browser (this will NOT publish anything)...")
            except EOFError:
                page.wait_for_timeout(5000)
            browser.close()
            print("✅ Draft-only test finished (not published).")
            return

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
                        
                    print("💾 Clicking '有料エリア設定' (Save/Confirm) button...")
                    setting_confirm_btn = page.get_by_role("button", name=re.compile("設定|保存|完了")).first
                    if setting_confirm_btn.is_visible():
                        setting_confirm_btn.click()
                        page.wait_for_timeout(2000)
                    else:
                        print("⚠️ '有料エリア設定' 保存ボタンが見つかりませんでした。画面の状態を確認してください。")

            print("📢 Clicking final '投稿' (Publish) button...")
            final_publish_btn = page.get_by_role("button", name=re.compile("投稿|公開")).filter(has_text=re.compile("投稿|公開")).last
            
            if final_publish_btn.is_visible():
                final_publish_btn.click()
                print("✅ Final publish button clicked!")
                page.wait_for_timeout(5000) 
                
                # 7. Post-process: Update status and archive file
                update_status_and_archive(file_path)
                
            else:
                print("⚠️ 最終的な '投稿' ボタンが見つかりませんでした。ステータス更新とアーカイブはスキップされます。")
                
        except Exception as e:
            print(f"⚠️ Error during publication settings automation: {e}")

        print("\n🎉 All automation steps completed!")
        input("Check the browser to confirm the article has been published successfully. Press Enter to close...")

        browser.close()
        print("✅ Session closed.")

if __name__ == "__main__":
    import sys
    main(draft_only="--draft-only" in sys.argv)