import os
import shutil
import glob
import json
import requests
import re
import sys
import html
from datetime import datetime
from playwright.sync_api import sync_playwright

# 💡 --dry-run: 生成結果をoutput/dry_run/に隔離し、note_status.jsonや
# 本番のoutput/に一切書き込まない検証モード(X側のrun_today_pipeline_parta.py
# --dry-runと同じ設計思想)
DRY_RUN = "--dry-run" in sys.argv

OLLAMA_URL = "http://localhost:11434/api/generate"

# --- Robust Agent Placement ---
TOC_MODEL = "qwen2.5-coder:14b"
WRITER_MODEL = "gemma4:12b"
REVIEWER_MODEL = "qwen2.5-coder:14b"
HOOK_MODEL = "qwen2.5-coder:14b"
INSIGHT_MODEL = "qwen2.5-coder:14b"
LINK_MODEL = "qwen2.5-coder:14b"

# 💡 モデルが「データが空/不十分」として本来の出力ではなく拒否・確認の
# 返答をしてきた場合に検出するためのマーカー。英語("Please provide...")
# だけでなく日本語での丁寧な拒否("申し訳ございません...")も実例を確認済み
REFUSAL_MARKERS = [
    "Please provide",
    "please provide",
    "申し訳ございません",
    "申し訳ありません",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_SUBDIR = "output/dry_run" if DRY_RUN else "output"
STATUS_FILE = (
    os.path.join(BASE_DIR, "output/dry_run/note_status.json")
    if DRY_RUN
    else os.path.join(BASE_DIR, "note_status.json")
)
PAYWALL_MARKER = "<!-- PAYWALL -->"

def call_llm(model_name: str, prompt: str, num_predict: int = 4000, num_ctx: int = 8192) -> str:
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "think": False,  # 💡 思考トレースがnum_predictを食い尽くすのを防ぐ
        "options": {
            "temperature": 0.6,
            "num_predict": num_predict,
            "num_ctx": num_ctx
        }
    }
    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=600)
        res.raise_for_status()
        response_text = res.json().get("response", "").strip()
        if any(marker in response_text for marker in REFUSAL_MARKERS):
            return ""
        return response_text
    except Exception as e:
        print(f"❌ LLM Error ({model_name}): {e}")
        return ""

def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except json.JSONDecodeError: return {}
    return {}

def save_status(data):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def split_raw_items(raw_content: str) -> list:
    """Stage1の生データを個別の要約に分割する。新形式は専用の境界トークン
    <<<CURATOR_ITEM_BOUNDARY>>>で区切られているが、2026-10-04より前に
    生成された既存ファイルは旧形式("---"区切り)のままなので両対応する。
    旧形式のまま新トークンだけで分割すると、1ファイル全体が1件の要約と
    誤認識され、無関係な複数記事の内容が1つの記事に混入する事故につながる。"""
    if "<<<CURATOR_ITEM_BOUNDARY>>>" in raw_content:
        parts = raw_content.split("<<<CURATOR_ITEM_BOUNDARY>>>")
    else:
        parts = re.split(r"\n+\s*---\s*\n+", raw_content)
    return [s.strip() for s in parts if s.strip()]

def get_active_raw_file():
    raw_dir = os.path.join(BASE_DIR, "../output/raw")
    status = load_status()
    raw_files = sorted(
        glob.glob(os.path.join(raw_dir, "output_prex_posts_*.md")),
        key=os.path.getmtime,
        reverse=True
    )
    for latest_file in raw_files:
        basename = os.path.basename(latest_file)
        with open(latest_file, "r", encoding="utf-8") as f:
            items = split_raw_items(f.read())
        if basename not in status:
            status[basename] = {}
        if any(not status[basename].get(str(i), {}).get("note_used", False) for i in range(len(items))):
            return latest_file, items, status
    return None, [], status

def is_japanese_text(text: str, min_ratio: float = 0.3) -> bool:
    """モデルが日本語化の指示を無視し、英語のまま(または丸ごと英訳して)
    返すケースを検出する。"""
    if not text:
        return False
    japanese_chars = re.findall(r"[぀-ヿ一-鿿]", text)
    return (len(japanese_chars) / len(text)) >= min_ratio

def strip_duplicate_intro(draft_body: str) -> str:
    """Gemmaが「タイトル/目次を繰り返すな」という指示を無視し、本文冒頭に
    TOCと同じタイトル・目次・得られることリストを再掲することがある。
    最初の番号付き見出し(例: "## 1. ...")より前の部分を取り除く。"""
    match = re.search(r'^#{1,3}\s*\d+[\.\、]', draft_body, flags=re.MULTILINE)
    if match and match.start() > 0:
        return draft_body[match.start():].strip()
    return draft_body

