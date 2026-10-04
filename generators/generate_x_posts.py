import os
import json
import shutil
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

def generate_detailed_summary(item: dict) -> str:
    # 💡 qwen2.5-coder:14bはコード特化モデルで、根拠のない技術詳細を自信満々に
    # 書く(ハルシネーション)傾向が見られたため、qwen3.8:27bに変更。
    # 処理時間は長くなる(実測: 約4倍)が、分からないことを明記する誠実さがあり
    # 技術要約の質が高い。
    model_name = os.getenv("QWEN_MODEL", "qwen3.8:27b")
    # Safely retrieve URL from item ('url' or 'link')
    item_url = item.get('url') or item.get('link') or ''
    
    prompt = f"""You are a senior tech analyst and AI researcher. Analyze the following article and write a comprehensive, detailed technical summary in ENGLISH.

--- ARTICLE DATA ---
Title: {item.get('title', '')}
Content: {item.get('content', '')}
Source: {item.get('source', '')}
URL: {item_url}
--------------------

--- INSTRUCTIONS ---
1. Provide a detailed explanation in English of WHAT this tool/article is, HOW it works, and WHY it matters to developers.
2. Use clear bullet points and structured formatting in English.
3. Include the original URL ({item_url}) at the very end.
4. Return ONLY the summary text. No meta-commentary or markdown code blocks.
5. Extract specific architecture names, benchmarks, key metrics, or concrete use cases rather than general overviews.
"""
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "think": False,  # 💡 思考トレースがnum_predictを食い尽くすのを防ぐ
                         # (有効時: 260秒 → 無効時: 130秒、品質は維持)
        "options": {"num_predict": 1500, "num_ctx": 4096},
    }
    
    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=300)
        res.raise_for_status()
        data = res.json()
        summary = data.get("response", "").strip()
        
        if summary:
            # Force append URL if it's missing from the generated summary
            if item_url and item_url not in summary:
                summary = f"{summary}\n\nURL: {item_url}"
            return summary
            
    except Exception as e:
        print(f"⚠️ Qwen API warning for '{item.get('title')}': {e}")
    
    return f"Title: {item.get('title')}\nURL: {item_url}"

def run(items: list, output_dir: str = "output", filename: str = "latest_summaries.md"):
    os.makedirs(output_dir, exist_ok=True)
    seen_urls_path = os.path.join(output_dir, "seen_urls.json")
    seen_urls_bak_path = os.path.join(output_dir, "seen_urls.json.bak")
    
    seen_urls = set()
    if os.path.exists(seen_urls_path):
        try:
            with open(seen_urls_path, "r", encoding="utf-8") as f:
                seen_urls = set(json.load(f))
        except Exception as e:
            print(f"Warning reading seen_urls.json: {e}")

    summaries = []
    for item in items:
        url = item.get("url") or item.get("link")
        if not url or url in seen_urls:
            print(f"⏩ Skipping duplicate URL: {url}")
            continue

        print(f"📝 Generating detailed English summary for: {item.get('title', '')[:40]}...")
        summary_text = generate_detailed_summary(item)
        summaries.append(summary_text)
        seen_urls.add(url)

    if not summaries:
        print("ℹ️ No new items to process (all duplicates).")
        return

    raw_file = os.path.join(output_dir, filename)
    # 💡 "---" はQwenが要約本文の区切り線として自然に使うことがあり、
    # 単純な"---"区切りだと1件の要約が誤って複数件に分割されてしまう。
    # 衝突しないユニークな区切り文字列を使う。
    content_to_write = "\n\n<<<CURATOR_ITEM_BOUNDARY>>>\n\n".join(summaries)

    with open(raw_file, "w", encoding="utf-8") as f:
        f.write(content_to_write)

    # 💡 履歴更新の直前に .bak バックアップを作成
    if os.path.exists(seen_urls_path):
        try:
            shutil.copy2(seen_urls_path, seen_urls_bak_path)
            print(f"📦 Created history backup: {seen_urls_bak_path}")
        except Exception as e:
            print(f"⚠️ Failed to create history backup: {e}")

    with open(seen_urls_path, "w", encoding="utf-8") as f:
        json.dump(list(seen_urls), f, ensure_ascii=False, indent=2)

    print(f"💾 Saved {len(summaries)} detailed summaries to `{raw_file}`.")

run_stage1 = run