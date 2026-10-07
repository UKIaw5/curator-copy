#!/bin/bash
# プランB: 日次自動実行スクリプト(Windowsタスクスケジューラ等から呼び出す想定)
#
# 自動化する範囲(無人実行):
#   1. Part A (新規ネタ取得・Xポスト案生成)
#   2. note.com記事生成
#   3. 監査(Claude Code非対話モードで /audit-drafts Skillを実行)
#
# 手動のまま残す範囲(実際に世に出る操作、このスクリプトではやらない):
#   - X投稿: python3 run_today_pipeline_partb.py
#   - note.com公開: cd for-note-post && python3 publish_to_note_free_batch.py
#
# 💡 公開系の自動化には実際に事故の実例がある(CLAUDE.md参照)ため、
# 生成・監査までを無人化し、実際の公開はユーザーの確認を経てから
# 手動で行う設計にしている。

set -e

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

mkdir -p output/daily_auto_logs
LOG_FILE="output/daily_auto_logs/$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Daily Auto Run: $(date) ==="

echo ""
echo "--- Step 1: Part A (fetch + curate + Stage1/2) ---"
source .venv/bin/activate
python3 run_today_pipeline_parta.py

echo ""
echo "--- Step 2: note.com article generation ---"
cd "$REPO_ROOT/for-note-post"
python3 autogenerate_note_article.py
cd "$REPO_ROOT"

echo ""
echo "--- Step 3: Audit via Claude Code (/audit-drafts) ---"
# 💡 bypassPermissions: 無人実行なので、ツール実行の都度の確認待ちで
# 止まらないようにする。監査はファイル読み書きとWorkflow呼び出しのみで、
# 公開等の不可逆操作は一切行わない設計なので許容できる
claude -p "/audit-drafts" --permission-mode bypassPermissions

echo ""
echo "=== Daily Auto Run finished: $(date) ==="
echo ""
echo "次の手動ステップ(確認の上、実行してください):"
echo "  X投稿:      python3 run_today_pipeline_partb.py"
echo "  note.com公開: cd for-note-post && python3 publish_to_note_free_batch.py"
