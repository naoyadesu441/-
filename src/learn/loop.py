"""フィードバック学習ループ。

3 つの責務を 1 モジュールに集約（純標準ライブラリのみ）:
  1. record_run()       — 各実行の候補ごとに実エンゲージメントを JSONL 追記
  2. analyze_history()  — 直近 N 日を集計し「伸びたキーワード/ジャンル」を算出
  3. format_trend_block() — Gemini プロンプトに差し込む日本語ブロックを生成

設計方針:
- 完全無料。すでに収集済みの engagement（Reddit upvote / HN points 等）だけを使う。
- engagement の読み取りは **ソース非依存**。将来 X コレクターが
  engagement={"likes":.., "views":..} を発行しても、コード変更なしで流れる。
- 履歴は news/ と同様にリポジトリにコミットする（history/engagement.jsonl）。
- 失敗・欠損に強い（破損行スキップ／履歴ゼロでもプロンプト不変）。
"""
from __future__ import annotations

import json
import logging
import math
import re
from datetime import date, datetime, timezone

from ..config import ROOT
from ..models import NewsItem

LOG = logging.getLogger("ai_news.learn")

HISTORY_PATH = ROOT / "history" / "engagement.jsonl"

# engagement dict のうち「指標ではない」キー（集計対象から除外）。
_NON_METRIC_KEYS = {"permalink", "url", "id", "guid"}
# コメント/リプライ系は会話量として 2 倍重み（rank._engagement_score と同じ思想）。
_COMMENT_KEYS = {"comments", "replies", "num_comments"}

_TITLE_CLIP = 200


# --------------------------------------------------------------------------
# ソース非依存のエンゲージメント読み取り
# --------------------------------------------------------------------------
def engagement_raw(it: NewsItem) -> float:
    """engagement 内の数値指標を汎用集計する。

    Reddit/HN: score + 2*comments。将来の X: likes + views + 2*replies 等。
    キー名に依存せず、コメント系だけ 2 倍にして合算する。
    """
    total = 0.0
    for key, val in (it.engagement or {}).items():
        if key in _NON_METRIC_KEYS:
            continue
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            continue
        weight = 2.0 if key in _COMMENT_KEYS else 1.0
        total += weight * float(val)
    return max(total, 0.0)


def engagement_score(it: NewsItem) -> float:
    """0〜1 の log 圧縮スコア。rank._engagement_score と同じカーブで横比較可能に。"""
    raw = engagement_raw(it)
    if raw <= 0:
        return 0.0
    return min(math.log10(raw + 1) / 3.0, 1.0)  # ~1000 で 1.0


def matched_keywords(text: str, keywords: list[str]) -> list[str]:
    """text にマッチした ai_keywords を返す。base.contains_ai_keyword と同じ一致規則。

    短いキーワード(<=3字)は単語境界、それ以外は部分一致。
    """
    low = (text or "").lower()
    hits: list[str] = []
    for kw in keywords or []:
        kw_low = kw.lower()
        if len(kw_low) <= 3:
            if re.search(r"\b" + re.escape(kw_low) + r"\b", low):
                hits.append(kw_low)
        else:
            if kw_low in low:
                hits.append(kw_low)
    return hits


# --------------------------------------------------------------------------
# (1) 記録
# --------------------------------------------------------------------------
def record_run(
    date_str: str,
    candidates: list[NewsItem],
    delivered: list[NewsItem],
    ai_keywords: list[str],
) -> None:
    """候補ごとに 1 行 JSONL を追記する。本実行時のみ呼ぶ（dry-run では呼ばない）。

    delivered（配信された item）には Gemini の category / buzz_score を付与する。
    同日の再実行は二重記録を避けるためスキップする。
    """
    if not candidates:
        LOG.info("learn.record: 候補なし — スキップ")
        return

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 同日 last-date ガード（手動再実行などで二重カウントしない）。
    if HISTORY_PATH.exists():
        last_date = _last_recorded_date()
        if last_date == date_str:
            LOG.info("learn.record: %s は記録済み — スキップ", date_str)
            return

    delivered_ids = {it.item_id for it in delivered}
    by_id = {it.item_id: it for it in delivered}

    lines: list[str] = []
    for it in candidates:
        text = f"{it.original_title} {it.raw_summary}"
        delivered_it = by_id.get(it.item_id)
        rec = {
            "kind": "candidate",
            "date": date_str,
            "item_id": it.item_id,
            "source_type": it.source_type,
            "tier": it.tier,
            "title": (it.original_title or "")[:_TITLE_CLIP],
            "keywords": matched_keywords(text, ai_keywords),
            "engagement_raw": round(engagement_raw(it), 2),
            "engagement_score": round(engagement_score(it), 4),
            "delivered": it.item_id in delivered_ids,
            "category": (delivered_it.category if delivered_it else "") or "",
            "buzz_score": int(delivered_it.buzz_score) if delivered_it else 0,
        }
        lines.append(json.dumps(rec, ensure_ascii=False))

    with HISTORY_PATH.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    LOG.info("learn.record: %s に %d 行を追記", date_str, len(lines))


def _last_recorded_date() -> str | None:
    """履歴ファイル末尾の有効レコードの date を返す（破損行は無視）。"""
    try:
        with HISTORY_PATH.open("r", encoding="utf-8") as fh:
            last = None
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    last = json.loads(line).get("date")
                except json.JSONDecodeError:
                    continue
            return last
    except OSError:
        return None


