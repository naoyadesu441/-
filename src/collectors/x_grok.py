"""X（Twitter）/ Grok バズシグナル — 将来用の安全な無効スタブ。

【重要】X API も Grok API も 2026 年時点で従量課金（カード登録必須）。
このプロジェクトの絶対条件「完全無料・勝手な課金は絶対NG」を守るため、
既定では `enabled: false` で **一切のネットワーク呼び出しを行わず []** を返す。

有効化条件（両方必要）:
  1. sources.yaml の x_grok.enabled を true にする
  2. cfg["secret_env"]（既定 X_BEARER_TOKEN）で指定した環境変数を設定する

実取得は未実装。将来実装する際は NewsItem(source_type="X",
engagement={"likes":.., "views":.., "reposts":..}) を発行すれば、
学習ループ（src/learn/loop.py）の汎用エンゲージメント集計にそのまま流れる。
"""
from __future__ import annotations

import logging

from ..config import Http, get_secret
from ..models import NewsItem

LOG = logging.getLogger("ai_news.collect.x_grok")


def collect(http: Http, cfg: dict) -> list[NewsItem]:
    """既定で no-op。enabled かつ secret 設定済みのときだけ将来の取得を行う。"""
    if not cfg.get("enabled", False):
        # 既定パス: ネットワーク呼び出しゼロ・課金リスクゼロ。
        return []

    secret_env = cfg.get("secret_env", "X_BEARER_TOKEN")
    token = get_secret(secret_env)
    if not token:
        LOG.info("x_grok: enabled だが %s 未設定 — 収集しません（呼び出しなし）", secret_env)
        return []

    # 課金を伴う実取得は未実装。誤って課金が発生しないよう、ここでは何もしない。
    LOG.warning("x_grok: 実取得は未実装のため [] を返します（将来実装）")
    return []
