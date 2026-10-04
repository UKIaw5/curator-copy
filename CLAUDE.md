# curator-copy

AI技術トレンド(arXiv / Hacker News / GitHub Trending / Hugging Face Papers)を自動収集し、
ローカルLLM(Ollama)で要約・日本語ポストに変換して、X(Twitter)とnote.comに自動投稿する
コンテンツ生成パイプライン。

> **現在、出力品質の改善作業中。** モデル構成・プロンプト・文字数制約などは実験的に変更され続ける。
> このファイルは「今の設定を固定するルール」ではなく「現状と設計意図を伝える地図」。
> モデルやロジックを変えたら、該当セクション(4, 5)も一緒に更新すること。

## 1. 全体のデータフロー

```
fetch (fetchers/)
  → curate 選別 (generators/curator.py)
  → Stage1 詳細要約・英語 (generators/generate_x_posts.py)   → output/raw/output_prex_posts_*.md
  → Stage2 Xポスト精製・日本語 (generators/refiner.py)        → output/output_x_posts_*.md
  → (手動確認) → 予約投稿 (automation/x_poster.py, CloakBrowser)
  → archive + Git同期
```

note.com向けには `for-note-post/` 配下に独立した並行パイプライン(記事生成→公開)がある。

重複排除は `output/history.json`(公開済みURL)と `output/seen_urls.json`(Stage1処理済みURL)で行う。
どちらも更新直前に `.bak` を作成し、`run_today_pipeline_parta_rb.py` でロールバックできる。

## 2. ディレクトリ構成

| ディレクトリ | 役割 |
|---|---|
| `fetchers/` | ソース別の取得処理。`arxiv.py`, `hacker_news.py`, `github_trending.py`, `huggingface.py` (`fetch_*.py` という別名ファイルは旧版/重複、使用箇所を要確認) |
| `generators/` | `curator.py`(Qwenで上位記事を選別) / `generate_x_posts.py`(Stage1: Qwenで英語詳細要約) / `refiner.py`(Stage2: Gemmaで日本語Xポストに精製) / `reviewer.py`(Gemmaによる校正、現状どこから呼ばれているか要確認) |
| `automation/` | `x_poster.py`(CloakBrowserでXに予約投稿) / `import_cookies.py`(cookie-editorで取得したcookieをPlaywright用に変換) / `save_session.py` |
| `for-note-post/` | note.com向けの記事生成(`generate_note_article.py`, `autogenerate_note_article*.py`)・画像生成(`generate_eyecatch.py`)・公開(`publish_to_note*.py`)。Xパイプラインとは別のモデル割り当て・状態管理(`note_status.json`)を持つ独立系 |
| `output/` | `raw/`(Stage1出力) / ルート直下(Stage2出力、未投稿) / `archive/`(投稿済みファイル) / `history.json`, `seen_urls.json`(重複排除用履歴) |
| `tests/` | pytest(`tests/pytest/`)・CloakBrowser関連の動作確認スクリプト |

## 3. 実行コマンド(日常運用)

```bash
# 初回環境構築
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install

# 日次パイプライン
python3 run_today_pipeline_parta.py          # Step1-4: 収集→選別→要約→Xポスト精製
# (ここで output/output_x_posts_*.md の内容を目視確認)
python3 run_today_pipeline_partb.py          # Xに予約投稿 → Git push
python3 run_today_pipeline_partb_manual.py   # 手動投稿後のアーカイブ&Git同期のみ行う場合

# 直前の Part A 実行を取り消したい場合
python3 run_today_pipeline_parta_rb.py

# note.com投稿
cd for-note-post
python3 generate_note_article.py        # または autogenerate_note_article.py / _2.py
python3 publish_to_note.py              # または publish_to_note_batch.py / publish_to_note_free_batch.py
```

X用cookie取得: ブラウザ拡張「cookie-editor」でログイン状態のcookieを取得 → `cookies.json`として配置
→ `python3 automation/import_cookies.py` で一度だけ変換(Playwright用contextとして`x_user_data/`に保存)。

## 4. LLM / Ollama 構成(現状のベースライン・変更対象)

