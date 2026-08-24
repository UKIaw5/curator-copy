import os
import re
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

def extract_clean_url(text: str) -> str:
    """テキストからURLを抽出し、末尾の記号やMarkdownノイズ(**等)を綺麗に除去する"""
    match = re.search(r'https?://[^\s<>"\)\]]+', text)
    if not match:
        return ""
    url = match.group(0)
    return re.sub(r'[\.\,\)\]\*\_\:]+$', '', url)

def get_x_effective_length(body_text: str, has_url: bool) -> int:
    url_cost = 25 if has_url else 0
    return len(body_text) + url_cost

def clean_llm_response(raw_text: str) -> str:
    """思考タグやメタ発言、Markdown太字ノイズなどをトリムする"""
    if not raw_text:
        return ""

    cleaned = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL)
    cleaned = re.sub(r"^```(?:markdown)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    cleaned = re.sub(r'https?://[^\s<>"]*', '', cleaned)

    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    meta_pattern = r'^(以下[のは]?|こちら[のは]?|ツイート[案本文：:]*|修正案[：:]*|Output:?|Here is:?|Post:?|Draft:?)\s*'
    
    processed_lines = []
    for line in lines:
        stripped = re.sub(meta_pattern, '', line, flags=re.IGNORECASE).strip()
        if stripped:
            processed_lines.append(stripped)

    if not processed_lines:
        return ""

    result = " ".join(processed_lines)
    result = re.sub(r'[【】\[\]]', '', result).strip()
    result = re.sub(r'\*\*', '', result).strip()
    return result

def refine_to_x_post(summary_text: str, max_retries: int = 3) -> str:
    target_url = extract_clean_url(summary_text)

    system_prompt = (
        "You are a concise X (Twitter) post generator.\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. Output ONLY the final Japanese text directly and immediately.\n"
        "2. Use strictly casual Japanese (タメ語 / だ・である調・ラフな口調). NEVER use desu/masu (です・ます)."
    )

    base_prompt = f"""You are an energetic tech developer sharing AI & software breakthroughs on X (Twitter).
Refine the following technical summary into a rich, high-impact Japanese X post.

[Strict Guidelines]
1. Tone & Diversity:
   - Use strictly casual Japanese (タメ語). No "です・ます".
   - Avoid repetitive patterns (DO NOT overuse "熱すぎる"). Mix up your hooks: use shock, deep insights, practical benefits, or architectural praise.
   - DO NOT use full-width brackets like 【】 or [ ].

2. Emoji Rules (CRITICAL):
   - NEVER place an emoji immediately after a Japanese period (。), comma (、), or other punctuation marks (e.g., "。🔥" or "。🚀" are strictly prohibited).
   - Emojis should be used naturally (e.g., attached to words like "熱い🔥" or placed at the end of a clause without a preceding period).

3. Content & Substance:
   - Must include at least ONE concrete technical feature, metric, or mechanism.

4. Output Rules:
   - DO NOT include any URL. Output ONLY the Japanese text.
   - Keep the response VERY CONCISE (strictly 1-2 short sentences).

Input:
{summary_text}
"""

    model_name = os.getenv("GEMMA_MODEL", "qwen3.8:27b")
    body_text = ""

    for attempt in range(1, max_retries + 1):
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": base_prompt}
            ],
            "stream": False,
            "keep_alive": 0,
            "options": {
                "temperature": 0.7, # 多様性を出すため少し温度を上げる
                "num_ctx": 8192,
                "num_predict": 8192
            }
        }
        
        try:
            res = requests.post(OLLAMA_URL, json=payload, timeout=300)
            res.raise_for_status()
            data = res.json()
            
            raw_response = data.get("message", {}).get("content", "").strip()
            body_text = clean_llm_response(raw_response)
            
            effective_len = get_x_effective_length(body_text, bool(target_url))
            print(f"📊 [Attempt {attempt}/{max_retries}] Body: {len(body_text)} chars | Effective X Length: {effective_len} chars")
            
            if 70 <= effective_len <= 140:
                print("✅ Perfect! Fits X length bounds.")
                return f"{body_text}\n\n{target_url}" if target_url else body_text
            else:
                print(f"⚠️ Length out of bounds ({effective_len} chars). Retrying...")
                
        except Exception as e:
            print(f"⚠️ Refine API error (Attempt {attempt}): {e}")
            if attempt == max_retries:
                break

    print("⚠️ Applying safe fallback...")
    if not body_text:
        clean_summary = re.sub(r'https?://[^\s<>"]*', '', summary_text).strip()
        first_line = clean_summary.split('\n')[0] if clean_summary else "注目のAI最新技術"
        first_line = first_line.replace("**", "").replace("[", "").replace("]", "")
        body_text = f"🚀 {first_line[:90]}"

    max_body_len = 115 if target_url else 140
    if len(body_text) > max_body_len:
        body_text = body_text[:max_body_len - 3] + "..."

    return f"{body_text}\n\n{target_url}" if target_url else body_text