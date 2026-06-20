"""オーケストレーター。

collect → normalize → dedupe → rank(preselect) → verify → gemini → render → deliver
各段階を try/except で独立保護（graceful degradation）。markdown が真実の記録。

使い方:
  python -m src.main              本実行（収集→要約→render→配信→※commitはCI側）
  python -m src.main --dry-run    収集→要約→render結果と配信payloadをstdout出力（送信なし）
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Http, load_dotenv, load_sources, setup_logging
from .collectors import (
    arxiv,
    hackernews,
    producthunt,
    reddit,
    youtube_rss,
)
from .collectors.feeds_rss import fetch_feed
from .models import NewsItem, SOURCE_NEWS, SOURCE_NEWSLETTER, VERIFY_BADGE, VERIFY_PRIMARY, VERIFY_SECONDARY, TIER_PRIMARY
from .pipeline import dedupe, gemini, normalize, rank, verify
from .render import markdown
from .deliver import discord, notion

LOG = logging.getLogger("ai_news.main")
JST = ZoneInfo("Asia/Tokyo")


def _safe(label: str, fn, default):
    """1 段階を保護実行。失敗しても default を返して全体を継続する。"""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("[%s] 失敗のためスキップ: %s", label, exc)
        return default


def collect_all(http: Http, src: dict) -> list[NewsItem]:
    kw = src.get("ai_keywords", [])
    items: list[NewsItem] = []

    items += _safe("youtube", lambda: youtube_rss.collect(http, src.get("youtube", []), kw), [])
    items += _safe("reddit", lambda: reddit.collect(http, src.get("reddit", {})), [])
    items += _safe("hackernews", lambda: hackernews.collect(http, src.get("hackernews", {}), kw), [])
    items += _safe(
        "producthunt", lambda: producthunt.collect(http, src.get("producthunt", {}), kw), []
    )
    items += _safe("arxiv", lambda: arxiv.collect(http, src.get("arxiv", {})), [])

    # feeds + newsletters（汎用 RSS）
    for feed in src.get("feeds", []) + src.get("newsletters", []):
        if not feed.get("enabled", True):
            continue
        stype = SOURCE_NEWSLETTER if feed in src.get("newsletters", []) else SOURCE_NEWS
        items += _safe(
            f"feed:{feed['name']}",
            lambda f=feed, st=stype: fetch_feed(
                http,
                name=f["name"],
                url=f["url"],
                source_type=st,
                tier=f.get("tier", "secondary"),
                weight=float(f.get("weight", 1.0)),
                ai_keywords=kw,
                # 汎用フィード(Ars Technica / Wired Japan / MIT Tech Review 等)は
                # require_ai:true でAI関連のみに絞る。Gemini不在のフォールバック時に
                # 非AI記事が「AIニュース」に混入するのを防ぐ。AI特化フィードは false でよい。
                require_ai=f.get("require_ai", False),
                max_items=20,
            ),
            [],
        )

    # note（日本語、任意）
    note = src.get("note", {})
    for user in note.get("users", []):
        items += _safe(
            f"note:{user}",
            lambda u=user: fetch_feed(
                http,
                name=f"note/{u}",
                url=f"https://note.com/{u}/rss",
                source_type=SOURCE_NEWS,
                tier=note.get("tier", "social"),
                weight=float(note.get("weight", 0.7)),
                ai_keywords=kw,
                require_ai=True,
                max_items=10,
            ),
            [],
        )

    LOG.info("collect_all: %d items (raw)", len(items))
    return items


def run(dry_run: bool) -> int:
    setup_logging()
    load_dotenv()
    src = load_sources()
    http = Http()
    date_str = datetime.now(JST).strftime("%Y-%m-%d")
    LOG.info("=== Daily AI News %s (dry_run=%s) ===", date_str, dry_run)

    # 1) collect
    raw = collect_all(http, src)

    # 2) normalize（URL正規化・ID付与・時間窓）
    items = _safe(
        "normalize",
        lambda: normalize.normalize(raw, int(src.get("window_hours", 26))),
        raw,
    )
    # 3) dedupe
    items = _safe("dedupe", lambda: dedupe.dedupe(items), items)
    # 4) rank → preselect
    candidates = _safe("rank", lambda: rank.preselect(items, 80), items[:80])
    # 5) verify（裏取り素案）
    candidates = _safe("verify", lambda: verify.assign_status(candidates), candidates)
    # 6) gemini（選定＋日本語化＋裏取り確定）。失敗時は内部でフォールバック。
    digest = _safe(
        "gemini",
        lambda: gemini.summarize(http, candidates),
        gemini._fallback(candidates),
    )

    # 6.5) 一次優先 + 二次補填 → バズ予測上位10件に絞る
    BUZZ_TOP_N = 10
    n_before = len(digest.items)
    primary_items = [
        it for it in digest.items
        if it.verify_status == VERIFY_PRIMARY
        and (it.tier == TIER_PRIMARY or it.primary_source_url)
    ]
    if len(primary_items) < BUZZ_TOP_N:
        secondary_items = [
            it for it in digest.items
            if it.verify_status == VERIFY_SECONDARY and it not in primary_items
        ]
        secondary_items.sort(key=lambda x: (x.buzz_score, x.score), reverse=True)
        primary_items += secondary_items[:BUZZ_TOP_N - len(primary_items)]
    primary_items.sort(key=lambda x: (x.buzz_score, x.score), reverse=True)
    digest.items = primary_items[:BUZZ_TOP_N]
    for idx, it in enumerate(digest.items, start=1):
        it.rank = idx
    LOG.info("一次+二次補填→バズTOP%d: %d → %d 件", BUZZ_TOP_N, n_before, len(digest.items))
    if not digest.items:
        digest.highlight = "本日は確認済のAIニュースはありませんでした。"

    # 7) render（常に markdown を作る＝真実の記録）
    md = markdown.build_markdown(date_str, digest)

    if dry_run:
        print("\n========== news/%s.md ==========\n" % date_str)
        print(md)
        print("\n========== Discord payloads ==========\n")
        print(json.dumps(discord.render_payloads(digest, date_str), ensure_ascii=False, indent=2))
        print("\n========== Notion payloads ==========\n")
        print(json.dumps(notion.render_payloads(digest, date_str), ensure_ascii=False, indent=2))
        print("\n[dry-run] 送信もファイル書き込みもコミットも行いません。")
        return 0

    # 本実行: ファイル書き出し → README 更新 → 配信
    _safe("write_news", lambda: markdown.write_news_file(date_str, md), None)
    _safe("update_readme", lambda: markdown.update_readme(date_str, digest), None)
    _safe("discord", lambda: discord.deliver(http, digest, date_str), None)
    _safe("notion", lambda: notion.deliver(http, digest, date_str), None)

    LOG.info("=== 完了: %d 件 ===", len(digest.items))
    for it in digest.items:
        LOG.info("  [%s] %s", VERIFY_BADGE.get(it.verify_status, ""), it.title_jp)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="海外AI最新トレンド 毎日リサーチ自動集約")
    ap.add_argument("--dry-run", action="store_true", help="送信・書込・commit せず内容を確認")
    args = ap.parse_args()
    raise SystemExit(run(args.dry_run))


if __name__ == "__main__":
    main()
