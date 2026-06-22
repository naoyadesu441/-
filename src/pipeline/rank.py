"""非AIのヒューリスティック事前ランク。

Gemini に渡す候補を ~60 件に絞るためのスコアリング。
新しさ・エンゲージメント・ソース重み・tier を合成する。
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from ..models import NewsItem, TIER_PRIMARY, TIER_SECONDARY, TIER_SOCIAL

LOG = logging.getLogger("ai_news.rank")

# 一次ソースは優遇するが、極端な差をつけない。エンゲージメントの高い二次ソース
# （TechCrunch等の消費者向けニュース）が、反応ゼロの学術系一次（arXiv等）と
# 互角に競えるようにして、SNS映えするニュースが上位に残るようにする。
_TIER_BONUS = {TIER_PRIMARY: 2.0, TIER_SECONDARY: 1.5, TIER_SOCIAL: 0.6}


def _recency_score(published: datetime | None) -> float:
    """0〜1。新しいほど高い。日付不明は中庸(0.5)。"""
    if published is None:
        return 0.5
    age_h = (datetime.now(timezone.utc) - published).total_seconds() / 3600.0
    age_h = max(age_h, 0.0)
    # 半減期 ~18h の指数減衰
    return math.exp(-age_h / 18.0)


def _engagement_score(it: NewsItem) -> float:
    """0〜1 程度。log スケールで score+comments を圧縮。"""
    score = int(it.engagement.get("score", 0))
    comments = int(it.engagement.get("comments", 0))
    raw = score + 2 * comments
    if raw <= 0:
        return 0.0
    return min(math.log10(raw + 1) / 3.0, 1.0)  # 1000 で ~1.0


def score_items(items: list[NewsItem]) -> list[NewsItem]:
    for it in items:
        s = (
            2.0 * _recency_score(it.published_at)
            + 1.5 * _engagement_score(it)
            + 1.0 * it.weight
            + _TIER_BONUS.get(it.tier, 0.5)
        )
        it.score = round(s, 4)
    items.sort(key=lambda x: x.score, reverse=True)
    for idx, it in enumerate(items, start=1):
        it.rank = idx
    return items


def preselect(items: list[NewsItem], limit: int = 60) -> list[NewsItem]:
    """事前ランク。一次(primary)は全件無条件で残し、残り枠を上位の非一次で埋める。

    配信は一次のみのため、一次候補が60件上限から押し出されないようにする。
    非一次(social/secondary)は裏取り(corroboration)の照合材料として残す。
    """
    ranked = score_items(items)
    primaries = [it for it in ranked if it.tier == TIER_PRIMARY]
    others = [it for it in ranked if it.tier != TIER_PRIMARY]
    selected = primaries + others[: max(0, limit - len(primaries))]
    LOG.info(
        "rank: %d items, preselect %d (一次 %d 全件 + 他 %d)",
        len(ranked),
        len(selected),
        len(primaries),
        len(selected) - len(primaries),
    )
    return selected
