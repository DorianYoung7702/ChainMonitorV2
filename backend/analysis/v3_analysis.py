# backend/analysis/v3_analysis.py
from __future__ import annotations

from decimal import Decimal, getcontext
from typing import Any, Dict, List, Optional, Tuple

# 高精度，避免 sqrtPriceX96^2 造成精度问题
getcontext().prec = 80

Q96 = Decimal(2) ** 96
Q192 = Decimal(2) ** 192


def sqrtPriceX96_to_price_token1_per_token0(
    sqrt_price_x96: int,
    token0_decimals: int,
    token1_decimals: int,
) -> Decimal:
    """
    V3 pool mid price:
      raw_price = (sqrtP^2) / 2^192   (raw units: token1_raw / token0_raw)
      human_price = raw_price * 10^(dec0-dec1)
    """
    sp = Decimal(int(sqrt_price_x96))
    raw = (sp * sp) / Q192
    adj = Decimal(10) ** Decimal(int(token0_decimals - token1_decimals))
    return raw * adj


def tick_to_price_token1_per_token0(
    tick: int,
    token0_decimals: int,
    token1_decimals: int,
) -> Decimal:
    """
    price = 1.0001^tick * 10^(dec0-dec1)
    """
    base = Decimal("1.0001") ** Decimal(int(tick))
    adj = Decimal(10) ** Decimal(int(token0_decimals - token1_decimals))
    return base * adj


def price_to_tick_approx(price_token1_per_token0: Decimal) -> int:
    """
    近似反解 tick（用于展示/调试，不用于严格执行）。
    """
    # tick = ln(price) / ln(1.0001)
    # Decimal 没有 ln；用 float 做近似即可
    import math

    p = float(price_token1_per_token0)
    if p <= 0:
        return 0
    return int(math.log(p) / math.log(1.0001))


def fee_to_fraction(fee: int) -> Decimal:
    """
    V3 fee: 500/3000/10000 (1e-6)
    fee fraction = fee / 1,000,000
    """
    return Decimal(int(fee)) / Decimal(1_000_000)


def _sqrtP_from_x96(sqrt_price_x96: int) -> Decimal:
    return Decimal(int(sqrt_price_x96)) / Q96


def estimate_swap_within_current_range_exact_in(
    *,
    amount_in_raw: int,
    zero_for_one: bool,
    sqrt_price_x96: int,
    liquidity: int,
    fee: int,
) -> Dict[str, Any]:
    """
    在“不跨 tick”的前提下，使用 V3 恒定流动性公式近似计算：
    - zero_for_one=True: 用 token0 换 token1（价格向下）
    - zero_for_one=False: 用 token1 换 token0（价格向上）

    这是“高级机制展示”的关键：你明确说明这是 range 内近似，
    若要严格执行需逐 tick 穿越（可用 ticks 分布迭代扩展）。
    """
    L = Decimal(int(liquidity))
    if L <= 0:
        return {"ok": False, "reason": "liquidity<=0"}

    f = fee_to_fraction(fee)
    amt_in = Decimal(int(amount_in_raw))
    amt_in_eff = amt_in * (Decimal(1) - f)

    sqrtP = _sqrtP_from_x96(sqrt_price_x96)
    if sqrtP <= 0:
        return {"ok": False, "reason": "sqrtP<=0"}

    # 输出：amount_out_raw(近似), new_price, price_impact
    if zero_for_one:
        # token0 -> token1: amount0 in, price down
        # sqrtQ = (L*sqrtP) / (L + amount0 * sqrtP)
        denom = (L + amt_in_eff * sqrtP)
        if denom <= 0:
            return {"ok": False, "reason": "denom<=0"}
        sqrtQ = (L * sqrtP) / denom
        amt1_out = L * (sqrtP - sqrtQ)  # token1 out (raw)
        mid_before = sqrtP * sqrtP
        mid_after = sqrtQ * sqrtQ
        impact = (mid_after - mid_before) / mid_before  # negative
        return {
            "ok": True,
            "amount_out_raw": int(max(0, amt1_out)),
            "sqrtP_before": str(sqrtP),
            "sqrtP_after": str(sqrtQ),
            "price_raw_before": str(mid_before),
            "price_raw_after": str(mid_after),
            "price_impact_fraction": float(impact),
            "fee_fraction": float(f),
        }
    else:
        # token1 -> token0: amount1 in, price up
        # sqrtQ = sqrtP + amount1/L
        sqrtQ = sqrtP + (amt_in_eff / L)
        if sqrtQ <= 0:
            return {"ok": False, "reason": "sqrtQ<=0"}
        amt0_out = L * (Decimal(1) / sqrtP - Decimal(1) / sqrtQ)  # token0 out (raw)
        mid_before = sqrtP * sqrtP
        mid_after = sqrtQ * sqrtQ
        impact = (mid_after - mid_before) / mid_before  # positive
        return {
            "ok": True,
            "amount_out_raw": int(max(0, amt0_out)),
            "sqrtP_before": str(sqrtP),
            "sqrtP_after": str(sqrtQ),
            "price_raw_before": str(mid_before),
            "price_raw_after": str(mid_after),
            "price_impact_fraction": float(impact),
            "fee_fraction": float(f),
        }


