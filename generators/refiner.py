import os
import random
import re
import requests

# 変更後 (環境変数に依存せずチャットAPIを強制指定)
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
GEMMA_MODEL = os.getenv("GEMMA_MODEL", "gemma4:12b")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen2.5-coder:14b") # 現在の14bモデルに合わせる

# --- 素材プール定義 ---
RAW_EMOJI_POOL = [
    "🔥",
    "🚀",
    "💡",
    "⚡",
    "👀",
    "💥",
    "✨",
    "🎯",
    "😎",
    "🛠️",
    "💪",
    "👏",
    "🧠",
    "📦",
    "🙌",
]

RAW_HOOK_POOL = [
    "が熱い",
    "が凄すぎる",
    "が天才的",
    "が神がかってる",
    "が革新的",
    "がエグい",
    "の進化が止まらない",
    "がぶっ飛んでる",
    "が異次元すぎる",
    "がマジで画期的",
    "の設計センスが光る",
    "が個人的に刺さりまくり",
    "の破壊力がヤバい",
    "のアプローチが面白すぎる",
    "が最高にスマート",
    "のポテンシャルが半端ない",
    "が完全にプロ仕様",
    "の完成度に脱帽",
    "が圧倒的すぎる件",
    "の本気度が伝わってくる",
    "がついに来てしまった",
    "が期待感しかない",
    "が本気で強い",
    "が優秀すぎる",
    "の速度感がエグい",
    "が刺さりすぎてツラい",
    "がマジで最高レベル",
    "の着眼点が神レベル",
    "が完全にアツい",
    "が最高にクール",
]

RAW_CLOSING_POOL = [
    "マジで筋が良い",
    "完成度が高すぎる",
    "アプローチが非常にスマート",
    "開発の参考になりすぎる",
    "現場で即役立つレベル",
    "思わず唸る出来栄え",
    "着眼点が鋭すぎる",
    "効率化のインパクトが大きい",
    "仕組みとして美しすぎる",
    "今すぐ試したくなるクオリティ",
    "必見の実装解",
    "開発者の強力な味方",
    "技術選定の強力な一手",
    "シンプルながら強い構成",
    "最良のパフォーマンス",
    "開発体験を爆上げする仕組み",
    "アーキテクチャの模範解答",
    "プロダクト組み込みの最適解",
    "色々と応用が効きそう",
    "キャッチアップ必須の内容",
    "えぐいな、このパフォーマンス",
    "天才かよ、このアプローチ",
    "凄すぎる、この設計思想",
    "マジで強い、この構成",
    "痺れるな、この実装解",
    "見事すぎる、この発想",
    "圧巻だわ、この精度",
    "スマートすぎる、この設計",
    "完璧すぎる、この着眼点",
    "完成度高すぎ、この仕組み",
]


class PoolManager:

  def __init__(self):
    self.emojis = []
    self.hooks = []
    self.closings = []

  def get_emoji(self) -> str:
    if not self.emojis:
      self.emojis = RAW_EMOJI_POOL.copy()
      random.shuffle(self.emojis)
    return self.emojis.pop()

  def get_hook(self) -> str:
    if not self.hooks:
      self.hooks = RAW_HOOK_POOL.copy()
      random.shuffle(self.hooks)
    return self.hooks.pop()

  def get_closing(self) -> str:
    if not self.closings:
      self.closings = RAW_CLOSING_POOL.copy()
      random.shuffle(self.closings)
    return self.closings.pop()


pool_manager = PoolManager()


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

  assigned_hook = pool_manager.get_hook()
  assigned_closing = pool_manager.get_closing()
  assigned_emoji = pool_manager.get_emoji()

  system_prompt = (
      "You are a concise X (Twitter) post generator.\n"
      "Output ONLY the final Japanese text directly and immediately.\n"
      "Use strictly casual Japanese (タメ語). NEVER use desu/masu (です・ます)."
  )

  base_prompt = f"""You are an energetic tech developer sharing AI breakthroughs on X.
Refine the summary into a high-impact Japanese post.

Rules:
1. Try to start with the product/paper name if possible.
2. Naturally include or align with these expressions:
   - Hook expression: "{assigned_hook}"
   - Closing idea: "{assigned_closing}"
3. Include emoji `{assigned_emoji}` (never right after '。' or '、').
4. Keep it short and punchy (around 50-80 Japanese characters).

Summary:
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
    safe_sentence = generate_safe_japanese_fallback(summary_text)
    body_text = f"{safe_sentence[:80]} {assigned_hook}{assigned_emoji}"

  max_body_len = 115 if target_url else 140
  if len(body_text) > max_body_len:
    body_text = body_text[: max_body_len - 3] + "..."

  body_text = clean_llm_response(body_text)

  return f"{body_text}\n\n{target_url}" if target_url else body_text