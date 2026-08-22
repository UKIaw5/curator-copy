import os
import json
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

def generate_detailed_summary(item: dict) -> str:
    model_name = os.getenv("QWEN_MODEL", "qwen2.5-coder:14b")
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
        "stream": False
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
    content_to_write = "\n\n---\n\n".join(summaries)

    with open(raw_file, "w", encoding="utf-8") as f:
        f.write(content_to_write)

    with open(seen_urls_path, "w", encoding="utf-8") as f:
        json.dump(list(seen_urls), f, ensure_ascii=False, indent=2)

    print(f"💾 Saved {len(summaries)} detailed summaries to `{raw_file}`.")

run_stage1 = run