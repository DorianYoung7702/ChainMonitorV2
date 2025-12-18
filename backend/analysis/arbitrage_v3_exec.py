# backend/analysis/arbitrage_v3_exec.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from web3 import Web3

from backend.config import make_web3
from backend.collectors.v3_data import (
    fetch_ticks_around_current,
    get_v3_pool_snapshot,
    v3_price_from_sqrtPriceX96,
)

Q96 = 1 << 96
FEE_DENOM = 1_000_000  # Uniswap V3 fee denominator (fee=500 => 0.05%)


# ============================================================
# ✅ FAST MODE (默认)：不扫 ticks，只用 discovery 的 v3_pools 进行套利粗筛
# ============================================================

def _fee_to_bps(fee: int) -> float:
    """
    Uniswap V3 fee: 500 => 0.05% => 5 bps
    bps = fee / 100
    """
    try:
        return float(int(fee)) / 100.0
    except Exception:
        return 0.0


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        return default


def _norm_addr(x: Any) -> str:
    s = (str(x) if x is not None else "").strip()
    return s.lower()


def _is_weth(sym: Any) -> bool:
    s = (str(sym) if sym is not None else "").strip().upper()
    return s in ("WETH", "ETH")


def _gas_price_wei(chain: str, gas_price_wei: Optional[int]) -> int:
    if gas_price_wei is not None:
        return int(gas_price_wei)
    env = (os.getenv("GAS_PRICE_WEI") or "").strip()
    if env:
        try:
            return int(env)
        except Exception:
            pass
    # fallback: query node
    try:
        w3 = make_web3(chain)
        return int(w3.eth.gas_price)
    except Exception:
        return 30_000_000_000  # 30 gwei fallback


def _gas_cost_token0_human(
    *,
    gas_cost_wei: int,
    symbol0: Any,
    symbol1: Any,
    price_token1_per_token0: float,
) -> Tuple[Optional[float], str]:
    """
    将 gas(ETH) 换算到 token0 计价（只对 token0/token1 含 WETH 的对有效）
    - 若 token0=WETH：gas_token0 = gas_eth
    - 若 token1=WETH：token0_per_weth = 1 / (weth_per_token0) = 1 / price_token1_per_token0
    """
    gas_eth = float(gas_cost_wei) / 1e18
    if _is_weth(symbol0):
        return gas_eth, "ok (token0 is WETH)"
    if _is_weth(symbol1):
        if price_token1_per_token0 <= 0:
            return None, "missing price for conversion"
        token0_per_weth = 1.0 / float(price_token1_per_token0)
        return gas_eth * token0_per_weth, "ok (token1 is WETH)"
    return None, "token0/token1 not WETH; cannot convert gas -> token0 without oracle"


def _to_raw(amount_human: float, decimals: int) -> int:
    """
    将 human 数量换算成 on-chain raw（int）。
    例如 USDC(6): 10000 -> 10000 * 10^6
    """
    try:
        if amount_human is None:
            return 0
        d = int(decimals or 0)
        return int(round(float(amount_human) * (10 ** d)))
    except Exception:
        return 0


def _from_raw(amount_raw: int, decimals: int) -> float:
    """
    将 on-chain raw（int）换算为 human（float）。
    """
    try:
        d = int(decimals or 0)
        return float(int(amount_raw)) / (10 ** d)
    except Exception:
        return 0.0


def _group_key(p: Dict[str, Any]) -> Tuple[str, str]:
    # pool token order matters for price_token1_per_token0, so we keep (token0, token1)
    return (_norm_addr(p.get("token0")), _norm_addr(p.get("token1")))


