---
name: audit-drafts
description: note.com向けに生成済みだが未監査の下書き記事を、公開前にハルシネーション/日本語品質/フォーマット崩れの観点で監査し、結果をnote_status.jsonに記録する
---

このSkillは、curator-copyプロジェクトのnote.com記事パイプラインにおける「公開前監査」を実行する。

## 手順

1. `/home/uk/Vault/curator-copy/for-note-post/note_status.json` を読む。
2. 各エントリ(`raw_file`, `idx`, `info`)について、以下の条件を満たすものを「監査対象」とする:
   - `info.generated_file` が存在し、そのファイルが実際にディスク上に存在する
   - `info.published_to_note` が `true` ではない(まだ未投稿)
   - `info.audit_passed` キーが存在しない(まだ監査していない)
3. 監査対象が0件なら「監査対象なし」と報告して終了する。
4. 各対象について、`info.generated_file` のbasenameを `id`、`info.generated_file` の絶対パスを `generated_path`、対応する `raw_file` を `output/raw/<raw_file>` に解決した絶対パスを `raw_path`、`idx` を整数化したものを `idx` として、`{id, generated_path, raw_path, idx}` の配列を作る。
   - `raw_path` が存在しない場合はその項目をスキップし、後で報告する(生データが削除済みの古いバックログ等)。
5. `Workflow` ツールを `scriptPath: "/home/uk/Vault/curator-copy/.claude/workflows/audit-note-drafts.js"` で呼び、上記配列を `args` として渡す。一度に渡す件数が多い場合も1回のWorkflow呼び出しでまとめてよい(内部で並列実行される)。
6. Workflowの結果(`[{id, verdict: {passed, hallucination_found, japanese_quality_ok, format_ok, reasons}}, ...]`)を受け取ったら、各 `id` に対応する `note_status.json` のエントリに以下を書き込んで保存する:
   - `audit_passed`: `verdict.passed`
   - `audit_reasons`: `verdict.reasons`
   - `audit_at`: 実行時刻(分かる範囲で)
7. 最後に、合格/不合格の件数と、不合格だった記事のタイトル・理由を日本語で簡潔に報告する。不合格のものは`publish_to_note_batch.py` / `publish_to_note_free_batch.py` 側のゲート(`audit_passed is True` のみ処理対象)によって自動的に公開対象から除外されるため、人間が個別に修正するか、生成しなおすかを判断してもらう。

## 注意

- `note_status.json` の読み書きは直接Pythonで行ってよい(このSkill自体はPythonスクリプトではなく、Claude自身がこの手順に従って都度ファイル操作とWorkflow呼び出しを行う)。
- 監査プロンプト(`audit-note-drafts.js`内)には、`<!-- PAYWALL -->`マーカー・ペイウォール・クリフハンガー(文末の「なぜなら——」)・末尾ハッシュタグが意図的な仕様であることが明記されているので、これらを理由にした不合格判定は誤検知の可能性が高い。もし新しい誤検知パターンが見つかったら、`audit-note-drafts.js`のプロンプトに追記して仕様を教えること。
