import os
import re
import requests

# 変更後 (環境変数に依存せずチャットAPIを強制指定)
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
GEMMA_MODEL = os.getenv("GEMMA_MODEL", "gemma4:12b")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen2.5-coder:14b") # 現在の14bモデルに合わせる


def extract_clean_url(text: str) -> str:
  match = re.search(r'https?://[^\s<>"\)\]]+', text)
  if not match:
    return ""
  url = match.group(0)
  return re.sub(r"[\.\,\)\]\*\_\:]+$", "", url)


def get_x_effective_length(body_text: str, has_url: bool) -> int:
  url_cost = 25 if has_url else 0
  return len(body_text) + url_cost


def clean_llm_response(raw_text: str) -> str:
  if not raw_text:
    return ""

  cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL)
  cleaned = re.sub(r"^```(?:markdown)?\s*", "", cleaned, flags=re.IGNORECASE)
  cleaned = re.sub(r"\s*```$", "", cleaned).strip()
  cleaned = re.sub(r'https?://[^\s<>"]*', "", cleaned)

  lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
  meta_pattern = r"^(以下[のは]?|こちら[のは]?|ツイート[案本文：:]*|修正案[：:]*|Output:?|Here is:?|Post:?|Draft:?)\s*"

  processed_lines = []
  for line in lines:
    stripped = re.sub(meta_pattern, "", line, flags=re.IGNORECASE).strip()
    if stripped:
      processed_lines.append(stripped)

  if not processed_lines:
    return ""

  result = " ".join(processed_lines)
  result = re.sub(r"[【】\[\]]", "", result).strip()
  result = re.sub(r"\*\*", "", result).strip()
  result = result.replace(",", "、")

  # --- 絵文字の前後に発生する不要なスペースを一律除去 ---
  emoji_pattern = r"\s*([\u2300-\u27BF\U0001F300-\U0001FAF6\U0001F600-\U0001F64F\U0001F680-\U0001F6FF])\s*"
  result = re.sub(emoji_pattern, r"\1", result)

  return result.strip()


def truncate_at_boundary(text: str, max_len: int) -> str:
  """文字数上限を超えた場合、句点等の境界で切る。適切な境界が見つからない
  場合のみ文字単位で切って"..."を付ける。"""
  if len(text) <= max_len:
    return text
  truncated = text[:max_len]
  boundary = max(truncated.rfind(c) for c in "。！？")
  if boundary >= int(max_len * 0.5):
    return truncated[: boundary + 1]
  return truncated[: max_len - 3] + "..."


def is_subject_missing(text: str) -> bool:
  if not text:
    return True
  return bool(re.match(r"^(が|の|を|は|に|で|と|より|から|、)", text.strip()))


def is_japanese_text(text: str, min_ratio: float = 0.3) -> bool:
  """GemmaがタメOK語への変換を放棄し、入力の英語をそのまま返すケースを検出する。"""
  if not text:
    return False
  japanese_chars = re.findall(r"[぀-ヿ一-鿿]", text)
  return (len(japanese_chars) / len(text)) >= min_ratio


def fix_subject_with_qwen(summary_text: str, draft_post: str) -> str:
  prompt = f"""You are a precise text editor.
Given a Technical Summary and a Draft X Post, extract the primary Product/Paper/Library name from the Summary, and prepend it onto the Draft Post so it naturally completes the sentence.

[Rule]
1. Output ONLY the fixed Japanese text. No explanations.
2. Ensure the sentence starts explicitly with the product name as the subject.

[Input Summary]
{summary_text}

[Draft Post (Missing Subject)]
{draft_post}
"""

  payload = {
      "model": QWEN_MODEL,
      "messages": [{"role": "user", "content": prompt}],
      "stream": False,
      "think": False,  # 💡 思考トレースがnum_predictを食い尽くすのを防ぐ
      "keep_alive": 0,  # 💡 QwenのVRAM残留を防止
      "options": {
          "temperature": 0.2,
          "num_ctx": 2048,  # 💡 VRAM領域の過剰確保を抑制
          "num_predict": 256,
      },
  }

  try:
    res = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=60)
    res.raise_for_status()
    raw = res.json().get("message", {}).get("content", "").strip()
    fixed_text = clean_llm_response(raw)
    return fixed_text if fixed_text else draft_post
  except Exception as e:
    print(f"⚠️ Qwen repair error: {e}")
    return draft_post


def generate_safe_japanese_fallback(summary_text: str) -> str:
  """最終手段のフォールバック。summary_textの1行目を直接使うと英語のまま
  投稿に混入するため、Qwenに明示的に日本語一文へ圧縮させる。"""
  clean_summary = re.sub(r'https?://[^\s<>"]*', "", summary_text).strip()
  if not clean_summary:
    return "注目の技術情報"

  prompt = f"""Read the following technical summary (it may be in English) and write ONE short, natural Japanese sentence (casual タメ語, 40-90 characters) that starts with the product/paper/library name as the subject and briefly states what it does.

Rules:
1. Output ONLY the Japanese sentence. No English words except the proper noun itself.
2. Never use です/ます. No preamble, no explanation, no markdown.

Summary:
{clean_summary[:800]}
"""

  payload = {
      "model": QWEN_MODEL,
      "messages": [{"role": "user", "content": prompt}],
      "stream": False,
      "think": False,
      "keep_alive": 0,
      "options": {"temperature": 0.3, "num_ctx": 2048, "num_predict": 200},
  }

  try:
    res = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=60)
    res.raise_for_status()
    raw = res.json().get("message", {}).get("content", "").strip()
    fixed = clean_llm_response(raw)
    if fixed and not is_subject_missing(fixed) and is_japanese_text(fixed):
      return fixed
  except Exception as e:
    print(f"⚠️ Qwen fallback-translation error: {e}")

  return "注目の技術情報"


