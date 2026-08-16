import os
import re
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

def refine_to_x_post(summary_text: str) -> str:
    """Refine the Stage 1 summary into a highly professional X post."""
    
    # Extract URL safely from input summary text if available
    url_match = re.search(r'https?://[^\s<>"]+|www\.[^\s<>"]+', summary_text)
    target_url = url_match.group(0) if url_match else ""

    prompt = f"""
You are a highly skilled and sophisticated technology curator.
Your task is to refine the following technical summary into a single X (Twitter) post in Japanese.

[Strict Tone & Style Guidelines]
1. Fact-based and Matter-of-fact: Introduce the core technology, paper, or news calmly and objectively.
2. Quiet Enthusiasm: Convey the significance of the technical breakthrough without shouting. Readers should feel the depth of the innovation through facts, not hype.
3. NO Hype Words: NEVER use cheap clickbait words like "ヤバい", "ヤバすぎ", "マジで", "革命", or "神".
4. NO Clickbait Formatting: NEVER use brackets like 【 】 or bold attention-grabbers at the beginning of the post.
5. Minimal Emojis: Do NOT use exaggerated emojis like 🤯, 🔥, or 🚀. Use only structural or subtle emojis if necessary (e.g., 💡, 📊, 📝).

[Strict Anti-Hallucination Rule for URLs]
- NEVER invent, guess, or generate fake URLs (like example.com).
- ONLY use the exact URL if it is explicitly provided in the input text.
- If the input does not contain a valid URL, DO NOT append any URL at the end.

[Few-Shot Examples]
Input: 
DeepSeek Harness is a new dev platform. It allows AI features like NLP as plugins. Makes desktop app dev easier. https://github.com/deepseek-ai/deepseek-harness
Output: 
DeepSeekから新しい開発プラットフォーム「DeepSeek Harness」が公開されました。
自然言語処理などのAI機能を、プラグイン形式で手軽に組み込めるアーキテクチャを採用しています。今後のローカルAIを活用したデスクトップアプリ開発の敷居を、一段階下げるアプローチとして非常に興味深いです。
https://github.com/deepseek-ai/deepseek-harness

Input: 
Maglev is a new Transformer combining full attention and sliding-window. Improves efficiency and accuracy. https://huggingface.co/papers/2608.02870
Output:
Full attentionとSliding-windowを組み合わせた新しいTransformerアーキテクチャ「Maglev」の論文。
計算効率を最適化しつつ、推論精度を向上させる手法が提案されています。大規模言語モデルの今後の軽量化・高速化において、重要なベースラインになりそうな研究です。
https://huggingface.co/papers/2608.02870

[Actual Task]
Input: 
{summary_text}

Output (in Japanese, following ALL guidelines above):
"""

    model_name = "gemma2:9b"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }
    
    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=120)
        res.raise_for_status()
        data = res.json()
        refined = data.get("response", "").strip()
        
        # Clean up markdown code blocks if present
        refined = re.sub(r"^```(?:markdown)?\s*", "", refined, flags=re.IGNORECASE)
        refined = re.sub(r"\s*```$", "", refined).strip()
        
        if target_url:
            # If the model output a placeholder like [original_url] or a broken URL, replace it
            if re.search(r"https?://\[.*?\]", refined) or "https://[original_url]" in refined:
                refined = re.sub(r"https?://\[.*?\]", target_url, refined)
                refined = refined.replace("https://[original_url]", target_url)
            elif target_url not in refined:
                # If model forgot the URL entirely, append it cleanly at the end
                refined = f"{refined}\n\n{target_url}"
                
        return refined
        
    except Exception as e:
        print(f"⚠️ Refine API error with {model_name}: {e}")
        
    return summary_text