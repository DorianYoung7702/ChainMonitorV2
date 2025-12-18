from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Tuple

from web3 import Web3
from backend.config import make_web3


# ------------------------------------------------------------
# Uniswap V2 Pair ABI：Swap + token0/token1 + getReserves
# ------------------------------------------------------------
UNISWAP_V2_PAIR_ABI = [
    # Swap event
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount0In", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "amount1In", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "amount0Out", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "amount1Out", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
        ],
        "name": "Swap",
        "type": "event",
    },
    # token0/token1
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    # getReserves
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
    },
]


# ------------------------------------------------------------
# Helper: detect getLogs too large
# ------------------------------------------------------------
def _is_getlogs_too_large(err: Exception) -> bool:
    if not isinstance(err, ValueError):
        return False

    obj = err.args[0] if err.args else {}
    msg = ""
    code = None

    if isinstance(obj, dict):
        code = obj.get("code")
        msg = (obj.get("message") or "").lower()
    else:
        msg = str(err).lower()

    if code == -32005:
        return True
    if "more than 10000 results" in msg:
        return True
    if "query returned more than" in msg:
        return True
    if "response size exceeded" in msg:
        return True
    return False


def _event_get_logs_compat(event, from_block: int, to_block: int):
    """
    兼容不同 web3 版本的 get_logs 参数名：
      - 新版：from_block / to_block
      - 旧版：fromBlock / toBlock
    """
    try:
        return event.get_logs(from_block=from_block, to_block=to_block)
    except TypeError:
        return event.get_logs(fromBlock=from_block, toBlock=to_block)


def _swap_logs_with_auto_split(
    swap_event,
    from_block: int,
    to_block: int,
    depth: int = 0,
    max_depth: int = 20,
) -> List[Any]:
    """
    RPC get_logs 超过限制时自动二分切块获取，保证大池子在长时间窗口也能跑通。
    """
    if from_block > to_block:
        return []

    try:
        return _event_get_logs_compat(swap_event, from_block, to_block)
    except ValueError as e:
        if _is_getlogs_too_large(e) and from_block < to_block and depth < max_depth:
            mid = (from_block + to_block) // 2
            left = _swap_logs_with_auto_split(swap_event, from_block, mid, depth + 1, max_depth)
            right = _swap_logs_with_auto_split(swap_event, mid + 1, to_block, depth + 1, max_depth)
            return left + right
        raise


def _estimate_blocks_back(w3, start_time: datetime, end_time: datetime, sample_blocks: int = 200) -> int:
    """
    用链上真实 block timestamp 估算回溯 blocks（避免拍脑袋写死 12s/块）
    """
    latest = w3.eth.block_number
    if latest <= sample_blocks:
        sample_blocks = max(1, latest)

    try:
        b_latest = w3.eth.get_block(latest)
        b_prev = w3.eth.get_block(max(0, latest - sample_blocks))
        dt = int(b_latest["timestamp"]) - int(b_prev["timestamp"])
        avg_block_sec = (dt / sample_blocks) if dt > 0 else 12.0
    except Exception:
        avg_block_sec = 12.0

    window_sec = max(0.0, (end_time - start_time).total_seconds())
    blocks = int(window_sec / avg_block_sec) + 200  # buffer
    blocks = max(500, min(blocks, 200000))
    return blocks