def run_v3_arbitrage(
    v3_pools: List[Dict[str, Any]],
    chain: str = "mainnet",
    *,
    gas_price_wei: Optional[int] = None,
    gas_units: int = 320_000,
) -> Dict[str, Any]:
    """
    ✅ Pipeline 用：
      - FAST: 粗筛（不会扫 ticks，不会卡死）
      - DEEP: tick-level 两腿模拟（可能慢；用环境变量显式开启）
    输入：discovery_run.py v3_report["pools"]（包含 token0/token1/fee/liquidity/price_token1_per_token0/decimals/symbol）
    输出：opportunities + best
    """

    # mode: fast | deep（deep 会扫 ticks，默认别开）
    mode = (os.getenv("V3_ARB_MODE") or "fast").strip().lower()

    # ============================================================
    # ✅ DEEP 模式：tick-level 两腿模拟（token0->token1->token0）
    # ============================================================
    if mode == "deep":
        warnings = [
            "V3_ARB_MODE=deep enabled: this will scan ticks and may be slow / hang on some RPCs.",
            "Use FAST mode for pipeline demo; use DEEP mode for offline validation.",
        ]
        opps: List[Dict[str, Any]] = []

        pools = [p for p in v3_pools if isinstance(p, dict) and p.get("pool")]
        words_each_side = _safe_int(os.getenv("V3_ARB_WORDS_EACH_SIDE"), 8)
        max_ticks = _safe_int(os.getenv("V3_ARB_MAX_TICKS"), 1200)

        for i in range(len(pools)):
            for j in range(i + 1, len(pools)):
                a = pools[i].get("pool")
                b = pools[j].get("pool")
                try:
                    opps.append(
                        compute_executable_v3_v3_arbitrage(
                            pool_a=str(a),
                            pool_b=str(b),
                            chain=chain,
                            gas_units=gas_units,
                            gas_price_wei=gas_price_wei,
                            words_each_side=words_each_side,
                            max_ticks=max_ticks,
                        )
                    )
                except Exception as e:
                    warnings.append(f"deep arb failed: {str(e)[:160]}")

        # best = 最大净收益 bps（net_spread_bps）
        best = None
        best_net = -1e18
        for o in opps:
            net = _safe_float(o.get("net_spread_bps"), -1e18)
            if net > best_net:
                best_net = net
                best = o

        return {
            "enabled": True,
            "mode": "deep",
            "chain": chain,
            "pool_count": len(v3_pools),
            "opportunities": opps,
            "best": best or {},
            "warnings": warnings,
            "assumptions": {
                "gas_units": gas_units,
                "gas_price_wei": gas_price_wei,
                "words_each_side": words_each_side,
                "max_ticks": max_ticks,
            },
        }

    # ============================================================
    # ✅ FAST mode starts here（保持你原逻辑不变）
    # ============================================================
    gp = _gas_price_wei(chain, gas_price_wei)
    gas_cost_wei = int(gas_units) * int(gp)

    # group pools by token0/token1
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    warnings: List[str] = []

    for p in v3_pools:
        if not isinstance(p, dict):
            continue
        if not p.get("pool"):
            continue
        if not p.get("token0") or not p.get("token1"):
            warnings.append(f"pool missing token0/token1: {p.get('pool')}")
            continue
        price = _safe_float(p.get("price_token1_per_token0"), 0.0)
        if price <= 0:
            warnings.append(f"pool missing price_token1_per_token0: {p.get('pool')}")
            continue
        k = _group_key(p)
        groups.setdefault(k, []).append(p)

    opps: List[Dict[str, Any]] = []

    for k, pools in groups.items():
        if len(pools) < 2:
            continue

        # sort by price (token1 per token0)
        pools_sorted = sorted(pools, key=lambda x: _safe_float(x.get("price_token1_per_token0"), 1e99))
        for i in range(len(pools_sorted)):
            for j in range(i + 1, len(pools_sorted)):
                lowp = pools_sorted[i]
                highp = pools_sorted[j]
                p_low = _safe_float(lowp.get("price_token1_per_token0"), 0.0)
                p_high = _safe_float(highp.get("price_token1_per_token0"), 0.0)
                if p_low <= 0 or p_high <= 0:
                    continue

                gross = (p_high - p_low) / max(p_low, 1e-18)
                if gross <= 0:
                    continue

                gross_bps = gross * 10000.0

                fee_low_bps = _fee_to_bps(_safe_int(lowp.get("fee"), 0))
                fee_high_bps = _fee_to_bps(_safe_int(highp.get("fee"), 0))
                fee_total_bps = fee_low_bps + fee_high_bps

                # gas -> token0 (only when WETH involved)
                gas_token0_human, gas_note = _gas_cost_token0_human(
                    gas_cost_wei=gas_cost_wei,
                    symbol0=lowp.get("symbol0"),
                    symbol1=lowp.get("symbol1"),
                    price_token1_per_token0=p_low,  # conversion needs low-side price is fine
                )

                # gas bps 需要 trade_size 假设：用 env 覆盖
                trade_size_token0 = _safe_float(os.getenv("V3_ARB_TRADE_SIZE_TOKEN0"), 10_000.0)
                gas_bps = None
                if gas_token0_human is not None and trade_size_token0 > 0:
                    gas_bps = (gas_token0_human / trade_size_token0) * 10000.0

                # net spread bps（如果无法换算 gas，则给 net_without_gas）
                net_without_gas_bps = gross_bps - fee_total_bps
                net_bps = net_without_gas_bps
                if gas_bps is not None:
                    net_bps = net_without_gas_bps - gas_bps

                opps.append(
                    {
                        "strategy": "v3_v3_fast_screen",
                        "pair_token0": lowp.get("token0"),
                        "pair_token1": lowp.get("token1"),
                        "symbol0": lowp.get("symbol0"),
                        "symbol1": lowp.get("symbol1"),
                        "best_buy_pool": lowp.get("pool"),
                        "best_sell_pool": highp.get("pool"),
                        "buy_fee": lowp.get("fee"),
                        "sell_fee": highp.get("fee"),
                        "buy_liquidity": lowp.get("liquidity"),
                        "sell_liquidity": highp.get("liquidity"),
                        "buy_price_token1_per_token0": p_low,
                        "sell_price_token1_per_token0": p_high,
                        "gross_spread_bps": gross_bps,
                        "fee_total_bps": fee_total_bps,
                        "net_spread_bps": net_bps,
                        "net_spread_bps_without_gas": net_without_gas_bps,
                        "gas_units": int(gas_units),
                        "gas_price_wei": int(gp),
                        "gas_cost_wei": int(gas_cost_wei),
                        "gas_cost_token0_human": gas_token0_human,
                        "gas_conversion_note": gas_note,
                        "assumptions": {
                            "trade_size_token0": trade_size_token0,
                            "note": "FAST screening (no tick-level simulation). Use V3_ARB_MODE=deep for heavy validation.",
                        },
                    }
                )

    opps.sort(key=lambda x: _safe_float(x.get("net_spread_bps"), -1e18), reverse=True)
    best = opps[0] if opps else {}

    return {
        "enabled": True,
        "mode": "fast",
        "chain": chain,
        "pool_count": len(v3_pools),
        "opportunities": opps[:25],  # report 不要太长
        "best": best,
        "warnings": warnings,
        "assumptions": {"gas_units": gas_units, "gas_price_wei": gas_price_wei},
    }


