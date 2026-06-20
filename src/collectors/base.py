"""コレクター共通のヘルパー。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import struct_time
from typing import Optional

LOG = logging.getLogger("ai_news.collect")


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def struct_to_utc(t: Optional[struct_time]) -> Optional[datetime]:
    """feedparser の published_parsed (struct_time, UTC) を aware datetime に。"""
    if not t:
        return None
    try:
        return datetime(*t[:6], tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def clip(text: Optional[str], limit: int) -> str:
    if not text:
        return ""
    text = " ".join(text.split())  # 連続空白・改行を畳む
    return text if len(text) <= limit else text[: limit - 1] + "…"


def contains_ai_keyword(text: str, keywords: list[str]) -> bool:
    import re
    low = text.lower()
    for kw in keywords:
        if len(kw) <= 3:
            if re.search(r'\b' + re.escape(kw) + r'\b', low):
                return True
        else:
            if kw in low:
                return True
    return False
