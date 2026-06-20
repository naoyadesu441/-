"""汎用 RSS/Atom コレクター。

feeds / newsletters / producthunt / note / youtube はすべて RSS なので、ここに
共通のパーサを置き、各呼び出し側が source_type と抽出条件を渡す。
"""
from __future__ import annotations

import html
import logging

import feedparser

from ..config import Http
from ..models import NewsItem
from .base import clip, contains_ai_keyword, struct_to_utc

LOG = logging.getLogger("ai_news.collect.rss")


def _strip_html(text: str) -> str:
    """RSS summary に混ざる簡易 HTML を雑に除去（依存を増やさない範囲で）。"""
    import re

    text = re.sub(r"<[^>]+>", " ", text or "")
    return html.unescape(text)


def fetch_feed(
    http: Http,
    *,
    name: str,
    url: str,
    source_type: str,
    tier: str,
    weight: float,
    ai_keywords: list[str] | None = None,
    require_ai: bool = False,
    max_items: int = 30,
) -> list[NewsItem]:
    """1 本の RSS/Atom フィードを取得して NewsItem 化する。

    require_ai=True の場合、タイトル＋要約に ai_keywords が含まれる項目のみ採用
    （Product Hunt や Fireship のような汎用フィードの絞り込み用）。
    """
    items: list[NewsItem] = []
    try:
        resp = http.get(url)
        if resp.status_code != 200:
            LOG.warning("%s: HTTP %s", name, resp.status_code)
            return items
        parsed = feedparser.parse(resp.content)
        if parsed.bozo and not parsed.entries:
            LOG.warning("%s: feed parse error (%s)", name, getattr(parsed, "bozo_exception", ""))
            return items
        for entry in parsed.entries[:max_items]:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue
            summary = _strip_html(entry.get("summary") or entry.get("description") or "")
            if require_ai and ai_keywords and not contains_ai_keyword(
                f"{title} {summary}", ai_keywords
            ):
                continue
            published = struct_to_utc(
                entry.get("published_parsed") or entry.get("updated_parsed")
            )
            item = NewsItem(
                source_type=source_type,
                source=name,
                tier=tier,
                original_title=title,
                url=link,
                published_at=published,
                raw_summary=clip(summary, 600),
                weight=weight,
            )
            items.append(item)
    except Exception as exc:  # noqa: BLE001 — 1フィードの失敗で全体を止めない
        LOG.warning("%s: fetch failed: %s", name, exc)
    LOG.info("%s: %d items", name, len(items))
    return items
