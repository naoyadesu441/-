"""arXiv API（鍵不要）から最新の AI/ML 論文を収集する。

礼儀として呼び出し前に約 3 秒待つ（arXiv の利用案内に従う）。
"""
from __future__ import annotations

import logging
import time
from urllib.parse import urlencode

import feedparser

from ..config import Http
from ..models import NewsItem, SOURCE_PAPER
from .base import clip, struct_to_utc

LOG = logging.getLogger("ai_news.collect.arxiv")

API = "http://export.arxiv.org/api/query"


def collect(http: Http, cfg: dict) -> list[NewsItem]:
    if not cfg.get("enabled", True):
        return []
    params = {
        "search_query": cfg.get("query", "cat:cs.AI"),
        "max_results": int(cfg.get("max_results", 40)),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    weight = float(cfg.get("weight", 0.6))
    tier = cfg.get("tier", "primary")
    items: list[NewsItem] = []
    try:
        time.sleep(3)  # arXiv への礼儀待ち
        resp = http.get(f"{API}?{urlencode(params)}")
        if resp.status_code != 200:
            LOG.warning("arxiv: HTTP %s", resp.status_code)
            return items
        parsed = feedparser.parse(resp.content)
        for entry in parsed.entries:
            title = " ".join((entry.get("title") or "").split())
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue
            items.append(
                NewsItem(
                    source_type=SOURCE_PAPER,
                    source="arXiv",
                    tier=tier,
                    original_title=title,
                    url=link,
                    published_at=struct_to_utc(entry.get("published_parsed")),
                    raw_summary=clip(entry.get("summary") or "", 500),
                    weight=weight,
                )
            )
    except Exception as exc:  # noqa: BLE001
        LOG.warning("arxiv: failed: %s", exc)
    LOG.info("arxiv: %d items", len(items))
    return items
