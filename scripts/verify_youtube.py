#!/usr/bin/env python3
"""YouTube の channel_id を検証する（読み取り専用）。

sources.yaml の各 youtube チャンネルについて RSS を取得し、フィードの author 名を表示する。
表示名が想定チャンネルと一致するか目視確認する。⚠ 付き(Lex Fridman / Nate Herk)を特に確認。

使い方:  python scripts/verify_youtube.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feedparser  # noqa: E402

from src.config import Http, load_sources  # noqa: E402

FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"


def main() -> None:
    src = load_sources()
    http = Http()
    print(f"{'設定名':<22} {'channel_id':<26} {'取得author / 状態'}")
    print("-" * 80)
    for ch in src.get("youtube", []):
        name = ch.get("name", "?")
        cid = (ch.get("channel_id") or "").strip()
        if not cid:
            print(f"{name:<22} {'(未設定)':<26} ⚠ channel_id 未設定")
            continue
        try:
            resp = http.get(FEED.format(cid=cid))
            if resp.status_code != 200:
                print(f"{name:<22} {cid:<26} ❌ HTTP {resp.status_code}")
                continue
            parsed = feedparser.parse(resp.content)
            author = parsed.feed.get("title") or parsed.feed.get("author") or "(不明)"
            n = len(parsed.entries)
            print(f"{name:<22} {cid:<26} ✅ {author} ({n}本)")
        except Exception as exc:  # noqa: BLE001
            print(f"{name:<22} {cid:<26} ❌ {exc}")


if __name__ == "__main__":
    main()
