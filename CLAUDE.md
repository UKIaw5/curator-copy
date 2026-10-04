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
  → (手動確認) → 予約投稿 (automation/socialdog_poster.py, CloakBrowser経由でSocialDogのUIを操作)
  → archive + Git同期
```

note.com向けには `for-note-post/` 配下に独立した並行パイプライン(記事生成→公開)がある。

重複排除は `output/history.json`(公開済みURL)と `output/seen_urls.json`(Stage1処理済みURL)で行う。
どちらも更新直前に `.bak` を作成し、`run_today_pipeline_parta_rb.py` でロールバックできる。

Stage1の複数要約は `<<<CURATOR_ITEM_BOUNDARY>>>` という専用トークンで連結・分割している(`generate_x_posts.py`で書き込み、`run_today_pipeline_parta.py`等で読み込み)。**`---`のような自然言語に出現しうる文字列を区切りに使わないこと** — Qwenが要約本文の末尾に`---`区切りの「Source:」フッターを自然に出力し、1件の要約が誤って2分割された実例がある(空の断片をGemmaが別内容で「捏造」し、無関係なURLに紐付けて投稿する事故につながった)。

`output/raw/`には2026-10-04より前に生成された、旧形式(`---`区切り)の生データファイルが現存している(18件)。これらを読む箇所は全て新トークンが見つからない場合に旧形式へフォールバックする`split_raw_items`相当のロジックを持つ(新トークンのみで分割すると、旧ファイル全体が1件の要約として誤認識され、無関係な複数記事の内容が混入する事故が実際に発生した)。

## 2. ディレクトリ構成

| ディレクトリ | 役割 |
|---|---|
| `fetchers/` | ソース別の取得処理。`arxiv.py`, `hacker_news.py`, `github_trending.py`, `huggingface.py`。`arxiv.py`は2026-10-04に検索API(`export.arxiv.org/api/query`)方式へ変更済み(旧: 日次RSSフィードで土日は`skipDays`のため0件になっていた)。投稿日の新しい順に`limit`件(デフォルト15)を取得するため、土日でも直前の配信日まで自動的に遡る |
| `generators/` | `curator.py`(Qwenで上位記事を選別) / `generate_x_posts.py`(Stage1: Qwenで英語詳細要約) / `refiner.py`(Stage2: Gemmaで日本語Xポストに精製) / `reviewer.py`(Stage3: Qwenによる校正。`run_today_pipeline_parta.py`から呼ばれる本番ステージ) |
| `automation/` | `socialdog_poster.py`(本番の予約投稿経路。SocialDogのWeb UIをCloakBrowserで操作し、正規のEnterprise API経由でXに投稿。2026-10-04導入) / `x_poster.py`(旧経路。Xに直接CloakBrowserで予約投稿、Bot検知警告が出るため現在は未使用・参考用に残置) / `import_cookies.py`(X用、cookie-editorで取得したcookieをPlaywright用に変換) / `save_session.py` |
| `for-note-post/` | note.com向けの記事生成(`generate_note_article.py`, `autogenerate_note_article*.py`)・画像生成(`generate_eyecatch.py`)・公開(`publish_to_note*.py`)。Xパイプラインとは別のモデル割り当て・状態管理(`note_status.json`)を持つ独立系 |
| `output/` | `raw/`(Stage1出力) / ルート直下(Stage2出力、未投稿) / `archive/`(投稿済みファイル) / `history.json`, `seen_urls.json`(重複排除用履歴) / `dry_run/`(検証用サンドボックス、gitignore対象、8章参照) |
| `tests/` | CloakBrowser動作確認・Stage2/4の手動再実行用アドホックスクリプト中心。CIで網羅的に走る正式なテストスイートではない |

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

X用cookie取得(旧経路・現在未使用): ブラウザ拡張「cookie-editor」でログイン状態のcookieを取得 → `cookies.json`として配置
→ `python3 automation/import_cookies.py` で一度だけ変換(Playwright用contextとして`x_user_data/`に保存)。

SocialDog用cookie取得(現在の本番経路): cookie-editorで`web.social-dog.net`のcookieを取得し、
`automation/socialdog_cookies.json`としてそのまま配置するだけ(変換スクリプト不要、`socialdog_poster.py`が
実行時に直接読み込む)。セッション有効期限(`expirationDate`)が切れたら取り直すこと。

## 4. LLM / Ollama 構成(現状のベースライン・変更対象)

Ollamaがローカルで起動している前提(`http://localhost:11434`)。

