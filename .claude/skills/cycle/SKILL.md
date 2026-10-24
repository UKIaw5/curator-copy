---
name: cycle
description: 日次パイプラインでX投稿・note.com公開のいずれかが未完了のまま残っている場合に、原因を調査・修正し、両方とも完了させた上でDiscord通知まで行う(旧fix-audit-failed-notes→complete-daily-cycleを経て改名。X投稿+note.com両方の「やり残し」を一括完了させる)
---

このSkillは、CLAUDE.md 7章の「監査不合格で未公開のまま残っている記事」サイクルに加えて、
**X投稿が何らかの理由で未完了のまま残っているケース**も対象に含めた、日次パイプラインの
「やり残し」を一括で完了させるSkill。2026-10-19に、SocialDogのセッションCookie期限切れで
X投稿が0件のまま`daily_auto_run.sh`が「成功」と誤報告していた事故をきっかけに、
note.com限定だった`fix-audit-failed-notes`を拡張した。

## `/audit-drafts`との違い

`/audit-drafts`は「まだ監査していない」新規note.comドラフトが対象(`audit_passed`キーが
存在しないもの)。このSkillのnote.com側は「監査済みで不合格だった(`audit_passed: false`)」
ドラフトの**修復**が対象。両者は対象の条件で重複しない。

## 前提

- `/home/uk/Vault/curator-copy/for-note-post/note_status.json` を読み書きする。
- playwright依存のスクリプト(`publish_to_note_free_batch.py`、`run_today_pipeline_partb.py`経由の
  `automation/socialdog_poster.py`)を呼ぶ際は、システムのpython3ではなく`.venv/bin/python3`
  (または`source .venv/bin/activate`後)を使うこと。
- 監査(再監査)は`Agent`ツールを`model: "sonnet"`で使う(`audit-drafts`と同じ、誤字・ハルシネーションの
  ような小さな違和感を拾う検知タスクは大きいモデルの方が精度が高いため)。
- `LEARNINGS.md`冒頭の運用ルール(再現性のあるコード/パイプラインのバグは1回目で即修正、LLMのランダムな
  生成ノイズは同種の内容が3回記録されてから検討)に従うこと。
- **X投稿側のCookie/認証切れは、このSkillだけでは解決できない**(ユーザーがcookie-editorで
  ブラウザから取得し直す必要がある)。検出したら無理に繰り返さず、その旨を明確にユーザーへ報告して
  その部分だけ「未解決」として扱うこと(note.com側は可能な範囲で完了させる)。

## 手順

### パート1: X投稿側の未完了を解消する

1. **対象の洗い出し**:
   - `output/output_x_posts_*.md`(タイムスタンプ付き、まだ`output/archive/`に移動されていない
     ファイル)が存在するか確認する。存在すれば「精製済みだが投稿されていない」状態。
   - 存在しない場合は、`output/raw/output_prex_posts_*.md`のうち、対応する
     `output/output_x_posts_<timestamp>.md`も`output/archive/output_x_posts_<timestamp>.md`も
     存在しないものがないか確認する(`/refine-x-posts`の手順1と同じ判定ロジック)。該当すれば
     「まだ精製すらされていない」状態。
   - どちらも無ければX投稿側は完了しているので、パート2(note.com側)へ進む。

2. **未精製の場合**: `/refine-x-posts`相当の処理(Skillとして存在するので、このSkill内から
   同じ手順を実行する)で`output/output_x_posts_<timestamp>.md`を生成する。生成後、手順3へ進む。

3. **未投稿の場合**: `.venv/bin/python3 run_today_pipeline_partb.py`を実行する(X投稿の予約
   スケジューリング+Git同期を内部で行う)。終了コードを確認すること(2026-10-19以降、
   `automation/socialdog_poster.py`は失敗時に非ゼロで終了するよう修正済みなので、
   `subprocess`の成否メッセージだけでなく実際の終了コード・標準出力の内容で判断すること)。

