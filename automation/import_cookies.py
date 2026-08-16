import os
import json
import time
from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.abspath("./x_user_data")
COOKIE_FILE = "cookies.json"

def main():
    if not os.path.exists(COOKIE_FILE):
        print(f"❌ {COOKIE_FILE} not found. Please export your cookies first.")
        return

    print("📖 Reading cookies.json...")
    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    # Convert Cookie-Editor format to Playwright format if necessary
    formatted_cookies = []
    for c in cookies:
        cookie_dict = {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c["path"],
            "secure": c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
            "sameSite": "Lax" if c.get("sameSite") == "no_restriction" else "Lax"
        }
        if "expirationDate" in c:
            cookie_dict["expires"] = c["expirationDate"]
        formatted_cookies.append(cookie_dict)

    print("🚀 Launching Playwright browser...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # Inject cookies into the browser context
        context.add_cookies(formatted_cookies)
        
        page = context.new_page()
        print("🌐 Opening X home page with injected session...")
        page.goto("https://x.com/home")
        
        time.sleep(3)
        print("\n------------------------------------------------------------")
        print("🎉 If you see your home timeline logged in, it succeeded!")
        print("Press Enter to save this persistent session and exit.")
        print("------------------------------------------------------------\n")
        
        input("Press Enter once verified...")
        context.close()
        print("💾 Session profile updated in x_user_data/!")

if __name__ == "__main__":
    main()
