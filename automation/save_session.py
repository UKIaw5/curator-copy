import os
from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.abspath("./x_user_data")

def main():
    print("🚀 Launching Google Chrome via Playwright...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            channel="chrome",  # ★ PCの正規Google Chromeを使用する指定
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = context.new_page()
        page.goto("https://x.com/login")
        
        print("\n------------------------------------------------------------")
        print("🔑 Log in using your Email or Username (@uk_indiehack_jp).")
        print("Once logged in, return here and press Enter.")
        print("------------------------------------------------------------\n")
        
        input("Press Enter after completing login...")
        
        print("💾 Session profile saved successfully!")
        context.close()

if __name__ == "__main__":
    main()
    