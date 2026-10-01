# 海外AI最新トレンド「毎日リサーチ → 台本自動生成」システム

海外で話題のAI最新情報を**毎日自動でリサーチ**し、「日本語要約＋裏取りステータス（一次ソース確認済みか）＋元リンク」に整理。さらにそのリサーチから **YouTube動画の台本まで自動生成**します。

**完全無料・従量課金リスクゼロ**で動くよう設計しています（鍵不要の無料ソース＋Gemini無料枠＋公開リポジトリのGitHub Actions）。

## 最新リサーチ
<!--LATEST-->
**最終更新: 2026-10-01**

> 今週は、Googleが次世代AIモデル「Gemini 4 Argon」を発表し、AI技術のさらなる進化を示唆しました。また、OpenAIは中小企業向けのAI活用支援を強化し、副業や業務効率化を目指すユーザーにとって実践的なAI導入の機会を広げています。Hugging Faceからは多言語TTS/音声クローン評価ツールが登場し、コンテンツ制作におけるAI活用を後押しする動きも見られます。

- [News][🟢一次] Googleが次世代AI「Gemini 4 Argon」発表 — https://deepmind.google/blog/gemini-4-argon-our-next-era-of-frontier-intelligence
- [News][🟢一次] OpenAIが中小企業のAI活用を支援 — https://openai.com/index/helping-small-businesses-put-ai-to-work
- [News][🟢一次] Hugging Faceが多言語TTS評価ツール公開 — https://huggingface.co/blog/open-tts-leaderboard
- [News][🟢一次] Amazon Bedrockで対話型AIアシスタント構築 — https://aws.amazon.com/blogs/machine-learning/query-claims-in-natural-language-with-amazon-bedrock-knowledge-bases
- [News][🟢一次] AWS BedrockでマルチAI音楽制作パイプライン — https://aws.amazon.com/blogs/machine-learning/build-a-multi-agent-music-production-pipeline-on-amazon-bedrock-agentcore-runtime-instances
- [Paper][🟢一次] LLMがプログラム実行エラーを自動修復 — https://arxiv.org/abs/2609.39086v1
- [Paper][🟢一次] AIコーディングエージェントが数学問題に挑戦 — https://arxiv.org/abs/2609.39081v1
- [News][🟢一次] OpenAIが不正モデル抽出を阻止 — https://openai.com/index/disrupting-a-coordinated-model-distillation-campaign
- [Paper][🟢一次] 深層研究AIエージェントの計画手法 — https://arxiv.org/abs/2609.39154v1
- [Paper][🟢一次] LLMエージェントのスキル自己進化を促進 — https://arxiv.org/abs/2609.39149v1

全文: [`news/2026-10-01.md`](news/2026-10-01.md)
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
