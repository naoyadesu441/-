"""Notion データベースへ蓄積する（1 項目 = 1 ページ）。

蓄積したデータは将来のアカウント配信に再利用する想定。
REST API（鍵: NOTION_TOKEN）を直接叩く。SDK は使わない。

事前に Notion 側で DB を作成し、インテグレーションに共有しておくこと。
必要プロパティ（README に手順記載）:
  Title (JP)=title, OriginalTitle=rich_text, Date=date, Category=select,
  SourceType=select, Tier=select, VerifyStatus=select, URL=url,
  PrimarySource=url, SummaryJP=rich_text, Score=number, Rank=number
"""
from __future__ import annotations

import logging
import time

from ..config import Http, get_secret
from ..models import NewsItem
from ..pipeline.gemini import Digest

LOG = logging.getLogger("ai_news.deliver.notion")

API = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"
RICH_TEXT_LIMIT = 2000


def _rt(text: str) -> dict:
    return {"rich_text": [{"text": {"content": (text or "")[:RICH_TEXT_LIMIT]}}]}


def _select(name: str) -> dict:
    # Notion の select は名前にカンマ不可。安全のため除去。
    return {"select": {"name": (name or "その他").replace(",", " ")[:100]}}


def _properties(it: NewsItem, date_str: str) -> dict:
    props = {
        "Title (JP)": {"title": [{"text": {"content": (it.title_jp or it.original_title)[:200]}}]},
        "OriginalTitle": _rt(it.original_title),
        "Date": {"date": {"start": date_str}},
        "Category": _select(it.category or "その他"),
        "SourceType": _select(it.source_type),
        "Tier": _select(it.tier),
        "VerifyStatus": _select(it.verify_status),
        "URL": {"url": it.url or None},
        "SummaryJP": _rt(it.summary_jp),
        "Score": {"number": round(float(it.score), 3)},
        "Rank": {"number": int(it.rank)},
    }
    if it.primary_source_url:
        props["PrimarySource"] = {"url": it.primary_source_url}
    return props


def deliver(http: Http, digest: Digest, date_str: str) -> None:
    token = get_secret("NOTION_TOKEN")
    db_id = get_secret("NOTION_DATABASE_ID")
    if not token or not db_id:
        LOG.warning("NOTION_TOKEN / NOTION_DATABASE_ID 未設定 — Notion配信スキップ")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    ok = 0
    for it in digest.items:
        payload = {"parent": {"database_id": db_id}, "properties": _properties(it, date_str)}
        try:
            resp = http.session.post(API, headers=headers, json=payload, timeout=30)
            if resp.status_code == 429:
                time.sleep(float(resp.headers.get("Retry-After", 1.0)))
                resp = http.session.post(API, headers=headers, json=payload, timeout=30)
            if resp.status_code >= 300:
                LOG.warning("Notion HTTP %s: %s", resp.status_code, resp.text[:200])
            else:
                ok += 1
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Notion 投入失敗: %s", exc)
        time.sleep(0.35)
    LOG.info("Notion: %d/%d 件投入", ok, len(digest.items))


def render_payloads(digest: Digest, date_str: str) -> list[dict]:
    """dry-run 用: 送信せずページ payload を返す。"""
    return [
        {"parent": {"database_id": "<DB>"}, "properties": _properties(it, date_str)}
        for it in digest.items
    ]
