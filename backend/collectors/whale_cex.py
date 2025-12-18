from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from web3 import Web3

from backend.config import make_web3

__all__ = [
    "estimate_pool_liquidity",
    "fetch_whale_metrics",
    "fetch_cex_net_inflow",
]

# -------------------- Etherscan V2 基础配置 --------------------

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
ETHERSCAN_BASE_URL = os.getenv("ETHERSCAN_BASE_URL", "https://api.etherscan.io/v2/api")
ETH_MAINNET_CHAIN_ID = "1"

_DEFAULT_CHAINID_BY_NETWORK = {
    "mainnet": "1",
    "ethereum": "1",
    "eth": "1",
    "sepolia": "11155111",
}

_SESSION = requests.Session()


def _get_etherscan_chain_id(network: str = "mainnet") -> str:
    env_global = os.getenv("ETHERSCAN_CHAIN_ID")
    if env_global:
        return env_global.strip()

    env_net = os.getenv(f"ETHERSCAN_CHAIN_ID_{(network or 'mainnet').upper()}")
    if env_net:
        return env_net.strip()

    return _DEFAULT_CHAINID_BY_NETWORK.get((network or "mainnet").lower(), ETH_MAINNET_CHAIN_ID)


def _etherscan_get_json(
    params: Dict[str, Any],
    timeout: int = 15,
    max_retries: int = 5,
    backoff_base: float = 1.5,
) -> Optional[Dict[str, Any]]:
    for attempt in range(max_retries):
        try:
            resp = _SESSION.get(ETHERSCAN_BASE_URL, params=params, timeout=timeout)

            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                wait = (backoff_base**attempt) + (0.2 * attempt)
                print(f"⚠️ Etherscan HTTP {resp.status_code}，第 {attempt+1}/{max_retries} 次重试，等待 {wait:.2f}s")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()

            message = (data.get("message") or "").lower()
            result = data.get("result")
            result_str = result.lower() if isinstance(result, str) else ""

            if ("rate limit" in message) or ("rate limit" in result_str) or ("max calls" in result_str) or ("max rate limit" in result_str):
                wait = (backoff_base**attempt) + 0.5
                print(f"⚠️ Etherscan 限流返回，第 {attempt+1}/{max_retries} 次重试，等待 {wait:.2f}s；返回={data}")
                time.sleep(wait)
                continue

            return data
        except (requests.Timeout, requests.ConnectionError) as e:
            wait = (backoff_base**attempt) + (0.2 * attempt)
            print(f"⚠️ Etherscan 网络异常: {e}，第 {attempt+1}/{max_retries} 次重试，等待 {wait:.2f}s")
            time.sleep(wait)
            continue
        except Exception as e:
            print(f"⚠️ 请求 Etherscan 失败: {e}")
            time.sleep(0.3)

    print("⚠️ Etherscan 多次重试后仍失败，已放弃本次请求")
    return None


def _etherscan_get_normal_txs(
    address: str,
    start_block: int,
    end_block: int,
    page: int = 1,
    offset: int = 10_000,
    sort: str = "asc",
    network: str = "mainnet",
) -> List[Dict[str, Any]]:
    if not ETHERSCAN_API_KEY:
        print("⚠️ 未配置 ETHERSCAN_API_KEY，跳过 Etherscan 请求")
        return []

    chainid = _get_etherscan_chain_id(network)
    params = {
        "apikey": ETHERSCAN_API_KEY,
        "chainid": chainid,
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": int(start_block),
        "endblock": int(end_block),
        "page": int(page),
        "offset": int(offset),
        "sort": sort,
    }

    data = _etherscan_get_json(params=params)
    if not data:
        return []

    status = data.get("status")
    result = data.get("result")

    if status == "1" and isinstance(result, list):
        return result

    # 兼容两种“无交易”的返回
    if isinstance(result, str) and "No transactions found" in result:
        return []
    if status == "0":
        msg = (data.get("message") or "").lower()
        if "no transactions found" in msg and isinstance(result, list) and len(result) == 0:
            return []

    print(f"⚠️ Etherscan 返回非成功状态: {data}")
    return []


# -------------------- DEX 池子流动性估计 --------------------

UNISWAP_V2_PAIR_ABI = [
    {
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"internalType": "uint112", "name": "_reserve0", "type": "uint112"},
            {"internalType": "uint112", "name": "_reserve1", "type": "uint112"},
            {"internalType": "uint32", "name": "_blockTimestampLast", "type": "uint32"},
        ],
        "stateMutability": "view",
        "type": "function",
    }
]


