"""収集アイテムの正規化スキーマ。

すべてのコレクターは雑多な生データを `NewsItem` に正規化して返す。
後段（normalize → dedupe → rank → verify → gemini）が同じ形を前提に処理できる。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


# source_type の取りうる値（表記ゆれ防止のため定数化）
SOURCE_NEWS = "News"
SOURCE_YOUTUBE = "YouTube"
SOURCE_REDDIT = "Reddit"
SOURCE_HN = "HN"
SOURCE_PRODUCTHUNT = "ProductHunt"
SOURCE_PAPER = "Paper"
SOURCE_NEWSLETTER = "Newsletter"

# tier（裏取りの土台になる信頼度の階層）
TIER_PRIMARY = "primary"
TIER_SECONDARY = "secondary"
TIER_SOCIAL = "social"

# verify_status（裏取りステータス。日本語ラベル＝そのまま Notion / markdown に出る）
VERIFY_PRIMARY = "一次確認済"
VERIFY_SECONDARY = "二次"
VERIFY_UNCONFIRMED = "未確認"

# verify_status → 絵文字バッジ
VERIFY_BADGE = {
    VERIFY_PRIMARY: "🟢一次",
    VERIFY_SECONDARY: "🟡二次",
    VERIFY_UNCONFIRMED: "🔴未確認",
}


@dataclass
class NewsItem:
    # --- 収集時に必ず埋める ---
    source_type: str                 # SOURCE_* のいずれか
    source: str                      # 具体名（"OpenAI", "r/LocalLLaMA" など）
    tier: str                        # TIER_* のいずれか
    original_title: str
    url: str                         # 正規化後の URL（normalize で確定）
    published_at: Optional[datetime] = None   # UTC aware
    raw_summary: str = ""            # 元の説明文（後で切り詰める）
    weight: float = 1.0              # ソース定義の重み
    engagement: dict = field(default_factory=dict)   # {"score": int, "comments": int} 等

    # --- 後段で付与 ---
    item_id: str = ""                # 安定ID（url ハッシュ）。Gemini との突き合わせキー
    title_jp: str = ""
    summary_jp: str = ""
    category: str = ""
    verify_status: str = ""          # VERIFY_*
    primary_source_url: str = ""     # 裏取りに使った一次/二次リンク（任意）
    rank: int = 0
    score: float = 0.0
    buzz_score: int = 0              # SNSバズ予測（1-5）。Geminiが判定
    buzz_reason: str = ""            # バズ予測の理由（日本語1文）

    def ensure_id(self) -> str:
        """url から安定 ID を生成（未設定なら）。"""
        if not self.item_id:
            basis = (self.url or self.original_title).strip().lower()
            self.item_id = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
        return self.item_id

    def to_dict(self) -> dict:
        d = asdict(self)
        if isinstance(self.published_at, datetime):
            d["published_at"] = self.published_at.isoformat()
        return d
