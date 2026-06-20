"""重複排除。

1) URL 正規化済みの完全一致
2) タイトル近似（difflib ratio > 0.85）

優先順位: weight が高い → engagement(score) が高い → tier が上位 を残す。
（複数ソースが同じ話題を扱う場合、より信頼できる/話題性の高い方を代表に）
"""
from __future__ import annotations

import logging
from difflib import SequenceMatcher

from ..models import NewsItem, TIER_PRIMARY, TIER_SECONDARY, TIER_SOCIAL

LOG = logging.getLogger("ai_news.dedupe")

_TIER_RANK = {TIER_PRIMARY: 3, TIER_SECONDARY: 2, TIER_SOCIAL: 1}
_SIMILARITY = 0.85


def _priority(it: NewsItem) -> tuple:
    return (
        it.weight,
        int(it.engagement.get("score", 0)),
        _TIER_RANK.get(it.tier, 0),
    )


def _norm_title(title: str) -> str:
    return " ".join(title.lower().split())


def dedupe(items: list[NewsItem]) -> list[NewsItem]:
    # 1) URL 完全一致 — 優先度の高い方を残す
    by_url: dict[str, NewsItem] = {}
    for it in items:
        key = it.url
        if key not in by_url or _priority(it) > _priority(by_url[key]):
            by_url[key] = it
    deduped = list(by_url.values())

    # 2) タイトル近似 — 優先度降順に走査し、既存代表に似ていれば捨てる
    deduped.sort(key=_priority, reverse=True)
    kept: list[NewsItem] = []
    kept_titles: list[str] = []
    for it in deduped:
        t = _norm_title(it.original_title)
        if any(SequenceMatcher(None, t, kt).ratio() > _SIMILARITY for kt in kept_titles):
            continue
        kept.append(it)
        kept_titles.append(t)

    LOG.info("dedupe: %d -> %d", len(items), len(kept))
    return kept
