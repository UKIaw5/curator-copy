# 引き継ぎ — 次にやることは、ここだけ読めば分かる

セッションを切り替えるときの**唯一の入り口**。

- **このファイルは毎回上書きする。** 履歴は残さない
- **「次にやること」の出所はここ 1 箇所。** `CLAUDE.md` や `LEARNINGS.md` に同じ話を書き足さない
- 不変のルール・設計意図・地雷の詳細は `CLAUDE.md`、失敗の記録は `LEARNINGS.md`(月次で `LEARNINGS_YYYY-MM.md` に退避)

| | |
|---|---|
| 最終更新 | 2026-11-22 |
| 直前のセッション | 公式版 Orca から fork 版 Orca(orca-dev)へ乗せ換える準備。この引継ぎ書を main 基準で新規作成しただけ(コード変更なし)。直前のコード作業は `/cycle` による 11/22 の note.com 監査不合格 2 件(固有名詞の誤字)の修正と公開(`1ddc824`) |
| ブランチ | **`main`**(本体: `/home/uk/Vault/curator-copy`、HEAD `1ddc824`)が正。`origin/main` と一致(差 0、未 push なし)。この worktree `UKIaw5/encantado`(`/home/uk/orca/workspaces/curator-copy/encantado`)も同じ `1ddc824` で、main との差は 0。他の worktree は無い |
| 作業ツリー | `scripts/daily_auto_run.sh` の**実行権限だけ**が変わっている(100755 → 100644、中身の差分は 0)。この `docs/handoff.md` は未追跡。他に未追跡ファイルは無し |

---

## 0. 始める前に(3 つだけ)

1. **`main` が最新。** 作業は main(または main から切ったブランチ)で始める。
   `git log --oneline -3` で `1ddc824` が先頭であることを確認する(日次の自動実行が `Auto: Update ...` コミットを積むので、
   時間が経っていれば先頭は進んでいる。その場合は `git pull` してから)
2. **日次パイプラインは自動でコミット/push する**(`run_today_pipeline_parta.py` の `git pull`、`partb*.py` の `git add/commit/push`。
   `CLAUDE.md` 7 章)。手作業の変更中に自動実行が走ると競合する。毎日 11:00 が自動実行の時刻
3. **新しい worktree には `.venv`・`.env`・各種 cookie が無い**(すべて gitignore 対象で、`git worktree add` では付いてこない)。
   この worktree もそうなっている。パイプラインを動かす・動作確認するなら、これらが揃っている本体 `/home/uk/Vault/curator-copy`
   (`.venv` あり)で行う。秘密の値はこのファイルにも書かない

---

## 1. いま立っている場所

AI 技術トレンド(arXiv / Hacker News / GitHub Trending / Hugging Face Papers)を自動収集し、ローカル LLM(Ollama)と Claude で
要約・日本語化して、X(SocialDog 経由の予約投稿)と note.com に自動投稿するパイプライン。**出力品質の改善作業中**(`CLAUDE.md` 冒頭)。

| | 状態 |
|---|---|
| 日次の自動実行 | Windows タスクスケジューラ `CuratorCopyDailyAutoRun`(毎日 11:00、`wsl.exe` 経由で `scripts/daily_auto_run.sh`)。Part A → note.com 記事生成 → `/audit-drafts` + `/refine-x-posts` → note.com 公開 → X 予約 → Discord 通知。`CLAUDE.md` 7 章 |
| Cookie 期限の監視 | タスク `CuratorCopyCookieExpiryCheck`(毎日 12:00)。SocialDog の Cookie が 2 日以内に切れるときだけ Discord へ警告 |
| 直近の運用 | 2026-11-22 の `/cycle` で note.com の監査不合格 2 件(固有名詞の誤字)を修正し、両方公開済み(`1ddc824`)。この時点で未完了として把握しているものは無い |
| モデル構成 | Stage1・選別は Ollama `qwen3.8:27b`、Stage2+3(X ポスト精製)は Claude Sonnet(`.claude/skills/refine-x-posts/`)、note 監査は Claude Sonnet(`audit-drafts`)。詳細は `CLAUDE.md` 4 章 |
| セッション Cookie | SocialDog(`automation/socialdog_cookies.json`)・note.com(`for-note-post/note_cookies.json` と常駐プロファイル)。有効期限は**このファイルでは未確認**(ファイルが無い worktree から見ているため) |
| テスト | 網羅的なテストスイートは無い(`tests/` はアドホックなスクリプト中心、`CLAUDE.md` 7 章) |
| リモート | `origin` = `git@github.com:UKIaw5/curator-copy.git`(自分のリポジトリ、SSH)。`main` は `origin/main` と一致 |

---

## 2. 次にやること(優先順)

