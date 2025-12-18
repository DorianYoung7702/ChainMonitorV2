# backend/collectors/v3_data.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from web3 import Web3
from backend.config import make_web3

# ---------------------------
# Minimal ABIs
# ---------------------------
UNISWAP_V3_POOL_ABI = [
    {"inputs": [], "name": "token0", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "token1", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "fee", "outputs": [{"internalType": "uint24", "name": "", "type": "uint24"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "tickSpacing", "outputs": [{"internalType": "int24", "name": "", "type": "int24"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "liquidity", "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}], "stateMutability": "view", "type": "function"},
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
            {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
            {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
            {"internalType": "bool", "name": "unlocked", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {"inputs": [{"internalType": "int16", "name": "wordPosition", "type": "int16"}], "name": "tickBitmap", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {
        "inputs": [{"internalType": "int24", "name": "tick", "type": "int24"}],
        "name": "ticks",
        "outputs": [
            {"internalType": "uint128", "name": "liquidityGross", "type": "uint128"},
            {"internalType": "int128", "name": "liquidityNet", "type": "int128"},
            {"internalType": "uint256", "name": "feeGrowthOutside0X128", "type": "uint256"},
            {"internalType": "uint256", "name": "feeGrowthOutside1X128", "type": "uint256"},
            {"internalType": "int56", "name": "tickCumulativeOutside", "type": "int56"},
            {"internalType": "uint160", "name": "secondsPerLiquidityOutsideX128", "type": "uint160"},
            {"internalType": "uint32", "name": "secondsOutside", "type": "uint32"},
            {"internalType": "bool", "name": "initialized", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

ERC20_MIN_ABI = [
    {"inputs": [], "name": "decimals", "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "symbol", "outputs": [{"internalType": "string", "name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
]


@dataclass(frozen=True)
class V3PoolSnapshot:
    network: str
    pool_address: str
    token0: str
    token1: str
    token0_symbol: str
    token1_symbol: str
    token0_decimals: int
    token1_decimals: int
    fee: int
    tick_spacing: int
    liquidity: int
    sqrt_price_x96: int
    tick: int
    unlocked: bool


def _to_checksum(addr: str) -> str:
    return Web3.to_checksum_address(addr)


def _safe_str(x: Any) -> str:
    try:
        return str(x)
    except Exception:
        return ""


def _get_erc20_meta(w3: Web3, token_addr: str) -> Tuple[str, int]:
    c = w3.eth.contract(address=_to_checksum(token_addr), abi=ERC20_MIN_ABI)
    sym = ""
    dec = 18
    try:
        sym = c.functions.symbol().call()
    except Exception:
        sym = token_addr[:6]
    try:
        dec = int(c.functions.decimals().call())
    except Exception:
        dec = 18
    return _safe_str(sym), int(dec)


def get_v3_pool_snapshot(
    pool_address: str,
    network: str = "mainnet",
    w3: Optional[Web3] = None,
) -> Optional[V3PoolSnapshot]:
    w3 = w3 or make_web3(network)
    try:
        pool = w3.eth.contract(address=_to_checksum(pool_address), abi=UNISWAP_V3_POOL_ABI)

        token0 = pool.functions.token0().call()
        token1 = pool.functions.token1().call()
        fee = int(pool.functions.fee().call())
        tick_spacing = int(pool.functions.tickSpacing().call())
        liq = int(pool.functions.liquidity().call())

        slot0 = pool.functions.slot0().call()
        sqrt_price_x96 = int(slot0[0])
        tick = int(slot0[1])
        unlocked = bool(slot0[6])

        t0_sym, t0_dec = _get_erc20_meta(w3, token0)
        t1_sym, t1_dec = _get_erc20_meta(w3, token1)

        return V3PoolSnapshot(
            network=network,
            pool_address=_to_checksum(pool_address),
            token0=_to_checksum(token0),
            token1=_to_checksum(token1),
            token0_symbol=t0_sym,
            token1_symbol=t1_sym,
            token0_decimals=t0_dec,
            token1_decimals=t1_dec,
            fee=fee,
            tick_spacing=tick_spacing,
            liquidity=liq,
            sqrt_price_x96=sqrt_price_x96,
            tick=tick,
            unlocked=unlocked,
        )
    except Exception as e:
        print(f"⚠️ V3 snapshot 失败: pool={pool_address} err={e}")
        return None


# ---------------------------
# Price math
# ---------------------------
def v3_price_from_sqrtPriceX96(sqrtPriceX96: int, decimals0: int, decimals1: int) -> float:
    """
    返回 “token1 per token0” 的人类可读价格
    sqrtPriceX96 = sqrt(P_raw) * 2^96
    P_raw = amount1_raw / amount0_raw
    P_human = P_raw * 10^(decimals0 - decimals1)
    """
    try:
        sp = float(int(sqrtPriceX96))
        p_raw = (sp * sp) / float(2**192)
        scale = 10 ** (int(decimals0) - int(decimals1))
        return float(p_raw) * float(scale)
    except Exception:
        return 0.0


# ---------------------------
# Tick bitmap helpers
# ---------------------------
def _word_pos_for_tick(tick: int, tick_spacing: int) -> int:
    compressed = int(tick // tick_spacing)
    return int(compressed >> 8)


def _tick_for_word_bit(word_pos: int, bit_pos: int, tick_spacing: int) -> int:
    compressed = int(word_pos * 256 + bit_pos)
    return int(compressed * tick_spacing)


def _iter_set_bits(u256: int) -> List[int]:
    out: List[int] = []
    x = int(u256)
    while x:
        lsb = x & -x
        b = (lsb.bit_length() - 1)
        out.append(int(b))
        x ^= lsb
    return out


def fetch_ticks_around_current(
    pool_address: str,
    network: str = "mainnet",
    *,
    words_each_side: int = 8,
    max_ticks: int = 800,
    w3: Optional[Web3] = None,
) -> Dict[str, Any]:
    w3 = w3 or make_web3(network)
    snap = get_v3_pool_snapshot(pool_address, network=network, w3=w3)
    if not snap:
        return {"pool_address": pool_address, "network": network, "ticks": [], "snapshot": None}

    pool = w3.eth.contract(address=_to_checksum(pool_address), abi=UNISWAP_V3_POOL_ABI)

    center_word = _word_pos_for_tick(snap.tick, snap.tick_spacing)
    word_positions = list(range(center_word - words_each_side, center_word + words_each_side + 1))

    ticks_out: List[Dict[str, Any]] = []
    fetched = 0

    for wp in word_positions:
        if fetched >= max_ticks:
            break
        try:
            bitmap = int(pool.functions.tickBitmap(int(wp)).call())
        except Exception:
            continue
        if bitmap == 0:
            continue

        bits = _iter_set_bits(bitmap)
        for b in bits:
            if fetched >= max_ticks:
                break
            t = _tick_for_word_bit(int(wp), int(b), snap.tick_spacing)
            try:
                info = pool.functions.ticks(int(t)).call()
                initialized = bool(info[7])
                if not initialized:
                    continue
                lg = int(info[0])
                ln = int(info[1])
                ticks_out.append(
                    {
                        "tick": int(t),
                        "liquidityGross": lg,
                        "liquidityNet": ln,
                        "wordPos": int(wp),
                        "bitPos": int(b),
                    }
                )
                fetched += 1
            except Exception:
                continue

    ticks_out.sort(key=lambda x: x["tick"])
    return {
        "pool_address": snap.pool_address,
        "network": snap.network,
        "snapshot": {
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
            "unlocked": snap.unlocked,
        },
        "ticks": ticks_out,
    }


# ============================================================
# ✅ Pipeline-compat wrappers (对齐 discovery_run.py 的调用)
# ============================================================

def fetch_v3_pool_state(pool_address: str, chain: str = "mainnet") -> Dict[str, Any]:
    """
    discovery_run.py 会调用它，并期待 dict 字段：
      sqrtPriceX96, tick, liquidity, fee, token0, token1, decimals0, decimals1
    """
    w3 = make_web3(chain)
    snap = get_v3_pool_snapshot(pool_address, network=chain, w3=w3)
    if not snap:
        return {}

    return {
        "chain": chain,
        "pool": snap.pool_address,
        "token0": snap.token0,
        "token1": snap.token1,
        "symbol0": snap.token0_symbol,
        "symbol1": snap.token1_symbol,
        "decimals0": snap.token0_decimals,
        "decimals1": snap.token1_decimals,
        "fee": snap.fee,
        "tickSpacing": snap.tick_spacing,
        "liquidity": snap.liquidity,
        "sqrtPriceX96": snap.sqrt_price_x96,
        "tick": snap.tick,
        "unlocked": snap.unlocked,
    }


def fetch_v3_liquidity_distribution(
    pool_address: str,
    chain: str = "mainnet",
    *,
    num_ticks_each_side: int = 200,
) -> Dict[str, Any]:
    """
    返回一个不会把报告撑爆的结构：
    - ticks: 仅少量（默认不直接塞全部到 report）
    - summary: 面试/报告友好的摘要
    """
    # 将 “ticks_each_side” 粗略映射到 “words_each_side”
    # 每个 word 256 个 “compressed ticks”（约等于 256 * tickSpacing）
    # 这里做一个保守换算：num_ticks_each_side / 256 -> words_each_side
    words_each_side = max(1, int(num_ticks_each_side // 256) + 1)

    raw = fetch_ticks_around_current(
        pool_address,
        network=chain,
        words_each_side=words_each_side,
        max_ticks=min(2000, max(400, num_ticks_each_side * 4)),
    )

    snap = raw.get("snapshot") or {}
    ticks = raw.get("ticks") or []
    if not snap or not isinstance(ticks, list):
        return {"pool": pool_address, "chain": chain, "ticks": [], "summary": {}}

    # --- summary: 最近的上下边界 tick / 缺口等
    cur_tick = int(snap.get("tick") or 0)
    initialized = sorted([int(t.get("tick")) for t in ticks if isinstance(t, dict) and t.get("tick") is not None])

    lower = None
    upper = None
    for t in initialized:
        if t <= cur_tick:
            lower = t
        if t > cur_tick and upper is None:
            upper = t

    gap = None
    if lower is not None and upper is not None:
        gap = int(upper - lower)

    # 用一个“可解释”的缺口判定：gap > tickSpacing * 200 视为明显缺口（你可按经验调整）
    tick_spacing = int(snap.get("tick_spacing") or snap.get("tickSpacing") or 1)
    gap_is_large = bool(gap is not None and tick_spacing > 0 and gap > tick_spacing * 200)

    summary = {
        "current_tick": cur_tick,
        "tick_spacing": tick_spacing,
        "initialized_ticks_scanned": len(initialized),
        "nearest_initialized_tick_below": lower,
        "nearest_initialized_tick_above": upper,
        "gap_ticks_between_nearest_bounds": gap,
        "gap_is_large": gap_is_large,
        "note": "This is a bounded online scan around current tick (tickBitmap window).",
    }

    return {
        "pool": raw.get("pool_address"),
        "chain": raw.get("network"),
        "summary": summary,
        # ticks 不要全塞进 report，pipeline 里只用 summary；这里保留以便你需要时调试
        "ticks": ticks,
    }