def refine_to_x_post(summary_text: str, max_retries: int = 3) -> str:
  target_url = extract_clean_url(summary_text)

  system_prompt = (
      "You are a sharp, credible Japanese tech writer who explains the latest"
      " AI tools and papers to engineers on X (Twitter).\n"
      "Output ONLY the final Japanese text directly and immediately.\n"
      "Use casual but confident Japanese (だ・である調/タメ語). NEVER use"
      " desu/masu (です・ます)."
  )

  # 💡 固定の煽り文句プールを強制挿入する方式をやめ、要約内の具体的な事実
  # (数値・手法名・ベンチマーク等)を1つ盛り込むことを必須化した。
  # これにより「が熱い」「が凄すぎる」のような中身のない誇張表現が
  # 全ての投稿で同じになる問題と、内容の薄さを解消する。
  # 2026-10-04: いいねを押させる工夫として、(1)書き出しをインパクトのある
  # 事実から始める「フック優先」構成、(2)余裕があれば読み手にとっての
  # 具体的な意味を締めに加える、の2点を追加。
  # 💡 最初はフック+事実+読み手メリットの3点を全部必須にしたところ、
  # 3回とも120〜135文字まで超過して安全フォールバックに落ちた(実測)。
  # 読み手メリットの一文は「余裕があれば」の優先度最下位にし、文字数指定も
  # 厳守を明記することで、文字数内に収まる成功率を優先している。
  base_prompt = f"""以下の技術要約を、エンジニアが読んで「何がどう凄いのか」が具体的に伝わり、思わずいいねを押したくなるXの投稿文に変換してください。

ルール:
1. 書き出しは、最もインパクトのある具体的な事実(数値・結果)から入り、読み手の注意を引いてください。製品名・論文名・ライブラリ名は、その直後の自然な流れの中で明かしてください(例: 「Rank-8のLoRAを当てるだけで精度が15.5%から99%に跳ね上がる。その手法の名はEarly-Layer LoRA。」のように、事実→名前の順)。
2. 「神」「ヤバい」「エグい」のような中身のない誇張表現だけに頼らず、要約の中にある**具体的な事実を1つ以上**(数値、手法名、ベンチマーク結果、仕組みなど)を必ず盛り込んでください。
3. 文字数に余裕がある場合のみ、この情報が読み手(個人開発者・エンジニア)にとってどう役立つかを一言添えてください。**文字数を超過するくらいなら、この一言は省略してください。** 記事の内容に即した具体的な内容にし、「が熱い」のような決まり文句は使わないでください。
4. 絵文字は任意です。使う場合は1つだけ、文末付近に自然に置いてください(句読点の直後は避ける)。無理に絵文字を入れる必要はありません。
5. 文字数は日本語本文で**必ず100文字以内**に収めてください(最優先事項。超過は絶対に禁止)。目安は80〜100文字です。

要約:
{summary_text}
"""

  body_text = ""

  for attempt in range(1, max_retries + 1):
    payload = {
        "model": GEMMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": base_prompt},
        ],
        "stream": False,
        "think": False,  # 💡 思考トレースがnum_predictを食い尽くし、
                         # contentが空になる/尻切れになるのを防ぐ
        "keep_alive": 0,
        "options": {
            "temperature": 0.7,
            "num_ctx": 2048,  # 💡 8192 -> 2048 (クラッシュの最大の原因を排除)
            "num_predict": 256,  # 💡 8192 -> 256 (短文生成に必要な最小枠に絞る)
        },
    }

    try:
      res = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=90)
      res.raise_for_status()
      data = res.json()

      raw_response = data.get("message", {}).get("content", "").strip()
      body_text = clean_llm_response(raw_response)

      if is_subject_missing(body_text):
        print(f"⚠️ [Attempt {attempt}] Subject missing detected in Gemma output.")
        body_text = fix_subject_with_qwen(summary_text, body_text)

      effective_len = get_x_effective_length(body_text, bool(target_url))
      print(
          f"📊 [Attempt {attempt}/{max_retries}] Body: {len(body_text)} chars |"
          f" Effective Length: {effective_len} chars"
      )

      if (
          60 <= effective_len <= 135
          and not is_subject_missing(body_text)
          and is_japanese_text(body_text)
      ):
        print("✅ Perfect! Fits X length bounds and structure.")
        return f"{body_text}\n\n{target_url}" if target_url else body_text
      elif not is_japanese_text(body_text):
        print(f"⚠️ [Attempt {attempt}] Gemma output is not Japanese. Retrying...")

    except Exception as e:
      print(f"⚠️ Refine API error (Attempt {attempt}): {e}")

  print("⚠️ Applying safe fallback...")
  if is_subject_missing(body_text) or not is_japanese_text(body_text):
    body_text = generate_safe_japanese_fallback(summary_text)

  max_body_len = 115 if target_url else 140
  body_text = truncate_at_boundary(body_text, max_body_len)

  body_text = clean_llm_response(body_text)

  return f"{body_text}\n\n{target_url}" if target_url else body_text