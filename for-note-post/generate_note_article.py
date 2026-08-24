import os
import shutil
import glob
import json
import requests
import re
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"

# --- Robust Agent Placement ---
TOC_MODEL = "qwen3.8:27b"
WRITER_MODEL = "gemma4:12b"
REVIEWER_MODEL = "qwen3.8:27b"
HOOK_MODEL = "qwen3.8:27b"
INSIGHT_MODEL = "qwen3.8:27b"
LINK_MODEL = "qwen2.5-coder:14b"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(BASE_DIR, "note_status.json")
PAYWALL_MARKER = "<!-- PAYWALL -->"

def call_llm(model_name: str, prompt: str, num_predict: int = 4000, num_ctx: int = 8192) -> str:
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
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
        if "Please provide" in response_text or "Professional Engineering" in response_text:
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
            items = [s.strip() for s in f.read().split("\n\n---\n\n") if s.strip()]
        if basename not in status:
            status[basename] = {}
        if any(not status[basename].get(str(i), {}).get("note_used", False) for i in range(len(items))):
            return latest_file, items, status
    return None, [], status

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
        lines = t.splitlines()
        processed_lines = []
        for line in lines:
            if re.match(r'^#+\s*', line):
                processed_lines.append(re.sub(r'^#+\s*', '■ ', line))
            else:
                processed_lines.append(line)
        t = "\n".join(processed_lines)
        
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

def main():
    print("=== Note Article Generator v2.5 (English Comments & Hardened Sanitizer) ===")
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
    if not part_intro: part_intro = "# 技術解説記事\n\n## この記事で得られること\n- 最新ツールの解説\n- アーキテクチャの理解\n- 実装への応用\n\n## 目次\n1. 概要\n2. 仕組み\n3. まとめ"

    # --- Step 2: Body Generation (Syncing with Step 1 TOC) ---
    body_writer_prompt = f"""
Write a comprehensive, deep-dive Japanese technical article based on the raw data.
[Strict Rules]
1. Professional engineering Japanese only. No English sentences.
2. CRITICAL: You MUST use the exact section headings defined in the [Target Table of Contents] below. Do NOT invent your own headings (like "1. 概要") unless they are in the TOC.
3. Do NOT repeat the Title or Table of Contents. Output ONLY the body sections starting directly from the first heading.
4. Provide deep explanations for every section. Ensure high volume and detail.

[Target Table of Contents]
{part_intro}

Raw Data:
{selected_text}
"""
    print(f"🤖 Step 2: Generating deep-dive body matching TOC with {WRITER_MODEL}...")
    draft_body = call_llm(WRITER_MODEL, body_writer_prompt, num_predict=6000)
    if not draft_body: draft_body = selected_text

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
    part_body = call_llm(REVIEWER_MODEL, reviewer_prompt, num_predict=6000)
    if not part_body: part_body = draft_body
    
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
        if optimized_hook:
            free_paragraphs[-1] = optimized_hook
            free_text = "\n\n".join(free_paragraphs)

    # --- Step 5: Field Impact ---
    insight_prompt = f"""
Write an advanced analytical subsection about concrete production-level insights and field impact based on the raw data.
Output ONLY the body paragraphs and bullet points in professional Japanese. Do not use Markdown headers.

Raw Data:
{selected_text}
"""
    print(f"💡 Step 5: Generating field impact with {INSIGHT_MODEL}...")
    part_insight = call_llm(INSIGHT_MODEL, insight_prompt)
    if not part_insight: part_insight = "実務における適用価値と今後の展望についての考察。"

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

    # --- Step 7: Linting & Assembly ---
    print(f"🧹 Step 7: Linting and assembling final article...")
    final_raw = (
        f"{part_intro}\n\n"
        f"{free_text}\n\n"
        f"{PAYWALL_MARKER}\n\n"
        f"{paid_text}\n\n"
        f"### 現場での具体的インパクトと適用場面\n\n"
        f"{part_insight}\n\n"
        f"### 参考文献 / 公式リンク\n\n"
        f"{part_links}"
    )
    final_article = lint_markdown(final_raw)

    os.makedirs(os.path.join(BASE_DIR, "output"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(BASE_DIR, f"output/note_article_{ts}.md")
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(final_article)

    status[basename][str(orig_idx)] = {
        "note_used": True,
        "generated_at": ts,
        "generated_file": out_path
    }
    save_status(status)
    print(f"💾 Saved Final Article: {out_path}")
    print("✅ Done! Agent-sync execution completed.")

if __name__ == "__main__":
    main()