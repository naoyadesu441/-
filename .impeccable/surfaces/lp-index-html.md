---
version: 1
slug: "lp-index-html"
primary_target: "lp/index.html"
related_targets: []
---

# Surface brief: AIニュース速達便 LP (test)

Mode: Persuade. Audience: 海外AI動向を日本語で毎朝把握したい個人・小規模事業者. Action: 今日の便（news/YYYY-MM-DD.md）を読む. Proof: 実際の 2026-11-06 便の3件と元リンク. Constraints: 価格・利用者数・推薦文は書かない（存在しない）.

## Direction contract

FORM: seed:65ca14bb6e2b3929 — assigned grounded candidate 5「速達郵便と消印」. Challengers all declined; raises: zine → 消印のdraw-on（スクロールで押印）; azulejo → whole-unit grid（切手シートの目打ち単位でレイアウト）; timetable → 時刻表記は一書体で統一.
THESIS: 毎朝08:00に届く「一通の速達」。要約サイトのカード一覧という型を拒否。
OWN-WORLD: 速達の赤帯が面を占める（Committed）。白い便箋、ブルーブラックのインク、消印の朱。角丸ゼロ、1px罫（Refero: teenage engineering の罫と2値スペーシング規律）。和文ゴシック＋ステンシル数字。
STORY: 封筒→開封→便箋に3件→各件に「一次確認」消印と元リンク→配達ルート（08:00収集/09:00台本）→切り取り線の受取票で行動。
FIRST VIEWPORT: 赤帯の速達封筒、宛名欄に見出し、消印「2026.11.06 08:00 一次確認」、主ボタン「今日の便を読む」。
SIGNATURE: 封を開けると便箋がせり上がる（GSAP）、消印がスクロールで押される。受取票は目打ち（React Bits TearTicket の目打ち幾何）。
RISK: 実在の郵便事業者ロゴは使わない。〒マーク不使用。