| 用途 | 呼び出し元 | デフォルトモデル | 環境変数 |
|---|---|---|---|
| 記事選別(キュレーション) | `generators/curator.py` | `qwen3.8:27b` | `QWEN_MODEL` |
| Stage1 詳細要約(英語) | `generators/generate_x_posts.py` | `qwen3.8:27b`(旧: `qwen2.5-coder:14b`) | `QWEN_MODEL` |
| Stage2 投稿文精製(日本語) | `generators/refiner.py` | `gemma4:12b` | `GEMMA_MODEL` |
| 主語補完(Gemma出力の救済) | `generators/refiner.py` | `qwen2.5-coder:14b` | `QWEN_MODEL` |
| 日本語フォールバック圧縮(最終救済) | `generators/refiner.py` (`generate_safe_japanese_fallback`) | `qwen2.5-coder:14b` | `QWEN_MODEL` |
| Stage3 投稿文の校正 | `generators/reviewer.py` | `gemma4:12b` | `GEMMA_REVIEWER_MODEL` |
| note記事生成(TOC/本文/校正/フック/インサイト/リンク) | `for-note-post/*.py` | すべて `qwen2.5-coder:14b` or `gemma4:12b` 固定(環境変数非対応、コード内直書き)。`think: False`適用済み、Xパイプラインと同様に日本語チェックも導入済み(2026-10-04) | なし |

**注意:** `curator.py`と`generate_x_posts.py`は`qwen3.8:27b`、`refiner.py`の補助呼び出し(主語補完・フォールバック)は`qwen2.5-coder:14b`。同じ`QWEN_MODEL`環境変数を複数箇所で共有しているため、環境変数で上書きすると全箇所に影響する。モデルを個別に変えたい場合は環境変数を分けるかコードを直接変更する必要がある。

**Stage1を`qwen2.5-coder:14b`→`qwen3.8:27b`に変更した理由(2026-10-04):** 同一記事で比較したところ、`qwen2.5-coder:14b`(コード特化モデル)は元データに存在しない技術詳細(例: 存在しないNode.jsバックエンドの記述)を自信満々に書く、いわゆるハルシネーション傾向が見られた。`qwen3.8:27b`は「公開情報にこの詳細は含まれていない」と明記するなど、不確かな情報を補完せず誠実に書く傾向があり、要約の正確性を優先してこちらを採用した。**代償として処理時間が約4倍(1件あたり約30秒→約130秒)** になっている。日次バッチの実行時間が問題になる場合は、ここが再検討対象になる。

**⚠️ 思考(reasoning)モデルを使う場合は必ず`"think": False`をペイロードに付けること。** `qwen3.8:27b`や`gemma4:12b`はOllama上で内部思考トレース(`thinking`/`reasoning`フィールド)を出力する設定になっており、`think`を指定しないと`num_predict`の枠を思考だけで使い切り、本来の出力(`content`/`response`)が空文字・尻切れになる(`finish_reason/done_reason: "length"`で判別できる)。本プロジェクトでは2026-10-04に`curator.py`(AI選別が常にフォールバック)・`refiner.py`(リトライ多発)・`reviewer.py`(校正が常に空)の3箇所でこれが実際に発生し、全箇所に`think: False`を追加して解決した。**新しいOllama呼び出しを追加する際は、まずそのモデルがthinking対応かどうかを`curl http://localhost:11434/api/tags`等で確認し、思考トレースの有無を疑うこと。**