def estimate_pool_liquidity(pair_address: str, network: str = "mainnet") -> int:
    w3 = make_web3(network)
    pair = w3.eth.contract(
        address=Web3.to_checksum_address(pair_address),
        abi=UNISWAP_V2_PAIR_ABI,
    )
    reserve0, reserve1, _ = pair.functions.getReserves().call()
    liquidity = int(reserve0) + int(reserve1)
    print(f"📡 [DEX] getReserves: reserve0={reserve0}, reserve1={reserve1}, liquidity={liquidity}")
    return liquidity


# -------------------- markets 解析工具 --------------------

def _extract_from_markets(markets: List[Dict[str, Any]]) -> Tuple[List[str], List[str], Optional[str]]:
    whales: List[str] = []
    cex: List[str] = []
    pair_address: Optional[str] = None

    for m in markets:
        if not isinstance(m, dict):
            continue
        t = (m.get("type") or "").lower()

        if t in ("whale", "whale_eth"):
            addr = m.get("address")
            if isinstance(addr, str) and addr:
                whales.append(addr)

        elif t in ("exchange", "exchange_eth"):
            addr = m.get("address")
            if isinstance(addr, str) and addr:
                cex.append(addr)

        elif t in ("dex_pool", "dexpool", "pool"):
            if pair_address is None:
                p = m.get("pairAddress") or m.get("pair_address") or m.get("address")
                if isinstance(p, str) and p:
                    pair_address = p

    return whales, cex, pair_address


def _estimate_blocks_back(w3, start_time: datetime, end_time: datetime, sample_blocks: int = 200) -> int:
    latest = w3.eth.block_number
    sample_blocks = min(int(sample_blocks), int(latest)) if latest > 0 else 1
    sample_blocks = max(1, sample_blocks)

    try:
        b_latest = w3.eth.get_block(latest)
        b_prev = w3.eth.get_block(max(0, latest - sample_blocks))
        dt = int(b_latest["timestamp"]) - int(b_prev["timestamp"])
        avg_block_sec = (dt / sample_blocks) if dt > 0 else 12.0
    except Exception:
        avg_block_sec = 12.0

    window_sec = max(0.0, (end_time - start_time).total_seconds())
    blocks = int(window_sec / avg_block_sec) + 200
    return max(500, min(blocks, 200000))


def _coerce_int(x: Any, default: int = 2000) -> int:
    if x is None:
        return int(default)
    if isinstance(x, bool):
        return int(default)
    if isinstance(x, int):
        return x
    try:
        return int(x)
    except Exception:
        try:
            return int(float(str(x).strip()))
        except Exception:
            return int(default)


# -------------------- 核心统计逻辑 --------------------

def _fetch_whale_metrics_core(
    whales: List[str],
    cex_addresses: List[str],
    blocks_back: Union[int, str] = 2000,
    network: str = "mainnet",
) -> Tuple[int, int]:
    if not whales:
        return 0, 0

    w3 = make_web3(network)
    latest = int(w3.eth.block_number)
    blocks_back_int = _coerce_int(blocks_back, default=2000)

    from_block = max(0, latest - blocks_back_int)
    to_block = latest

    print(f"✅ 已连接 {network}, 最新区块: {latest}")
    print(f"📡 [Whale] 统计区块区间 {from_block} ~ {to_block}")

    cex_lower = {a.lower() for a in cex_addresses if isinstance(a, str)}
    whale_sell_total = 0
    selling_whales: set[str] = set()

    for whale in whales:
        try:
            whale_checksum = Web3.to_checksum_address(whale)
        except ValueError:
            print(f"⚠️ 非法巨鲸地址，已跳过: {whale}")
            continue

        txs = _etherscan_get_normal_txs(
            address=whale_checksum,
            start_block=from_block,
            end_block=to_block,
            network=network,
        )

        for tx in txs:
            from_addr = (tx.get("from") or "").lower()
            to_addr = (tx.get("to") or "").lower()
            value_wei = int(tx.get("value") or 0)

            if from_addr == whale_checksum.lower() and to_addr in cex_lower:
                whale_sell_total += value_wei
                selling_whales.add(whale_checksum)

    whale_count_selling = len(selling_whales)
    print(f"📡 [Whale] 卖出巨鲸数: {whale_count_selling}, 卖出总量(Wei): {whale_sell_total}")
    return whale_sell_total, whale_count_selling


