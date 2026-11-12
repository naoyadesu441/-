# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

delegated: static HTML/CSS + GSAP（CDN）。テスト用LPのため、ビルド不要で claude.ai Artifact として公開できる構成を選択。

## Users

海外AIの最新動向を、英語の一次情報を自分で追う時間なしに把握したい日本語話者。AIを副業・仕事効率化・SNS発信に使いたい個人や小規模事業者。（推定: README の「AIを使った副業や仕事効率化、SNSマーケティングに関心のあるユーザー」記述から）

## Product Purpose

海外で話題のAI情報を毎日自動でリサーチし、「日本語要約＋裏取りステータス（一次ソース確認済みか）＋元リンク」に整理して届ける。さらにそのリサーチからYouTube/Threads台本を自動生成する。

## Positioning

一次ソースで裏取りできたニュースだけを残す（🟢一次 フィルタ）。要約だけでなく元リンクと裏取り状態を必ず添える。

## Operating Context

- Stage 1: GitHub Actions が毎日 08:00 JST に収集→重複排除→裏取り判定→Gemini要約→news/YYYY-MM-DD.md、Discord通知、Notion DB蓄積
- Stage 2: Claude Code Routine が毎日 09:00 JST に台本生成
- 完全無料・従量課金ゼロ設計（鍵不要の無料ソース＋Gemini無料枠＋公開リポのActions）

## Capabilities and Constraints

- 実データ: news/*.md（日次）、scripts/（台本）
- 未決: 料金・購読導線（配信の受け取り方法を一般公開するかどうか）は未定。LPでは価格を記載しない

## Evidence on Hand

- news/2026-11-06.md など日次リサーチ実物
- 利用者数・推薦文・メディア掲載は存在しない。捏造しない

## Product Principles

1. 裏取りが先、速さは後
2. 要約には必ず元リンク
3. 毎日届く仕組みそのものが価値（使い回せる資産になる）