# --------------------------------------------------------------------------
# (2) 分析
# --------------------------------------------------------------------------
def _iter_records(window_days: int):
    """直近 window_days 日の有効レコードを yield する（破損行・欠損に耐性）。"""
    if not HISTORY_PATH.exists():
        return
    today = datetime.now(timezone.utc).date()
    with HISTORY_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            d = rec.get("date")
            if not d:
                continue
            try:
                rec_date = date.fromisoformat(d)
            except ValueError:
                continue
            age_days = (today - rec_date).days
            if age_days < 0 or age_days > window_days:
                continue
            rec["_age_days"] = age_days
            yield rec


def _recency_weight(age_days: int) -> float:
    """7 日半減期。直近を重く。"""
    return 0.5 ** (age_days / 7.0)


def analyze_history(window_days: int = 14, ai_keywords: list[str] | None = None) -> dict:
    """履歴を集計して伸び傾向を返す。履歴ゼロ/欠損でも安全に空を返す。"""
    kw_acc: dict[str, list[float]] = {}   # keyword -> [weighted_score, n]
    cat_acc: dict[str, list[float]] = {}  # category -> [weighted_score, n]
    cal_abs_err: list[float] = []         # |予測buzz - 実エンゲージ(1-5換算)|
    n_records = 0
    n_days: set[str] = set()

    for rec in _iter_records(window_days):
        n_records += 1
        n_days.add(rec.get("date", ""))
        w = _recency_weight(int(rec.get("_age_days", 0)))
        eng = float(rec.get("engagement_score", 0.0))
        weighted = w * eng

        for kw in rec.get("keywords", []) or []:
            slot = kw_acc.setdefault(kw, [0.0, 0.0])
            slot[0] += weighted
            slot[1] += 1

        cat = rec.get("category") or ""
        if rec.get("delivered") and cat:
            slot = cat_acc.setdefault(cat, [0.0, 0.0])
            slot[0] += weighted
            slot[1] += 1

        # calibration: 配信された item の予測 buzz(1-5) vs 実エンゲージ(0-1→1-5)
        if rec.get("delivered") and int(rec.get("buzz_score", 0)) > 0:
            actual_1_5 = 1 + 4 * eng
            cal_abs_err.append(abs(int(rec["buzz_score"]) - actual_1_5))

    # n>=2 でノイズ(単発)を抑制してソート
    keyword_scores = sorted(
        ((k, round(v[0], 4), int(v[1])) for k, v in kw_acc.items() if v[1] >= 2),
        key=lambda x: x[1],
        reverse=True,
    )
    category_scores = sorted(
        ((k, round(v[0], 4), int(v[1])) for k, v in cat_acc.items()),
        key=lambda x: x[1],
        reverse=True,
    )
    calibration = None
    if cal_abs_err:
        calibration = {
            "mean_abs_error": round(sum(cal_abs_err) / len(cal_abs_err), 2),
            "n": len(cal_abs_err),
        }

    return {
        "keyword_scores": keyword_scores,
        "category_scores": category_scores,
        "calibration": calibration,
        "days": len(n_days),
        "records": n_records,
    }


# --------------------------------------------------------------------------
# (3) プロンプト整形
# --------------------------------------------------------------------------
def format_trend_block(insight: dict, top_k: int = 8) -> str:
    """学習シグナルを日本語ブロックに整形。履歴ゼロなら空文字（プロンプト不変）。"""
    if not insight or insight.get("records", 0) == 0:
        return ""

    lines = [
        f"【学習シグナル（過去{insight.get('days', 0)}日の実エンゲージメント）】",
        "直近、海外SNS/掲示板で実際に伸びた傾向です。選定とbuzz_scoreの参考にしてください（最終判断は内容で）。",
    ]

    kws = [k for k, _s, _n in insight.get("keyword_scores", [])[:top_k]]
    if kws:
        lines.append("- よく伸びたキーワード: " + ", ".join(kws))

    cats = [k for k, _s, _n in insight.get("category_scores", [])[:5]]
    if cats:
        lines.append("- よく伸びたジャンル: " + " > ".join(cats))

    cal = insight.get("calibration")
    if cal:
        mae = cal["mean_abs_error"]
        if mae >= 1.5:
            tendency = "（予測が実態とズレ気味→慎重に）"
        else:
            tendency = "（おおむね妥当）"
        lines.append(f"- buzz_score予測の最近の平均誤差: {mae}/5 {tendency}")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# 任意: 履歴の剪定（自動実行しない。手動/CI 任意）
# --------------------------------------------------------------------------
def prune_history(keep_days: int = 90) -> int:
    """keep_days より古い行を削除する。残した行数を返す。手動運用想定。"""
    if not HISTORY_PATH.exists():
        return 0
    today = datetime.now(timezone.utc).date()
    kept: list[str] = []
    with HISTORY_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            try:
                d = date.fromisoformat(json.loads(s).get("date", ""))
            except (json.JSONDecodeError, ValueError):
                continue
            if (today - d).days <= keep_days:
                kept.append(s)
    with HISTORY_PATH.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(kept) + ("\n" if kept else ""))
    return len(kept)
