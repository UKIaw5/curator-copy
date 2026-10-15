---
name: fix-audit-failed-notes
description: 自動実行(daily_auto_run.sh)で生成されたが監査不合格のまま未公開で残っているnote.com記事を調査・修正し、再監査→公開→Discord通知までを一括で行う
---

このSkillは、CLAUDE.md 7章で説明されている「監査不合格で未公開のまま残っている記事」に対する次のサイクル
(原因を見てコードを修正 → 該当idxのnote_usedを外して再生成、または手動修正 → `/audit-drafts`で再監査 →
合格したら`publish_to_note_free_batch.py`で公開)を自動化し、最後にDiscord通知まで行うもの。

## `/audit-drafts`との違い

`/audit-drafts`は「まだ監査していない」新規ドラフトが対象(`audit_passed`キーが存在しないもの)。
このSkillは「監査済みで不合格だった(`audit_passed: false`)」ドラフトの**修復**が対象。両者は対象の条件で
重複しないため、どちらかを実行してもう一方の対象を誤って処理することはない。

## 前提

- `/home/uk/Vault/curator-copy/for-note-post/note_status.json` を読み書きする。
- playwright依存のスクリプト(`publish_to_note_free_batch.py`)を呼ぶ際は、システムのpython3ではなく
  `.venv/bin/python3`(または`source .venv/bin/activate`後)を使うこと。
- 監査(再監査)は`Agent`ツールを`model: "sonnet"`で使う(`audit-drafts`と同じ、誤字・ハルシネーションの
  ような小さな違和感を拾う検知タスクは大きいモデルの方が精度が高いため)。
- `LEARNINGS.md`冒頭の運用ルール(再現性のあるコード/パイプラインのバグは1回目で即修正、LLMのランダムな
  生成ノイズは同種の内容が3回記録されてから検討)に従うこと。

## 手順

1. **対象の洗い出し**: `note_status.json`の全`raw_file`・全`idx`をスキャンし、以下をすべて満たすものを
   「対象」とする:
   - `info.generated_file`が存在し、そのファイルが実際にディスク上に存在する
   - `info.published_to_note`が`true`ではない
   - `info.audit_passed`が`false`(既に監査済みで不合格、キー自体が無い未監査のものは対象外)

   対象が0件なら「修正対象なし」とだけ報告してここで終了する(公開・通知も行わない)。

2. **原因の診断(対象ごと)**: 各対象の`info.audit_reasons`を読み、対応する`generated_file`を実際に開いて
   指摘箇所を確認する。次の3種類に分類する(推測で決めず、関連コードを実際に読んで判断すること — 過去に
   「フェンスが無い=壊れている」という監査側の思い込みを、`lint_markdown()`の実装を読んで誤検知と判定した
   実例がある):

   a. **検出器のカバレッジ漏れ**: `has_foreign_script_mixed()`(キリル文字・簡体字中国語・ハングル等の
      混入検出)や`lint_markdown()`等、"本来検出すべき設計のコードが、特定のパターンを検出できていない"
      タイプの不具合。モデル出力のランダム性とは独立して、同じ文字種・パターンが来れば毎回必ず素通りする
      ため、LEARNINGS.mdの運用ルールにより**3回ルールを待たず直ちにコード修正する**。
      `for-note-post/autogenerate_note_article.py` / `autogenerate_note_article_2.py` /
      `generate_note_article.py` の**3ファイル全てに同じ修正を適用すること**(1ファイルだけ直して
      再発した実例がある)。
   b. **監査側の誤検知**: `.claude/skills/audit-drafts/SKILL.md`に既に明記されている仕様、または
      関連コード(`lint_markdown()`等)を実際に読んで確認した結果、実害が無いと判明したケース。この場合は
      コードも記事本文も変更しない。新しい誤検知パターンだった場合は、`audit-drafts/SKILL.md`の
      「このプロジェクト固有の仕様」節に追記して再発を防ぐこと。
   c. **LLMのランダムな生成ノイズ**: ハルシネーション、誤字、誤訳など、再現性が無い(または無いと現時点
      では判断できる)単発の出力不良。該当ファイルを直接編集して修正する。被害が一箇所に留まらず記事全体に
      及ぶ場合のみ、`note_status.json`で該当idxの`note_used`を`false`に戻し、`autogenerate_note_article.py`
      (`.venv/bin/python3`で実行)で再生成する。コード/プロンプトの変更は、LEARNINGS.mdに**同種の内容が
      3回記録されるまで行わない**。

