# backend/market_loader.py
"""
统一加载 markets.json + auto_whales.json（+ 预留 auto_cex.json），
对外暴露 load_markets()，供 monitor.py 等模块使用。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent
MARKETS_PATH = BASE_DIR / "markets.json"
AUTO_WHALES_PATH = BASE_DIR / "auto_whales.json"
AUTO_CEX_PATH = BASE_DIR / "auto_cex.json"  # 预留，将来可以做动态交易所热钱包收集


def _safe_load_json(path: Path) -> Any:
    """安全加载 JSON 文件"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_markets() -> List[Dict[str, Any]]:
    """
    返回合并后的 market 配置数组。

    合并策略:
      1) 先加载 markets.json，作为基础列表
      2) 再加载 auto_whales.json，如存在，则把其中每个 item 追加到列表
      3) 再加载 auto_cex.json（预留，将来可选），也追加
    """
    base: List[Dict[str, Any]] = []

    # 1. 静态 markets.json
    static_cfg = _safe_load_json(MARKETS_PATH)
    if isinstance(static_cfg, list):
        base.extend(static_cfg)
    elif isinstance(static_cfg, dict):
        # 兼容 {"markets":[...]} 这种写法
        items = static_cfg.get("markets")
        if isinstance(items, list):
            base.extend(items)

    # 2. 动态鲸鱼地址
    auto_whales = _safe_load_json(AUTO_WHALES_PATH)
    if isinstance(auto_whales, list):
        for item in auto_whales:
            if not isinstance(item, dict):
                continue
            if "address" not in item:
                continue
            if "type" not in item:
                item["type"] = "whale_eth"
            if "network" not in item:
                item["network"] = "mainnet"
            base.append(item)

    # 3. （可选）动态 CEX 地址
    auto_cex = _safe_load_json(AUTO_CEX_PATH)
    if isinstance(auto_cex, list):
        for item in auto_cex:
            if not isinstance(item, dict):
                continue
            if "address" not in item:
                continue
            if "type" not in item:
                item["type"] = "exchange_eth"
            if "network" not in item:
                item["network"] = "mainnet"
            base.append(item)

    return base


def load_cross_chain_markets(chain1: str, chain2: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    加载并比较两个链上的市场数据。
    例如：Ethereum 和 BSC 上相同交易对的对比数据。

    :param chain1: 第一个链的名称（例如 'mainnet'）
    :param chain2: 第二个链的名称（例如 'bsc'）
    :return: 返回一个字典，包含两个链的市场数据
    """
    print(f"加载 {chain1} 和 {chain2} 的市场数据进行对比...")

    # 加载两个链的市场数据
    markets_chain1 = load_markets_for_chain(chain1)
    markets_chain2 = load_markets_for_chain(chain2)

    return {
        "chain1": markets_chain1,
        "chain2": markets_chain2,
    }


def load_markets_for_chain(chain: str) -> List[Dict[str, Any]]:
    """
    根据网络名称加载对应链的市场数据
    例如：'mainnet'、'bsc'，支持通过不同的 `markets_{network}.json` 文件加载
    """
    # 读取对应链的 markets.json 文件
    markets_path = BASE_DIR / f"markets_{chain}.json"

    markets_data = _safe_load_json(markets_path)
    if not isinstance(markets_data, list):
        return []

    return markets_data


if __name__ == "__main__":
    # 简单打印一下合并后的结果，方便调试
    markets = load_markets()
    print(f"共加载 markets 条目: {len(markets)}")
    for m in markets:
        t = m.get("type")
        if t in ("whale_eth", "exchange_eth", "whale", "exchange"):
            print(f"- [{t}] {m.get('label') or ''} {m.get('address')}")