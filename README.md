# curator-copy

> An autonomous content pipeline that collects AI/tech trends (arXiv, Hacker News, GitHub Trending, Hugging Face), summarizes them with local LLMs via Ollama, and publishes curated Japanese posts to X and note.com — with an AI-driven pre-publish audit gate and a rotating human-in-the-loop safety net. Built as a human–AI pair-programming project (see "AIとの協業について" below).

AI技術トレンド(arXiv / Hacker News / GitHub Trending / Hugging Face Papers)を自動収集し、ローカルLLM(Ollama)で要約・日本語コンテンツに変換して、X(Twitter)とnote.comに自動投稿する個人開発のコンテンツパイプラインです。

## これは何か

- 毎日決まった時刻に、複数ソースから最新のAI関連トレンドを自動収集
- ローカルLLM(Qwen / Gemma、Ollama経由)で技術的に正確な要約を生成
- X向けの短文投稿とnote.com向けの長文記事、それぞれ専用の生成パイプラインで作成
- 生成物は**公開前に自動監査**(ハルシネーション・日本語品質・フォーマット崩れをチェック)され、合格したものだけが自動公開される
- X投稿はSocialDogのEnterprise API経由、note.com記事はブラウザ自動操作(Playwright)で投稿
- 無人実行(Windowsタスクスケジューラ)に対応しつつ、公開済み履歴の重複排除とロールバック機構で事故を防ぐ設計

## パイプライン概要

```
┌─────────────┐   ┌──────────────┐   ┌───────────────────┐
│ 収集          │ → │ 選別・要約     │ → │ 生成・精製            │
│ arXiv/HN/     │   │ (ローカルLLM) │   │ (ローカルLLM + Claude) │
│ GitHub/HF     │   │ Qwen 27B     │   │ X: Claude(Haiku)    │
└─────────────┘   └──────────────┘   │ note: Qwen/Gemma    │
                                       └─────────┬──────────┘
                                                 ↓
                                       ┌───────────────────┐
                                       │ 公開前自動監査        │
                                       │ (Claude Workflow)   │
                                       │ ハルシネーション検知 等 │
                                       └─────────┬──────────┘
                                   合格分のみ自動公開
                                                 ↓
                         ┌───────────────────────┴───────────────────────┐
                         ↓                                               ↓
               ┌─────────────────┐                           ┌─────────────────┐
               │ X (SocialDog API) │                           │ note.com (Playwright)│
               └─────────────────┘                           └─────────────────┘
```

note.com向けには、X向けとは独立した並行パイプライン(記事生成→アイキャッチ画像生成→公開)があります。詳細な設計・運用ルールは [`CLAUDE.md`](./CLAUDE.md) にまとめています。

## 技術スタック

| 分野 | 技術 |
|---|---|
| 言語 | Python 3 |
| ローカルLLM推論 | Ollama(Qwen2.5-coder / Qwen3.8 / Gemma4) |
| ブラウザ自動化 | Playwright, CloakBrowser(ステルス機能付きPlaywrightラッパー) |
| AI協業基盤 | Claude Code(Skills / Workflows によるコンテンツ監査・精製の自動化) |
| 投稿先API | SocialDog Enterprise API(X投稿の正規経路) |
| 実行環境 | WSL2 + Windowsタスクスケジューラ(日次無人実行) |
| セキュリティ | pre-commit + detect-secrets、GitHub Secret Scanning / Push Protection |

## 工夫したポイント

- **ローカルLLMの不安定さへの対策**: 12B〜27B級のローカルモデルは、指示追従性や日本語の安定性でフロンティアモデルに劣る場面がある。複数段の検証(日本語チェック、重複検出、外国語混入検知)とフォールバック機構を重ね、人手を介さずに一定の品質を担保できるようにした
- **公開前の自動監査ゲート**: note.com記事・Xポストとも、生成後にAI(Claude)による監査ステップを通し、`audit_passed`なものだけが公開対象になるようゲートを実装。無人実行でも「とりあえず全部出す」のではなく、不合格分は人間が後から確認・再生成するサイクルを設計した
- **Bot検知を避ける正規経路の選定**: X投稿は当初cookieベースの直接操作を試みたが、Bot検知リスクが高いと判断し、SocialDogのEnterprise API経由に切り替え
- **公開前のセキュリティ監査**: オープンソース化にあたり、作業ツリーだけでなくgit全履歴を対象にシークレットスキャンを実施。過去に混入していた資格情報を発見し、無効化(セッションログアウトで実地確認)。再発防止としてpre-commitフック(ローカル)とGitHub Secret Scanning / Push Protection(リモート)の二重の仕組みを導入した

## AIとの協業について

このプロジェクトは、Claude Code(AIペアプログラマー)と協働して開発しました。ポートフォリオとして、役割分担を具体的に書いておきます。

**開発者(私)が判断・決定したこと**
- プロダクトの要件・優先順位(どのソースから集めるか、どの頻度で投稿するか等)
- 投稿経路の選定(X: Bot検知リスクを避けSocialDog API経由を採用 / note.com: ブラウザ自動操作)
- 自動化の範囲とタイミング(「生成・監査まで無人化し公開は手動」から「監査ゲート通過を条件に公開まで無人化」へ、実運用の結果を見ながら段階的に拡大)
- 安全機構(重複排除のロールバック機構、dry-runモード)を残すか外すかの最終判断
- 公開前セキュリティ監査の実施判断、発見した資格情報の無効化・再発防止策の承認
- 実際のブラウザ画面を目視しての動作確認(自動テストでは拾いきれないUI崩れ・リンク破損の検知)
- 日次実行のスケジュール設計(実行時刻、PCがオフだった場合の挙動等)

**Claude Codeに任せたこと**
- 各モジュールの実装・リファクタリング
- ローカルLLM特有の不具合(出力の重複、外国語混入、文字数超過等)の調査・修正
- 監査・自動生成のためのWorkflow/Skill設計と実装
- 設計意図・運用ルールのドキュメント化(`CLAUDE.md`の継続的なメンテナンス)
- セキュリティスキャンの実行とレポーティング

実装の大部分はAIに任せつつ、「何を作るか」「どこまで自動化して良いか」「安全性をどう担保するか」といった判断は一貫して自分で行う、という開発スタイルを取っています。

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install

# シークレットスキャン用(開発時のみ)
pip install -r requirements-dev.txt
pre-commit install
```

Ollamaがローカルで起動している必要があります(`http://localhost:11434`)。認証情報(cookie)の取得方法や日次運用コマンドなど、詳細は [`CLAUDE.md`](./CLAUDE.md) を参照してください。

## 免責

個人の学習・検証目的のプロジェクトです。各プラットフォームの利用規約の範囲内での利用を前提としています。
