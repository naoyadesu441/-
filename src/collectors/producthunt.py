"""Product Hunt の RSS から AI 関連プロダクトを収集する。

汎用フィードなので AI キーワードで絞り込む（require_ai=True）。
"""
from __future__ import annotations

from ..config import Http
from ..models import NewsItem, SOURCE_PRODUCTHUNT
from .feeds_rss import fetch_feed


def collect(http: Http, cfg: dict, ai_keywords: list[str]) -> list[NewsItem]:
    if not cfg.get("enabled", True):
        return []
    return fetch_feed(
        http,
        name="Product Hunt",
        url=cfg["url"],
        source_type=SOURCE_PRODUCTHUNT,
        tier=cfg.get("tier", "secondary"),
        weight=float(cfg.get("weight", 0.7)),
        ai_keywords=ai_keywords,
        require_ai=True,
        max_items=40,
    )
