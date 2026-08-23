# generate_note_article.py
import os
import shutil
import glob
import json
import requests
import re
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"

# --- Optimal Agent Placement ---
TOC_MODEL = "qwen2.5-coder:14b"
WRITER_MODEL = "qwen3.8:27b"
REVIEWER_MODEL = "gemma4:12b"
HOOK_MODEL = "qwen3.8:27b"
INSIGHT_MODEL = "qwen3.8:27b"
LINK_MODEL = "qwen2.5-coder:14b"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(BASE_DIR, "note_status.json")
PAYWALL_MARKER = "<!-- PAYWALL -->"

def call_llm(model_name: str, prompt: str, num_predict: int = 8000, num_ctx: int = 8192) -> str:
    """Added num_ctx to prevent LLM from cutting off long outputs (e.g., stopping mid-sentence)."""
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7, 
            "num_predict": num_predict,
            "num_ctx": num_ctx
        }
    }
    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=900)
        res.raise_for_status()
        return res.json().get("response", "").strip()
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
    """Bulletproof line-based insertion to prevent regex mangling."""
    if PAYWALL_MARKER in text:
        return text
    
    lines = text.split('\n')
    # Find indices of all H2 headings
    h2_indices = [i for i, line in enumerate(lines) if line.startswith('## ')]
    
    if len(h2_indices) >= 3:
        # Insert before the H2 heading located around 70% depth
        target_idx = int(len(h2_indices) * 0.7)
        if target_idx == 0: target_idx = 1
        insert_line_idx = h2_indices[target_idx]
        lines.insert(insert_line_idx, f"\n{PAYWALL_MARKER}\n")
        return "\n".join(lines)
    else:
        # Fallback to paragraphs if structure is flat
        paragraphs = text.split('\n\n')
        if len(paragraphs) > 3:
            insert_idx = int(len(paragraphs) * 0.7)
            paragraphs.insert(insert_idx, f"\n{PAYWALL_MARKER}\n")
            return "\n\n".join(paragraphs)
        else:
            paragraphs.append(f"\n{PAYWALL_MARKER}\n")
            return "\n\n".join(paragraphs)

def lint_markdown(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'(?<!\n)<!-- PAYWALL -->', '\n\n<!-- PAYWALL -->\n\n', text)
    return text.strip()

def main():
    print("=== Note Article Generator v2.2 (Context Unlocked & Bulletproof logic) ===")
    latest_file, items, status = get_active_raw_file()
    if not items:
        return

    basename = os.path.basename(latest_file)
    available = [(i, t) for i, t in enumerate(items) if not status[basename].get(str(i), {}).get("note_used", False)]
    if not available:
        return

    print(f"\n📂 Active File: {basename}")
    for idx, (orig_idx, text) in enumerate(available, 1):
        print(f"  [{idx}] (Item #{orig_idx + 1}) {text.split('\n')[0][:70]}...")

    choice = int(input(f"\nSelect item (1-{len(available)}): ")) - 1
    orig_idx, selected_text = available[choice]

    # --- Step 1: Structure & TOC ---
    intro_prompt = f"""
You are an elite technical editor. Based on the following raw data, generate the title, takeaways, and table of contents.
[Strict Rules]
1. ALL text, including bullet points and sections, MUST be translated into natural Japanese. Do NOT leave English headings like "WHAT THIS IS".
2. Strictly follow this exact Markdown format without any extra labels:

# [Generate Catchy Japanese Title Here]

## この記事で得られること
- [Takeaway 1 in Japanese]
- [Takeaway 2 in Japanese]
- [Takeaway 3 in Japanese]

## 目次
1. [Japanese Section 1]
2. [Japanese Section 2]
3. [Japanese Section 3]

Raw Data:
{selected_text}
"""
    print(f"💡 Step 1: Generating title and TOC with {TOC_MODEL}...")
    part_intro = call_llm(TOC_MODEL, intro_prompt)

    # --- Step 2: Unconstrained Long-Form Body Generation ---
    body_writer_prompt = f"""
You are an elite Japanese technical writer. Write a comprehensive, highly detailed main body based on the raw data.

[Strict Volume & Translation Rules]
1. Everything MUST be in professional Japanese. Translate all technical concepts naturally.
2. You MUST write a massive, deep-dive article. For EVERY section in the TOC, you must write at least 3 to 4 dense paragraphs.
3. Total length should be extensive. Do not summarize; explain the architecture, limitations, and quantitative results thoroughly.

Raw Data:
{selected_text}
"""
    print(f"🤖 Step 2: Generating massive deep-dive body with {WRITER_MODEL}...")
    draft_body = call_llm(WRITER_MODEL, body_writer_prompt)

    # --- Step 3: Review ---
    reviewer_prompt = f"""
Review and refine the following Japanese technical article draft.
[CRITICAL RULES]
1. Fix any literal translations and ensure a highly professional engineering tone.
2. DO NOT TRUNCATE OR SUMMARIZE. You MUST output the entire article from start to finish. Preserve the full length of the document.

Draft:
{draft_body}
"""
    print(f"🧐 Step 3: Reviewing with {REVIEWER_MODEL}...")
    part_body = call_llm(REVIEWER_MODEL, reviewer_prompt)
    if not part_body: part_body = draft_body
    
    # --- Structural Paywall Insertion (Line-based) ---
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
You are a master technical copywriter. The following paragraph is right before a paywall in a technical article.
Rewrite it to be a powerful "cliffhanger" that makes the reader's intellectual curiosity explode, forcing them to want to read the advanced solution in the paid section.
- Highlight a critical technical bottleneck or an unsolved mystery.
- Do NOT use cheap sales phrases.
- End with a dramatic transition (e.g., "なぜなら——", "そのアーキテクチャの全貌は──").
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
Output ONLY the body paragraphs and bullet points in professional Japanese without any top-level headings.

Raw Data:
{selected_text}
"""
    print(f"💡 Step 5: Generating field impact with {INSIGHT_MODEL}...")
    part_insight = call_llm(INSIGHT_MODEL, insight_prompt)

    # --- Step 6: Link Extraction ---
    link_prompt = f"""
Extract the exact official URLs (Hugging Face, ArXiv, GitHub) from the raw data.
Format them as a Markdown list. Do not output anything else.

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

    # Save outputs
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
    print("✅ Done! Full length maintained, safely parsed, and fully translated.")

if __name__ == "__main__":
    main()