import os
import pytest
from cloakbrowser import launch

@pytest.fixture(scope="module")
def stealth_browser():
    """
    Phase 2: ステルス検証用フィクスチャ
    実際の人間らしい動作をテストするため headless=False / humanize=True を推奨
    """
    browser = launch(
        headless=False,  # 動作確認のため画面を表示
        humanize=True    # マウス移動や入力を人間らしくシミュレート
    )
    yield browser
    browser.close()

def test_sannysoft_stealth_check(stealth_browser):
    """
    bot.sannysoft.com で主要なボットフラグが隠せているかテスト
    """
    page = stealth_browser.new_page()
    
    # 1. 検出サイトへアクセス
    page.goto("https://bot.sannysoft.com/", wait_until="networkidle")
    
    # 2. 主要なJSプロパティをページ内で直接評価（Eval）
    webdriver_flag = page.evaluate("navigator.webdriver")
    chrome_obj = page.evaluate("window.chrome")
    
    print(f"\n[Stealth Test] navigator.webdriver: {webdriver_flag}")
    print(f"[Stealth Test] window.chrome exists: {chrome_obj is not None}")
    
    # 3. アサーション（自動化フラグが False または None であること）
    assert not webdriver_flag, "❌ navigator.webdriver が検知されています！"
    assert chrome_obj is not None, "❌ window.chrome が存在しません（Bot特徴）"
    
    # 4. 判定結果のスクリーンショットを保存
    os.makedirs("results", exist_ok=True)
    screenshot_path = "results/stealth_result.png"
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"📷 判定画面のスクリーンショットを保存しました: {screenshot_path}")
    
    page.close()

if __name__ == "__main__":
    # 直接実行用（pytestを介さない場合）
    print("--- ステルステスト（直実行） ---")
    browser = launch(headless=False, humanize=True)
    page = browser.new_page()
    page.goto("https://bot.sannysoft.com/", wait_until="networkidle")
    
    wd = page.evaluate("navigator.webdriver")
    print(f"navigator.webdriver -> {wd} (期待値: False または undefined)")
    
    os.makedirs("results", exist_ok=True)
    page.screenshot(path="results/stealth_direct.png", full_page=True)
    browser.close()
    print("完了しました。results/stealth_direct.png を確認してください。")
