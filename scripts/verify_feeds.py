#!/usr/bin/env python3
"""RSS フィードの取得可否を検証する（読み取り専用）。

sources.yaml の feeds / newsletters / producthunt / note を取得し、HTTP ステータス・
bozo(パース異常)・エントリ件数・最新日付を表示する。enabled:false のものも確認できる。
取得できないニュースレター等は sources.yaml で enabled:false のままにする判断材料にする。

使い方:  python scripts/verify_feeds.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feedparser  # noqa: E402

from src.config import Http, load_sources  # noqa: E402


def _check(http: Http, name: str, url: str, enabled: bool) -> None:
    flag = "on " if enabled else "off"
    try:
        resp = http.get(url)
        if resp.status_code != 200:
            print(f"[{flag}] {name:<26} ❌ HTTP {resp.status_code}  {url}")
            return
        parsed = feedparser.parse(resp.content)
        n = len(parsed.entries)
        latest = ""
        if n:
            e = parsed.entries[0]
            latest = e.get("published") or e.get("updated") or ""
        bozo = "⚠bozo" if (parsed.bozo and not n) else "ok"
        mark = "✅" if n else "❌"
        print(f"[{flag}] {name:<26} {mark} {n:>3}件 {bozo:<6} {latest:<31} {url}")
    except Exception as exc:  # noqa: BLE001
        print(f"[{flag}] {name:<26} ❌ {exc}  {url}")


def main() -> None:
    src = load_sources()
    http = Http()
    print("RSS フィード検証（enabled:on/off 両方を確認）")
    print("-" * 100)

    for feed in src.get("feeds", []):
        _check(http, feed["name"], feed["url"], feed.get("enabled", True))
    print("--- newsletters ---")
    for feed in src.get("newsletters", []):
        _check(http, feed["name"], feed["url"], feed.get("enabled", True))
    print("--- product hunt ---")
    ph = src.get("producthunt", {})
    if ph:
        _check(http, "Product Hunt", ph["url"], ph.get("enabled", True))
    print("--- note ---")
    note = src.get("note", {})
    for user in note.get("users", []):
        _check(http, f"note/{user}", f"https://note.com/{user}/rss", True)


if __name__ == "__main__":
    main()