Ollamaがローカルで起動している前提(`http://localhost:11434`)。

| 用途 | 呼び出し元 | デフォルトモデル | 環境変数 |
|---|---|---|---|
| 記事選別(キュレーション) | `generators/curator.py` | `qwen3.8:27b` | `QWEN_MODEL` |
| Stage1 詳細要約(英語) | `generators/generate_x_posts.py` | `qwen2.5-coder:14b` | `QWEN_MODEL` |
| Stage2 投稿文精製(日本語) | `generators/refiner.py` | `gemma4:12b` | `GEMMA_MODEL` |
| 主語補完(Gemma出力の救済) | `generators/refiner.py` | `qwen2.5-coder:14b` | `QWEN_MODEL` |
| 投稿文の校正(未結線の可能性あり) | `generators/reviewer.py` | `gemma4:12b` | `GEMMA_REVIEWER_MODEL` |
| note記事生成(TOC/本文/校正/フック/インサイト/リンク) | `for-note-post/*.py` | すべて `qwen2.5-coder:14b` or `gemma4:12b` 固定(環境変数非対応、コード内直書き) | なし |

**注意:** `curator.py`のQwenデフォルトだけ`qwen3.8:27b`で、他は`qwen2.5-coder:14b`。同じ`QWEN_MODEL`変数を共有しているため、環境変数で上書きすると全箇所に影響する。モデルを個別に変えたい場合は環境変数を分けるかコードを直接変更する必要がある。

モデル/プロンプトを変更したら、この表を更新すること。

## 5. 設計上の注意点

### 変えてよい(品質改善の実験対象)
- Xポストの文字数判定: `refiner.py`の`60 <= effective_len <= 135`、`reviewer.py`の`50〜135`。URL有りの場合は実効文字数に+25文字加算(`get_x_effective_length`)
- `refiner.py`の絵文字/フック/クロージングのプール(`RAW_EMOJI_POOL`等)とプロンプト文言
- 各段のモデル割り当て(4章参照)、`temperature`, `num_ctx`, `num_predict`などのOllamaオプション
- `curator.py`の`max_select`(選別件数)

### 変えると実害が出る(慎重に扱う)
- `automation/x_poster.py`のBot検知回避ロジック:
  - 予約投稿機能を使い、投稿間隔は「3時間 ± 40分のゆらぎ」で分散させる(機械的な規則性を避ける)
  - テキスト入力はキー1文字ずつではなく`page.keyboard.insert_text`で貼り付け相当の操作をする
  - スケジュールモーダルのクリックは通常クリックが弾かれるため`evaluate("node => node.click()")`でJS経由の強制クリックを使う
  - ドロップダウン要素は非表示スタイルのため`state="attached"`で待機する(`state="visible"`では失敗する)
  - これらを安易に「効率化」すると、Xのシャドウバン/アカウントロックのリスクが上がる。変更する場合は意図を理解した上で行うこと
- `output/history.json` / `seen_urls.json`の重複排除ロジックと`.bak`によるロールバック機構(壊すと同じ記事が再投稿される恐れ)

## 6. 認証情報の取り扱い

以下は**絶対にコミットしない**(`.gitignore`で除外済みのものもあるが要確認):
- `cookies.json`, `automation/cookies.json`, `x_user_data/`(X用セッション)
- `for-note-post/note_cookies.json`(note.com用セッション)

> ⚠️ **既知の問題:** `for-note-post/note_cookies.json`は現在git管理下に入っている(`.gitignore`は`cookies.json`のみを除外しており`note_cookies.json`は対象外)。認証情報が含まれる可能性があるため、`git rm --cached`と`.gitignore`追記での対応が別途必要。

## 7. その他

- Gitへの自動コミット/プッシュをパイプラインスクリプト自身が行う(`run_today_pipeline_parta.py`の`git pull`、`partb*.py`の`git add/commit/push`)。手動での変更作業中に自動実行すると競合する可能性があるので注意
- `tests/`配下はCloakBrowserのステルス機能検証や履行移行(`test_migrate_history.py`)用のアドホックスクリプトが中心で、CIでの網羅的なテストスイートではない
