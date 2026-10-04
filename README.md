# 海外AI最新トレンド「毎日リサーチ → 台本自動生成」システム

海外で話題のAI最新情報を**毎日自動でリサーチ**し、「日本語要約＋裏取りステータス（一次ソース確認済みか）＋元リンク」に整理。さらにそのリサーチから **YouTube動画の台本まで自動生成**します。

**完全無料・従量課金リスクゼロ**で動くよう設計しています（鍵不要の無料ソース＋Gemini無料枠＋公開リポジトリのGitHub Actions）。

## 最新リサーチ
<!--LATEST-->
**最終更新: 2026-10-04**

> 今日のAI界隈では、AIエージェントの信頼性に関する技術的な課題が注目されています。Hugging Faceの報告によると、AIエージェントがタスク完了を主張しても、実際のデータベースと結果が一致しないケースが確認されており、AIシステムの統合における正確性の確保が課題として浮上しています。

- [Newsletter][🟡二次] AnthropicとOpenAIが新モデル発表 — https://lastweekin.ai/p/lwiai-podcast-258-opus-55-sol-and
- [News][🟡二次] Geminiが電話代行、Pixel 11新機能 — https://wired.jp/article/googles-gemini-can-now-make-calls-for-you-on-pixel-phones
- [News][🟡二次] OpenAI安全責任者が辞任、企業文化に警鐘 — https://techcrunch.com/2026/10/03/openai-safety-employee-resigns-claiming-the-companys-culture-is-broken
- [News][🟡二次] OpenAI安全担当者が辞任、警鐘を鳴らす — https://www.theverge.com/ai-artificial-intelligence/1004408/openai-safety-quits-sounding-the-alarm
- [News][🟡二次] MetaがMuse AIガジェットをオープンソース化 — https://www.theverge.com/tech/1004330/meta-muse-ai-gadgets-home-link
- [ProductHunt][🟡二次] MetaのAIガジェット構築キット公開 — https://www.producthunt.com/products/muse-22
- [News][🟡二次] カプコン、AIとゲーム制作の未来へ — https://www.theverge.com/games/1004418/capcom-ai-game-development
- [News][🟡二次] テキストで使えるAIエージェント一覧 — https://techcrunch.com/2026/10/03/all-the-ai-agents-that-can-live-in-your-text-messages
- [News][🟡二次] Meta、ガジェットへのMuse搭載を推進 — https://techcrunch.com/2026/10/02/meta-wants-you-to-build-your-own-muse-gadget
- [News][🟢一次] AIエージェントとデータベースの不一致 — https://huggingface.co/blog/microsoft/thinkingbox

全文: [`news/2026-10-04.md`](news/2026-10-04.md)
<!--/LATEST-->

---

## 仕組み（2ステージ）

```
[Stage 1] リサーチ自動集約 — GitHub Actions（毎日 08:00 JST, 公開リポで無料）
   収集(無料ソース) → 正規化 → 重複排除 → 事前ランク → 裏取り判定
   → Gemini(1コール: 選定＋日本語要約＋裏取り確定) → 一次のみフィルタ
   → news/YYYY-MM-DD.md → Discord通知 ＋ Notion DB蓄積 ＋ git commit

[Stage 2] 台本自動生成 — Claude Code Web Routine「⚡ ai-news-daily-cloud」（毎日 09:00 JST）
   当日の news/*.md を読む → 裏取り済みを優先 → なおや式台本原則で台本化
   → scripts/YYYY-MM-DD.md → commit
```

- **Stage 1** は鍵不要ソース（YouTube/各種ニュースRSS/Reddit/Hacker News/Product Hunt/arXiv/ニュースレター/note）＋ Gemini 無料枠で機械的に毎日回ります。
- **Stage 2** は Claude Code の品質で台本化（あなたの Claude Code 購読内で実行＝従量課金なし）。

裏取りステータス: **🟢一次**=公式/論文で確認済 ・ **🟡二次**=信頼メディア報道 ・ **🔴未確認**=SNS/掲示板の噂レベル。

> **配信ポリシー: 一次のみ。** 正しさが確認できる **🟢一次（公式発表・論文、または一次ソースで裏取りできたもの）だけ**を配信します。🟡二次・🔴未確認は除外。収集は広く行い（Google News RSS 等を含む「おすすめが流れてくる」発見層）、その中から一次に裏取りできたものだけを出力します。該当が無い日は「本日は一次確認済のニュースはありませんでした」と通知します。

---

## セットアップ（初回のみ・あなたの操作）

### 1. リポジトリを公開（推奨）
公開リポジトリなら GitHub Actions の標準ランナーが**無制限無料**で、超過課金の概念がありません。
`Settings → General → Danger Zone → Change repository visibility → Public`。

### 2. GitHub シークレットを4つ登録
`Settings → Secrets and variables → Actions → New repository secret`:

