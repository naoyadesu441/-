"""Reddit のサブレディット top（当日）を収集する。

公開 JSON エンドポイント（鍵不要）。記述的 User-Agent が無いと 429 になるため、
共有 Http セッションの UA を必ず使う。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..config import Http, REDDIT_USER_AGENT
from ..models import NewsItem, SOURCE_REDDIT, TIER_SOCIAL
from .base import clip

LOG = logging.getLogger("ai_news.collect.reddit")

URL_TMPL = "https://www.reddit.com/r/{sub}/top.json?t=day&limit={limit}"


def collect(http: Http, cfg: dict) -> list[NewsItem]:
    items: list[NewsItem] = []
    subs = cfg.get("subreddits", [])
    limit = int(cfg.get("limit", 25))
    weight = float(cfg.get("weight", 0.9))
    min_score = int(cfg.get("min_score", 0))
    tier = cfg.get("tier", TIER_SOCIAL)

    for sub in subs:
        try:
            resp = http.get(
                URL_TMPL.format(sub=sub, limit=limit),
                headers={"User-Agent": REDDIT_USER_AGENT},
            )
            if resp.status_code != 200:
                LOG.warning("r/%s: HTTP %s", sub, resp.status_code)
                continue
            children = resp.json().get("data", {}).get("children", [])
            for child in children:
                d = child.get("data", {})
                if d.get("stickied") or d.get("over_18"):
                    continue
                score = int(d.get("score", 0))
                if score < min_score:
                    continue
                title = (d.get("title") or "").strip()
                if not title:
                    continue
                # 外部リンク投稿は外部 URL を、自己投稿は permalink を採用
                permalink = "https://www.reddit.com" + d.get("permalink", "")
                external = (d.get("url_overridden_by_dest") or d.get("url") or "").strip()
                url = external if (external and not d.get("is_self")) else permalink
                created = d.get("created_utc")
                published = (
                    datetime.fromtimestamp(created, tz=timezone.utc) if created else None
                )
                items.append(
                    NewsItem(
                        source_type=SOURCE_REDDIT,
                        source=f"r/{sub}",
                        tier=tier,
                        original_title=title,
                        url=url,
                        published_at=published,
                        raw_summary=clip(d.get("selftext") or "", 400),
                        weight=weight,
                        engagement={
                            "score": score,
                            "comments": int(d.get("num_comments", 0)),
                            "permalink": permalink,
                        },
                    )
                )
        except Exception as exc:  # noqa: BLE001
            LOG.warning("r/%s: failed: %s", sub, exc)
    LOG.info("reddit: %d items", len(items))
    return items