def build_liquidity_profile_from_ticks(
    *,
    current_tick: int,
    tick_spacing: int,
    current_liquidity: int,
    ticks: List[Dict[str, Any]],
    token0_decimals: int,
    token1_decimals: int,
    max_segments: int = 300,
) -> List[Dict[str, Any]]:
    """
    由 ticks(liquidityNet) 推导“分段有效流动性”：
    - 在 V3 中，active liquidity 在 tick 区间内为常量，跨越 initialized tick 发生跳变。
    - 这里做“当前 tick 周围窗口”的 profile，用于热图/缺口检测/滑点解释。

    输入 ticks: [{"tick":..., "liquidityNet":...}, ...] 已按 tick 升序。
    """
    # 过滤出 spacing 对齐的 tick
    ts = int(tick_spacing)
    if ts <= 0:
        return []

    # 仅取有限窗口 tick
    sorted_ticks = sorted(ticks, key=lambda x: int(x.get("tick", 0)))
    if not sorted_ticks:
        return []

    # 找到 current_tick 所在位置
    # active liquidity 在 current tick 内为 current_liquidity
    L = int(current_liquidity)

    # 我们构建 segments: [tick_i, tick_{i+1}) 的 liquidity
    # 在向上走时，遇到 tick boundary，L += liquidityNet(tick)
    segs: List[Dict[str, Any]] = []

    # 选取一个合理的切片范围：以 current_tick 为中心取前后若干个 boundary
    # 这里直接用传入 ticks 全部，但用 max_segments 截断。
    # 找 index
    idx = 0
    while idx < len(sorted_ticks) and int(sorted_ticks[idx]["tick"]) <= int(current_tick):
        idx += 1

    # 向上构建
    up_L = L
    up_ticks = sorted_ticks[idx:]
    last_tick = int(current_tick)

    for it in up_ticks:
        if len(segs) >= max_segments:
            break
        t = int(it["tick"])
        if t <= last_tick:
            continue
        segs.append(
            {
                "tick_lower": int(last_tick),
                "tick_upper": int(t),
                "liquidity": int(up_L),
                "price_lower": str(tick_to_price_token1_per_token0(last_tick, token0_decimals, token1_decimals)),
                "price_upper": str(tick_to_price_token1_per_token0(t, token0_decimals, token1_decimals)),
            }
        )
        # 跨过 boundary 后 liquidity 变化
        up_L = int(up_L + int(it.get("liquidityNet", 0)))
        last_tick = t

    # 向下构建（反方向）
    down_L = L
    down_ticks = list(reversed(sorted_ticks[:idx]))
    last_tick = int(current_tick)

    for it in down_ticks:
        if len(segs) >= max_segments:
            break
        t = int(it["tick"])
        if t >= last_tick:
            continue
        # 向下走：[t, last_tick)
        segs.append(
            {
                "tick_lower": int(t),
                "tick_upper": int(last_tick),
                "liquidity": int(down_L),
                "price_lower": str(tick_to_price_token1_per_token0(t, token0_decimals, token1_decimals)),
                "price_upper": str(tick_to_price_token1_per_token0(last_tick, token0_decimals, token1_decimals)),
            }
        )
        # 向下跨过 boundary，liquidity 变化方向与向上相反：
        # 如果向上跨过 tick: L += liquidityNet(tick)
        # 那么向下跨过 tick: L -= liquidityNet(tick)
        down_L = int(down_L - int(it.get("liquidityNet", 0)))
        last_tick = t

    # 最后按 tick_lower 排序
    segs.sort(key=lambda x: int(x["tick_lower"]))
    return segs


