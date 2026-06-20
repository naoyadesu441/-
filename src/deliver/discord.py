"""Discord Webhook へ通知する。

Discord の制限: 1メッセージ embed 最大10個 / 全 embed 合計 6000字。
安全側に 1メッセージ最大5 embed・合計 ≤5500字でバッチ送信する。
"""
from __future__ import annotations

import logging
import time

from ..config import Http, get_secret
from ..models import NewsItem, VERIFY_BADGE
from ..pipeline.gemini import Digest

LOG = logging.getLogger("ai_news.deliver.discord")

MAX_EMBEDS = 5
MAX_TOTAL_CHARS = 5500
EMBED_DESC_LIMIT = 1000

# verify_status → embed の左色帯
COLOR = {
    "一次確認済": 0x2ECC71,  # green
    "二次": 0xF1C40F,        # yellow
    "未確認": 0xE74C3C,      # red
}


_BUZZ_LABEL = {5: "🔥確実バズ", 4: "🔥高バズ", 3: "✨そこそこ", 2: "📌ニッチ", 1: "📄専門的"}


def _embed(it: NewsItem) -> dict:
    badge = VERIFY_BADGE.get(it.verify_status, "")
    buzz = _BUZZ_LABEL.get(it.buzz_score, "")
    desc = it.summary_jp or it.raw_summary or ""
    if it.buzz_score and it.buzz_reason:
        desc += f"\n**SNSバズ予測: {buzz}** — {it.buzz_reason}"
    if it.primary_source_url:
        desc += f"\n🔎 裏取り: {it.primary_source_url}"
    desc = desc[:EMBED_DESC_LIMIT]
    footer = " / ".join(filter(None, [it.source, it.category, f"#{it.rank}"]))
    return {
        "title": f"[{badge}] {(it.title_jp or it.original_title)[:240]}",
        "url": it.url,
        "description": desc,
        "color": COLOR.get(it.verify_status, 0x95A5A6),
        "footer": {"text": footer[:2048]},
    }


def _embed_len(e: dict) -> int:
    return len(e.get("title", "")) + len(e.get("description", "")) + len(
        e.get("footer", {}).get("text", "")
    )


def _post(http: Http, webhook: str, payload: dict) -> None:
    for attempt in range(3):
        resp = http.session.post(f"{webhook}?wait=true", json=payload, timeout=30)
        if resp.status_code == 429:
            retry = float(resp.json().get("retry_after", 1.0))
            time.sleep(min(retry, 10))
            continue
        if resp.status_code >= 300:
            LOG.warning("Discord HTTP %s: %s", resp.status_code, resp.text[:200])
        return
    LOG.warning("Discord: リトライ上限到達")


def deliver(http: Http, digest: Digest, date_str: str) -> None:
    webhook = get_secret("DISCORD_WEBHOOK_URL")
    if not webhook:
        LOG.warning("DISCORD_WEBHOOK_URL 未設定 — Discord配信スキップ")
        return

    # 先頭メッセージ: ハイライト
    header = f"**🗞 海外AI最新トレンド {date_str}**\n{digest.highlight}"[:2000]
    _post(http, webhook, {"content": header})
    time.sleep(0.4)

    # embed をバッチ送信
    batch: list[dict] = []
    total = 0
    for it in digest.items:
        e = _embed(it)
        elen = _embed_len(e)
        if batch and (len(batch) >= MAX_EMBEDS or total + elen > MAX_TOTAL_CHARS):
            _post(http, webhook, {"embeds": batch})
            time.sleep(0.4)
            batch, total = [], 0
        batch.append(e)
        total += elen
    if batch:
        _post(http, webhook, {"embeds": batch})
    LOG.info("Discord: 配信完了 (%d items)", len(digest.items))


def render_payloads(digest: Digest, date_str: str) -> list[dict]:
    """dry-run 用: 送信せずペイロードを返す。"""
    payloads: list[dict] = [{"content": f"**🗞 {date_str}**\n{digest.highlight}"}]
    batch: list[dict] = []
    total = 0
    for it in digest.items:
        e = _embed(it)
        elen = _embed_len(e)
        if batch and (len(batch) >= MAX_EMBEDS or total + elen > MAX_TOTAL_CHARS):
            payloads.append({"embeds": batch})
            batch, total = [], 0
        batch.append(e)
        total += elen
    if batch:
        payloads.append({"embeds": batch})
    return payloads
