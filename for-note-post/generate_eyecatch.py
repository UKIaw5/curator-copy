import os
from playwright.sync_api import sync_playwright

def get_latest_markdown_file():
    output_dir = "output"
    if not os.path.exists(output_dir):
        return None, None
    files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".md")]
    if not files:
        return None, None
    latest_file = max(files, key=os.path.getmtime)
    with open(latest_file, "r", encoding="utf-8") as f:
        content = f.read()
    return latest_file, content

def generate_eyecatch_image(title, output_path):
    print(f"🎨 Generating eyecatch image for: '{title}'")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@700&family=Noto+Sans+JP:wght@700&display=swap');
            body {{
                width: 1920px;
                height: 1006px;
                margin: 0;
                padding: 0;
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                font-family: 'Noto Sans JP', 'Inter', sans-serif;
                color: #ffffff;
                box-sizing: border-box;
                overflow: hidden;
            }}
            .card {{
                width: 1680px;
                height: 766px;
                background: rgba(30, 41, 59, 0.7);
                border: 2px solid rgba(56, 189, 248, 0.3);
                border-radius: 24px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                padding: 100px;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(10px);
                text-align: center;
            }}
            .title {{
                font-size: 80px;
                font-weight: 700;
                line-height: 1.35;
                color: #f8fafc;
                margin: 0;
                display: -webkit-box;
                -webkit-line-clamp: 4;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="title">{title}</div>
        </div>
    </body>
    </html>
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1920, "height": 1006})
        page.set_content(html_content)
        page.wait_for_timeout(1000) # レンダリング安定待ち
        page.screenshot(path=output_path, clip={"x": 0, "y": 0, "width": 1920, "height": 1006})
        browser.close()
    
    print(f"✅ Eyecatch saved to: {output_path}")

def main():
    latest_file, content = get_latest_markdown_file()
    if not latest_file:
        print("❌ No markdown files found in output/")
        return
    
    lines = content.splitlines()
    title = lines[0].replace("#", "").replace("■", "").strip() if lines else "Untitled"
    
    base_name = os.path.splitext(os.path.basename(latest_file))[0]
    output_image_path = os.path.join("output", f"{base_name}.png")
    
    generate_eyecatch_image(title, output_image_path)

if __name__ == "__main__":
    main()