def detect_liquidity_gaps(
    profile: List[Dict[str, Any]],
    *,
    min_liquidity: Optional[int] = None,
    gap_percentile: float = 0.1,
) -> List[Dict[str, Any]]:
    """
    识别“流动性缺口”：
    - 如果未指定 min_liquidity，则用 profile liquidity 的分位数作为阈值（默认最低10%）。
    - 输出 liquidity 低于阈值的 segments。
    """
    if not profile:
        return []

    liqs = [int(x.get("liquidity", 0)) for x in profile]
    liqs_sorted = sorted(liqs)
    if min_liquidity is None:
        k = int(max(0, min(len(liqs_sorted) - 1, int(len(liqs_sorted) * gap_percentile))))
        min_liquidity = liqs_sorted[k]

    gaps: List[Dict[str, Any]] = []
    for seg in profile:
        if int(seg.get("liquidity", 0)) <= int(min_liquidity):
            gaps.append(
                {
                    "tick_lower": seg["tick_lower"],
                    "tick_upper": seg["tick_upper"],
                    "liquidity": int(seg.get("liquidity", 0)),
                    "price_lower": seg.get("price_lower"),
                    "price_upper": seg.get("price_upper"),
                }
            )
    return gaps


def compare_fee_tiers(
    snapshots: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    fee tier 套利的最小实现：
    - 输入多个 V3 snapshot（同一 token0/token1，不同 fee）
    - 计算 mid price，找出最高/最低的 fee tier 差异
    - 输出“可解释”的候选机会（后续可叠加滑点/成本）
    """
    # 按 token0-token1 分组
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for s in snapshots:
        t0 = s.get("token0")
        t1 = s.get("token1")
        if not t0 or not t1:
            continue
        key = f"{t0}-{t1}"
        groups.setdefault(key, []).append(s)

    out: List[Dict[str, Any]] = []
    for key, items in groups.items():
        if len(items) < 2:
            continue
        mids: List[Tuple[Decimal, Dict[str, Any]]] = []
        for it in items:
            try:
                mid = sqrtPriceX96_to_price_token1_per_token0(
                    int(it["sqrt_price_x96"]),
                    int(it["token0_decimals"]),
                    int(it["token1_decimals"]),
                )
                mids.append((mid, it))
            except Exception:
                continue
        if len(mids) < 2:
            continue
        mids.sort(key=lambda x: x[0])
        low_mid, low = mids[0]
        high_mid, high = mids[-1]
        if low_mid <= 0:
            continue
        spread = (high_mid - low_mid) / low_mid
        out.append(
            {
                "pair": key,
                "low_pool": low.get("pool_address"),
                "high_pool": high.get("pool_address"),
                "low_fee": int(low.get("fee", 0)),
                "high_fee": int(high.get("fee", 0)),
                "low_mid_price": str(low_mid),
                "high_mid_price": str(high_mid),
                "relative_spread": float(spread),
                "strategy": "v3_fee_tier_spread",
            }
        )
    out.sort(key=lambda x: x["relative_spread"], reverse=True)
    return out