def insert_paywall_smartly(text: str) -> str:
    if PAYWALL_MARKER in text:
        return text
    
    lines = text.split('\n')
    h2_indices = [i for i, line in enumerate(lines) if line.startswith('## ') or line.startswith('■ ')]
    
    if len(h2_indices) >= 3:
        target_idx = int(len(h2_indices) * 0.7)
        if target_idx == 0: target_idx = 1
        insert_line_idx = h2_indices[target_idx]
        lines.insert(insert_line_idx, f"\n{PAYWALL_MARKER}\n")
        return "\n".join(lines)
    else:
        paragraphs = text.split('\n\n')
        if len(paragraphs) > 3:
            insert_idx = int(len(paragraphs) * 0.7)
            paragraphs.insert(insert_idx, f"\n{PAYWALL_MARKER}\n")
            return "\n\n".join(paragraphs)
        else:
            paragraphs.append(f"\n{PAYWALL_MARKER}\n")
            return "\n\n".join(paragraphs)

def lint_markdown(text: str) -> str:
    if not text:
        return ""

    parts = text.split(PAYWALL_MARKER)
    sanitized_parts = []

    for part in parts:
        t = part
        
        # 1. Fix duplicated numbering (e.g., "2. 2. " or "3.3. ")
        t = re.sub(r'(?m)^\s*(\d+)[\.\s]+\1\.\s+', r'\1. ', t)
        
        # 2. Convert Markdown headers to ■
        # 💡 "#"の直後にスペースが無い行("#LLM #Python"等のハッシュタグ行)は
        # 見出しではないので変換しない。\s*だと0文字にもマッチしてしまい、
        # ハッシュタグ1つ目の"#"まで誤って消してしまう事故があったため\s+に変更
        lines = t.splitlines()
        processed_lines = []
        for line in lines:
            if re.match(r'^#+\s+', line):
                processed_lines.append(re.sub(r'^#+\s+', '■ ', line))
            else:
                processed_lines.append(line)
        t = "\n".join(processed_lines)
        
        # --- 🛡️ 追加: LaTeXの数式（$R_{AI}$など）のアンダースコア崩れを防ぐ置換 ---
        # $R_{AI}$ のような記法をプレーンな R_AI に置換する
        t = re.sub(r'\$([A-Za-z0-9]+)_([A-Za-z0-9]+)\$', r'\1_\2', t)
        # -----------------------------------------------------------------

        # 3. Remove bold formatting syntax
        t = t.replace('**', '')
        
        # 4. Convert bullet points to ・
        t = re.sub(r'(?m)^\s*[\*\-]\s+', '・ ', t)
        
        # 5. Remove code block fences
        t = re.sub(r'```[a-zA-Z]*\n?', '', t)
        
        sanitized_parts.append(t.strip())

    result = f"\n\n{PAYWALL_MARKER}\n\n".join(sanitized_parts)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()

def generate_eyecatch(title: str, output_image_path: str):
    """推奨サイズ 1920x1006px でダークモード風のアイキャッチ画像を自動生成する"""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                margin: 0;
                width: 1920px;
                height: 1006px;
                background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                padding: 120px 140px;
                box-sizing: border-box;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                color: #f8fafc;
            }}
            .badge {{
                background: #3b82f6;
                color: white;
                font-size: 28px;
                font-weight: 600;
                padding: 12px 28px;
                border-radius: 10px;
                width: fit-content;
                letter-spacing: 0.05em;
            }}
            .title {{
                font-size: 72px;
                font-weight: 800;
                line-height: 1.35;
                color: #ffffff;
                margin: 0;
                display: -webkit-box;
                -webkit-line-clamp: 3;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }}
            .footer {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-top: 1px solid rgba(255, 255, 255, 0.15);
                padding-top: 36px;
            }}
            .brand {{
                font-size: 32px;
                font-weight: 700;
                color: #94a3b8;
                letter-spacing: 0.05em;
            }}
        </style>
    </head>
    <body>
        <div class="badge">TECHNICAL INSIGHT</div>
        <div class="title">{html.escape(title)}</div>
        <div class="footer">
            <div class="brand">Local LLM & MLOps Pipeline</div>
        </div>
    </body>
    </html>
    """
    
    temp_html = os.path.join(BASE_DIR, "output", "temp_eyecatch.html")
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1006})
        page.goto(f"file://{os.path.abspath(temp_html)}")
        page.screenshot(path=output_image_path)
        browser.close()
        
    if os.path.exists(temp_html):
        os.remove(temp_html)
    print(f"🖼️ Eyecatch image generated: {output_image_path}")

def main():
    print("=== Note Article Generator v2.6 (With 1920x1006 Eyecatch & Hashtags) ===")
    if DRY_RUN:
        print(
            "🧪 DRY RUN MODE: output goes to `output/dry_run/`, and "
            "`note_status.json` is NOT touched. The selected item will NOT "
            "be marked as used in the real status file."
        )
    latest_file, items, status = get_active_raw_file()
    if not items:
        print("❌ No active raw items found.")
        return

    basename = os.path.basename(latest_file)
    available = [(i, t) for i, t in enumerate(items) if not status[basename].get(str(i), {}).get("note_used", False)]
    if not available:
        print("❌ No unused items remaining in current file.")
        return

    print(f"\n📂 Active File: {basename}")
    for idx, (orig_idx, text) in enumerate(available, 1):
        print(f"  [{idx}] (Item #{orig_idx + 1}) {text.split('\n')[0][:70]}...")

    choice = int(input(f"\nSelect item (1-{len(available)}): ")) - 1
    orig_idx, selected_text = available[choice]

    # --- Step 1: Specific Title & TOC ---
    intro_prompt = f"""
