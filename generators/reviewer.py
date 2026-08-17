import re
import requests
from generators.refiner import extract_clean_url, get_x_effective_length

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:14b"

def review_and_edit_post(gemma_post: str, original_summary: str) -> str:
    target_url = extract_clean_url(gemma_post) or extract_clean_url(original_summary)
    body_text = re.sub(r'https?://[^\s<>"]*', '', gemma_post).strip()
    
    max_body_len = 110 if target_url else 135

    prompt = f"""You are a strict technical editor for a tech news X account.
Polish the following Japanese draft to make it punchy, concise, and compelling.

[Original Context]
{original_summary}

[Draft to Edit]
{body_text}

[Strict Rules]
1. DO NOT add new information or change core facts.
2. DO NOT use full-width brackets like 【】 or [ ].
3. Ensure natural, varied developer phrasing (Avoid repetitive, monotone reaction patterns).
4. STRICT LENGTH: Output Japanese body MUST be between 55 and {max_body_len} characters.
5. DO NOT include URLs.

Polished Japanese Text:"""

    payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False, "options": {"temperature": 0.3}}

    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=120)
        res.raise_for_status()
        edited_body = res.json().get("response", "").strip()
        
        edited_body = re.sub(r"^```(?:markdown)?\s*", "", edited_body, flags=re.IGNORECASE)
        edited_body = re.sub(r"\s*```$", "", edited_body).strip()
        edited_body = re.sub(r'https?://[^\s<>"]*', '', edited_body).strip()
        edited_body = re.sub(r'[【】\[\]]', '', edited_body).strip()

        effective_len = get_x_effective_length(edited_body, bool(target_url))
        
        # 下限を80（本文55文字〜）に設定
        if 80 <= effective_len <= 135:
            print(f"✅ Qwen review accepted ({effective_len} chars).")
            return f"{edited_body}\n\n{target_url}" if target_url else edited_body
        else:
            print(f"⚠️ Qwen review length out of bounds ({effective_len} chars). Falling back to Gemma draft.")
            return gemma_post
            
    except Exception as e:
        print(f"⚠️ Review error: {e}. Keeping original Gemma draft.")
        return gemma_post