import os
import re
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL_NAME = os.getenv("QWEN_MODEL", "qwen3.8:27b")

def select_best_items(items: list, max_select: int = 6) -> list:
    """
    Selects the most impactful items using Qwen.
    If the number of items is less than or equal to max_select, returns all items.

    💡 2026-10-11: 「質より量」の運用方針に変更(X投稿の時間枠数
    `automation/socialdog_poster.py`のTARGET_TIME_SLOTS=6枠に合わせて、
    毎日必ずmax_select件を投稿したいという要望)。Qwenがmax_select未満しか
    「これは載せるべき」と判断しなかった場合、選ばれなかった残りの候補から
    (フェッチ順で)不足分を埋めて、必ずmax_select件になるようにする。
    候補の総数自体がmax_select未満の場合は、そのまま全件を返す(上のif文)。
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
- Select exactly {max_select} items: the most interesting, trending, or useful ones available in the list below. Always return {max_select} items even if some are only moderately noteworthy.
- Rank by innovation, real-world utility, or significant breakthrough, but prioritize filling the quota over being overly selective.

Return ONLY the selected indices as a comma-separated list of numbers (e.g., 0, 2, 5, 11). Do not include any other text, markdown, or explanation.

[Items List]
{items_summary_text}

Selected Indices (comma-separated numbers only):
"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "think": False,  # 💡 Qwen3の思考トレースがnum_predictを食い尽くし、
                          # responseが空になるのを防ぐ
        "keep_alive": 0,
        # 💡 arXivフェッチャー分(limit=15)を含めると候補が40件前後になり、
        # 2048だとプロンプトが収まらずcontextオーバーフローの恐れがある
        "options": {"num_ctx": 4096, "num_predict": 512, "temperature": 0.5}
    }

    try:
        print(f"🤖 Qwen ({MODEL_NAME}) is curating the best items from {len(items)} candidates...")
        res = requests.post(OLLAMA_URL, json=payload, timeout=300)
        res.raise_for_status()
        data = res.json()
        response_text = data.get("response", "").strip()
        
        indices_str = re.findall(r'\d+', response_text)
        selected_indices = [int(i) for i in indices_str if int(i) < len(items)]
        selected_indices = list(dict.fromkeys(selected_indices))[:max_select]

        if len(selected_indices) < max_select:
            remaining = [i for i in range(len(items)) if i not in selected_indices]
            shortfall = max_select - len(selected_indices)
            print(f"ℹ️ Qwen selected only {len(selected_indices)} item(s); backfilling {shortfall} more from the remaining candidates to reach {max_select}.")
            selected_indices += remaining[:shortfall]

        selected_items = [items[i] for i in selected_indices]
        print(f"✨ Qwen Curated: Selected {len(selected_items)} items out of {len(items)} (target: {max_select}).")
        return selected_items

    except Exception as e:
        print(f"⚠️ Qwen curation error: {e}. Falling back to top {max_select} items.")
        return items[:max_select]