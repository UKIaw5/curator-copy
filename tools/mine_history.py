#!/usr/bin/env python3
"""Claude Codeの履歴(JSONL)から、不満・中断の候補と、セッションをまたぐ類似依頼を抽出する。

使い方: python3 tools/mine_history.py [プロジェクトのパス] [出力ファイル]
"""
import json
import re
import sys
from pathlib import Path

FRUSTRATION = [
    r"違う", r"そうじゃない", r"そうではない", r"なんで", r"何度", r"さっき(も)?言",
    r"言ったよね", r"勝手に", r"余計な", r"やめて", r"聞いてない", r"もういい",
    r"\bwrong\b", r"I (already )?told you", r"\bagain\b", r"\bstop\b",
]
FR = re.compile("|".join(FRUSTRATION), re.I)
SKIP_PREFIX = ("<command-", "<local-command", "Caveat:", "<system-reminder", "<task-notification")


def project_history_dir(project_path: str) -> Path:
    # Claude Codeは絶対パスの英数字以外を "-" に置き換えたフォルダ名で履歴を保存する
    name = re.sub(r"[^A-Za-z0-9]", "-", str(Path(project_path).expanduser().resolve()))
    return Path.home() / ".claude" / "projects" / name


def blocks_text(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):  # tool_result / tool_use は除外し text だけ拾う
        return "\n".join(
            b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def grams(s):
    s = re.sub(r"\W+", "", s.lower())
    return {s[i:i + 3] for i in range(len(s) - 2)}


def main(project_path=".", out_path="digest.md"):
    hist = project_history_dir(project_path)
    files = sorted(hist.glob("*.jsonl"))
    if not files:
        sys.exit(f"履歴が見つかりません: {hist}")

    prompts, frustr = [], []
    for f in files:
        last_ai = ""
        with f.open(encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("isSidechain"):
                    continue
                # claude -p 等の非対話(SDK/自動実行)セッションは対象外にする。
                # 人間がタイプしたプロンプトはentrypoint:"cli"、daily_auto_run.sh等の
                # `claude -p`経由はentrypoint:"sdk-cli"になることを実機のJSONLで確認済み。
                if d.get("entrypoint") == "sdk-cli":
                    continue
                msg = d.get("message") or {}
                if d.get("type") == "assistant":
                    last_ai = blocks_text(msg)[:200]
                elif d.get("type") == "user" and not d.get("isMeta"):
                    t = blocks_text(msg).strip()
                    if not t or t.startswith(SKIP_PREFIX):
                        continue
                    rec = (f.stem[:8], d.get("timestamp", "")[:10], t, last_ai)
                    prompts.append(rec)
                    if "Request interrupted" in t or FR.search(t):
                        frustr.append(rec)

    # 別セッションで似た依頼(3-gramのJaccard類似度)
    cands = [(p, grams(p[2])) for p in prompts if 8 <= len(p[2]) <= 300]
    pairs = []
    for a in range(len(cands)):
        for b in range(a + 1, len(cands)):
            (pa, ga), (pb, gb) = cands[a], cands[b]
            if pa[0] == pb[0] or not ga or not gb:
                continue
            if len(ga & gb) / len(ga | gb) >= 0.5:
                pairs.append((pa, pb))

    with open(out_path, "w", encoding="utf-8") as o:
        o.write(f"# 履歴ダイジェスト\n\n対象: {hist}\nセッション数: {len(files)} / 総発言数: {len(prompts)}\n\n")
        o.write(f"## A. 不満・中断の候補 ({len(frustr)})\n\n")
        for s, d, t, ai in frustr:
            o.write(f"- [{d} {s}] 発言: {t[:300]!r}\n  - 直前のClaude: {ai!r}\n")
        o.write(f"\n## B. セッションをまたいだ類似依頼 ({len(pairs)})\n\n")
        for p, q in pairs[:100]:
            o.write(f"- [{p[1]} {p[0]}] {p[2][:150]!r}\n  - [{q[1]} {q[0]}] {q[2][:150]!r}\n")
    print(f"done: {out_path} (不満候補 {len(frustr)} 件 / 類似依頼 {len(pairs)} 組)")


if __name__ == "__main__":
    main(*sys.argv[1:3])
