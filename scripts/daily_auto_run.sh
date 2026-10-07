#!/bin/bash
# プランB: 日次自動実行スクリプト(Windowsタスクスケジューラ等から呼び出す想定)
#
# 自動化する範囲(無人実行、2026-10-07にPart A/note生成/監査のみから拡張):
#   1. Part A (新規ネタ取得・Stage1英語詳細要約。Xポストの精製はここでは行わない)
#   2. note.com記事生成
#   3. note監査(/audit-drafts) + Xポスト精製(/refine-x-posts)を、1回の
#      claude -p 非対話セッションの中で順番に実行する(セッション起動の
#      固定コストを2回払わないよう、1セッションにまとめている)
#   4. note.com公開(audit_passed=trueの記事のみ。ゲートはpublish_to_note_free_batch.py
#      側の get_next_unpublished_article() に実装済みなので、このスクリプトからは
#      単に呼ぶだけでよい)
#   5. X投稿(SocialDog予約投稿 + Git push)。Xポストには現時点でnote.comのような
#      個別audit_passedゲートが無いため、精製された分は全件予約される
#   6. 最終レポート: audit不合格で未公開のまま残っている記事を一覧表示
#
# 💡 設計変更の経緯(2026-10-07): 導入当初はここで無人実行を止め、公開は
# ユーザーが結果を見てから手動で行う設計だった(公開系自動化には過去に
# 複数の事故実例があったため)。その後、監査ゲート(audit_passed)が
# ハルシネーション・重複・簡体字混入等を実際に検知できることが実運用で
# 確認できたため、「合格したものはそのまま公開まで自動で終わらせ、
# 不合格のものだけ人間が見てバグを直し、再生成→再監査→再公開する」
# という日次サイクルに変更した。公開オペレーション自体(note.com UI操作、
# SocialDog予約)は従来どおり壊さず、変更していない。
#
# 💡 同日さらに、Xポストの精製(Stage2/3)もGemma/Qwenのローカルモデルから
# Claude自身(/refine-x-posts Skill、Haiku経由)に置き換えた。ハルシネーション・
# 重複・外国語混入への耐性がローカルモデルより高いと判断したため。
# refiner.py/reviewer.py自体は削除せず、手動比較用に残してある。
set -e

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

mkdir -p output/daily_auto_logs
LOG_FILE="output/daily_auto_logs/$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Daily Auto Run: $(date) ==="

echo ""
echo "--- Step 1: Part A (fetch + curate + Stage1) ---"
source .venv/bin/activate
python3 run_today_pipeline_parta.py

echo ""
echo "--- Step 2: note.com article generation ---"
cd "$REPO_ROOT/for-note-post"
python3 autogenerate_note_article.py
cd "$REPO_ROOT"

echo ""
echo "--- Step 3: Audit (/audit-drafts) + X post refine (/refine-x-posts), one session ---"
# 💡 bypassPermissions: 無人実行なので、ツール実行の都度の確認待ちで
# 止まらないようにする。両Skillともファイル読み書きとWorkflow呼び出しのみで、
# 公開等の不可逆操作は一切行わない設計なので許容できる。
# 💡 2つのSkillを1つのclaude -pセッションにまとめているのは、セッション起動時に
# 読み込まれる固定コンテキスト(システムプロンプト等)のコストを2回払わないため。
claude -p "まず /audit-drafts を実行して。完了したら、続けて /refine-x-posts を実行して。" --permission-mode bypassPermissions

# 💡 ここから先は「公開」なので、個々のステップが失敗しても
# スクリプト全体を止めず(set -eを解除)、必ず最後のレポートまで到達させる
set +e

echo ""
echo "--- Step 4: note.com publish (audit_passed articles only) ---"
cd "$REPO_ROOT/for-note-post"
python3 publish_to_note_free_batch.py
NOTE_PUBLISH_STATUS=$?
cd "$REPO_ROOT"
if [ $NOTE_PUBLISH_STATUS -ne 0 ]; then
    echo "⚠️ note.com publish exited with status $NOTE_PUBLISH_STATUS. Continuing to Step 5."
fi

echo ""
echo "--- Step 5: X post scheduling (SocialDog) + Git sync ---"
python3 run_today_pipeline_partb.py
X_PUBLISH_STATUS=$?
if [ $X_PUBLISH_STATUS -ne 0 ]; then
    echo "⚠️ X post scheduling exited with status $X_PUBLISH_STATUS."
fi

echo ""
echo "--- Step 6: Final report (audit-failed articles still awaiting a fix) ---"
python3 - <<'PYEOF'
import json
import os

status_path = "for-note-post/note_status.json"
status = json.load(open(status_path, encoding="utf-8"))

pending_failures = []
for raw_file, entries in status.items():
    if not isinstance(entries, dict):
        continue
    for idx, info in entries.items():
        if not isinstance(info, dict):
            continue
        if info.get("audit_passed") is not False:
            continue
        if info.get("published_to_note") is True:
            continue
        gen = info.get("generated_file")
        if not gen or not os.path.exists(gen):
            continue
        pending_failures.append((raw_file, idx, gen, info.get("audit_reasons", [])))

if not pending_failures:
    print("✅ 監査不合格のまま残っている記事はありません。")
else:
    print(f"⚠️ 監査不合格で未公開のまま残っている記事が{len(pending_failures)}件あります:")
    for raw_file, idx, gen, reasons in pending_failures:
        print(f"\n- {os.path.basename(gen)} (raw: {raw_file}, idx: {idx})")
        for r in reasons:
            print(f"    理由: {r}")
    print("\n次のサイクル: 原因を見てコードを修正 → 該当idxのnote_usedを外して再生成")
    print("(autogenerate_note_article.py / --dry-run推奨) → /audit-drafts で再監査")
    print("→ 合格したらpublish_to_note_free_batch.py / run_today_pipeline_partb.pyで公開")
PYEOF

echo ""
echo "=== Daily Auto Run finished: $(date) ==="
