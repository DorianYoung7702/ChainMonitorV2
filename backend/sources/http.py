# backend/sources/http.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests


class HTTPClient:
    """
    轻量 HTTP Client：
    - requests.Session 复用连接
    - 429 / 5xx 自动重试 + 指数退避
    - 返回 JSON（可能是 dict / list / str 等），失败返回 None
    """

    def __init__(
        self,
        timeout: int = 15,
        max_retries: int = 5,
        backoff_base: float = 1.6,
        user_agent: Optional[str] = None,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base

        self.sess = requests.Session()
        # 一些公共 API 对 UA 为空更容易 429；这里给默认 UA，允许外部覆盖
        self.user_agent = user_agent or os.getenv(
            "HTTP_USER_AGENT",
            "defi-market-monitor/1.0 (+https://example.com)",
        )

        self.debug = os.getenv("HTTP_DEBUG", "").strip().lower() in ("1", "true", "yes")

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        GET 并解析 JSON。
        - 成功：返回解析后的 JSON（dict/list/...）
        - 失败：返回 None
        """
        headers = {"User-Agent": self.user_agent}

        last_err: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                r = self.sess.get(url, params=params, timeout=self.timeout, headers=headers)

                # 处理 429/5xx：退避重试
                if r.status_code == 429 or 500 <= r.status_code < 600:
                    # 如果有 Retry-After，优先用
                    ra = r.headers.get("Retry-After")
                    if ra:
                        try:
                            wait = float(ra)
                        except Exception:
                            wait = (self.backoff_base ** attempt) + 0.2 * attempt
                    else:
                        wait = (self.backoff_base ** attempt) + 0.2 * attempt

                    if self.debug:
                        print(f"⚠️ HTTP {r.status_code} retry {attempt+1}/{self.max_retries} wait={wait:.2f}s url={url}")

                    time.sleep(min(wait, 10.0))
                    continue

                r.raise_for_status()

                # JSON 解析（可能抛 ValueError/JSONDecodeError）
                return r.json()

            except Exception as e:
                last_err = e
                wait = (self.backoff_base ** attempt) + 0.2 * attempt
                if self.debug:
                    print(f"⚠️ HTTP error retry {attempt+1}/{self.max_retries} wait={wait:.2f}s url={url} err={e}")
                time.sleep(min(wait, 8.0))

        if self.debug and last_err is not None:
            print(f"❌ HTTP failed after retries url={url} err={last_err}")

        return None
