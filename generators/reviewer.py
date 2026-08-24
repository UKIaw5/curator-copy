import os
import re
import requests
from generators.refiner import extract_clean_url, get_x_effective_length

# 💡 OllamaのOpenAI互換エンドポイントを指定
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/v1/chat/completions")
MODEL_NAME = os.getenv("QWEN_REVIEWER_MODEL", "smtek/Qwen3.8-27B:Q2_K_XL")

def review_and_edit_post(gemma_post: str, original_summary: str) -> str:
  target_url = extract_clean_url(gemma_post) or extract_clean_url(
      original_summary
  )
  body_text = re.sub(r'https?://[^\s<>"]*', "", gemma_post).strip()

  max_body_len = 110 if target_url else 135

  prompt = f"""You are an elite technical editor for a cutting-edge tech X (Twitter) account.
Polish the following Japanese draft to make it punchy, highly engaging, and irresistible for developers to retweet.

[Original Context]
{original_summary}

[Draft to Edit]
{body_text}

[Strict Rules]
1. Output ONLY the final polished Japanese post. NO conversational filler, NO greetings, NO explanations, NO meta-commentary (e.g., do NOT write "修正しました" or "問題ありません").
2. Tone: Strictly casual Japanese (タメ語 / だ・である調). Absolutely NO desu/masu (です・ます).
3. Emoji & Punctuation Rules (CRITICAL):
    - NEVER place an emoji immediately after a period (。), comma (、), or punctuation (e.g., "。🔥" or "。🚀" are forbidden). Separate them or remove the period before an emoji.
4. Impact & Variety: Make the phrasing sharp, diverse, and exciting. Avoid repetitive buzzwords.
5. Accuracy: Do not distort core technical facts.
6. STRICT LENGTH: Output Japanese body MUST be between 55 and {max_body_len} characters.
7. DO NOT include URLs.

Polished Japanese Text:"""

  payload = {
      "model": MODEL_NAME,
      "messages": [{"role": "user", "content": prompt}],
      "temperature": 0.4,
  }

  try:
    # 💡 Ollamaへリクエスト送信
    res = requests.post(OLLAMA_URL, json=payload, timeout=300)
    res.raise_for_status()

    # 💡 OpenAI互換レスポンス構造（choices -> message -> content）
    res_json = res.json()
    edited_body = (
        res_json.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )

    # ▼ Qwenの相槌・メタ発言を検知した場合はGemmaのオリジナル原稿を採用する安全装置
    filler_keywords = [
        "問題なし",
        "そのまま",
        "誤字脱字",
        "確認しました",
        "見当たりません",
        "出力します",
        "修正点",
    ]
    if any(keyword in edited_body for keyword in filler_keywords):
      print(
          "⚠️ Qwen returned conversational filler. Falling back to Gemma draft."
      )
      return gemma_post

    edited_body = re.sub(
        r"^```(?:markdown)?\s*", "", edited_body, flags=re.IGNORECASE
    )
    edited_body = re.sub(r"\s*```$", "", edited_body).strip()
    edited_body = re.sub(r'https?://[^\s<>"]*', "", edited_body).strip()
    edited_body = re.sub(r"[【】\[\]]", "", edited_body).strip()

    effective_len = get_x_effective_length(edited_body, bool(target_url))

    if 80 <= effective_len <= 135:
      print(f"✅ Qwen review accepted via Ollama ({effective_len} chars).")
      return f"{edited_body}\n\n{target_url}" if target_url else edited_body
    else:
      print(
          f"⚠️ Qwen review length out of bounds ({effective_len} chars)."
          " Falling back to Gemma draft."
      )
      return gemma_post

  except Exception as e:
    print(f"⚠️ Review error via Ollama: {e}. Keeping original Gemma draft.")
    return gemma_post