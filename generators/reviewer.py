import os
import re
import requests
from generators.refiner import extract_clean_url, get_x_effective_length

OLLAMA_URL = os.getenv(
    "OLLAMA_URL", "http://localhost:11434/v1/chat/completions"
)
MODEL_NAME = os.getenv("GEMMA_REVIEWER_MODEL", "gemma4:12b")


def review_and_edit_post(gemma_post: str, original_summary: str) -> str:
  target_url = extract_clean_url(gemma_post) or extract_clean_url(
      original_summary
  )
  body_text = re.sub(r'https?://[^\s<>"]*', "", gemma_post).strip()

  max_body_len = 110 if target_url else 135

  # 💡 日本語プロンプトに統一し、前置きや解説の出力を徹底排除
  prompt = f"""あなたは技術系X（旧Twitter）アカウントの優秀なテクニカルエディターです。
以下の日本語の下書き（Draft）を、エンジニアが思わずリツイートしたくなるような、切れ味鋭い魅力的な文章に推敲・校正してください。

【元データ文脈】
{original_summary}

【校正対象の下書き】
{body_text}

【厳格なルール】
1. 校正後の本文のみを出力してください。「修正しました」「問題ありません」などの挨拶・解説・前置きは一切禁止です。
2. 語調: 常体（だ・である調 / タメ語）。「です・ます」は絶対に使用禁止。
3. 絵文字・句読点ルール:
   - 句読点（。、）の直後に絵文字を置くのは禁止（例: 「。🔥」はNG）。
4. 本文の文字数: 日本語本文は必ず50文字〜{max_body_len}文字以内に収めてください。
5. URLは含めないでください。

校正後の日本語本文:"""

  payload = {
      "model": MODEL_NAME,
      "messages": [{"role": "user", "content": prompt}],
      "temperature": 0.3,
  }

  try:
    res = requests.post(OLLAMA_URL, json=payload, timeout=300)
    res.raise_for_status()

    res_json = res.json()
    edited_body = (
        res_json.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )

    # 前置きフレーズの検知と安全装置
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
      print("⚠️ Reviewer returned conversational filler. Falling back...")
      return gemma_post

    edited_body = re.sub(
        r"^```(?:markdown)?\s*", "", edited_body, flags=re.IGNORECASE
    )
    edited_body = re.sub(r"\s*```$", "", edited_body).strip()
    edited_body = re.sub(r'https?://[^\s<>"]*', "", edited_body).strip()
    edited_body = re.sub(r"[【】\[\]]", "", edited_body).strip()

    effective_len = get_x_effective_length(edited_body, bool(target_url))

    # 💡 判定範囲を 50〜135 文字へ緩和
    if 50 <= effective_len <= 135:
      print(f"✅ Review accepted via Ollama ({effective_len} chars).")
      return f"{edited_body}\n\n{target_url}" if target_url else edited_body
    else:
      print(
          f"⚠️ Review length out of bounds ({effective_len} chars). Falling back"
          " to Gemma draft."
      )
      return gemma_post

  except Exception as e:
    print(f"⚠️ Review error via Ollama: {e}. Keeping original Gemma draft.")
    return gemma_post