Generate a catchy, specific Japanese technical article title containing proper nouns (tool names, repositories, or frameworks) from the raw data, followed by takeaways and a table of contents.
[Strict Rules]
1. Do NOT use generic titles like "自動プロンプトコーディングエージェントスキル". Include specific names (e.g., repository or framework names).
2. Translate everything into natural Japanese.
3. Output ONLY the Markdown format below, with no extra conversational text or labels.

# [Specific Catchy Title with Proper Nouns]

## この記事で得られること
- [Takeaway 1]
- [Takeaway 2]
- [Takeaway 3]

## 目次
1. [Section 1 Name]
2. [Section 2 Name]
3. [Section 3 Name]

Raw Data:
{selected_text}
"""
    print(f"💡 Step 1: Generating specific title and TOC with {TOC_MODEL}...")
    part_intro = call_llm(TOC_MODEL, intro_prompt)
    if not part_intro or not is_japanese_text(part_intro):
        part_intro = "# 技術解説記事\n\n## この記事で得られること\n- 最新ツールの解説\n- アーキテクチャの理解\n- 実装への応用\n\n## 目次\n1. 概要\n2. 仕組み\n3. まとめ"

    # --- Step 2: Body Generation ---
    body_writer_prompt = f"""
Write a comprehensive, deep-dive Japanese technical article based on the raw data.
[Strict Rules]
1. Professional engineering Japanese only. No English sentences.
2. CRITICAL: You MUST use the exact section headings defined in the [Target Table of Contents] below. Do NOT invent your own headings.
3. Do NOT repeat the Title or Table of Contents. Output ONLY the body sections starting directly from the first heading.
4. Provide deep explanations for every section. Ensure high volume and detail.

[Target Table of Contents]
{part_intro}

Raw Data:
{selected_text}
"""
    print(f"🤖 Step 2: Generating deep-dive body matching TOC with {WRITER_MODEL}...")
    draft_body = call_llm(WRITER_MODEL, body_writer_prompt, num_predict=3000)
    if not draft_body or not is_japanese_text(draft_body):
        draft_body = selected_text
    draft_body = strip_duplicate_intro(draft_body)

    # --- Step 3: Review ---
    reviewer_prompt = f"""
Refine the following Japanese technical article draft for professional tone and grammar.
[Strict Rules]
1. Fix literal translations. Ensure smooth engineering phrasing.
2. Do NOT truncate or summarize. Output the full text.
3. Output ONLY the refined Markdown.

Draft:
{draft_body}
"""
    print(f"🧐 Step 3: Reviewing with {REVIEWER_MODEL}...")
    part_body = call_llm(REVIEWER_MODEL, reviewer_prompt, num_predict=3000)
    if not part_body or not is_japanese_text(part_body):
        part_body = draft_body
    
    part_body = insert_paywall_smartly(part_body)

    # --- Step 4: Hook Optimizer ---
    print(f"🪝 Step 4: Optimizing Paywall Cliffhanger with {HOOK_MODEL}...")
    parts = part_body.split(PAYWALL_MARKER)
    free_text = parts[0].strip()
    paid_text = parts[1].strip() if len(parts) > 1 else ""

    free_paragraphs = free_text.split("\n\n")
    if len(free_paragraphs) > 0:
        target_paragraph = free_paragraphs[-1]
        hook_prompt = f"""
Rewrite the following paragraph to be a powerful cliffhanger right before a paywall in a technical article.
- Highlight a critical technical bottleneck or unsolved mystery.
- End with a dramatic transition like "なぜなら——" or "そのアーキテクチャの全貌は──".
- Output ONLY the rewritten Japanese paragraph.