def _fetch_cex_net_inflow_core(
    cex_addresses: List[str],
    blocks_back: Union[int, str] = 2000,
    network: str = "mainnet",
) -> int:
    if not cex_addresses:
        return 0

    w3 = make_web3(network)
    latest = int(w3.eth.block_number)
    blocks_back_int = _coerce_int(blocks_back, default=2000)

    from_block = max(0, latest - blocks_back_int)
    to_block = latest

    print(f"✅ 已连接 {network}, 最新区块: {latest}")
    print(f"📡 [CEX] 统计区块区间 {from_block} ~ {to_block}")

    net_inflow = 0

    for cex in cex_addresses:
        try:
            cex_checksum = Web3.to_checksum_address(cex)
        except ValueError:
            print(f"⚠️ 非法交易所地址，已跳过: {cex}")
            continue

        txs = _etherscan_get_normal_txs(
            address=cex_checksum,
            start_block=from_block,
            end_block=to_block,
            network=network,
        )

        for tx in txs:
            from_addr = (tx.get("from") or "").lower()
            to_addr = (tx.get("to") or "").lower()
            value_wei = int(tx.get("value") or 0)

            if to_addr == cex_checksum.lower() and from_addr != cex_checksum.lower():
                net_inflow += value_wei
            elif from_addr == cex_checksum.lower() and to_addr != cex_checksum.lower():
                net_inflow -= value_wei

    print(f"📡 [CEX] 净流入(Wei): {net_inflow}")
    return net_inflow


# -------------------- ✅ 对外导出：保证 pipeline 能 import 到 --------------------

def fetch_whale_metrics(
    arg1: Union[List[Dict[str, Any]], List[str]],
    arg2: Any,
    arg3: Any,
    arg4: Any = None,
    arg5: Any = None,
    network: str = "mainnet",
) -> Union[Dict[str, Any], Tuple[int, int]]:
    """
    A) pipeline：fetch_whale_metrics(markets, start_time, end_time, chain) -> dict
    B) legacy： fetch_whale_metrics(whales, cex_addresses, pair_address, blocks_back?, network?) -> tuple
    """
    # pipeline
    if isinstance(arg1, list) and (len(arg1) == 0 or isinstance(arg1[0], dict)):
        markets: List[Dict[str, Any]] = arg1
        start_time = arg2
        end_time = arg3
        chain = arg4 if isinstance(arg4, str) else network

        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime) or not isinstance(chain, str):
            raise TypeError("pipeline 模式需要：fetch_whale_metrics(markets, start_time(datetime), end_time(datetime), chain(str))")

        whales, cex_addresses, _ = _extract_from_markets(markets)

        w3 = make_web3(chain)
        blocks_back = _estimate_blocks_back(w3, start_time, end_time)

        sell_total, whale_count = _fetch_whale_metrics_core(
            whales=whales,
            cex_addresses=cex_addresses,
            blocks_back=blocks_back,
            network=chain,
        )
        return {
            "whale_sell_total": int(sell_total),
            "whale_count_selling": int(whale_count),
        }

    # legacy（保持原项目可用）
    whales = arg1  # type: ignore[assignment]
    cex_addresses = arg2
    blocks_back = arg4 if arg4 is not None else 2000
    net = arg5 if isinstance(arg5, str) and arg5 else network

    if isinstance(blocks_back, str) and blocks_back.lower() in _DEFAULT_CHAINID_BY_NETWORK:
        net = blocks_back
        blocks_back = 2000

    if not isinstance(whales, list) or not isinstance(cex_addresses, list):
        raise TypeError("legacy 模式需要：fetch_whale_metrics(whales(list), cex_addresses(list), pair_address(str), blocks_back?, network?)")

    return _fetch_whale_metrics_core(
        whales=whales,
        cex_addresses=cex_addresses,
        blocks_back=blocks_back,
        network=net,
    )


def fetch_cex_net_inflow(
    arg1: Union[List[Dict[str, Any]], List[str]],
    arg2: Any = None,
    arg3: Any = None,
    arg4: Any = None,
    blocks_back: Union[int, str] = 2000,
    network: str = "mainnet",
) -> int:
    """
    A) pipeline：fetch_cex_net_inflow(markets, start_time, end_time, chain) -> int
    B) legacy： fetch_cex_net_inflow(cex_addresses, blocks_back=..., network=...) -> int
    """
    # pipeline
    if isinstance(arg1, list) and (len(arg1) == 0 or isinstance(arg1[0], dict)):
        markets: List[Dict[str, Any]] = arg1
        start_time = arg2
        end_time = arg3
        chain = arg4 if isinstance(arg4, str) else network

        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime) or not isinstance(chain, str):
            raise TypeError("pipeline 模式需要：fetch_cex_net_inflow(markets, start_time(datetime), end_time(datetime), chain(str))")

        _, cex_addresses, _ = _extract_from_markets(markets)
        w3 = make_web3(chain)
        bb = _estimate_blocks_back(w3, start_time, end_time)
        return _fetch_cex_net_inflow_core(cex_addresses=cex_addresses, blocks_back=bb, network=chain)

    # legacy
    cex_addresses = arg1
    if not isinstance(cex_addresses, list):
        raise TypeError("legacy 模式需要：fetch_cex_net_inflow(cex_addresses(list), blocks_back?, network?)")

    return _fetch_cex_net_inflow_core(cex_addresses=cex_addresses, blocks_back=blocks_back, network=network)
