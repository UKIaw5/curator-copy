import os
import re
import json
import shutil
from datetime import datetime
from playwright.sync_api import sync_playwright

# 💡 カレントディレクトリに依存する相対パスだと、リポジトリルートから
# `python3 for-note-post/publish_to_note_batch.py` のように実行された際に
# note_status.json/cookieが見つからず、エラーも出さずに「何も無い」と
# 誤判定してしまう(実例で確認)。スクリプト自身の場所からの絶対パスにする
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(BASE_DIR, "note_status.json")
ARCHIVE_DIR = os.path.join(BASE_DIR, "output", "archive_published")

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
        return True
    except Exception as e:
        print(f"⚠️ Failed to load cookies: {e}")
        return False

def get_next_unpublished_article():
    """note_status.json を走査して、未投稿かつ監査通過済みの記事ファイルを1つ見つけて返す。
    💡 audit_passedがTrueのものだけを対象にする(監査ゲート)。未監査(キー無し)や
    不合格(False)の記事は、ハルシネーション等が未確認のまま自動公開されてしまう
    事故を防ぐため、ここでは返さない。監査は`/audit-drafts`Skillで事前に実行すること"""
    status_data = load_status()
    for raw_file, items in status_data.items():
        if not isinstance(items, dict):
            continue
        for idx, info in items.items():
            if isinstance(info, dict) and not info.get("published_to_note", False) and info.get("audit_passed") is True:
                md_path = info.get("generated_file")
                if md_path and os.path.exists(md_path):
                    return raw_file, idx, md_path, status_data
    return None, None, None, status_data

def parse_article_content(raw_content):
    lines = raw_content.splitlines()
    # 💡 モデルがタイトル中のツール名等をMarkdownのコード書式(`name`)や太字(**name**)
    # で装飾することがあり、#/■だけ除去してもバッククォートがタイトルに残ってしまう
    # (実例: "■ `universal-modder`: ..." → note.comのタイトル欄にバッククォートが
    # そのまま表示される事故を確認)
    title = lines[0].replace("#", "").replace("■", "").replace("`", "").replace("**", "").strip() if lines else "無題のタイトル"
    
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

def main(draft_only=False):
    print("=== Starting Note Batch Auto-Publisher (Loop Mode) ===")
    if draft_only:
        print("🧪 DRAFT-ONLY MODE: will stop at '下書き保存', nothing will be published. Status/archive will NOT be updated.")

    while True:
        # 1. 未投稿の物件（記事）を1つ取得
        raw_file, idx, file_path, status_data = get_next_unpublished_article()
        
        if not file_path:
            print("\n✅ All generated articles have been successfully published to note!")
            break
            
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
            
        title, free_section, paid_section = parse_article_content(raw_content)
        print(f"\n==============================================")
        print(f"📌 Target Article: {file_path}")
        print(f"📌 Title: {title}")
        print(f"📊 Free section length: {len(free_section)} chars")
        print(f"📊 Paid section length: {len(paid_section) if paid_section else 0} chars")
        print(f"==============================================")

        publish_success = False

        # 2. 1記事ごとにブラウザを新規起動
        with sync_playwright() as p:
            print("🌐 Launching browser for this article...")
            browser = p.chromium.launch(
                headless=False,  # 動作確認のため一旦False。安定したらTrueでもOK
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

                # --- タイトル入力 ---
                print("✍️ Typing title...")
                title_input = page.locator("textarea.p-editor__titleInput, textarea").first
                title_input.click()
                title_input.fill(title)
                
                # --- 無料部分入力 ---
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

                # --- 有料境界の挿入 & 有料部分入力 ---
                if paid_section:
                    print("💰 Inserting paid boundary via keyboard navigation...")
                    page.keyboard.press("End")
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(800)
                    
                    page.keyboard.press("Tab")
                    page.wait_for_timeout(400)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(800)
                    
                    page.keyboard.press("ArrowUp")
                    page.wait_for_timeout(400)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(1200)
                    
                    page.keyboard.press("ArrowDown")
                    page.wait_for_timeout(300)
                    page.keyboard.press("ArrowDown")
                    page.wait_for_timeout(400)
                    
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
                    draft_btn = page.get_by_role("button", name=re.compile("下書き保存"))
                    draft_btn.click()
                    page.wait_for_timeout(3000)
                    print("🧪 Saved as draft. Check note.com now to confirm no corruption and that the link is clickable.")
                    input("Press Enter here to close the browser (this will NOT publish anything)...")
                    browser.close()
                    print("✅ Draft-only test finished (not published, status/archive untouched).")
                    return

                # --- 公開設定画面へ ---
                print("🚀 Clicking '公開に進む' button...")
                publish_btn = page.get_by_role("button", name=re.compile("公開に進む"))
                publish_btn.click()
                page.wait_for_timeout(4000)

                # --- 有料設定（100円） ---
                if paid_section:
                    print("💰 Selecting '有料' option...")
                    paid_option = page.get_by_text("有料", exact=True)
                    if paid_option.count() > 0:
                        paid_option.first.click()
                        page.wait_for_timeout(1000)
                        
                        print("💴 Setting price to 100 yen...")
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

                # --- 最終投稿ボタン ---
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

        # 3. 投稿成功したらステータスを更新してファイルを移動し、次のループへ
        if publish_success:
            update_status_and_archive(file_path, raw_file, idx, status_data)
            print("🎉 Article successfully posted! Moving to next item...")
            # 連続投稿によるレームダッシュやnote側のブロックを防ぐため少しウェイト
            import time
            time.sleep(3)
        else:
            print("❌ Publication failed for this article. Stopping batch to prevent cascade errors.")
            break

    print("✅ All batch publication tasks finished!")

if __name__ == "__main__":
    import sys
    main(draft_only="--draft-only" in sys.argv)