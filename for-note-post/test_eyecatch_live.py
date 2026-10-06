"""アイキャッチ画像アップロード機能の単体ライブテスト。
本番のnote_status.json・記事ファイルには一切触れない。

デフォルト: 下書き保存で止まり、公開はしない。
--publish 指定時: URL再リンク→アイキャッチ→実際に「公開」まで完走する
(テスト用のダミー記事が実際に公開されるので、確認後はnote.com側で手動削除すること)。"""
import os
import re
import sys
import tempfile
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_eyecatch import generate_eyecatch_image
from publish_to_note_free_batch import load_cookies_to_context, attach_eyecatch_image, relink_urls_in_editor, extract_urls

TEST_TITLE = "【テスト】自動投稿パイプライン完走確認(後ほど削除します)"
TEST_BODY = (
    "これは自動投稿パイプラインの完走確認用テスト記事です。確認が終わったら削除してください。\n\n"
    "■ 参考リンク\n\n"
    "https://github.com/anthropics/claude-code\n\n"
    "#テスト #自動化"
)

def main(do_publish=False):
    eyecatch_path = os.path.join(tempfile.gettempdir(), "eyecatch_live_test.png")
    print("🎨 Generating test eyecatch image...")
    generate_eyecatch_image(TEST_TITLE, eyecatch_path)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100, args=["--window-size=1024,720"])
        context = browser.new_context(viewport={"width": 1024, "height": 720})
        if not load_cookies_to_context(context):
            print("❌ Failed to load cookies.")
            browser.close()
            return
        page = context.new_page()
        page.goto("https://editor.note.com/new/", timeout=60000)
        page.wait_for_selector("textarea, div[contenteditable='true']", timeout=30000)
        print("✅ Editor loaded.")

        # 💡 順番を入れ替えて検証: 画像アップロードを本文入力より先に行う
        print("🖼️ Attaching eyecatch image (BEFORE writing title/body, as a test)...")
        attach_eyecatch_image(page, eyecatch_path)
        page.wait_for_timeout(3000)

        title_input = page.locator("textarea.p-editor__titleInput, textarea").first
        title_input.click()
        title_input.fill(TEST_TITLE)

        body_editor = page.locator("div.ProseMirror").first
        body_editor.click()
        page.keyboard.insert_text(TEST_BODY)
        page.wait_for_timeout(1000)

        urls = extract_urls(TEST_BODY)
        if urls:
            print(f"🔗 Relinking {len(urls)} URL(s)...")
            relink_urls_in_editor(page, urls)

        after_shot = os.path.join(tempfile.gettempdir(), "note_after_eyecatch.png")
        page.screenshot(path=after_shot)
        print(f"📸 Post-write screenshot saved to: {after_shot}")
        print(f"🔎 Visible buttons: {page.get_by_role('button').all_text_contents()}")

        if not do_publish:
            print("🧪 Clicking '下書き保存'...")
            draft_btn = page.get_by_role("button", name="下書き保存")
            draft_btn.click()
            page.wait_for_timeout(3000)
            print("🧪 Saved as draft (not published). Check the eyecatch image in the browser now.")
        else:
            print("🚀 Clicking '公開に進む'...")
            publish_btn = page.get_by_role("button", name=re.compile("公開に進む"))
            publish_btn.click()
            page.wait_for_timeout(4000)
            print("📢 Clicking final '投稿' button...")
            final_publish_btn = page.get_by_role("button", name=re.compile("投稿|公開")).filter(has_text=re.compile("投稿|公開")).last
            if final_publish_btn.is_visible():
                final_publish_btn.click()
                page.wait_for_timeout(5000)
                print("✅ PUBLISHED for real. Please delete this test article on note.com after confirming.")
            else:
                print("⚠️ Final publish button not found. Diagnosing...")
                shot_path = os.path.join(tempfile.gettempdir(), "note_publish_debug.png")
                page.screenshot(path=shot_path)
                print(f"📸 Screenshot saved to: {shot_path}")
                all_buttons = page.get_by_role("button").all_text_contents()
                print(f"🔎 Visible buttons on screen: {all_buttons}")

        # 💡 `!`モード等、標準入力がTTYでない場合はinput()がEOFErrorで落ちる
        # (socialdog_poster.pyで実例あり)。ここで落ちると目視確認の前に
        # ブラウザが強制終了してしまうので握りつぶす
        try:
            input("Press Enter here to close the browser...")
        except EOFError:
            page.wait_for_timeout(5000)
        browser.close()

    if os.path.exists(eyecatch_path):
        os.remove(eyecatch_path)
    print("✅ Test finished.")

if __name__ == "__main__":
    main(do_publish="--publish" in sys.argv)
