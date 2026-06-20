"""YouTube チャンネルの RSS を収集する。

feed: https://www.youtube.com/feeds/videos.xml?channel_id=ID
"""
from __future__ import annotations

import logging

from ..config import Http
from ..models import NewsItem, SOURCE_YOUTUBE
from .feeds_rss import fetch_feed

LOG = logging.getLogger("ai_news.collect.youtube")

FEED_TMPL = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"


def collect(http: Http, channels: list[dict], ai_keywords: list[str]) -> list[NewsItem]:
    items: list[NewsItem] = []
    for ch in channels:
        if not ch.get("enabled", True):
            continue
        cid = (ch.get("channel_id") or "").strip()
        if not cid:
            LOG.warning("%s: channel_id 未設定のためスキップ", ch.get("name"))
            continue
        # Fireship 等の低 weight は AI キーワード必須で絞る
        require_ai = float(ch.get("weight", 1.0)) < 0.8
        items += fetch_feed(
            http,
            name=ch["name"],
            url=FEED_TMPL.format(cid=cid),
            source_type=SOURCE_YOUTUBE,
            tier=ch.get("tier", "social"),
            weight=float(ch.get("weight", 1.0)),
            ai_keywords=ai_keywords,
            require_ai=require_ai,
            max_items=8,
        )
    return items