Original paragraph:
{target_paragraph}
"""
        optimized_hook = call_llm(HOOK_MODEL, hook_prompt, num_predict=1000)
        if optimized_hook and is_japanese_text(optimized_hook):
            free_paragraphs[-1] = optimized_hook
            free_text = "\n\n".join(free_paragraphs)

    # --- Step 5: Field Impact ---
    # 💡 本文(part_body)を渡さず生データだけから生成していたため、本文と
    # ほぼ同じ内容を焼き直すだけの重複セクションになっていた(実例で確認)。
    # 本文を踏まえた上で「本文にはない新しい切り口」を明示的に要求する
    insight_prompt = f"""
以下は、ある技術記事の本文です。この本文の内容を踏まえた上で、「現場での具体的インパクトと適用場面」について分析してください。

[厳守事項]
1. 本文で既に説明されている内容をそのまま言い換えたり要約したりしないでください。
2. 実務導入のメリット・コストや工数への影響・既存ワークフローとの比較・競合技術との違いなど、本文にはない新しい切り口を加えてください。
3. 出力は日本語の本文段落・箇条書きのみとし、Markdown見出しは使わないでください。

[本文]
{part_body}

[元データ(参考)]
{selected_text}
"""
    print(f"💡 Step 5: Generating field impact with {INSIGHT_MODEL}...")
    # 💡 本文全体をプロンプトに含めるため、デフォルトのnum_ctx(8192)では
    # 本文が長い記事だと収まらない恐れがあるので拡張しておく
    part_insight = call_llm(INSIGHT_MODEL, insight_prompt, num_ctx=16384)
    if not part_insight or not is_japanese_text(part_insight):
        part_insight = "実務における適用価値と今後の展望についての考察。"

    # --- Step 6: Link Extraction ---
    link_prompt = f"""
Extract the exact official URLs (Hugging Face, ArXiv, GitHub) from the raw data.
[Strict Rules]
1. Output ONLY the raw URLs, one URL per line.
2. Do NOT include any site names, bullet points, or markdown link syntax. Just the pure URL strings.

Raw Data:
{selected_text}
"""
    print(f"🔗 Step 6: Extracting links with {LINK_MODEL}...")
    part_links = call_llm(LINK_MODEL, link_prompt, num_predict=1000)

    # --- Step 6.5: Hashtag Generation ---
    hashtag_prompt = f"""
Generate 3 relevant technical hashtags in Japanese or English (e.g., #Python #LLM #AI) based on the raw data.
[Strict Rules]
1. Output ONLY the hashtags separated by spaces (e.g., "#LLM #Python #MCP").
2. No extra text or explanations.

Raw Data:
{selected_text}
"""
    print(f"🏷️ Step 6.5: Generating hashtags with {LINK_MODEL}...")
    part_hashtags = call_llm(LINK_MODEL, hashtag_prompt, num_predict=200).strip()
    if not part_hashtags:
        part_hashtags = "#LLM #Python #AI"

    # --- Step 7: Linting & Assembly ---
    print(f"🧹 Step 7: Linting and assembling final article...")
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 💡 安定確認のため、アイキャッチ生成は一時的にコメントアウト
    # eyecatch_filename = f"note_article_{ts}.png"
    # eyecatch_path = os.path.join(BASE_DIR, "output", eyecatch_filename)
    # clean_title = part_intro.split('\n')[0].replace("#", "").replace("■", "").strip()
    # generate_eyecatch(clean_title, eyecatch_path)

    final_raw = (
        f"{part_intro}\n\n"
        # f"![Eyecatch]({eyecatch_filename})\n\n" # 画像タグも一旦除外
        f"{free_text}\n\n"
        f"{PAYWALL_MARKER}\n\n"
        f"{paid_text}\n\n"
        f"### 現場での具体的インパクトと適用場面\n\n"
        f"{part_insight}\n\n"
        f"### 参考リンク\n\n"
        f"{part_links}\n\n"
        f"{part_hashtags}"
    )
    final_article = lint_markdown(final_raw)

    os.makedirs(os.path.join(BASE_DIR, OUTPUT_SUBDIR), exist_ok=True)
    out_path = os.path.join(BASE_DIR, f"{OUTPUT_SUBDIR}/note_article_{ts}.md")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(final_article)

    status[basename][str(orig_idx)] = {
        "note_used": True,
        "generated_at": ts,
        "generated_file": out_path
    }
    save_status(status)
    print(f"💾 Saved Final Article: {out_path}")
    if DRY_RUN:
        print(
            "🧪 Dry run complete. Review the output above/in "
            f"`{OUTPUT_SUBDIR}/`, then delete that folder when done - "
            "it's gitignored and never touched by production runs."
        )
    print("✅ Done! Agent-sync execution completed.")

if __name__ == "__main__":
    main()