3. **修正の実施**:
   - (a) 検出器のカバレッジ漏れ: 3ファイルの検出ロジックを修正し、既存の生成済みファイルの該当箇所も
     直接編集する。
   - (b) 誤検知: `audit-drafts/SKILL.md`の追記のみ(対象の生成ファイルは変更しない)。
   - (c) LLMノイズ: 生成済みファイルの該当箇所を編集する(または上記の通り再生成する)。
   いずれの場合も、1件5行以内で`/home/uk/Vault/curator-copy/LEARNINGS.md`に記録する(既存のフォーマットに
   従う。同種の内容が既にあれば新規追加せず「再発回数」を+1するだけにする)。

4. **再監査**: 修正した対象ごとに`Agent`ツールを`model: "sonnet"`で呼ぶ(対象が複数あれば1つのメッセージ
   内で並列発行してよい、待つ必要はない)。プロンプトは`.claude/skills/audit-drafts/SKILL.md`内の監査
   プロンプトテンプレート(「このプロジェクト固有の仕様」「本当にチェックすべき観点」節を含む全文)をそのまま
   使い、「最後に、必ず次の形式で結果を出力してください」の直前に次の1文を追加する:

   ```
   この記事は前回、{info.audit_reasonsの内容}という理由で不合格となった。{手順3で行った具体的な修正内容}。
   この修正が正しく反映されているか、他に同種の問題が残っていないかを重点的に確認すること。
   ```

   応答は`audit-drafts`と同じ`VERDICT: passed=<true|false>` / `REASONS: ...`形式でパースする。パースできない
   場合は安全側に倒し`passed=false`として扱う。

5. **結果の反映**: 再監査に合格した対象は、`note_status.json`の該当エントリを
   `audit_passed: true`, `audit_reasons: []`, `audit_at: <実行時刻>` に更新する。
   再監査でも不合格だった場合は、その新しい理由を元に手順2〜4を**最大2回まで**繰り返す。それでも合格しない
   対象はスキップし、最終報告で「未解決」として明示する(無理に公開しない)。

6. **公開**: 合格した対象が1件以上あれば、`.venv/bin/python3`で
   `for-note-post/publish_to_note_free_batch.py`を実行する(このスクリプトは`audit_passed is True`かつ
   未公開のものだけを自動的に対象にするゲートを内部に持っている)。

7. **Gitへの記録**: 変更したコード・`note_status.json`・`LEARNINGS.md`・(誤検知修正時のみ)
   `audit-drafts/SKILL.md`・公開済みアーカイブファイル(`for-note-post/output/archive_published/`)を
   まとめてcommit・pushする(このプロジェクトはパイプラインスクリプト自身が自動でgit同期する設計であり、
   この修正サイクルも同じ運用に含める)。

8. **通知**: 以下のように`scripts/notify_daily_result.py`内の既存のDiscord/Notepad通知関数を再利用し、
   ログファイルからではなく今回の実行結果から組み立てたレポート文字列を渡して通知する:

   ```python
   import sys, os
   sys.path.insert(0, "/home/uk/Vault/curator-copy/scripts")
   from notify_daily_result import load_env_file, post_to_discord, open_in_notepad, ENV_FILE

   env = load_env_file(ENV_FILE)
   webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or env.get("DISCORD_WEBHOOK_URL")

   report_text = """📅 curator-copy 監査不合格修正サイクル
   (ここに: 対象件数、記事ごとのタイトル・原因・対応内容(コード修正/誤検知/手動修正のいずれか)・
   再監査結果、公開件数、未解決件数を日本語で簡潔にまとめて埋め込む)
   """

   post_to_discord(webhook_url, report_text)
   open_in_notepad(report_text)
   ```

9. 最後に、日本語でサマリーを報告する(対象件数、分類ごとの件数(a/b/c)、公開件数、未解決件数)。

## 注意

- 検出器のコード修正(手順3-a)は3ファイル(`autogenerate_note_article.py` / `_2.py` /
  `generate_note_article.py`)に必ず同時適用すること。1ファイルだけ直すと、次回別の生成ルートで同じ問題が
  再発する(実例あり)。
- 公開(`publish_to_note_free_batch.py`)はブラウザを実際に操作してnote.comに公開する、外部に見える操作。
  実行前に対象が本当に合格しているか(手順5)を再確認すること。
- Discord通知・Git pushはどちらも外部に見える/届く操作だが、このプロジェクトは元々パイプラインスクリプト
  自身がこれらを無人で行う設計(`daily_auto_run.sh`等)であり、この修正サイクルもその運用の延長として扱う。
- `.claude/workflows/`配下の`.js`ファイルは使われていない(存在しない`Workflow`ツールを前提にした設計の
  名残)。参照しないこと。存在しないツールを探して独自の代替処理を即興で作ったりしないこと。