# ============================================================
# ✅ DEEP 模拟：tick 扫描 + swap step（两腿模拟）
#    注意：可能很慢，RPC 不稳会卡死；不要在 pipeline 默认调用
# ============================================================

# TickMath constants
MIN_TICK = -887272
MAX_TICK = 887272
MIN_SQRT_RATIO = 4295128739
MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342


def _mul_shift(a: int, b: int) -> int:
    return (a * b) >> 128


def get_sqrt_ratio_at_tick(tick: int) -> int:
    if tick < MIN_TICK or tick > MAX_TICK:
        raise ValueError("tick out of range")

    abs_tick = -tick if tick < 0 else tick

    ratio = 0x100000000000000000000000000000000
    if abs_tick & 0x1:
        ratio = _mul_shift(ratio, 0xfffcb933bd6fad37aa2d162d1a594001)
    if abs_tick & 0x2:
        ratio = _mul_shift(ratio, 0xfff97272373d413259a46990580e213a)
    if abs_tick & 0x4:
        ratio = _mul_shift(ratio, 0xfff2e50f5f656932ef12357cf3c7fdcc)
    if abs_tick & 0x8:
        ratio = _mul_shift(ratio, 0xffe5caca7e10e4e61c3624eaa0941cd0)
    if abs_tick & 0x10:
        ratio = _mul_shift(ratio, 0xffcb9843d60f6159c9db58835c926644)
    if abs_tick & 0x20:
        ratio = _mul_shift(ratio, 0xff973b41fa98c081472e6896dfb254c0)
    if abs_tick & 0x40:
        ratio = _mul_shift(ratio, 0xff2ea16466c96a3843ec78b326b52861)
    if abs_tick & 0x80:
        ratio = _mul_shift(ratio, 0xfe5dee046a99a2a811c461f1969c3053)
    if abs_tick & 0x100:
        ratio = _mul_shift(ratio, 0xfcbe86c7900a88aedcffc83b479aa3a4)
    if abs_tick & 0x200:
        ratio = _mul_shift(ratio, 0xf987a7253ac413176f2b074cf7815e54)
    if abs_tick & 0x400:
        ratio = _mul_shift(ratio, 0xf3392b0822b70005940c7a398e4b70f3)
    if abs_tick & 0x800:
        ratio = _mul_shift(ratio, 0xe7159475a2c29b7443b29c7fa6e889d9)
    if abs_tick & 0x1000:
        ratio = _mul_shift(ratio, 0xd097f3bdfd2022b8845ad8f792aa5825)
    if abs_tick & 0x2000:
        ratio = _mul_shift(ratio, 0xa9f746462d870fdf8a65dc1f90e061e5)
    if abs_tick & 0x4000:
        ratio = _mul_shift(ratio, 0x70d869a156d2a1b890bb3df62baf32f7)
    if abs_tick & 0x8000:
        ratio = _mul_shift(ratio, 0x31be135f97d08fd981231505542fcfa6)
    if abs_tick & 0x10000:
        ratio = _mul_shift(ratio, 0x9aa508b5b7a84e1c677de54f3e99bc9)
    if abs_tick & 0x20000:
        ratio = _mul_shift(ratio, 0x5d6af8dedb81196699c329225ee604)
    if abs_tick & 0x40000:
        ratio = _mul_shift(ratio, 0x2216e584f5fa1ea926041bedfe98)
    if abs_tick & 0x80000:
        ratio = _mul_shift(ratio, 0x48a170391f7dc42444e8fa2)

    if tick > 0:
        ratio = (1 << 256) // ratio

    sqrt_price_x96 = (ratio >> 32) + (1 if (ratio & ((1 << 32) - 1)) != 0 else 0)
    return int(sqrt_price_x96)


