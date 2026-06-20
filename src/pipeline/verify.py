"""裏取り層 — 各候補に verify_status と裏取りリンク素案を付与する。

ヒューリスティックで素案を作り、後段の Gemini が最終確定する（gemini が失敗した
場合はこの素案がそのまま採用される＝フォールバック）。

判定方針:
- tier=primary 自体 → 一次確認済（公式発表/論文）。
- tier=secondary 自体 → 二次。
- tier=social（Reddit/HN/YouTube）→ 候補集合内に同じ話題を扱う primary/secondary が
  あれば、その tier に引き上げ＋裏取りリンクを紐付け。無ければ未確認（噂）。
"""
from __future__ import annotations

import logging
from difflib import SequenceMatcher

from ..models import (
    NewsItem,
    TIER_PRIMARY,
    TIER_SECONDARY,
    TIER_SOCIAL,
    VERIFY_PRIMARY,
    VERIFY_SECONDARY,
    VERIFY_UNCONFIRMED,
)

LOG = logging.getLogger("ai_news.verify")

_MATCH = 0.55  # 別ソース間の話題一致しきい値（一次へ昇格しやすいよう緩め。誤マッチ注意）


def _norm(title: str) -> str:
    return " ".join(title.lower().split())


def _corroborates(social_title: str, other: NewsItem) -> bool:
    """social 記事と other(一次/二次) が同じ話題かを近似判定。"""
    ratio = SequenceMatcher(None, _norm(social_title), _norm(other.original_title)).ratio()
    return ratio >= _MATCH


def assign_status(items: list[NewsItem]) -> list[NewsItem]:
    primaries = [it for it in items if it.tier == TIER_PRIMARY]
    secondaries = [it for it in items if it.tier == TIER_SECONDARY]

    for it in items:
        if it.tier == TIER_PRIMARY:
            it.verify_status = VERIFY_PRIMARY
            continue
        if it.tier == TIER_SECONDARY:
            it.verify_status = VERIFY_SECONDARY
            continue

        # social: 一次→二次の順で裏取りを探す
        match = next((p for p in primaries if _corroborates(it.original_title, p)), None)
        if match:
            it.verify_status = VERIFY_PRIMARY
            it.primary_source_url = match.url
            continue
        match = next((s for s in secondaries if _corroborates(it.original_title, s)), None)
        if match:
            it.verify_status = VERIFY_SECONDARY
            it.primary_source_url = match.url
            continue
        it.verify_status = VERIFY_UNCONFIRMED

    counts = {
        VERIFY_PRIMARY: sum(1 for i in items if i.verify_status == VERIFY_PRIMARY),
        VERIFY_SECONDARY: sum(1 for i in items if i.verify_status == VERIFY_SECONDARY),
        VERIFY_UNCONFIRMED: sum(1 for i in items if i.verify_status == VERIFY_UNCONFIRMED),
    }
    LOG.info("verify: %s", counts)
    return items
