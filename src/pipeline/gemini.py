"""Gemini 呼び出し（1 日 1 コール）。

無料枠（Google AI Studio）の gemini-2.5-flash を REST で叩く。SDK は使わず、
無料枠の挙動（モデル名・認証ヘッダ・構造化出力）を明示制御する。

- 入力: 事前ランク上位の候補リスト（id を保持）。
- 出力: 構造化 JSON。highlight ＋ 選定 items（id で元 NewsItem に再結合）。
- URL はモデルに生成させない。裏取りリンクは primary_source_id（候補内 id）で受け取り、
  こちら側で url に解決する。
- 失敗時（429/503/解析不能）はヒューリスティックのフォールバックを使う。
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

from ..config import Http, get_secret
from ..models import (
    NewsItem,
    VERIFY_PRIMARY,
    VERIFY_SECONDARY,
    VERIFY_UNCONFIRMED,
    VERIFY_BADGE,
)

LOG = logging.getLogger("ai_news.gemini")

MODEL = "gemini-2.5-flash"
ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

MAX_CANDIDATES = 80
RAW_SUMMARY_LIMIT = 300
TARGET_MIN, TARGET_MAX = 10, 20

_VALID_STATUS = {VERIFY_PRIMARY, VERIFY_SECONDARY, VERIFY_UNCONFIRMED}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "highlight": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title_jp": {"type": "string"},
                    "summary_jp": {"type": "string"},
                    "category": {"type": "string"},
                    "verify_status": {
                        "type": "string",
                        "enum": [VERIFY_PRIMARY, VERIFY_SECONDARY, VERIFY_UNCONFIRMED],
                    },
                    "primary_source_id": {"type": "string"},
                    "score": {"type": "number"},
                },
                "required": ["id", "title_jp", "summary_jp", "category", "verify_status"],
            },
        },
    },
    "required": ["highlight", "items"],
}

PROMPT = """\
あなたは日本語のAIニュースキュレーターです。海外のAI関連の候補ニュースを渡します。

【最重要ポリシー】配信するのは「一次確認済」のニュースだけです。
- 一次確認済 = 公式発表・公式ブログ・論文など、一次ソースで内容が確認できるもの。
- 候補の tier が "primary" のもの、または社会系(social)/二次(secondary)の話題でも
  候補集合内に同じ話題を扱う "primary" ソースがあって裏取りできるものだけを採用する。
- 信頼メディアのみの報道（二次）、SNS/掲示板の噂（未確認）は**選ばない**。
- 目標は{tmin}件以上。候補に tier="primary" が多数あるはず（公式ブログ・論文含む）。
  積極的に一次を拾い、{tmin}〜{tmax}件を目指す。どうしても一次が{tmin}件に満たない場合のみ、少数でよい。

採用したものについて、重要度・話題性・新規性が高い順に{tmin}〜{tmax}件を選び、整理してください。

厳守事項:
- 各候補の "id" は絶対に変更せず、選んだものはその id をそのまま返す。
- title_jp: 日本語の見出し（40字以内、誇張しない）。
- summary_jp: 日本語要約（120〜200字。何が・どこが・なぜ重要かを端的に）。
- category: 次から1つ — モデル/プロダクト/研究/資金調達/規制・倫理/ツール/その他。
- verify_status: 採用するものは必ず "一次確認済" とする（"二次"・"未確認" は選定しない）。
- primary_source_id: 裏取りに使った一次候補の id を必ず入れる。tier が "primary" 自身の
  場合は自分の id でよい。URLやタイトルを創作しないこと。裏取りできないものは採用しない。
- highlight: 今日のAI界隈の要点を2〜3文の日本語でまとめる（一次確認済の範囲で）。