def mul_div(a: int, b: int, denom: int) -> int:
    if denom == 0:
        raise ZeroDivisionError("mul_div denom=0")
    return (a * b) // denom


def mul_div_round_up(a: int, b: int, denom: int) -> int:
    if denom == 0:
        raise ZeroDivisionError("mul_div denom=0")
    prod = a * b
    return (prod + denom - 1) // denom


def get_amount0_delta(sqrtA: int, sqrtB: int, liquidity: int, round_up: bool) -> int:
    if sqrtA > sqrtB:
        sqrtA, sqrtB = sqrtB, sqrtA
    if sqrtA == 0:
        raise ValueError("sqrtA=0")
    numerator1 = liquidity << 96
    numerator2 = sqrtB - sqrtA
    denom = sqrtB * sqrtA
    if round_up:
        return mul_div_round_up(numerator1 * numerator2, 1, denom)
    return mul_div(numerator1 * numerator2, 1, denom)


def get_amount1_delta(sqrtA: int, sqrtB: int, liquidity: int, round_up: bool) -> int:
    if sqrtA > sqrtB:
        sqrtA, sqrtB = sqrtB, sqrtA
    delta = sqrtB - sqrtA
    if round_up:
        return mul_div_round_up(liquidity, delta, Q96)
    return mul_div(liquidity, delta, Q96)


def get_next_sqrt_from_amount0_in_round_up(sqrtP: int, liquidity: int, amount0_in: int) -> int:
    if amount0_in == 0:
        return sqrtP
    numerator = (liquidity << 96) * sqrtP
    denom = (liquidity << 96) + amount0_in * sqrtP
    return mul_div_round_up(numerator, 1, denom)