4. **失敗した場合の診断**: 標準出力を読み、原因を次のいずれかに分類する:
   - **SocialDogセッションCookie期限切れ**(「Redirected to login page」「session has expired」
     等のメッセージ、またはログに"/login"へのリダイレクトが見える): これはこのSkillだけでは
     解決できない。ユーザーに「`automation/socialdog_cookies.json`をcookie-editorで
     web.social-dog.netから取得し直して配置してください」と明確に報告し、X投稿側はこれ以上
     リトライせず「未解決(要ユーザー対応)」として最終報告に含める。note.com側の処理は止めず続行する。
   - **再現性のあるコードの不具合**(セレクタが変わった、例外処理が握り潰されている等): 1回目で
     即修正する(3回ルールの対象外)。修正後、再度`run_today_pipeline_partb.py`を1回だけ実行して
     解消したか確認する。解消しなければ無理に繰り返さず「未解決」として報告する。
   - **単発の一時的エラー**(タイムアウト等、原因が特定できない一過性のもの): 1回だけ再実行して
     みる。それでも失敗する場合は「未解決」として報告する(3回以上リトライしない)。
   - いずれの場合も、修正や判明した事実を`LEARNINGS.md`に記録する(既存フォーマット・運用ルールに従う)。

5. 成功した場合(全件予約+アーカイブ+Git push完了)、X投稿側は完了。パート2へ進む。

### パート2: note.com側の未完了を解消する(旧fix-audit-failed-notesと同じ)

6. **対象の洗い出し**: `note_status.json`の全`raw_file`・全`idx`をスキャンし、以下をすべて満たす
   ものを「対象」とする:
   - `info.generated_file`が存在し、そのファイルが実際にディスク上に存在する
   - `info.published_to_note`が`true`ではない
   - `info.audit_passed`が`false`(既に監査済みで不合格、キー自体が無い未監査のものは対象外)

   対象が0件なら、note.com側は「修正対象なし」として手順13(最終報告・通知)へ進む。

7. **原因の診断(対象ごと)**: 各対象の`info.audit_reasons`を読み、対応する`generated_file`を
   実際に開いて指摘箇所を確認する。次の3種類に分類する(推測で決めず、関連コードを実際に読んで
   判断すること):

   a. **検出器のカバレッジ漏れ**: `has_foreign_script_mixed()`(キリル文字・簡体字中国語・
      ハングル等の混入検出)や`lint_markdown()`等、"本来検出すべき設計のコードが特定のパターンを
      検出できていない"タイプの不具合。モデル出力のランダム性とは独立して同じパターンが来れば
      毎回必ず素通りするため、**3回ルールを待たず直ちにコード修正する**。
      `for-note-post/autogenerate_note_article.py` / `autogenerate_note_article_2.py` /
      `generate_note_article.py` の**3ファイル全てに同じ修正を適用すること**(1ファイルだけ直して
      再発した実例がある)。
   b. **監査側の誤検知**: `.claude/skills/audit-drafts/SKILL.md`に既に明記されている仕様、または
      関連コードを実際に読んで確認した結果、実害が無いと判明したケース。この場合はコードも記事本文も
      変更しない。新しい誤検知パターンだった場合は、`audit-drafts/SKILL.md`の「このプロジェクト
      固有の仕様」節に追記して再発を防ぐこと。
   c. **LLMのランダムな生成ノイズ**: ハルシネーション、誤字、誤訳など、再現性が無い(または無いと
      現時点では判断できる)単発の出力不良。該当ファイルを直接編集して修正する。被害が一箇所に
      留まらず記事全体に及ぶ場合のみ、`note_status.json`で該当idxの`note_used`を`false`に戻し、
      `autogenerate_note_article.py`(`.venv/bin/python3`で実行)で再生成する。コード/プロンプトの
      変更は、LEARNINGS.mdに**同種の内容が3回記録されるまで行わない**。

8. **修正の実施**:
   - (a) 検出器のカバレッジ漏れ: 3ファイルの検出ロジックを修正し、既存の生成済みファイルの
     該当箇所も直接編集する。
   - (b) 誤検知: `audit-drafts/SKILL.md`の追記のみ(対象の生成ファイルは変更しない)。
   - (c) LLMノイズ: 生成済みファイルの該当箇所を編集する(または上記の通り再生成する)。
   いずれの場合も、1件5行以内で`/home/uk/Vault/curator-copy/LEARNINGS.md`に記録する(既存の
   フォーマットに従う。同種の内容が既にあれば新規追加せず「再発回数」を+1するだけにする)。

9. **再監査**: 修正した対象ごとに`Agent`ツールを`model: "sonnet"`で呼ぶ(対象が複数あれば
   1つのメッセージ内で並列発行してよい、待つ必要はない)。プロンプトは
   `.claude/skills/audit-drafts/SKILL.md`内の監査プロンプトテンプレート(「このプロジェクト
   固有の仕様」「本当にチェックすべき観点」節を含む全文)をそのまま使い、「最後に、必ず次の形式で
   結果を出力してください」の直前に次の1文を追加する:

   ```
   この記事は前回、{info.audit_reasonsの内容}という理由で不合格となった。{手順8で行った具体的な修正内容}。
   この修正が正しく反映されているか、他に同種の問題が残っていないかを重点的に確認すること。
   ```

   応答は`audit-drafts`と同じ`VERDICT: passed=<true|false>` / `REASONS: ...`形式でパースする。
   パースできない場合は安全側に倒し`passed=false`として扱う。