モデル/プロンプトを変更したら、この表を更新すること。

## 5. 設計上の注意点

### 変えてよい(品質改善の実験対象)
- Xポストの文字数判定: `refiner.py`の`60 <= effective_len <= 135`、`reviewer.py`の`50〜135`。URL有りの場合は実効文字数に+25文字加算(`get_x_effective_length`)
- `refiner.py`のプロンプト文言。2026-10-04に、固定の煽り文句プール(`RAW_HOOK_POOL`/`RAW_CLOSING_POOL`/`RAW_EMOJI_POOL`、全投稿が「が熱い」「が凄すぎる」等の同じ表現になる原因だった)を廃止し、「要約内の具体的事実を1つ以上盛り込む」ことを必須化する方式に変更済み。絵文字は任意・モデルが自由に選ぶ方式
- 各段のモデル割り当て(4章参照)、`temperature`, `num_ctx`, `num_predict`などのOllamaオプション
- `curator.py`の`max_select`(選別件数。2026-10-04に8→6へ変更。量より質重視のアカウント運用方針のため、エンゲージメントを見ながら再調整してよい)
- `automation/socialdog_poster.py`の`TARGET_TIME_SLOTS`(狙いたい投稿時間帯)。現状は個人開発者/エンジニア層を想定した仮置き(07:30/09:30/12:15/15:30/19:00/22:00)。実際のエンゲージメントデータを見て調整すべき対象

### 変えると実害が出る(慎重に扱う)
- `automation/x_poster.py`のBot検知回避ロジック(現在は未使用の旧経路だが、参考用に残置。復活させる場合は要注意):
  - 予約投稿機能を使い、投稿間隔は「3時間 ± 40分のゆらぎ」で分散させる(機械的な規則性を避ける)
  - テキスト入力はキー1文字ずつではなく`page.keyboard.insert_text`で貼り付け相当の操作をする
  - スケジュールモーダルのクリックは通常クリックが弾かれるため`evaluate("node => node.click()")`でJS経由の強制クリックを使う
  - ドロップダウン要素は非表示スタイルのため`state="attached"`で待機する(`state="visible"`では失敗する)
  - これらを安易に「効率化」すると、Xのシャドウバン/アカウントロックのリスクが上がる。変更する場合は意図を理解した上で行うこと
- `automation/socialdog_poster.py`のセレクタ。全て実際のDevTools検証済み: 投稿欄は`<textarea placeholder="投稿内容を入力">`(本物のplaceholder属性、contenteditableではない)、日時ピッカーは`.datetime_picker_blueprint .bp3-popover-target`で開き、中の`aria-label="日付"`なBlueprint.js DateInput(`YYYY/MM/DD H:mm`形式)に直接文字列を入力するだけでよい(カレンダー日付セルや時/分スピンボックスの個別操作は不要)。SocialDog側のUI更新で壊れた場合は同じ手順(DevToolsでElementsパネルをスクショ)で再特定すること
- `output/history.json` / `seen_urls.json`の重複排除ロジックと`.bak`によるロールバック機構(壊すと同じ記事が再投稿される恐れ)
- Stage1要約の連結・分割に使う`<<<CURATOR_ITEM_BOUNDARY>>>`境界トークン(1章参照)。`---`等の自然言語に出現しうる文字列に戻さないこと。**`for-note-post/generate_note_article.py`・`autogenerate_note_article.py`・`autogenerate_note_article_2.py`の`get_active_raw_file()`も同じ生データファイルをこのトークンで分割している** — Stage1側のdelimiterを変更したら必ずこの3ファイルも同時に直すこと(2026-10-04に一度ズレて修正済み)
- Ollama呼び出しの`"think": False`指定(4章参照)。外したり新しい呼び出しで付け忘れると、該当ステージが静かに機能不全になる(エラーは出ず、ただ空文字が返るだけなので発見しづらい)
- note.com記事生成の各LLMステップの日本語チェック(`is_japanese_text`、`for-note-post/*.py`)。実データで校正ステップが記事全文を英訳してしまう事例を確認済み。外すと英語の記事がそのまま本文になるリスクがある
- `for-note-post/publish_to_note*.py`のタイトル行除去。位置ベース(先頭行のみ除去)で実装すること。文字列一致(`str.replace(title, "")`等)に戻すと、タイトルと同じ文言が本文中に再出現した箇所まで誤って消えるバグが再発する
- `for-note-post/*.py`の`call_llm`内`REFUSAL_MARKERS`。モデルが「データが空/不十分」と判断した際、Qwen系は英語で("Please provide...")、Gemma系は**日本語で**("申し訳ございません...")拒否することを実例で確認済み。英語パターンだけに戻すと、日本語の拒否文がそのまま記事本文として使われてしまう

