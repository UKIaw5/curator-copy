import os
import random
import re
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

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
    "完璧すぎる,この着眼点",
    "完成度高すぎ、この仕組み",
]


class PoolManager:
  """実行セッション内でフレーズや絵文字が重複しないよう管理するクラス"""

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


# グローバルプールマネージャー（プロセス内でユニーク性を保持）
pool_manager = PoolManager()


def extract_clean_url(text: str) -> str:
  """テキストからURLを抽出し、末尾の記号やMarkdownノイズ(**等)を綺麗に除去する"""
  match = re.search(r'https?://[^\s<>"\)\]]+', text)
  if not match:
    return ""
  url = match.group(0)
  return re.sub(r"[\.\,\)\]\*\_\:]+$", "", url)


def get_x_effective_length(body_text: str, has_url: bool) -> int:
  url_cost = 25 if has_url else 0
  return len(body_text) + url_cost


def clean_llm_response(raw_text: str) -> str:
  """思考タグやメタ発言、Markdown太字ノイズなどをトリムする"""
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
  return result


def refine_to_x_post(summary_text: str, max_retries: int = 3) -> str:
  target_url = extract_clean_url(summary_text)

  # プールから今回専用の要素を1つずつ重複なしで抽出
  assigned_hook = pool_manager.get_hook()
  assigned_closing = pool_manager.get_closing()
  assigned_emoji = pool_manager.get_emoji()

  system_prompt = (
      "You are a concise X (Twitter) post generator.\n"
      "CRITICAL INSTRUCTIONS:\n"
      "1. Output ONLY the final Japanese text directly and immediately.\n"
      "2. Use strictly casual Japanese (タメ語 / だ・である調・ラフな口調). NEVER use"
      " desu/masu (です・ます)."
  )

  base_prompt = f"""You are an energetic tech developer sharing AI & software breakthroughs on X (Twitter).
Refine the following technical summary into a rich, high-impact Japanese X post.

[Strict Style Guidelines]
1. Hook & Tone:
   - Use strictly casual Japanese (タメ語). No "です・ます".
   - Naturally incorporate or align with these specific expressions:
     * Hook expression idea: "{assigned_hook}"
     * Closing sentiment idea: "{assigned_closing}"
   - DO NOT use full-width brackets like 【】 or [ ].

2. Emoji Rules (CRITICAL):
   - Use the designated emoji `{assigned_emoji}` naturally.
   - NEVER place an emoji immediately after a Japanese period (。), comma (、), or punctuation mark (e.g., "。{assigned_emoji}" is strictly prohibited).

3. Content & Substance:
   - Must include at least ONE concrete technical feature, metric, or mechanism from the input.

4. Output Rules:
   - DO NOT include any URL. Output ONLY the Japanese text.
   - Keep the response VERY CONCISE (strictly 1-2 short sentences).

Input:
{summary_text}
"""

  model_name = os.getenv("GEMMA_MODEL", "gemma4:12b")
  body_text = ""

  for attempt in range(1, max_retries + 1):
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": base_prompt},
        ],
        "stream": False,
        "keep_alive": 0,
        "options": {
            "temperature": 0.75,
            "num_ctx": 8192,
            "num_predict": 8192,
        },
    }

    try:
      res = requests.post(OLLAMA_URL, json=payload, timeout=300)
      res.raise_for_status()
      data = res.json()

      raw_response = data.get("message", {}).get("content", "").strip()
      body_text = clean_llm_response(raw_response)

      effective_len = get_x_effective_length(body_text, bool(target_url))
      print(
          f"📊 [Attempt {attempt}/{max_retries}] Body: {len(body_text)} chars |"
          f" Effective X Length: {effective_len} chars"
      )

      if 70 <= effective_len <= 140:
        print("✅ Perfect! Fits X length bounds.")
        return f"{body_text}\n\n{target_url}" if target_url else body_text
      else:
        print(
            f"⚠️ Length out of bounds ({effective_len} chars)."
            " Retrying..."
        )

    except Exception as e:
      print(f"⚠️ Refine API error (Attempt {attempt}): {e}")
      if attempt == max_retries:
        break

  print("⚠️ Applying safe fallback...")
  if not body_text:
    clean_summary = re.sub(r'https?://[^\s<>"]*', "", summary_text).strip()
    first_line = (
        clean_summary.split("\n")[0] if clean_summary else "注目のAI最新技術"
    )
    first_line = (
        first_line.replace("**", "").replace("[", "").replace("]", "")
    )
    body_text = f"{assigned_emoji} {first_line[:90]}"

  max_body_len = 115 if target_url else 140
  if len(body_text) > max_body_len:
    body_text = body_text[: max_body_len - 3] + "..."

  return f"{body_text}\n\n{target_url}" if target_url else body_text