def get_next_sqrt_from_amount1_in_round_down(sqrtP: int, liquidity: int, amount1_in: int) -> int:
    if amount1_in == 0:
        return sqrtP
    return sqrtP + mul_div(amount1_in, Q96, liquidity)


def compute_swap_step(
    sqrtP: int,
    sqrtPTarget: int,
    liquidity: int,
    amount_remaining: int,
    fee: int,
    zero_for_one: bool,
) -> Tuple[int, int, int, int]:
    if amount_remaining <= 0:
        return sqrtP, 0, 0, 0

    amount_remaining_less_fee = mul_div(amount_remaining, (FEE_DENOM - fee), FEE_DENOM)

    if zero_for_one:
        amount_in_max = get_amount0_delta(sqrtPTarget, sqrtP, liquidity, True)
        if amount_remaining_less_fee >= amount_in_max:
            sqrt_next = sqrtPTarget
            amount_in = amount_in_max
            amount_out = get_amount1_delta(sqrtPTarget, sqrtP, liquidity, False)
            fee_amount = mul_div_round_up(amount_in, fee, (FEE_DENOM - fee))
        else:
            sqrt_next = get_next_sqrt_from_amount0_in_round_up(sqrtP, liquidity, amount_remaining_less_fee)
            amount_in = amount_remaining_less_fee
            amount_out = get_amount1_delta(sqrt_next, sqrtP, liquidity, False)
            fee_amount = amount_remaining - amount_in
    else:
        amount_in_max = get_amount1_delta(sqrtP, sqrtPTarget, liquidity, True)
        if amount_remaining_less_fee >= amount_in_max:
            sqrt_next = sqrtPTarget
            amount_in = amount_in_max
            amount_out = get_amount0_delta(sqrtP, sqrtPTarget, liquidity, False)
            fee_amount = mul_div_round_up(amount_in, fee, (FEE_DENOM - fee))
        else:
            sqrt_next = get_next_sqrt_from_amount1_in_round_down(sqrtP, liquidity, amount_remaining_less_fee)
            amount_in = amount_remaining_less_fee
            amount_out = get_amount0_delta(sqrtP, sqrt_next, liquidity, False)
            fee_amount = amount_remaining - amount_in

    return int(sqrt_next), int(amount_in), int(amount_out), int(fee_amount)


@dataclass
class V3SimPool:
    chain: str
    pool: str
    token0: str
    token1: str
    decimals0: int
    decimals1: int
    symbol0: str
    symbol1: str
    fee: int
    tick_spacing: int
    sqrtP: int
    tick: int
    liquidity: int
    ticks: List[Tuple[int, int]]  # [(tick, liquidityNet), ...]


def build_sim_pool(pool_addr: str, chain: str, *, words_each_side: int = 8, max_ticks: int = 1200) -> Optional[V3SimPool]:
    snap = get_v3_pool_snapshot(pool_addr, network=chain)
    if not snap:
        return None

    raw = fetch_ticks_around_current(
        pool_addr,
        network=chain,
        words_each_side=words_each_side,
        max_ticks=max_ticks,
    )

    ticks_list = raw.get("ticks") or []
    ticks: List[Tuple[int, int]] = []
    for t in ticks_list:
        if not isinstance(t, dict):
            continue
        tick_i = int(t.get("tick"))
        liq_net = int(t.get("liquidityNet"))
        ticks.append((tick_i, liq_net))
    ticks.sort(key=lambda x: x[0])

    return V3SimPool(
        chain=chain,
        pool=Web3.to_checksum_address(pool_addr),
        token0=snap.token0,
        token1=snap.token1,
        decimals0=snap.token0_decimals,
        decimals1=snap.token1_decimals,
        symbol0=snap.token0_symbol,
        symbol1=snap.token1_symbol,
        fee=snap.fee,
        tick_spacing=snap.tick_spacing,
        sqrtP=snap.sqrt_price_x96,
        tick=snap.tick,
        liquidity=snap.liquidity,
        ticks=ticks,
    )


def _next_initialized_tick(pool: V3SimPool, tick_current: int, zero_for_one: bool) -> Optional[int]:
    if not pool.ticks:
        return None
    if zero_for_one:
        cand = None
        for t, _ in pool.ticks:
            if t <= tick_current:
                cand = t
            else:
                break
        return cand
    else:
        for t, _ in pool.ticks:
            if t > tick_current:
                return t
        return None


