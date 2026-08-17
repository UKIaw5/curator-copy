import re
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:14b"

def select_best_items(items: list, max_select: int = 5) -> list:
    """
    Selects the most impactful items using Qwen.
    If the number of items is less than or equal to max_select, returns all items.
    """
    if len(items) <= max_select:
        print(f"ℹ️ Item count ({len(items)}) is small. Bypassing AI curation and selecting all.")
        return items

    items_summary_text = ""
    for idx, item in enumerate(items):
        title = item.get("title", "No Title")
        summary = item.get("summary", item.get("content", ""))[:150]
        items_summary_text += f"[{idx}] Title: {title}\nSummary: {summary}...\n\n"

    prompt = f"""You are an elite technology curator. Review the following list of newly fetched technical items.
Select the most impactful, timely, and valuable items to share on a tech curator X account.
- Since there are many items, select ONLY the top most impressive and trending ones (up to a maximum of {max_select} items).
- Choose items that show strong innovation, real-world utility, or significant breakthrough.

Return ONLY the selected indices as a comma-separated list of numbers (e.g., 0, 2, 5, 11). Do not include any other text, markdown, or explanation.

[Items List]
{items_summary_text}

Selected Indices (comma-separated numbers only):
"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    try:
        print(f"🤖 Qwen ({MODEL_NAME}) is curating the best items from {len(items)} candidates...")
        res = requests.post(OLLAMA_URL, json=payload, timeout=120)
        res.raise_for_status()
        data = res.json()
        response_text = data.get("response", "").strip()
        
        indices_str = re.findall(r'\d+', response_text)
        selected_indices = [int(i) for i in indices_str if int(i) < len(items)]
        selected_indices = list(dict.fromkeys(selected_indices))
        
        if not selected_indices:
            print("⚠️ Qwen selector returned no valid indices. Falling back to top items.")
            return items[:max_select]

        selected_items = [items[i] for i in selected_indices[:max_select]]
        print(f"✨ Qwen Curated: Successfully selected {len(selected_items)} hot items out of {len(items)}.")
        return selected_items

    except Exception as e:
        print(f"⚠️ Qwen curation error: {e}. Falling back to top {max_select} items.")
        return items[:max_select]