## 6. 認証情報の取り扱い

以下は**絶対にコミットしない**(`.gitignore`で除外済み):
- `cookies.json`, `automation/cookies.json`, `x_user_data/`(X用セッション、旧経路)
- `for-note-post/note_cookies.json`, `note_cookies.json`(note.com用セッション)
- `automation/socialdog_cookies.json`, `socialdog_cookies.json`, `automation/socialdog_user_data/`(SocialDog用セッション、現在の本番経路)

## 7. その他

- Gitへの自動コミット/プッシュをパイプラインスクリプト自身が行う(`run_today_pipeline_parta.py`の`git pull`、`partb*.py`の`git add/commit/push`)。手動での変更作業中に自動実行すると競合する可能性があるので注意
- `tests/`配下はCloakBrowserのステルス機能検証や履行移行(`test_migrate_history.py`)用のアドホックスクリプトが中心で、CIでの網羅的なテストスイートではない

## 8. 動作検証・デバッグ時の運用ルール

**本番の状態ファイル(`output/raw/seen_urls.json`, `output/history.json`)や本番の出力先(`output/`, `output/raw/`)を、動作確認のためだけに汚さないこと。** 過去に実データでPart Aを検証目的で直接実行し、`seen_urls.json`に試験的に処理したURLが書き込まれてしまい、本番運用に使えるよう手動で巻き戻す対応が必要になったことがある。

- **Part Aの動作確認には必ず`python3 run_today_pipeline_parta.py --dry-run`を使うこと。** 出力は`output/dry_run/`(gitignore対象)に隔離され、`seen_urls.json`等の本番履歴ファイルには一切書き込まれない。Part B/`x_poster.py`は`output/`直下しかglobしないため、dry-runの出力が誤って投稿されることもない
- **note.com側(`generate_note_article.py`, `autogenerate_note_article.py`, `autogenerate_note_article_2.py`)の動作確認にも`--dry-run`を使うこと。** 出力は`for-note-post/output/dry_run/`に隔離され、`note_status.json`・本番の生データアーカイブ移動には一切影響しない。バッチ版(`autogenerate_*`)は1件処理したら自動的に停止する
- これらのスクリプトは`playwright`に依存するため、**システムのpython3ではなく`.venv/bin/python3`(または`source .venv/bin/activate`後)で実行すること**。system pythonには`playwright`が入っていない
- 確認が終わったら各`output/dry_run/`は削除してよい(gitignoreされているため残しても実害はないが、紛れるので消すほうが安全)
- `generators/`配下の個々の関数(`refine_to_x_post`, `review_and_edit_post`, `generate_detailed_summary`等)を単体で素のPythonから直接呼ぶ検証は、ファイルへの書き込みが発生しないため安全(このセッションでもバグ調査に多用した)
- 新しくファイル書き込み・履歴更新を伴うステージを追加する場合は、同じく`--dry-run`で書き込み先を切り替えられるようにしておくこと
