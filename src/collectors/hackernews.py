"""Hacker News を Algolia API（鍵不要）で収集する。

- search_by_date で当日の AI 関連 story / Show HN を取得。
- front_page は注目度の高い記事を拾う（relevance）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..config import Http
from ..models import NewsItem, SOURCE_HN, TIER_SOCIAL
from .base import clip, contains_ai_keyword

LOG = logging.getLogger("ai_news.collect.hn")

BY_DATE = "https://hn.algolia.com/api/v1/search_by_date"
SEARCH = "https://hn.algolia.com/api/v1/search"
ITEM_URL = "https://news.ycombinator.com/item?id={oid}"


def collect(http: Http, cfg: dict, ai_keywords: list[str] | None = None) -> list[NewsItem]:
    query = cfg.get("query", "AI")
    tags = cfg.get("tags", ["story"])
    hits = int(cfg.get("hits_per_page", 40))
    weight = float(cfg.get("weight", 1.0))
    min_points = int(cfg.get("min_points", 0))
    require_ai = cfg.get("require_ai", False)

    seen: set[str] = set()
    items: list[NewsItem] = []

    for tag in tags:
        # front_page は relevance（search）、それ以外は新着（search_by_date）
        endpoint = SEARCH if tag == "front_page" else BY_DATE
        params = {"tags": tag, "hitsPerPage": hits}
        # 全タグに AI クエリを付与。show_hn / front_page も AI 関連に絞り、
        # 「Big Banana Car」等の非AI記事がそもそも取得されないようにする
        # （後段の require_ai フィルタとの二重防御）。
        if query:
            params["query"] = query
        try:
            resp = http.get(endpoint, params=params)
            if resp.status_code != 200:
                LOG.warning("HN[%s]: HTTP %s", tag, resp.status_code)
                continue
            for hit in resp.json().get("hits", []):
                oid = str(hit.get("objectID", ""))
                if not oid or oid in seen:
                    continue
                title = (hit.get("title") or hit.get("story_title") or "").strip()
                if not title:
                    continue
                points = int(hit.get("points") or 0)
                if points < min_points:
                    continue
                if require_ai and ai_keywords and not contains_ai_keyword(title, ai_keywords):
                    continue
                seen.add(oid)
                url = (hit.get("url") or "").strip() or ITEM_URL.format(oid=oid)
                created_iso = hit.get("created_at")
                published = None
                if created_iso:
                    try:
                        published = datetime.fromisoformat(
                            created_iso.replace("Z", "+00:00")
                        ).astimezone(timezone.utc)
                    except ValueError:
                        published = None
                items.append(
                    NewsItem(
                        source_type=SOURCE_HN,
                        source="Hacker News" + (" / Show HN" if tag == "show_hn" else ""),
                        tier=TIER_SOCIAL,
                        original_title=title,
                        url=url,
                        published_at=published,
                        raw_summary=clip(hit.get("story_text") or "", 300),
                        weight=weight,
                        engagement={
                            "score": points,
                            "comments": int(hit.get("num_comments") or 0),
                            "permalink": ITEM_URL.format(oid=oid),
                        },
                    )
                )
        except Exception as exc:  # noqa: BLE001
            LOG.warning("HN[%s]: failed: %s", tag, exc)
    LOG.info("hackernews: %d items", len(items))
    return items
