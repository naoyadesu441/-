"""設定読み込みとHTTPユーティリティ。

- sources.yaml を読む（データとコードを分離）。
- .env はローカル用に best-effort で読む（依存追加を避けるため自前パーサ）。
- 全ネットワーク呼び出しで共有する requests.Session（timeout + 簡易リトライ）を提供。
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import requests
import yaml

LOG = logging.getLogger("ai_news")

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "sources.yaml"

# RSS フィードの正規取得。ボット扱いで 403 になるのを防ぐためブラウザ風 UA。
USER_AGENT = (
    "Mozilla/5.0 (compatible; DailyAINews/1.0; "
    "+https://github.com/naoyadesu441/-)"
)

# Reddit API は記述的 UA を要求するため別途用意。他コレクターでは使わない。
REDDIT_USER_AGENT = (
    "daily-ai-news-aggregator/1.0 "
    "(+https://github.com/naoyadesu441/-; contact via GitHub issues)"
)

REQUEST_TIMEOUT = 20  # 秒


def load_sources() -> dict[str, Any]:
    with SOURCES_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_dotenv() -> None:
    """ローカルの .env を環境変数に流し込む（既存値は上書きしない）。

    GitHub Actions ではシークレットが環境変数として渡るので .env は無くてよい。
    """
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_secret(name: str) -> str | None:
    val = os.environ.get(name)
    return val.strip() if val else None


class Http:
    """共有 HTTP セッション。timeout 既定値と GET の簡易リトライを持つ。"""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def get(self, url: str, *, retries: int = 2, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = self.session.get(url, **kwargs)
                if resp.status_code == 429 and attempt < retries:
                    wait = float(resp.headers.get("Retry-After", 2 * (attempt + 1)))
                    LOG.warning("429 from %s, waiting %.1fs", url, wait)
                    time.sleep(min(wait, 10))
                    continue
                return resp
            except requests.RequestException as exc:  # noqa: PERF203
                last_exc = exc
                if attempt < retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise
        # ここには通常到達しない
        raise last_exc if last_exc else RuntimeError("unreachable")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
