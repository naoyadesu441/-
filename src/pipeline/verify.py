"""裏取り層 — 各候補に verify_status と裏取りリンク素案を付与する。

ヒューリスティックで素案を作り、後段の Gemini が最終確定する（gemini が失敗した
場合はこの素案がそのまま採用される＝フォールバック）。

判定方針:
- tier=primary 自体 → 一次確認済（公式発表/論文）。
- tier=secondary 自体 → 二次。
- tier=social（Reddit/HN/YouTube）→ 候補集合内に同じ話題を扱う primary/secondary が
  あれば、その tier に引き上げ＋裏取りリンクを紐付け。無ければ未確認（噂）。
"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

from ..models import (
    NewsItem,
    TIER_PRIMARY,
    TIER_SECONDARY,
    TIER_SOCIAL,
    VERIFY_PRIMARY,
    VERIFY_SECONDARY,
    VERIFY_UNCONFIRMED,
)

LOG = logging.getLogger("ai_news.verify")

_MATCH = 0.55  # 別ソース間の話題一致しきい値（一次へ昇格しやすいよう緩め。誤マッチ注意）

# クロス言語マッチで無視する一般英単語（固有名詞ではないもの）。
_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "are", "was", "has",
    "have", "how", "new", "you", "your", "ai", "llm", "gpt", "all", "can", "now",
    "out", "its", "but", "not", "who", "why", "what", "when", "more", "into",
}

# 固有名詞ではない一般的なテック語。これらは「共通していても」話題一致の
# 決め手にはしない（"video model" 同士で別話題が誤って裏取り扱いされるのを防ぐ）。
_GENERIC = {
    "video", "videos", "audio", "image", "images", "model", "models", "modeling",
    "agent", "agents", "agentic", "builder", "tool", "tools", "app", "apps",
    "api", "apis", "data", "chat", "code", "coding", "open", "source", "update",
    "updates", "release", "releases", "feature", "features", "mode", "version",
    "launch", "launches", "system", "systems", "platform", "cloud", "online",
    "free", "beta", "pro", "plus", "max", "mini", "large", "small", "generation",
    "generative", "learning", "network", "neural", "vision", "voice", "text",
    "search", "assistant", "studio", "news", "report", "study", "paper",
    "research", "tech", "startup", "company", "users", "user", "announces",
    "announce", "announced", "introducing", "introduces", "unveils", "adds",
}


def _norm(title: str) -> str:
    return " ".join(title.lower().split())


def _proper_nouns(text: str) -> set[str]:
    """英数字トークン（3文字以上）を固有名詞候補として抽出する。

    日本語の見出しに混ざる英語の固有名詞（Anthropic, Mythos, ChatGPT 等）を拾い、
    日本語タイトルと英語タイトルのクロス言語照合に使う。
    """
    return {
        w.lower()
        for w in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text)
        if w.lower() not in _STOPWORDS
    }


def _corroborates(social_title: str, other: NewsItem) -> bool:
    """social 記事と other(一次/二次) が同じ話題かを近似判定。"""
    ratio = SequenceMatcher(None, _norm(social_title), _norm(other.original_title)).ratio()
    if ratio >= _MATCH:
        return True
    # クロス言語フォールバック: 日本語⇔英語など文字列が一致しなくても、
    # 共通トークンが2つ以上あり、かつ少なくとも1つが固有名詞らしい（汎用語でない）
    # 場合のみ同じ話題とみなす。"video"/"model" のような汎用語だけの一致では
    # 別企業の別発表を誤って一次確認済に昇格させてしまうため、決め手にしない。
    shared = _proper_nouns(social_title) & _proper_nouns(other.original_title)
    distinctive = shared - _GENERIC
    return len(shared) >= 2 and len(distinctive) >= 1


def assign_status(items: list[NewsItem]) -> list[NewsItem]:
    primaries = [it for it in items if it.tier == TIER_PRIMARY]
    secondaries = [it for it in items if it.tier == TIER_SECONDARY]

    for it in items:
        if it.tier == TIER_PRIMARY:
            it.verify_status = VERIFY_PRIMARY
            continue
        if it.tier == TIER_SECONDARY:
            it.verify_status = VERIFY_SECONDARY
            continue

        # social: 一次→二次の順で裏取りを探す
        match = next((p for p in primaries if _corroborates(it.original_title, p)), None)
        if match:
            it.verify_status = VERIFY_PRIMARY
            it.primary_source_url = match.url
            continue
        match = next((s for s in secondaries if _corroborates(it.original_title, s)), None)
        if match:
            it.verify_status = VERIFY_SECONDARY
            it.primary_source_url = match.url
            continue
        it.verify_status = VERIFY_UNCONFIRMED

    counts = {
        VERIFY_PRIMARY: sum(1 for i in items if i.verify_status == VERIFY_PRIMARY),
        VERIFY_SECONDARY: sum(1 for i in items if i.verify_status == VERIFY_SECONDARY),
        VERIFY_UNCONFIRMED: sum(1 for i in items if i.verify_status == VERIFY_UNCONFIRMED),
    }
    LOG.info("verify: %s", counts)
    return items
