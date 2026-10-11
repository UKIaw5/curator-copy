# LEARNINGS

## 運用ルール
- 昇格基準: 同種の内容が3回記録されたらCLAUDE.mdへの昇格を提案し、承認後にここを[昇格済]にする
- 1件は5行以内。事実と対策だけ書く
- 同じ内容が既にあれば、新規追加せず「再発回数」を+1する

## 記録

### 2026-10-11 | (例)記録の書き方
- 状況: 何をしていて何が起きたか
- 原因: 分かっている範囲で
- 対策: 次回どうするか
- 再発回数: 1

### 2026-10-11 | socialdog_poster.pyがSIGTERMで落ちgit同期がスキップされる
- 状況: `/analyze-history`での履歴調査中に発見。2026-10-08・2026-10-09の無人実行ログで、socialdog_poster.pyが投稿スケジューリング完了("🎉 All posts scheduled!"まで出力)後にSIGTERM(15)で異常終了(`output/daily_auto_logs/20261008_110000.log:311`, `20261009_101501.log:219`)。`run_today_pipeline_partb.py:28-31`の`except subprocess.CalledProcessError`が`git_commit_and_push()`を呼ばずreturnするため、その日のGit同期がスキップされた。
- 原因: 未確定(Task Schedulerの実行時間制限/WSLセッション終了/CloakBrowserのclose処理のハング等が候補だが未検証)。両日とも別タイミングで`Auto: Update multi-source...`コミットが記録されている(git log: 10-08は14:42と15:45、10-09は12:13)が、手動再実行によるものかは未確認。10-10・10-11のログでは同エラーは再発していない。
- 対策: 再発時はまずSIGTERMの送信元を特定する。恒久対応として、socialdog_poster.py失敗時でも(そこまでに完了した分の)`git_commit_and_push()`を試みるよう`run_today_pipeline_partb.py`を見直すことも検討。
- 再発回数: 2(2026-10-08, 2026-10-09)
