"""アイキャッチ画像アップロード機能の単体ライブテスト。
本番のnote_status.json・記事ファイルには一切触れない。下書き保存で止まり、
公開はしない。確認が終わったらnote.com側でこの下書きを手動削除すること。"""
import os
import sys
import tempfile
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_eyecatch import generate_eyecatch_image
from publish_to_note_free_batch import load_cookies_to_context, attach_eyecatch_image

TEST_TITLE = "【テスト】アイキャッチ画像アップロード確認"
TEST_BODY = "これはアイキャッチ画像アップロード機能の動作確認用テスト記事です。下書き保存のまま公開はしません。"

def main():
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

        title_input = page.locator("textarea.p-editor__titleInput, textarea").first
        title_input.click()
        title_input.fill(TEST_TITLE)

        body_editor = page.locator("div.ProseMirror").first
        body_editor.click()
        page.keyboard.insert_text(TEST_BODY)
        page.wait_for_timeout(1000)

        print("🖼️ Attaching eyecatch image...")
        attach_eyecatch_image(page, eyecatch_path)

        print("🧪 Clicking '下書き保存'...")
        draft_btn = page.get_by_role("button", name="下書き保存")
        draft_btn.click()
        page.wait_for_timeout(3000)

        print("🧪 Saved as draft. Check the eyecatch image in the browser now.")
        # 💡 `!`モード等、標準入力がTTYでない場合はinput()がEOFErrorで落ちる
        # (socialdog_poster.pyで実例あり)。ここで落ちると目視確認の前に
        # ブラウザが強制終了してしまうので握りつぶす
        try:
            input("Press Enter here to close the browser (this will NOT publish anything)...")
        except EOFError:
            page.wait_for_timeout(5000)
        browser.close()

    if os.path.exists(eyecatch_path):
        os.remove(eyecatch_path)
    print("✅ Test finished. Please manually delete this test draft on note.com.")

if __name__ == "__main__":
    main()