def _liq_net_at(pool: V3SimPool, tick: int) -> int:
    for t, ln in pool.ticks:
        if t == tick:
            return ln
    return 0


def simulate_swap_exact_in(
    pool: V3SimPool,
    amount_in: int,
    zero_for_one: bool,
    *,
    max_cross: int = 80,
) -> Tuple[int, Dict[str, Any]]:
    sqrtP = int(pool.sqrtP)
    tick = int(pool.tick)
    liquidity = int(pool.liquidity)
    fee = int(pool.fee)

    amount_remaining = int(amount_in)
    amount_out_acc = 0
    crossed = 0
    incomplete = False

    while amount_remaining > 0:
        if crossed > max_cross:
            incomplete = True
            break

        next_tick = _next_initialized_tick(pool, tick, zero_for_one)
        if next_tick is None:
            incomplete = True
            break

        sqrt_target = get_sqrt_ratio_at_tick(next_tick)
        if zero_for_one and sqrt_target >= sqrtP:
            incomplete = True
            break
        if (not zero_for_one) and sqrt_target <= sqrtP:
            incomplete = True
            break

        sqrt_next, amt_in, amt_out, fee_amt = compute_swap_step(
            sqrtP, sqrt_target, liquidity, amount_remaining, fee, zero_for_one
        )

        amount_remaining -= (amt_in + fee_amt)
        amount_out_acc += amt_out
        sqrtP = sqrt_next

        if sqrtP == sqrt_target:
            ln = _liq_net_at(pool, next_tick)
            if zero_for_one:
                liquidity -= ln
                tick = next_tick - 1
            else:
                liquidity += ln
                tick = next_tick
            crossed += 1
        else:
            break

        if liquidity <= 0:
            incomplete = True
            break

    dbg = {
        "final_sqrtP": sqrtP,
        "final_tick": tick,
        "crossed_ticks": crossed,
        "incomplete": incomplete,
        "amount_in_consumed": int(amount_in) - amount_remaining,
        "amount_in_left": int(amount_remaining),
    }
    return int(amount_out_acc), dbg


def _human_price_token1_per_token0(pool: V3SimPool) -> float:
    return float(v3_price_from_sqrtPriceX96(pool.sqrtP, pool.decimals0, pool.decimals1))


