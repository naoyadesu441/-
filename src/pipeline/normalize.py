"""URL 正規化と時間窓フィルタ。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from ..models import NewsItem

LOG = logging.getLogger("ai_news.normalize")

# 除去するトラッキング系クエリパラメータ
_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"fbclid", "gclid", "ref", "ref_src", "ref_url", "mc_cid", "mc_eid"}


def normalize_url(url: str) -> str:
    if not url:
        return url
    try:
        parts = urlsplit(url.strip())
        scheme = parts.scheme.lower() or "https"
        netloc = parts.netloc.lower()
        # トラッキングパラメータを除去
        query = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=False)
            if not k.lower().startswith(_TRACKING_PREFIXES) and k.lower() not in _TRACKING_KEYS
        ]
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((scheme, netloc, path, urlencode(query), ""))
    except Exception:  # noqa: BLE001
        return url


def normalize(items: list[NewsItem], window_hours: int) -> list[NewsItem]:
    """URL を正規化し、ID を確定し、時間窓でフィルタする。

    published_at が無いアイテムは（新着の RSS 等で日付欠落のことがあるため）
    保守的に残す。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    out: list[NewsItem] = []
    for it in items:
        it.url = normalize_url(it.url)
        it.ensure_id()
        if it.published_at is not None and it.published_at < cutoff:
            continue
        out.append(it)
    LOG.info("normalize: %d -> %d (window=%dh)", len(items), len(out), window_hours)
    return out