10. **結果の反映**: 再監査に合格した対象は、`note_status.json`の該当エントリを
    `audit_passed: true`, `audit_reasons: []`, `audit_at: <実行時刻>` に更新する。
    再監査でも不合格だった場合は、その新しい理由を元に手順7〜9を**最大2回まで**繰り返す。
    それでも合格しない対象はスキップし、最終報告で「未解決」として明示する(無理に公開しない)。

11. **公開**: 合格した対象が1件以上あれば、`.venv/bin/python3`で
    `for-note-post/publish_to_note_free_batch.py`を実行する(このスクリプトは
    `audit_passed is True`かつ未公開のものだけを自動的に対象にするゲートを内部に持っている)。

### パート3: 仕上げ

12. **Gitへの記録**: 変更したコード・`note_status.json`・`LEARNINGS.md`・(誤検知修正時のみ)
    `audit-drafts/SKILL.md`・公開済みアーカイブファイル(`for-note-post/output/archive_published/`)
    をまとめてcommit・pushする(X投稿側の`run_today_pipeline_partb.py`は既に自分でcommit・pushして
    いるので、ここでは残っている変更分だけがコミットされる形になる。このプロジェクトはパイプライン
    スクリプト自身が自動でgit同期する設計であり、この修正サイクルも同じ運用に含める)。

13. **通知**: 以下のように`scripts/notify_daily_result.py`内の既存のDiscord通知関数を再利用し、
    ログファイルからではなく今回の実行結果から組み立てたレポート文字列を渡して通知する
    (2026-10-24にNotepad自動起動機能はユーザーの要望で削除済み、Discordのみ):

    ```python
    import sys, os
    sys.path.insert(0, "/home/uk/Vault/curator-copy/scripts")
    from notify_daily_result import load_env_file, post_to_discord, ENV_FILE

    env = load_env_file(ENV_FILE)
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or env.get("DISCORD_WEBHOOK_URL")

    report_text = """📅 curator-copy 日次サイクル完了処理
    (ここに: X投稿側の結果(予約件数/未解決理由)、note.com側の結果(対象件数・分類ごとの件数(a/b/c)・
    公開件数・未解決件数)を日本語で簡潔にまとめて埋め込む)
    """

    post_to_discord(webhook_url, report_text)
    ```

14. 最後に、日本語でサマリーを報告する(X投稿: 予約件数/未解決理由の有無、note.com: 対象件数・
    分類ごとの件数(a/b/c)・公開件数・未解決件数)。**X投稿側がCookie期限切れ等のユーザー対応待ちで
    未解決の場合は、それを目立つ形で明示すること**(「全て完了」と誤って報告しない)。

## 注意

- 検出器のコード修正(手順8-a)は3ファイル(`autogenerate_note_article.py` / `_2.py` /
  `generate_note_article.py`)に必ず同時適用すること。1ファイルだけ直すと、次回別の生成ルートで
  同じ問題が再発する(実例あり)。
- 公開(`publish_to_note_free_batch.py`)・X投稿予約(`run_today_pipeline_partb.py`経由の
  `socialdog_poster.py`)はどちらもブラウザを実際に操作して外部サービスに投稿する、外部に見える
  操作。実行前に対象が本当に処理可能な状態か(note.com側は手順10、X側は認証状態)を確認すること。
- Discord通知・Git pushはどちらも外部に見える/届く操作だが、このプロジェクトは元々パイプライン
  スクリプト自身がこれらを無人で行う設計(`daily_auto_run.sh`等)であり、この修正サイクルもその
  運用の延長として扱う。
- X投稿側のCookie/セッション切れは**このSkillの権限では直接解決できない**。ユーザーに
  ブラウザでの再ログイン・cookie-editorでの取得・ファイル配置を依頼すること。代わりに推測で
  ログイン処理を自動化しようとしないこと(認証情報の扱いに関わるため)。
- `.claude/workflows/`配下の`.js`ファイルは使われていない(存在しない`Workflow`ツールを前提に
  した設計の名残)。参照しないこと。存在しないツールを探して独自の代替処理を即興で作ったりしないこと。
