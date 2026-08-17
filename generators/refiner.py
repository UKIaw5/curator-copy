import os
import re
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

def extract_clean_url(text: str) -> str:
    match = re.search(r'https?://[^\s<>"\)\]]+', text)
    if not match:
        return ""
    url = match.group(0)
    return re.sub(r'[\.\,\)\]]+$', '', url)

def get_x_effective_length(body_text: str, has_url: bool) -> int:
    url_cost = 25 if has_url else 0
    return len(body_text) + url_cost

def clean_llm_response(raw_text: str) -> str:
    cleaned = re.sub(r"^```(?:markdown)?\s*", "", raw_text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    cleaned = re.sub(r'https?://[^\s<>"]*', '', cleaned)
    
    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    if not lines:
        return ""
    
    if re.match(r'^(以下|こちら|ツイート|修正案)', lines[0]):
        lines = lines[1:]
        
    first_chunk = " ".join(lines[:2]) if lines else ""
    return first_chunk.strip()

def refine_to_x_post(summary_text: str, max_retries: int = 3) -> str:
    target_url = extract_clean_url(summary_text)

    # 本文長：55〜110文字（URL込 80〜135文字）
    max_body_len = 110 if target_url else 135
    min_body_len = 55 if target_url else 80

    base_prompt = f"""
You are an excited, passionate tech developer sharing AI & software breakthroughs on X (Twitter).
Refine the following technical summary into a rich, high-energy Japanese X post.

[Strict Guidelines]
1. Hook & Expressive Diversity:
   - Start with a punchy headline or emotional reaction using emojis (🤯, 🔥, 🚀, 💡, 🛠️, 😱).
   - DO NOT use full-width brackets like 【】 or [ ].
   - Match the emotional reaction angle to the content! (Don't just repeat generic hype phrases).
     * For architectural breakthroughs -> Focus on awe/elegance ("設計が賢すぎる", "アプローチが鮮やか")
     * For developer tools -> Focus on practical relief ("開発の地味なストレス消える", "現場で超助かる")
     * For unexpected research -> Focus on pure surprise ("統計じゃ説明つかない", "マジかその視点")
     * For game-changers -> Focus on impact ("これ流れ変わるな", "胸熱すぎる")

2. Content & Substance:
   - Must include at least ONE concrete technical feature or mechanism.

3. Output Rules:
   - DO NOT include any URL. Output ONLY the Japanese text.
   - STRICT Body Length: Between {min_body_len} and {max_body_len} characters.

[Example]
Input: LLM内部の回路解析で、人間脳のようなモジュール構造が自然発生していることが判明した。
Output:
LLMに脳の構造が自然発生！？🤯 内部解析したら言語や論理のモジュールが勝手に形成されてたらしい。単なる統計処理じゃなく、スケールに伴って脳の構造に寄っていくのアプローチとして鮮やかすぎる。

Input:
{summary_text}
"""

    model_name = "gemma2:9b"
    refined_post = summary_text
    body_text = ""

    for attempt in range(1, max_retries + 1):
        payload = {
            "model": model_name,
            "prompt": base_prompt,
            "stream": False,
            "options": {"temperature": 0.5} # 表現の多様性を出すため少し引き上げ
        }
        
        try:
            res = requests.post(OLLAMA_URL, json=payload, timeout=120)
            res.raise_for_status()
            raw_response = res.json().get("response", "").strip()
            
            body_text = clean_llm_response(raw_response)
            
            refined_post = f"{body_text}\n\n{target_url}" if target_url else body_text
            effective_len = get_x_effective_length(body_text, bool(target_url))
            
            print(f"📊 [Attempt {attempt}/{max_retries}] Body: {len(body_text)} chars | Effective X Length: {effective_len} chars")
            
            if 80 <= effective_len <= 135:
                print("✅ Perfect! Fits X length bounds.")
                return refined_post
            else:
                print(f"⚠️ Length out of bounds ({effective_len} chars). Retrying...")
                
        except Exception as e:
            print(f"⚠️ Refine API error: {e}")
            if attempt == max_retries: break
                
    print("⚠️ Max retries reached. Applying safe fallback truncation...")
    allowed = max_body_len - 3
    body_text = body_text[:allowed] + "..." if len(body_text) > allowed else body_text
    return f"{body_text}\n\n{target_url}" if target_url else body_text