def compute_executable_v3_v3_arbitrage(
    pool_a: str,
    pool_b: str,
    *,
    chain: str = "mainnet",
    gas_units: int = 320_000,
    gas_price_wei: Optional[int] = None,
    words_each_side: int = 8,
    max_ticks: int = 1200,
) -> Dict[str, Any]:
    """
    ✅ DEEP 模式：tick 扫描 + swap step
    做一次“买入+卖出”的两腿模拟（token0 -> token1 -> token0），给出可执行净收益。

    约定：
    - token0/token1 顺序沿用 pool 内部顺序（非常重要）
    - 以 token0 作为记账单位（profit、net bps 都以 token0 计）
    - trade size 从环境变量读取：
        V3_ARB_TRADE_SIZE_TOKEN0 (默认 10000.0)
      如 token0=USDC，则代表 10k USDC 规模模拟
    """
    w3 = make_web3(chain)

    # --- build sim pools (tick snapshot) ---
    pa = build_sim_pool(pool_a, chain, words_each_side=words_each_side, max_ticks=max_ticks)
    pb = build_sim_pool(pool_b, chain, words_each_side=words_each_side, max_ticks=max_ticks)

    if not pa or not pb:
        return {"network": chain, "error": "failed to build sim pools", "pool_a": pool_a, "pool_b": pool_b}

    if pa.token0.lower() != pb.token0.lower() or pa.token1.lower() != pb.token1.lower():
        return {
            "network": chain,
            "error": "token mismatch",
            "pool_a": pa.pool,
            "pool_b": pb.pool,
            "token0_a": pa.token0,
            "token0_b": pb.token0,
            "token1_a": pa.token1,
            "token1_b": pb.token1,
        }

    # --- spot prices from current sqrtP (human token1 per token0) ---
    price_a = _human_price_token1_per_token0(pa)
    price_b = _human_price_token1_per_token0(pb)

    # choose buy(low price token1 per token0) & sell(high price token1 per token0)
    if price_a <= price_b:
        buy, sell = pa, pb
        low_spot, high_spot = price_a, price_b
    else:
        buy, sell = pb, pa
        low_spot, high_spot = price_b, price_a

    # --- trade size (token0) ---
    trade_size_token0 = _safe_float(os.getenv("V3_ARB_TRADE_SIZE_TOKEN0"), 10_000.0)
    amount0_in_raw = _to_raw(trade_size_token0, buy.decimals0)
    if amount0_in_raw <= 0:
        return {"network": chain, "error": "invalid trade size", "trade_size_token0": trade_size_token0}

    # --- simulation parameters ---
    max_cross = _safe_int(os.getenv("V3_ARB_MAX_TICK_CROSS"), 80)

    # ------------------------------------------------------------
    # LEG 1: buy pool, token0 -> token1 (zero_for_one=True)
    # ------------------------------------------------------------
    amount1_out_raw, dbg_buy = simulate_swap_exact_in(
        buy,
        amount0_in_raw,
        True,  # token0 -> token1
        max_cross=max_cross,
    )

    # if buy leg cannot finish, mark non-executable
    if amount1_out_raw <= 0 or bool(dbg_buy.get("incomplete")):
        return {
            "network": chain,
            "strategy": "v3_v3_deep_sim",
            "pair_token0": buy.token0,
            "pair_token1": buy.token1,
            "symbol0": buy.symbol0,
            "symbol1": buy.symbol1,
            "best_buy_pool": buy.pool,
            "best_sell_pool": sell.pool,
            "buy_fee": buy.fee,
            "sell_fee": sell.fee,
            "spot_buy_price_token1_per_token0": float(low_spot),
            "spot_sell_price_token1_per_token0": float(high_spot),
            "executable": False,
            "reason": "buy leg incomplete or zero output",
            "buy_leg_debug": dbg_buy,
            "assumptions": {
                "trade_size_token0": trade_size_token0,
                "max_tick_cross": max_cross,
                "words_each_side": words_each_side,
                "max_ticks": max_ticks,
            },
        }

    # ------------------------------------------------------------
    # LEG 2: sell pool, token1 -> token0 (zero_for_one=False)
    # ------------------------------------------------------------
    amount0_out_raw, dbg_sell = simulate_swap_exact_in(
        sell,
        int(amount1_out_raw),
        False,  # token1 -> token0
        max_cross=max_cross,
    )

    if amount0_out_raw <= 0 or bool(dbg_sell.get("incomplete")):
        return {
            "network": chain,
            "strategy": "v3_v3_deep_sim",
            "pair_token0": buy.token0,
            "pair_token1": buy.token1,
            "symbol0": buy.symbol0,
            "symbol1": buy.symbol1,
            "best_buy_pool": buy.pool,
            "best_sell_pool": sell.pool,
            "buy_fee": buy.fee,
            "sell_fee": sell.fee,
            "spot_buy_price_token1_per_token0": float(low_spot),
            "spot_sell_price_token1_per_token0": float(high_spot),
            "executable": False,
            "reason": "sell leg incomplete or zero output",
            "buy_leg_debug": dbg_buy,
            "sell_leg_debug": dbg_sell,
            "assumptions": {
                "trade_size_token0": trade_size_token0,
                "max_tick_cross": max_cross,
                "words_each_side": words_each_side,
                "max_ticks": max_ticks,
            },
        }

    # --- humanize amounts ---
    amount0_in_h = _from_raw(amount0_in_raw, buy.decimals0)
    amount1_out_h = _from_raw(amount1_out_raw, buy.decimals1)
    amount0_out_h = _from_raw(amount0_out_raw, buy.decimals0)

    profit_token0_h = amount0_out_h - amount0_in_h
    gross_return_bps = (profit_token0_h / amount0_in_h) * 10000.0 if amount0_in_h > 0 else -1e18

    # --- reference: spot spread (not executable, just reference) ---
    rel_spot_spread = (high_spot - low_spot) / max(low_spot, 1e-18)
    spot_spread_bps = rel_spot_spread * 10000.0

    # --- reference: total fee bps (for reporting) ---
    fee_total_bps = _fee_to_bps(int(buy.fee)) + _fee_to_bps(int(sell.fee))

    # --- gas ---
    gp = int(gas_price_wei) if gas_price_wei is not None else int(w3.eth.gas_price)
    gas_cost_wei = int(gas_units) * int(gp)

    gas_token0_human, gas_note = _gas_cost_token0_human(
        gas_cost_wei=gas_cost_wei,
        symbol0=buy.symbol0,
        symbol1=buy.symbol1,
        price_token1_per_token0=float(low_spot),
    )

    gas_bps = None
    net_bps = gross_return_bps
    profit_after_gas_token0_h = None
    is_profitable_after_gas = None

    if gas_token0_human is not None and amount0_in_h > 0:
        gas_bps = (float(gas_token0_human) / amount0_in_h) * 10000.0
        net_bps = gross_return_bps - float(gas_bps)
        profit_after_gas_token0_h = profit_token0_h - float(gas_token0_human)
        is_profitable_after_gas = bool(profit_after_gas_token0_h > 0)

    # --- effective prices (after slippage) ---
    # buy: token1_out / token0_in  (token1 per token0)
    eff_buy_price_t1_per_t0 = (amount1_out_h / amount0_in_h) if amount0_in_h > 0 else None
    # sell: token0_out / token1_in (token0 per token1), then invert to token1 per token0 if needed
    eff_sell_price_t0_per_t1 = (amount0_out_h / amount1_out_h) if amount1_out_h > 0 else None
    eff_sell_price_t1_per_t0 = (1.0 / eff_sell_price_t0_per_t1) if (eff_sell_price_t0_per_t1 and eff_sell_price_t0_per_t1 > 0) else None

    return {
        "network": chain,
        "strategy": "v3_v3_deep_sim",

        # pair identity
        "pair_token0": buy.token0,
        "pair_token1": buy.token1,
        "symbol0": buy.symbol0,
        "symbol1": buy.symbol1,

        # chosen route (buy low, sell high)
        "best_buy_pool": buy.pool,
        "best_sell_pool": sell.pool,
        "buy_fee": int(buy.fee),
        "sell_fee": int(sell.fee),

        # spot info (reference only)
        "spot_buy_price_token1_per_token0": float(low_spot),
        "spot_sell_price_token1_per_token0": float(high_spot),
        "spot_spread_bps": float(spot_spread_bps),

        # effective trade results (tick-level)
        "trade_size_token0": float(trade_size_token0),
        "amount0_in_token0_human": float(amount0_in_h),
        "amount1_out_token1_human": float(amount1_out_h),
        "amount0_out_token0_human": float(amount0_out_h),
        "effective_buy_price_token1_per_token0": eff_buy_price_t1_per_t0,
        "effective_sell_price_token1_per_token0": eff_sell_price_t1_per_t0,

        # profitability
        "fee_total_bps_reference": float(fee_total_bps),
        "profit_token0_human": float(profit_token0_h),
        "gross_return_bps": float(gross_return_bps),
        "net_spread_bps_without_gas": float(gross_return_bps),
        "net_spread_bps": float(net_bps),
        "is_profitable_after_gas_token0": is_profitable_after_gas,
        "profit_after_gas_token0_human": profit_after_gas_token0_h,

        # gas
        "gas_units": int(gas_units),
        "gas_price_wei": int(gp),
        "gas_cost_wei": int(gas_cost_wei),
        "gas_cost_token0_human": gas_token0_human,
        "gas_bps": gas_bps,
        "gas_conversion_note": gas_note,

        # executability
        "executable": True,

        # debug
        "buy_leg_debug": dbg_buy,
        "sell_leg_debug": dbg_sell,

        "assumptions": {
            "max_tick_cross": max_cross,
            "words_each_side": words_each_side,
            "max_ticks": max_ticks,
            "note": "DEEP sim: token0->token1 on buy pool, then token1->token0 on sell pool; tick-level swap steps included.",
        },
    }