### A. このプロジェクトを fork 版 Orca に登録して動くことを確認する

下の「fork 版での違い」の手順を実施する。

- **完了条件**: fork 版でプロジェクトが開け、worktree が一覧に出て、エージェントを 1 つ起動して
  `git status` と `git worktree list` が返る(返らないときは §3 の「dubious ownership」を疑う)

### B. 日次の自動実行が fork 版への移行に影響されないことを確認する

タスクスケジューラの 2 タスクは `wsl.exe` から本体のチェックアウトを直接動かす想定で、Orca 自体には依存しない(はず)。
ただし**タスクが指しているパス・実行ユーザーは、この作業では確認していない**。

- **完了条件**: 2 タスクが指すパスを確認し、fork 版への移行後も翌日 11:00 の実行が通る(Discord の通知が届き、`output/daily_auto_logs/` に新しいログが残る)
- 確認は読み取りのみ(`schtasks.exe /query /v /fo list /tn CuratorCopyDailyAutoRun` など)。タスクを変更・再登録しない
- 実行元が Orca の worktree だった場合は、そこに `.venv`・`.env`・Cookie があるかも確認する(§0-3)

### C. `scripts/daily_auto_run.sh` の実行権限変更の扱いを決める

100755 → 100644 の差分だけが worktree に出ている。WSL のパスを Windows 側の git(UNC 経由)で見ているために出た見かけの差分かもしれないが、
原因は**未確認**。実行権限が実際に落ちているなら、WSL から直接 `./scripts/daily_auto_run.sh` を呼ぶ運用では動かなくなる。

- **完了条件**: 使用者の判断で、元に戻す(`git checkout` ではなく実行権限の復元)/ そのままコミットする / 無視する、のいずれかが決まっている
- 確認なしに戻さない・コミットしない

### D. 日次運用の見張り(毎日)

- Discord の日次レポートを見て、X 予約件数・note.com 公開件数・監査不合格一覧・エラー行を確認する
- 不合格や未投稿が残っていれば `/cycle`(原因調査 → 修正 → 再生成 → 再公開 → Discord 通知)。`CLAUDE.md` 7 章
- **完了条件**: その日の X 予約 6 件・note.com 公開が揃い、監査不合格が 0 件
- Cookie 期限の警告が来たら、cookie-editor で取り直して配置する(`CLAUDE.md` 3 章・6 章)

### E.(保留・経過観察のみ)出力品質の改善

- X のインプレッション低下への対応(2026-10-20 のプロンプト調整、2026-10-25 の Haiku → Sonnet 変更)は**効果が未検証**。
  インプレッションの数値を取得する手段が無く、`TARGET_TIME_SLOTS` の見直しも保留中(`CLAUDE.md` 5 章)
- 2026-11-12・11-15 に足した note 記事生成の強制ルール(訳語統一・見出し `###` 強制・ヘッジ維持)も効果は未検証。
  再発したら `LEARNINGS.md` に追記して経過観察する(3 回記録されたら昇格を提案)
- **完了条件**: なし(問題が再発したときだけ動く)。先回りして変更しない

---

## 3. 踏みやすい地雷

| | |
|---|---|
| **Windows 側の git が WSL のリポジトリを「dubious ownership」で拒否する** | UNC パス(`\\wsl.localhost\Ubuntu\...`)越しに `git` を叩くと `fatal: detected dubious ownership` で止まる。コマンドごとに `git -c safe.directory='*' ...` を付ければ設定を変えずに通る。恒久対応(`git config --global --add safe.directory`)はグローバル設定を触るので、使用者の判断で |
| **自動実行と手作業が衝突する** | 日次パイプラインが `git pull` / `commit` / `push` を自分で行う(11:00 開始)。手作業中は時間帯に注意 |
| **動作確認は `--dry-run`** | 本番の `output/history.json`・`output/raw/seen_urls.json` を汚さない。Part A は `python3 run_today_pipeline_parta.py --dry-run`、note.com 側の 3 スクリプトも `--dry-run`(`CLAUDE.md` 8 章)。システムの `python3` には playwright が無いので `.venv/bin/python3` で |
| **Ollama の思考モデルには `"think": False` が必須** | 付け忘れると空文字が返るだけでエラーが出ない(`CLAUDE.md` 4 章) |
| **無人実行の判定は `isatty()` ではなく `CURATOR_UNATTENDED`** | `daily_auto_run.sh` が `export CURATOR_UNATTENDED=1` を立てる。`isatty()` だけだとタスクスケジューラ下でハングした実例あり(`CLAUDE.md` 5 章) |
| **`has_valid_session_cookie()` はローカルの期限しか見ない** | 新しい Cookie を配置しても反映されないことがある。有効性は実際にアクセスしてログインページへ飛ばされるかで判定する(`CLAUDE.md` 6 章) |
| **Stage1 の区切りは `<<<CURATOR_ITEM_BOUNDARY>>>`** | `---` に戻さない。変えるなら 4 箇所を同時に(`CLAUDE.md` 1 章・5 章) |
| **note.com 公開は `--draft-only` で目視確認してから** | 凝った改善を本番ループにいきなり入れない(`CLAUDE.md` 5 章) |
| **認証情報はコミットしない** | `cookies.json`・`*_user_data/`・`.env` 等は gitignore 済み。pre-commit の `detect-secrets` が効いている(`CLAUDE.md` 6 章)。Cookie ファイルの中身を読まない・貼らない |
| **本家 `stablyai/orca` へ push / PR / Issue を出さない** | fork 版のための作業であり、本家には何も送らない |

