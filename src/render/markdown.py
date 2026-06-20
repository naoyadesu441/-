"""日次リサーチ markdown を生成し、README の最新ブロックを差し替える。

markdown が「真実の記録」。Stage 2（台本生成）の入力にもなる。
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..config import ROOT
from ..models import NewsItem, VERIFY_BADGE
from ..pipeline.gemini import Digest

LOG = logging.getLogger("ai_news.render")

NEWS_DIR = ROOT / "news"
README = ROOT / "README.md"

LATEST_START = "<!--LATEST-->"
LATEST_END = "<!--/LATEST-->"


def _item_block(it: NewsItem) -> str:
    badge = VERIFY_BADGE.get(it.verify_status, it.verify_status or "")
    lines = [f"### [{it.source_type}][{badge}] {it.title_jp or it.original_title}"]
    if it.summary_jp:
        lines.append("")
        lines.append(it.summary_jp)
    lines.append("")
    meta = []
    if it.category:
        meta.append(f"カテゴリ: {it.category}")
    meta.append(f"ソース: {it.source}")
    if meta:
        lines.append(f"- {' / '.join(meta)}")
    lines.append(f"- 元リンク: {it.url}")
    if it.primary_source_url:
        lines.append(f"- 裏取りリンク: {it.primary_source_url}")
    perma = it.engagement.get("permalink")
    if perma and perma != it.url:
        lines.append(f"- 反応: {perma}")
    return "\n".join(lines)


def build_markdown(date_str: str, digest: Digest) -> str:
    parts = [
        f"# 海外AI最新トレンド — {date_str}",
        "",
        "## 今日のハイライト",
        "",
        digest.highlight,
        "",
        f"## ピックアップ（{len(digest.items)}件）",
        "",
    ]
    if not digest.items:
        parts.append("_対象期間内に該当ニュースがありませんでした。_")
    else:
        parts.append("\n\n".join(_item_block(it) for it in digest.items))
    parts.append("")
    parts.append(
        "---\n"
        "裏取りステータス: 🟢一次=公式/論文で確認済 ・ 🟡二次=信頼メディア報道 ・ "
        "🔴未確認=SNS/掲示板の噂レベル"
    )
    return "\n".join(parts) + "\n"


def write_news_file(date_str: str, content: str) -> Path:
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    path = NEWS_DIR / f"{date_str}.md"
    path.write_text(content, encoding="utf-8")
    LOG.info("wrote %s", path)
    return path


def update_readme(date_str: str, digest: Digest) -> None:
    """README の <!--LATEST--> ブロックを当日サマリで差し替える。

    README が無い／マーカーが無い場合は何もしない（main 側で初期 README を用意）。
    """
    if not README.exists():
        return
    text = README.read_text(encoding="utf-8")
    if LATEST_START not in text or LATEST_END not in text:
        return

    lines = [f"**最終更新: {date_str}**", "", f"> {digest.highlight}", ""]
    for it in digest.items[:10]:
        badge = VERIFY_BADGE.get(it.verify_status, "")
        lines.append(f"- [{it.source_type}][{badge}] {it.title_jp or it.original_title} — {it.url}")
    lines.append("")
    lines.append(f"全文: [`news/{date_str}.md`](news/{date_str}.md)")
    block = "\n".join(lines)

    pre = text.split(LATEST_START)[0]
    post = text.split(LATEST_END)[1]
    new_text = f"{pre}{LATEST_START}\n{block}\n{LATEST_END}{post}"
    README.write_text(new_text, encoding="utf-8")
    LOG.info("updated README LATEST block")