def _fetch_pair_swaps(
    pair_address: str,
    blocks_back: int = 2000,
    network: str = "mainnet",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    单 pair 抓 Swap（支持可选时间窗口过滤）
    - 自动切块抓 logs
    - 可选 INCLUDE_GAS=1 采集 gas_used/gas_price
    """
    w3 = make_web3(network)
    pair_checksum = Web3.to_checksum_address(pair_address)
    pair = w3.eth.contract(address=pair_checksum, abi=UNISWAP_V2_PAIR_ABI)

    token0_addr = ""
    token1_addr = ""
    try:
        token0_addr = (pair.functions.token0().call() or "")
        token1_addr = (pair.functions.token1().call() or "")
    except Exception as e:
        print(f"⚠️ 读取 token0/token1 失败（不影响抓 Swap）：{e}")

    latest = w3.eth.block_number
    from_block = max(0, latest - int(blocks_back))
    to_block = latest

    swap_event = pair.events.Swap()
    logs = _swap_logs_with_auto_split(swap_event, from_block, to_block)

    include_gas = os.getenv("INCLUDE_GAS", "").strip().lower() in ("1", "true", "yes")

    trades: List[Dict[str, Any]] = []
    for ev in logs:
        args = ev["args"]

        amount0_in = int(args["amount0In"])
        amount1_in = int(args["amount1In"])
        amount0_out = int(args["amount0Out"])
        amount1_out = int(args["amount1Out"])

        if amount0_in > 0:
            token_in = "token0"
            token_out = "token1"
            amount_in = amount0_in
            amount_out = amount1_out
        else:
            token_in = "token1"
            token_out = "token0"
            amount_in = amount1_in
            amount_out = amount0_out

        block_number = int(ev["blockNumber"])
        block = w3.eth.get_block(block_number)
        ts = int(block["timestamp"])

        if start_time is not None and ts < int(start_time.timestamp()):
            continue
        if end_time is not None and ts > int(end_time.timestamp()):
            continue

        gas_used = 0
        gas_price = 0
        if include_gas:
            try:
                receipt = w3.eth.get_transaction_receipt(ev["transactionHash"])
                tx = w3.eth.get_transaction(ev["transactionHash"])
                gas_used = int(receipt.get("gasUsed") or 0)
                gas_price = int(tx.get("gasPrice") or 0)
            except Exception:
                pass

        trades.append(
            {
                "timestamp": ts,
                "block_number": block_number,
                "tx_hash": ev["transactionHash"].hex(),
                "token_in": token_in,
                "token_out": token_out,
                "amount_in": int(amount_in),
                "amount_out": int(amount_out),
                "gas_used": int(gas_used),
                "gas_price": int(gas_price),
                "pair_address": pair_checksum,
                "network": network,
                "token0_address": token0_addr,
                "token1_address": token1_addr,
            }
        )

    print(f"✅ Pair {pair_checksum} 抓取到 {len(trades)} 笔 Swap")
    return trades


def fetch_recent_swaps(
    arg1: Union[str, List[Dict[str, Any]]],
    arg2: Optional[Any] = None,
    arg3: Optional[Any] = None,
    arg4: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    兼容两种调用方式（不改你的 pipeline）：

    1) 单 pair 模式：
        fetch_recent_swaps(pair_address, blocks_back=2000, network="mainnet")
        也兼容位置参数：fetch_recent_swaps(pair_address, blocks_back, network)

    2) pipeline 批量 + 时间窗口模式：
        fetch_recent_swaps(markets, start_time(datetime), end_time(datetime), chain(str))
    """
    # 模式 1：pair_address(str)
    if isinstance(arg1, str):
        pair_address = arg1
        blocks_back: int = 2000
        network: str = "mainnet"

        if arg2 is not None:
            # [新增] 兼容 "2000" / "2000.0" / 2000
            try:
                blocks_back = int(arg2)
            except Exception:
                blocks_back = int(float(str(arg2).strip()))

        if arg3 is not None:
            network = str(arg3)

        return _fetch_pair_swaps(pair_address, blocks_back=blocks_back, network=network)

    # 模式 2：markets(list[dict])
    if isinstance(arg1, list):
        markets = arg1

        if not isinstance(arg2, datetime) or not isinstance(arg3, datetime) or not isinstance(arg4, str):
            raise TypeError(
                "批量模式需要参数：fetch_recent_swaps(markets, start_time(datetime), end_time(datetime), chain(str))"
            )

        start_time: datetime = arg2
        end_time: datetime = arg3
        chain: str = arg4

        w3 = make_web3(chain)
        blocks_back = _estimate_blocks_back(w3, start_time, end_time)

        all_trades: List[Dict[str, Any]] = []
        for m in markets:
            if not isinstance(m, dict):
                continue

            t = (m.get("type") or "").lower()
            if t not in ("dex_pool", "dexpool", "pool"):
                continue

            pair_addr = m.get("pairAddress") or m.get("pair_address") or m.get("address")
            if not pair_addr:
                continue

            # [新增] 防止 markets.json 里出现无效地址
            try:
                pair_addr = Web3.to_checksum_address(pair_addr)
            except Exception:
                continue

            all_trades.extend(
                _fetch_pair_swaps(
                    pair_addr,
                    blocks_back=blocks_back,
                    network=chain,
                    start_time=start_time,
                    end_time=end_time,
                )
            )

        return all_trades

    raise TypeError("fetch_recent_swaps 第一个参数必须是 pair_address(str) 或 markets(list[dict])")


# ------------------------------------------------------------
# Arbitrage helpers (NEW): V2 executable simulation
# ------------------------------------------------------------

_WARNED_PAIRS: set[str] = set()

def _warn_once(key: str, msg: str):
    if key in _WARNED_PAIRS:
        return
    _WARNED_PAIRS.add(key)
    print(msg)

def _v2_amount_out(amount_in: int, reserve_in: int, reserve_out: int, fee_bps: int = 30) -> int:
    """
    UniswapV2 amountOut with fee:
      amount_in_with_fee = amount_in * (10000 - fee_bps) / 10000
      out = (amount_in_with_fee * reserve_out) / (reserve_in + amount_in_with_fee)
    """
    if amount_in <= 0 or reserve_in <= 0 or reserve_out <= 0:
        return 0
    fee_mul = 10000 - int(fee_bps)
    ain = amount_in * fee_mul // 10000
    if ain <= 0:
        return 0
    return (ain * reserve_out) // (reserve_in + ain)

def _simulate_two_pool_token0_cycle(
    amount_in_token0: int,
    buy_pool: Dict[str, Any],
    sell_pool: Dict[str, Any],
    fee_bps: int = 30,
) -> Tuple[int, int, int]:
    """
    Start with token0:
      token0 -> token1 on buy_pool
      token1 -> token0 on sell_pool
    Returns (amount_out_token0, mid_token1, profit_token0)
    """
    r0_buy = int(buy_pool["reserve0"])
    r1_buy = int(buy_pool["reserve1"])
    r0_sell = int(sell_pool["reserve0"])
    r1_sell = int(sell_pool["reserve1"])

    mid_token1 = _v2_amount_out(amount_in_token0, r0_buy, r1_buy, fee_bps=fee_bps)
    if mid_token1 <= 0:
        return 0, 0, 0

    out_token0 = _v2_amount_out(mid_token1, r1_sell, r0_sell, fee_bps=fee_bps)
    if out_token0 <= 0:
        return 0, mid_token1, 0

    profit = out_token0 - amount_in_token0
    return out_token0, mid_token1, profit

def _simulate_two_pool_token1_cycle(
    amount_in_token1: int,
    buy_pool: Dict[str, Any],
    sell_pool: Dict[str, Any],
    fee_bps: int = 30,
) -> Tuple[int, int, int]:
    """
    Start with token1:
      token1 -> token0 on buy_pool
      token0 -> token1 on sell_pool
    Returns (amount_out_token1, mid_token0, profit_token1)
    """
    r0_buy = int(buy_pool["reserve0"])
    r1_buy = int(buy_pool["reserve1"])
    r0_sell = int(sell_pool["reserve0"])
    r1_sell = int(sell_pool["reserve1"])

    mid_token0 = _v2_amount_out(amount_in_token1, r1_buy, r0_buy, fee_bps=fee_bps)
    if mid_token0 <= 0:
        return 0, 0, 0

    out_token1 = _v2_amount_out(mid_token0, r0_sell, r1_sell, fee_bps=fee_bps)
    if out_token1 <= 0:
        return 0, mid_token0, 0

    profit = out_token1 - amount_in_token1
    return out_token1, mid_token0, profit

def _scan_best_cycle(
    buy_pool: Dict[str, Any],
    sell_pool: Dict[str, Any],
    fee_bps: int,
    start_token: str,
    max_frac_of_reserve: float,
    steps: int,
) -> Dict[str, Any]:
    """
    扫描寻找最佳交易量（简单稳健、可解释）。
    - start_token: "token0" or "token1"
    - max_frac_of_reserve: 最大用 reserve 的比例（例如 0.003=0.3%）
    """
    if steps < 6:
        steps = 6

    r0_buy = int(buy_pool["reserve0"])
    r1_buy = int(buy_pool["reserve1"])

    if start_token == "token0":
        reserve_in = r0_buy
    else:
        reserve_in = r1_buy

    if reserve_in <= 0:
        return {"best_profit": 0, "best_amount_in": 0}

    # 上限：reserve 的一个小比例（避免把池子打穿；也更符合“信号检测”）
    max_in = int(reserve_in * float(max_frac_of_reserve))
    if max_in <= 0:
        return {"best_profit": 0, "best_amount_in": 0}

    # 下限：给一个最小值，避免太小导致 out=0
    min_in = max(1, max_in // 10_000)

    best = {
        "best_profit": 0,
        "best_amount_in": 0,
        "best_amount_out": 0,
        "best_mid": 0,
    }

    # 用几何序列扫描（覆盖量级）
    import math
    for i in range(steps):
        t = i / (steps - 1)
        amt_in = int(min_in * math.exp(math.log(max_in / min_in) * t))
        if amt_in <= 0:
            continue

        if start_token == "token0":
            out0, mid1, prof0 = _simulate_two_pool_token0_cycle(amt_in, buy_pool, sell_pool, fee_bps=fee_bps)
            if prof0 > best["best_profit"]:
                best.update({"best_profit": prof0, "best_amount_in": amt_in, "best_amount_out": out0, "best_mid": mid1})
        else:
            out1, mid0, prof1 = _simulate_two_pool_token1_cycle(amt_in, buy_pool, sell_pool, fee_bps=fee_bps)
            if prof1 > best["best_profit"]:
                best.update({"best_profit": prof1, "best_amount_in": amt_in, "best_amount_out": out1, "best_mid": mid0})

    return best

def _estimate_gas_cost_wei(w3: Web3) -> int:
    """
    估算 gas 成本（非常粗略但对“过滤假机会”很有用）：
      gas_cost = ARB_GAS_UNITS * gasPrice
    """
    gas_units = int(os.getenv("ARB_GAS_UNITS", "240000"))  # 两次 swap + 额外开销，保守点
    try:
        gp = int(w3.eth.gas_price)
    except Exception:
        gp = int(os.getenv("ARB_GAS_PRICE_WEI", "20000000000"))  # 20 gwei fallback
    return gas_units * gp

def _pick_best_executable_arbitrage(
    w3: Web3,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    在同一 token0-token1 的多个池子中，找“可执行”的最佳套利：
    - 尝试所有 pool pair (buy,sell)
    - 同时尝试从 token0 或 token1 起步
    - 扫描最优交易量
    - 返回最佳结果（若不赚钱则 profit<=0）
    """
    fee_bps = int(os.getenv("ARB_FEE_BPS", "30"))  # V2 默认 0.30%
    steps = int(os.getenv("ARB_SCAN_STEPS", "18"))
    max_frac = float(os.getenv("ARB_MAX_FRAC_RESERVE", "0.003"))  # 默认只用 0.3% reserve
    min_profit_wei = int(os.getenv("ARB_MIN_PROFIT_WEI", "0"))  # 允许你设阈值

    gas_cost_wei = _estimate_gas_cost_wei(w3)
    # 如果 token0=ETH/WETH，可以用 gas 做近似扣除；否则只报告 gas，不强扣
    # 这里我们会同时给出“未扣gas”和“扣gas(假设token0是ETH)”两套字段
    best: Dict[str, Any] = {
        "best_profit_token0": 0,
        "best_profit_after_gas_token0": 0,
        "best_amount_in": 0,
        "best_amount_out": 0,
        "best_mid": 0,
        "best_direction": "",
        "best_buy_pool": "",
        "best_sell_pool": "",
        "fee_bps": fee_bps,
        "gas_cost_wei": gas_cost_wei,
        "gas_price_wei": int(gas_cost_wei // max(1, int(os.getenv("ARB_GAS_UNITS", "240000")))),
        "gas_units": int(os.getenv("ARB_GAS_UNITS", "240000")),
    }

    n = len(items)
    if n < 2:
        return best

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            buy = items[i]
            sell = items[j]

            # 方向1：从 token0 开始
            s0 = _scan_best_cycle(buy, sell, fee_bps=fee_bps, start_token="token0", max_frac_of_reserve=max_frac, steps=steps)
            prof0 = int(s0.get("best_profit") or 0)

            if prof0 > best["best_profit_token0"]:
                best.update(
                    {
                        "best_profit_token0": prof0,
                        "best_profit_after_gas_token0": prof0 - gas_cost_wei,
                        "best_amount_in": int(s0.get("best_amount_in") or 0),
                        "best_amount_out": int(s0.get("best_amount_out") or 0),
                        "best_mid": int(s0.get("best_mid") or 0),
                        "best_direction": "token0_cycle",
                        "best_buy_pool": buy["pair_address"],
                        "best_sell_pool": sell["pair_address"],
                        "best_path_in": "token0->token1 (buy_pool) -> token0 (sell_pool)",
                    }
                )

            # 方向2：从 token1 开始（同理）
            s1 = _scan_best_cycle(buy, sell, fee_bps=fee_bps, start_token="token1", max_frac_of_reserve=max_frac, steps=steps)
            prof1 = int(s1.get("best_profit") or 0)
            if prof1 > best.get("best_profit_token1", 0):
                best["best_profit_token1"] = prof1
                best["best_amount_in_token1"] = int(s1.get("best_amount_in") or 0)
                best["best_amount_out_token1"] = int(s1.get("best_amount_out") or 0)
                best["best_mid_token0_from_token1"] = int(s1.get("best_mid") or 0)
                best["best_direction_token1"] = "token1_cycle"
                best["best_buy_pool_token1"] = buy["pair_address"]
                best["best_sell_pool_token1"] = sell["pair_address"]
                best["best_path_in_token1"] = "token1->token0 (buy_pool) -> token1 (sell_pool)"

    # 简单过滤（token0 方向）
    if best["best_profit_token0"] < min_profit_wei:
        # 仍返回，但会被上层用 is_profitable 标注为 False
        return best
    return best


def _get_pair_spot_price(w3, pair_address: str) -> Optional[Dict[str, Any]]:
    """
    用 getReserves 计算现货价（不需要 WETH、不需要 factory）
    返回：
      {
        pair_address,
        token0,
        token1,
        reserve0,
        reserve1,
        price_token1_per_token0,
        price_token0_per_token1
      }
    """
    pair_checksum = Web3.to_checksum_address(pair_address)
    pair = w3.eth.contract(address=pair_checksum, abi=UNISWAP_V2_PAIR_ABI)

    try:
        token0 = pair.functions.token0().call()
        token1 = pair.functions.token1().call()
        r0, r1, _ = pair.functions.getReserves().call()
        r0 = int(r0)
        r1 = int(r1)
        if r0 <= 0 or r1 <= 0:
            return None

        return {
            "pair_address": pair_checksum,
            "token0": Web3.to_checksum_address(token0),
            "token1": Web3.to_checksum_address(token1),
            "reserve0": r0,
            "reserve1": r1,
            "price_token1_per_token0": (r1 / r0),
            "price_token0_per_token1": (r0 / r1),
        }
    except Exception as e:
        # 这个 warning 会很吵：这里改成“每个pair只提醒一次”
        _warn_once(pair_checksum, f"⚠️ 读取 reserves/token0/token1 失败：pair={pair_checksum} err={e}")
        return None


def fetch_arbitrage_opportunities(
    arg1: Union[List[Dict[str, Any]], str],
    arg2: Optional[Any] = None,
    arg3: Optional[Any] = None,
    arg4: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    为了适配你 pipeline 的 import，这个函数必须存在，并且“真实可跑”。

    ✅ 现在支持“完整套利逻辑”：
      - 仍然计算 spot spread（旧字段不变）
      - 新增：基于 V2 公式的两池两跳模拟 + 扫描最优交易量 + gas 粗扣

    支持两种调用：
    1) pipeline 模式：fetch_arbitrage_opportunities(markets, start_time, end_time, chain)
       - 从 markets 里找 dex_pool（需要至少 2 个 pool 才可能有套利）
    2) 简单模式：fetch_arbitrage_opportunities(chain_str) -> []
    """
    # pipeline 模式：markets + start + end + chain
    if isinstance(arg1, list):
        markets = arg1
        if not isinstance(arg4, str):
            raise TypeError("pipeline 模式需要：fetch_arbitrage_opportunities(markets, start_time, end_time, chain)")
        chain = arg4

        w3 = make_web3(chain)

        pools: List[str] = []
        for m in markets:
            if not isinstance(m, dict):
                continue
            t = (m.get("type") or "").lower()
            if t not in ("dex_pool", "dexpool", "pool"):
                continue
            pair_addr = m.get("pairAddress") or m.get("pair_address") or m.get("address")
            if pair_addr:
                try:
                    pools.append(Web3.to_checksum_address(pair_addr))
                except Exception:
                    continue

        # 少于 2 个池子无法做“跨池价差套利”
        if len(pools) < 2:
            return []

        # 读取每个池子的现货价 + reserves
        prices: List[Dict[str, Any]] = []
        for p in pools:
            info = _get_pair_spot_price(w3, p)
            if info:
                prices.append(info)

        # 按 token0-token1 分组（同一交易对多个池子）
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for it in prices:
            key = f"{it['token0']}-{it['token1']}"
            groups.setdefault(key, []).append(it)

        opportunities: List[Dict[str, Any]] = []
        for key, items in groups.items():
            if len(items) < 2:
                continue

            # -------- 1) 旧逻辑：spot spread（保留）--------
            items_sorted = sorted(items, key=lambda x: x["price_token1_per_token0"])
            low = items_sorted[0]
            high = items_sorted[-1]

            low_p = float(low["price_token1_per_token0"])
            high_p = float(high["price_token1_per_token0"])
            if low_p <= 0:
                continue

            spread = (high_p - low_p) / low_p

            # -------- 2) 新逻辑：可执行套利（模拟 + 扫描）--------
            best_exec = _pick_best_executable_arbitrage(w3, items)

            # 是否赚钱：默认用 token0_cycle 的 profit_after_gas
            # 注意：gas 只能当 token0≈ETH/WETH 时才“强意义”；否则你可在报告里用字段解释
            is_profitable = bool(best_exec.get("best_profit_after_gas_token0", 0) > 0)

            op: Dict[str, Any] = {
                # --- 原字段 ---
                "pair": key,
                "network": chain,
                "low_price_pool": low["pair_address"],
                "high_price_pool": high["pair_address"],
                "low_price_token1_per_token0": low_p,
                "high_price_token1_per_token0": high_p,
                "relative_spread": spread,
                "low_reserve0": low["reserve0"],
                "low_reserve1": low["reserve1"],
                "high_reserve0": high["reserve0"],
                "high_reserve1": high["reserve1"],

                # --- 新字段（完整套利逻辑输出）---
                "strategy": "v2_cross_pool_executable",
                "is_profitable_after_gas_token0": is_profitable,
                "fee_bps": int(best_exec.get("fee_bps", 30)),
                "gas_units": int(best_exec.get("gas_units", 0)),
                "gas_price_wei": int(best_exec.get("gas_price_wei", 0)),
                "gas_cost_wei": int(best_exec.get("gas_cost_wei", 0)),

                # 最佳（token0 起步）
                "best_direction": best_exec.get("best_direction", ""),
                "best_buy_pool": best_exec.get("best_buy_pool", ""),
                "best_sell_pool": best_exec.get("best_sell_pool", ""),
                "best_path_in": best_exec.get("best_path_in", ""),
                "best_amount_in_token0": int(best_exec.get("best_amount_in", 0)),
                "best_amount_out_token0": int(best_exec.get("best_amount_out", 0)),
                "best_mid_token1": int(best_exec.get("best_mid", 0)),
                "best_profit_token0": int(best_exec.get("best_profit_token0", 0)),
                "best_profit_after_gas_token0": int(best_exec.get("best_profit_after_gas_token0", 0)),

                # 备选（token1 起步），用于你后续扩展展示
                "best_direction_token1": best_exec.get("best_direction_token1", ""),
                "best_buy_pool_token1": best_exec.get("best_buy_pool_token1", ""),
                "best_sell_pool_token1": best_exec.get("best_sell_pool_token1", ""),
                "best_path_in_token1": best_exec.get("best_path_in_token1", ""),
                "best_amount_in_token1": int(best_exec.get("best_amount_in_token1", 0)),
                "best_amount_out_token1": int(best_exec.get("best_amount_out_token1", 0)),
                "best_mid_token0_from_token1": int(best_exec.get("best_mid_token0_from_token1", 0)),
                "best_profit_token1": int(best_exec.get("best_profit_token1", 0)),
            }

            opportunities.append(op)

        # 排序：优先按“可执行利润(扣gas)”排序，其次按 spread
        opportunities.sort(
            key=lambda x: (
                int(x.get("best_profit_after_gas_token0", 0)),
                float(x.get("relative_spread", 0.0)),
            ),
            reverse=True,
        )

        # 可选：你也可以只返回赚钱的（默认不强过滤，方便你报告展示“为什么不赚钱”）
        if os.getenv("ARB_ONLY_PROFITABLE", "").strip().lower() in ("1", "true", "yes"):
            opportunities = [o for o in opportunities if int(o.get("best_profit_after_gas_token0", 0)) > 0]

        return opportunities

    if isinstance(arg1, str):
        return []

    raise TypeError("fetch_arbitrage_opportunities 参数不合法：需要 markets(list) 或 chain(str)")

# === ADD BELOW in backend/collectors/chain_data.py (append only) ===

from typing import Any, Dict, List
from backend.collectors.v3_data import get_v3_pool_snapshot, fetch_ticks_around_current
from backend.analysis.v3_analysis import (
    sqrtPriceX96_to_price_token1_per_token0,
    build_liquidity_profile_from_ticks,
    detect_liquidity_gaps,
    compare_fee_tiers,
)

def fetch_v3_advanced_metrics(
    markets: List[Dict[str, Any]],
    chain: str,
    *,
    words_each_side: int = 8,
    max_ticks: int = 800,
) -> Dict[str, Any]:
    """
    V3 Bonus 主入口：
    - 拉取每个 V3 pool 的 slot0/liquidity/fee/tickSpacing
    - 扫描 ticks（tickBitmap + ticks）
    - 推导 liquidity profile + gap
    - 做 fee tier spread 对比（同 token0-token1 多个 fee）
    """
    v3_pools: List[str] = []
    for m in markets:
        if not isinstance(m, dict):
            continue
        t = (m.get("type") or "").lower()
        if t not in ("dex_pool_v3", "uniswap_v3_pool", "v3_pool"):
            continue
        addr = m.get("poolAddress") or m.get("pool_address") or m.get("address")
        if addr:
            v3_pools.append(addr)

    snapshots: List[Dict[str, Any]] = []
    pools_detail: List[Dict[str, Any]] = []

    for p in v3_pools:
        snap = get_v3_pool_snapshot(p, network=chain)
        if not snap:
            continue

        mid = sqrtPriceX96_to_price_token1_per_token0(
            snap.sqrt_price_x96, snap.token0_decimals, snap.token1_decimals
        )

        tick_pack = fetch_ticks_around_current(
            snap.pool_address,
            network=chain,
            words_each_side=words_each_side,
            max_ticks=max_ticks,
        )

        ticks = tick_pack.get("ticks") or []
        profile = build_liquidity_profile_from_ticks(
            current_tick=snap.tick,
            tick_spacing=snap.tick_spacing,
            current_liquidity=snap.liquidity,
            ticks=ticks,
            token0_decimals=snap.token0_decimals,
            token1_decimals=snap.token1_decimals,
        )
        gaps = detect_liquidity_gaps(profile)

        sdict = {
            "network": snap.network,
            "pool_address": snap.pool_address,
            "token0": snap.token0,
            "token1": snap.token1,
            "token0_symbol": snap.token0_symbol,
            "token1_symbol": snap.token1_symbol,
            "token0_decimals": snap.token0_decimals,
            "token1_decimals": snap.token1_decimals,
            "fee": snap.fee,
            "tick_spacing": snap.tick_spacing,
            "liquidity": snap.liquidity,
            "sqrt_price_x96": snap.sqrt_price_x96,
            "tick": snap.tick,
            "mid_price_token1_per_token0": str(mid),
            "unlocked": snap.unlocked,
        }
        snapshots.append(sdict)

        pools_detail.append(
            {
                "snapshot": sdict,
                "ticks_scanned": len(ticks),
                "liquidity_profile": profile,  # 直接可用于画“热区/缺口”
                "liquidity_gaps": gaps,         # 缺口段落（套利/冲击风险展示点）
            }
        )

    fee_tier_spreads = compare_fee_tiers(snapshots)

    return {
        "v3_pool_count": len(snapshots),
        "pools": pools_detail,
        "fee_tier_spreads": fee_tier_spreads,
    }