---

## 4. 動作確認コマンド

```bash
# 本体(.venv がある場所)で
cd /home/uk/Vault/curator-copy
git status && git log --oneline -3 && git worktree list
git remote -v                                    # origin が UKIaw5/curator-copy のままか

# Ollama(日次パイプラインの前提)
curl -s http://localhost:11434/api/tags | head -c 600

# Part A の動作確認(本番の履歴を汚さない)
.venv/bin/python3 run_today_pipeline_parta.py --dry-run
.venv/bin/python3 for-note-post/generate_note_article.py --dry-run   # 確認後 output/dry_run/ は削除してよい

# 自動実行の結果確認
ls -t output/daily_auto_logs | head -3           # 最新ログ(中身にエラー行が無いか)
.venv/bin/python3 scripts/check_socialdog_cookie_expiry.py --test    # Discord へ強制送信(動作確認用、"[テスト通知]" 付き)
```

`--test` は実際に Discord へ投稿するので、確認が要るときだけ使う。

---

## fork 版での違い(公式版 Orca → orca-dev に乗せ換えるとき)

| | |
|---|---|
| **データ置き場が別** | 公式版 `%APPDATA%\orca`、fork 版 `%APPDATA%\orca-dev`。互いに共有されない。**どちらも手で編集・コピーしない**(読み取りのみ) |
| **Orca アカウント** | fork 版では**再ログインが必要** |
| **API キーなど** | **fork 版に入れ直しが必要**。入れ直す項目(名前だけ。値は書かない・ここにも貼らない): エージェント(Claude Code)のログインまたは API キー、GitHub への認証(`origin` は SSH のため SSH 鍵 / `gh auth status` で確認)、Orca 側のその他の連携・トークン類(公式版の設定画面を見て同じものを拾う) |
| **リポジトリ側の秘密(Orca とは無関係)** | `.env`(`DISCORD_WEBHOOK_URL`、`.env.example` 参照)、`automation/socialdog_cookies.json`、`for-note-post/note_cookies.json`、`for-note-post/note_user_data/`、`automation/socialdog_user_data/`。これらは gitignore 対象で**チェックアウトごとに存在する**。fork 版から**新しい worktree を作った場合は付いてこない**ので、パイプラインを動かすチェックアウトには手で用意する(公式版・本体からコピーするときも、中身を表示・貼り付けしない) |
| **セッション履歴・タブ** | **引き継がれない**。過去の会話・開いていたタブは無い。経緯が要るときは `git log` と `LEARNINGS.md` を見る(このファイルが引継ぎの唯一の入り口) |
| **このプロジェクトの登録し直し** | 下記 |

### プロジェクトを fork 版に登録し直す手順

1. 公式版は**終了させない**(動いたままでよい)。fork 版 Orca(orca-dev)を起動する
2. fork 版でログインし、上の API キーなどを設定する
3. fork 版の「プロジェクトを追加」で、本体のフォルダ `/home/uk/Vault/curator-copy`(Windows からは `\\wsl.localhost\Ubuntu\home\uk\Vault\curator-copy`、`main`)を選ぶ。
   リポジトリは 1 つ。worktree は登録後に fork 版から作る
4. 公式版で作った worktree `/home/uk/orca/workspaces/curator-copy/encantado`(`UKIaw5/encantado`)は Git 側に残っている。
   fork 版の worktree 一覧に出ればそれを使う。出なければ新しく作るか、既存フォルダを指定する(main と同じ `1ddc824` なので古さの心配は無い)
5. 動作確認: エージェントを 1 つ起動し `git status` と `git worktree list` が返ること(Windows 側の git で `dubious ownership` が出たら §3)
6. `git remote -v` が `UKIaw5/curator-copy` のままで、本家 `stablyai/orca` を向いていないことを確認する
7. 日次の自動実行(タスクスケジューラの 2 タスク)は触らない。移行後に指しているパスが変わっていないことだけ確認する(§2-B)
