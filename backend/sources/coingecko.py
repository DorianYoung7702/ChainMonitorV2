# backend/sources/coingecko.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .http import HTTPClient

COINGECKO_BASE = "https://api.coingecko.com/api/v3"


class CoinGecko:
    """
    CoinGecko 公共 API 封装（v3）：
    - coins_list(): coin id 列表（可包含平台信息）
    - simple_price(): 简单报价（支持附带 24h change / market_cap 等）
    - ping(): 连通性检查
    """

    def __init__(self, client: Optional[HTTPClient] = None, api_key: Optional[str] = None):
        self.http = client or HTTPClient()
        # 可选：加 key 会显著减少限流风险（没有也能跑）
        self.api_key = api_key or os.getenv("COINGECKO_API_KEY", "").strip()

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        内部统一入口：自动带上 demo api key（如果你配置了的话）。
        CoinGecko 对 header key 的命名经常是 x-cg-demo-api-key（免费/演示 key）。
        """
        url = f"{COINGECKO_BASE}{path}"
        params = dict(params or {})

        # 这里不改 HTTPClient 的签名（它不支持 headers 参数），
        # 所以用一个技巧：把 key 放到 query params（CoinGecko 支持 ?x_cg_demo_api_key= 形式）
        # 如果你使用付费/正式 key，后面可以再升级成 header 方式。
        if self.api_key:
            # 兼容两种常见写法：有的环境用 x_cg_demo_api_key
            params.setdefault("x_cg_demo_api_key", self.api_key)

        return self.http.get_json(url, params=params)

    def ping(self) -> bool:
        data = self._get("/ping")
        # 正常返回 {"gecko_says": "..."}
        return isinstance(data, dict) and ("gecko_says" in data)

    def coins_list(self, include_platform: bool = True) -> List[Dict[str, Any]]:
        data = self._get(
            "/coins/list",
            params={"include_platform": str(include_platform).lower()},
        )
        return data if isinstance(data, list) else []

    def simple_price(
        self,
        ids: List[str],
        vs: str = "usd",
        include_24hr_change: bool = False,
        include_market_cap: bool = False,
        include_24hr_vol: bool = False,
        include_last_updated_at: bool = False,
    ) -> Dict[str, Any]:
        """
        示例：
          simple_price(["ethereum"], "usd", include_24hr_change=True)
        返回形如：
          {"ethereum": {"usd": 2895.22, "usd_24h_change": -1.23, ...}}
        """
        ids_clean = [x.strip() for x in ids if isinstance(x, str) and x.strip()]
        if not ids_clean:
            return {}

        data = self._get(
            "/simple/price",
            params={
                "ids": ",".join(ids_clean),
                "vs_currencies": (vs or "usd").strip().lower(),
                "include_24hr_change": str(include_24hr_change).lower(),
                "include_market_cap": str(include_market_cap).lower(),
                "include_24hr_vol": str(include_24hr_vol).lower(),
                "include_last_updated_at": str(include_last_updated_at).lower(),
            },
        )
        return data if isinstance(data, dict) else {}