| 名前 | 取得元 |
|---|---|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) のAPIキー（**課金は有効化しない**＝無料枠のまま） |
| `DISCORD_WEBHOOK_URL` | Discordチャンネル設定 → 連携サービス → ウェブフック → URLをコピー |
| `NOTION_TOKEN` | [Notion Integrations](https://www.notion.so/my-integrations) で内部インテグレーション作成 → `secret_…` |
| `NOTION_DATABASE_ID` | 下記DBを作成し、URLの32桁英数字 |

### 3. Notion データベースを作成し、インテグレーションに共有
新規データベース（テーブル）を作り、右上 `…` → 連携 → 上で作ったインテグレーションを追加。
**プロパティ**（名前と型を正確に）:

| プロパティ名 | 型 |
|---|---|
| `Title (JP)` | タイトル |
| `OriginalTitle` | テキスト |
| `Date` | 日付 |
| `Category` | セレクト |
| `SourceType` | セレクト |
| `Tier` | セレクト |
| `VerifyStatus` | セレクト（一次確認済 / 二次 / 未確認） |
| `URL` | URL |
| `PrimarySource` | URL |
| `SummaryJP` | テキスト |
| `Score` | 数値 |
| `Rank` | 数値 |

### 4. Stage 2 の Routine を登録（kent-threads-daily-cloud と同手順）
Claude Code Web の **Routines** に新規登録:
- 名前: `⚡ ai-news-daily-cloud`
- リポジトリ: このリポジトリ（ブランチ: `main`）
- スケジュール: 毎日 **09:00 JST**（Stage 1 の後）
- プロンプト例: 「`/daily-ai-script` を実行して当日のAIニュース台本を作成し、`scripts/` にコミットして」

> 既存の「⚡ kent-threads-daily-cloud」の台本プロンプト/文体に厳密に合わせたい場合は、
> `.claude/skills/daily-ai-script/台本原則.md` をその内容に合わせて編集してください。

---

## 動作確認（本番前に推奨）

### Stage 1
```bash
pip install -r requirements.txt
cp .env.example .env   # 4つの値を入れる

# 送信もコミットもせず、生成内容と配信ペイロードを確認
python -m src.main --dry-run

# 個別検証（読み取り専用）
python scripts/verify_youtube.py        # channel_id を確認（⚠印を要チェック）
python scripts/verify_feeds.py          # RSS取得可否（不可なら sources.yaml で enabled:false）
python -m src.pipeline.gemini --sample fixtures/candidates.json   # Gemini 1コール＋裏取り解析
```
- GitHub 上では `Actions → daily-ai-news → Run workflow` で `dry_run=true` を選び、本番ソースで全パイプラインをログ確認 → 問題なければ `dry_run=false` で本実行。
- Discord は専用テストwebhook、Notion は使い捨てテストDBで先に試すとスパムを避けられます。

### Stage 2
- このリポジトリを開いた Claude Code セッションで `/daily-ai-script` を実行し、サンプルの `news/*.md` から `scripts/*.md` が原則どおり生成されるか確認 → 内容OKなら Routine を登録。

---

## 本番前に一度だけ確認したい項目
- (a) `sources.yaml` の Lex Fridman / Nate Herk の `channel_id`（`verify_youtube.py`）
- (b) Anthropic / Meta AI / 各ニュースレター / note の RSS可否（`verify_feeds.py`、不可は `enabled:false`）
- (c) Gemini が裏取り込みの解析可能JSONを返す（`--sample`）
- (d) Notion テストDB投入が成功する
- (e) `台本原則.md` のトーン・型が意図どおりか

---

## リポジトリ構成
```
.github/workflows/daily.yml      # Stage1 の cron / 手動実行
src/                             # Stage1 本体（collectors / pipeline / render / deliver）
  main.py / config.py / models.py
sources.yaml                     # ソース定義（チャンネルID・RSS・weight・tier・enabled）
scripts/verify_*.py              # 読み取り専用の検証スクリプト
scripts/YYYY-MM-DD.md            # Stage2 が生成する台本
news/YYYY-MM-DD.md               # Stage1 が生成する日次リサーチ（真実の記録）
.claude/skills/daily-ai-script/  # Stage2 のスキルと台本原則
fixtures/candidates.json         # Gemini検証用サンプル
requirements.txt / .env.example
```

## 無料・課金安全性
- 収集ソースはすべて **APIキー不要**。
- Gemini は**課金無効のまま無料枠**で 1日1〜2リクエストのみ（無料枠は十分大きい）。
- 公開リポジトリの GitHub Actions は無料。**有料APIへの露出はゼロ**＝設計上、勝手な課金は発生しません。
- 秘密情報はヘッダ経由・ログ非出力・`.env` は `.gitignore` 済み。
