# backend/sources/dex_screener.py
from __future__ import annotations

from typing import Any, Dict, Optional
from .http import HTTPClient

DEXSCREENER_BASE = "https://api.dexscreener.com/latest/dex"


def _normalize_chain_id(chain_id: str) -> str:
    """
    DexScreener 常用 chainId：
      - ethereum / bsc / polygon / arbitrum / optimism / base / avalanche / etc.
    这里做轻量映射，允许你传 mainnet/eth 这种别名。
    """
    c = (chain_id or "").strip().lower()
    if c in ("mainnet", "ethereum", "eth"):
        return "ethereum"
    if c in ("bsc", "bnb", "binance"):
        return "bsc"
    return c


def _normalize_addr(addr: str) -> str:
    """
    DexScreener 对 EVM 地址大小写一般不敏感，但这里做一下 strip。
    不强制 checksum，避免对 Solana 等非 EVM 地址造成误判。
    """
    return (addr or "").strip()


class DexScreener:
    """
    DexScreener 公共 API 封装：
      - pair(): 查询某个 DEX pair 的快照（价格、成交量、流动性等）
      - token_pairs(): 查询某个 token 在不同池子的列表
    """

    def __init__(self, client: Optional[HTTPClient] = None):
        self.http = client or HTTPClient()

    def pair(self, chain_id: str, pair_address: str) -> Dict[str, Any]:
        """
        GET /pairs/{chainId}/{pairAddress}
        返回 dict（失败时返回 {}）
        """
        cid = _normalize_chain_id(chain_id)
        p = _normalize_addr(pair_address)
        if not cid or not p:
            return {}

        url = f"{DEXSCREENER_BASE}/pairs/{cid}/{p}"
        data = self.http.get_json(url)
        return data if isinstance(data, dict) else {}

    def token_pairs(self, token_address: str) -> Dict[str, Any]:
        """
        GET /tokens/{tokenAddress}
        返回 dict（失败时返回 {}）
        """
        t = _normalize_addr(token_address)
        if not t:
            return {}

        url = f"{DEXSCREENER_BASE}/tokens/{t}"
        data = self.http.get_json(url)
        return data if isinstance(data, dict) else {}
