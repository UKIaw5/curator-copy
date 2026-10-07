---
name: refine-x-posts
description: Part A(Stage1)が生成した英語詳細要約を、Claudeが直接日本語のXポスト本文に精製する(Gemma refiner/reviewerの代替、本番経路)
---

このSkillは、curator-copyプロジェクトのXポスト生成パイプラインにおける「Stage2+3(精製・校正)」を、Gemma/Qwenのローカルモデルの代わりにClaude自身が行う。

## 手順

1. `output/raw/output_prex_posts_*.md` を新しい順に並べ、各候補について以下をチェックし、**最初に見つかった「まだ精製されていない」ファイル**を対象とする:
   - `output/output_x_posts_<timestamp>.md` が存在しない
   - かつ `output/archive/output_x_posts_<timestamp>.md` も存在しない
   (`<timestamp>` は raw ファイル名の `output_prex_posts_` と `.md` を除いた部分。この判定ロジックは `run_today_pipeline_parta.py` の `get_pending_raw_info()` と同じもの)
2. 対象が無ければ「精製対象なし」と報告して終了する。
3. 対象のraw fileを読み、区切りトークン`<<<CURATOR_ITEM_BOUNDARY>>>`で分割する(見つからない場合のみ`"---"`区切りの旧形式として扱う)。分割後の要素数を `N` とする。
4. `raw_path` を対象ファイルの絶対パスとして、`[{idx: 0, raw_path}, {idx: 1, raw_path}, ..., {idx: N-1, raw_path}]` の配列を作る。
5. `Workflow` ツールを `scriptPath: "/home/uk/Vault/curator-copy/.claude/workflows/refine-x-posts.js"` で呼び、上記配列を `args` として渡す(1回のWorkflow呼び出しで全件まとめてよい、内部で並列実行される)。
6. Workflowの結果(`[{idx, body_text, url}, ...]`)を `idx` の昇順に並べ替える。各要素について:
   - `effective_length = len(body_text) + (25 if url else 0)` を計算する。
   - `effective_length` が135を超える場合、句点(。！？)の位置で切り詰める(文の途中で不自然に切れないように、末尾から最も近い句点までを残す。適切な句点が見つからない場合のみ文字単位で切り、末尾に"..."を付ける)。
   - `effective_length` が60未満、または`body_text`が空、または日本語の文字(ひらがな・カタカナ・漢字)が明らかに少ない場合は、その項目だけ警告として記録する(全体の処理は止めない)。
7. 各要素を `{body_text}\n\n{url}` の形式(urlが空文字の場合は`{body_text}`のみ)に組み立て、`\n\n---\n\n` で連結して1つのテキストにする。`run_today_pipeline_parta.py`が従来`refine_to_x_post`+`review_and_edit_post`で書いていた`output/output_x_posts_<timestamp>.md`と同じ形式・同じパスに保存する。
8. 最後に、件数・各件の実効文字数・警告があった項目を日本語で簡潔に報告する。

## 注意

- `output_x_posts_<timestamp>.md`の読み書きは直接Pythonで行ってよい(このSkill自体はPythonスクリプトではなく、Claude自身がこの手順に従ってファイル操作とWorkflow呼び出しを行う)。
- このSkillは`run_today_pipeline_parta.py`のStage2(`generators/refiner.py`)・Stage3(`generators/reviewer.py`)を本番経路から置き換えるものである。`refiner.py`/`reviewer.py`自体は削除せず、手動比較・検証用に残してある。
- 区切りトークン`<<<CURATOR_ITEM_BOUNDARY>>>`を変更する場合は、`run_today_pipeline_parta.py`・note.com側の3ファイル(`for-note-post/generate_note_article.py`等)に加えて、この`refine-x-posts.js`内のプロンプトも同時に直すこと(CLAUDE.md参照)。
- 出力ファイル名(タイムスタンプ)は対象raw fileの命名規則(`output_prex_posts_<timestamp>.md` → `output_x_posts_<timestamp>.md`)に正確に合わせること。ずれると`run_today_pipeline_partb.py`/`automation/socialdog_poster.py`がファイルを見つけられない。