候補(JSON):
{candidates}
"""


@dataclass
class Digest:
    highlight: str
    items: list[NewsItem]


def _candidate_payload(items: list[NewsItem]) -> list[dict]:
    payload = []
    for it in items[:MAX_CANDIDATES]:
        payload.append(
            {
                "id": it.item_id,
                "source_type": it.source_type,
                "source": it.source,
                "tier": it.tier,
                "title": it.original_title,
                "summary": it.raw_summary[:RAW_SUMMARY_LIMIT],
                "engagement": it.engagement.get("score", 0),
                "suggested_status": it.verify_status,
            }
        )
    return payload


def _fallback(items: list[NewsItem], n: int = TARGET_MAX) -> Digest:
    """Gemini 不使用/失敗時。一次確認済のみをヒューリスティック上位 N で掲載。"""
    # ポリシー: 配信は一次確認済のみ。二次・未確認はフォールバックでも採用しない。
    selected = [it for it in items if it.verify_status == VERIFY_PRIMARY][:n]
    for it in selected:
        if not it.title_jp:
            it.title_jp = it.original_title
        if not it.summary_jp:
            it.summary_jp = it.raw_summary or "（要約なし。元リンクを参照）"
        if not it.category:
            it.category = "その他"
    if not selected:
        return Digest(
            highlight="本日は一次確認済（公式発表・論文）のAIニュースはありませんでした。",
            items=[],
        )
    highlight = (
        f"本日の一次確認済AIニュースを{len(selected)}件掲載。"
        "AI要約は利用できなかったため、ヒューリスティック順で掲載しています。"
    )
    return Digest(highlight=highlight, items=selected)


def summarize(http: Http, items: list[NewsItem]) -> Digest:
    """Gemini で選定＋日本語化。失敗時はフォールバック。"""
    if not items:
        return Digest(highlight="本日は対象期間内に該当ニュースがありませんでした。", items=[])
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        LOG.warning("GEMINI_API_KEY 未設定 — フォールバックを使用")
        return _fallback(items)

    by_id = {it.item_id: it for it in items}
    prompt = PROMPT.format(
        tmin=TARGET_MIN,
        tmax=TARGET_MAX,
        candidates=json.dumps(_candidate_payload(items), ensure_ascii=False),
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0.3,
        },
    }
    url = ENDPOINT.format(model=MODEL)
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    for attempt in range(2):
        try:
            resp = http.session.post(url, headers=headers, json=body, timeout=60)
            if resp.status_code in (429, 503) and attempt == 0:
                LOG.warning("Gemini %s — リトライします", resp.status_code)
                time.sleep(3)
                continue
            if resp.status_code != 200:
                LOG.warning("Gemini HTTP %s: %s", resp.status_code, resp.text[:200])
                break
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            return _reconcile(parsed, by_id, items)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Gemini 呼び出し失敗(attempt %d): %s", attempt, exc)
            if attempt == 0:
                time.sleep(3)
                continue
            break
    LOG.warning("Gemini 利用不可 — フォールバックを使用")
    return _fallback(items)


def _reconcile(parsed: dict, by_id: dict[str, NewsItem], all_items: list[NewsItem]) -> Digest:
    """Gemini の出力を id で元 NewsItem に再結合する。"""
    selected: list[NewsItem] = []
    for entry in parsed.get("items", []):
        it = by_id.get(entry.get("id"))
        if it is None:
            continue  # 創作 id は破棄
        it.title_jp = (entry.get("title_jp") or it.original_title).strip()
        it.summary_jp = (entry.get("summary_jp") or it.raw_summary).strip()
        it.category = (entry.get("category") or "その他").strip()
        status = entry.get("verify_status", "").strip()
        if status in _VALID_STATUS:
            it.verify_status = status
        # Gemini の判定を最終とする。verify層が付けたヒューリスティックの裏取りリンクは
        # 一旦クリアし、Gemini が有効な primary_source_id を返したときだけ再設定する
        # （未確認に格下げされたのに裏取りリンクが残る、を防ぐ）。
        it.primary_source_url = ""
        psid = (entry.get("primary_source_id") or "").strip()
        if psid and psid in by_id and psid != it.item_id:
            it.primary_source_url = by_id[psid].url
        if entry.get("score") is not None:
            try:
                it.score = float(entry["score"])
            except (TypeError, ValueError):
                pass
        selected.append(it)

    if not selected:
        LOG.warning("Gemini 出力に有効 item 無し — フォールバック")
        return _fallback(all_items)

    # score（あれば）で並べ替えて rank を振り直す
    selected.sort(key=lambda x: x.score, reverse=True)
    for idx, it in enumerate(selected, start=1):
        it.rank = idx
    highlight = (parsed.get("highlight") or "").strip() or "本日のAI注目トピックをまとめました。"
    LOG.info("gemini: %d items selected", len(selected))
    return Digest(highlight=highlight, items=selected)


# --- CLI: 実コール1回でJSON＋裏取り解析を確認する（検証用） ---
def _cli() -> None:
    import argparse
    from ..config import load_dotenv, setup_logging

    setup_logging()
    load_dotenv()
    ap = argparse.ArgumentParser(description="Gemini summarize の単体検証")
    ap.add_argument("--sample", required=True, help="候補 NewsItem の JSON 配列パス")
    args = ap.parse_args()

    with open(args.sample, encoding="utf-8") as fh:
        raw = json.load(fh)
    items = []
    for d in raw:
        it = NewsItem(
            source_type=d.get("source_type", "News"),
            source=d.get("source", "test"),
            tier=d.get("tier", "secondary"),
            original_title=d["original_title"],
            url=d.get("url", "https://example.com"),
            raw_summary=d.get("raw_summary", ""),
            weight=float(d.get("weight", 1.0)),
            verify_status=d.get("verify_status", ""),
        )
        it.ensure_id()
        items.append(it)

    digest = summarize(Http(), items)
    print("HIGHLIGHT:", digest.highlight)
    for it in digest.items:
        badge = VERIFY_BADGE.get(it.verify_status, it.verify_status)
        print(f"- [{it.source_type}][{badge}] {it.title_jp} ({it.category})")
        print(f"    {it.summary_jp}")
        print(f"    url={it.url} primary={it.primary_source_url}")


if __name__ == "__main__":
    _cli()
