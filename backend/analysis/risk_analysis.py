from typing import Dict, Any, List
import math


def calculate_realized_risk(realized_stats: Dict[str, Any]) -> float:
    """
    计算基于历史收益的风险，使用波动率和最大回撤
    """
    realized_vol = float(realized_stats.get("realized_vol", 0.0))
    realized_drawdown = float(realized_stats.get("realized_drawdown", 0.0))

    # 使用波动率和最大回撤来加权风险
    vol_weight = realized_vol * 0.5
    drawdown_weight = realized_drawdown * 0.5

    risk_score = vol_weight + drawdown_weight
    return max(0, min(risk_score, 100))  # 限制在 0 到 100 之间


def calculate_liquidity_risk(v3_snapshot: Dict[str, Any], v2_reserves: Dict[str, Any]) -> float:
    """
    基于V3池子的流动性分布和V2池子的预留流动性来评估流动性风险
    """
    # V3池子风险：gap_is_large，gap越大流动性风险越高
    v3_gap_is_large = v3_snapshot.get("summary", {}).get("gap_is_large", False)
    v3_liquidity = float(v3_snapshot.get("snapshot", {}).get("liquidity", 0))

    # V2池子风险：reserve0和reserve1的流动性较小的池子风险较高
    v2_reserve0 = float(v2_reserves.get("reserve0", 0))
    v2_reserve1 = float(v2_reserves.get("reserve1", 0))

    liquidity_risk = 0

    # V3流动性风险评估
    if v3_gap_is_large:
        liquidity_risk += 20  # gap过大，风险加成

    # V2流动性风险评估
    reserve_ratio = min(v2_reserve0, v2_reserve1) / max(v2_reserve0, v2_reserve1)
    if reserve_ratio < 0.5:
        liquidity_risk += 15  # 当流动性比值过低时，风险加成

    # 流动性风险值限制在0到100之间
    return max(0, min(liquidity_risk, 100))


def calculate_market_risk(whale_metrics: Dict[str, Any], cex_net_inflow_wei: float) -> float:
    """
    基于巨鲸卖出压力和CEX净流入来评估市场风险
    """
    whale_sell_total = int(whale_metrics.get("whale_sell_total", 0))
    whale_count_selling = int(whale_metrics.get("whale_count_selling", 0))

    # CEX净流入
    cex_net_inflow = cex_net_inflow_wei / 1e18  # 转换成ETH

    market_risk = 0

    # 如果有巨鲸卖出，总量和数量越大，市场风险越高
    if whale_sell_total > 0:
        market_risk += 20  # 卖出压力增加市场风险
    if whale_count_selling > 0:
        market_risk += 10  # 更多卖出鲸鱼，加剧市场的不稳定性

    # CEX净流入：大规模的净流入可能意味着市场上存在大量资金进入，可能会导致价格波动
    if cex_net_inflow > 50:  # 假设 50 ETH 是高净流入
        market_risk += 15  # 大量资金流入可能增加市场波动

    # 市场风险值限制在0到100之间
    return max(0, min(market_risk, 100))


def calculate_execution_risk(gas_price_wei: int, is_profitable_after_gas: bool) -> float:
    """
    计算基于gas费用和套利是否执行的风险
    """
    gas_cost_wei = gas_price_wei * 240000  # 假设gas单位240000
    gas_cost_eth = gas_cost_wei / 1e18  # 转换为ETH

    execution_risk = 0

    # 如果交易不盈利（after-gas），则不执行
    if not is_profitable_after_gas:
        execution_risk += 50  # 如果不盈利，则为最大风险

    # gas费用过高的情况，可能增加风险
    if gas_cost_eth > 0.1:  # 假设高于0.1 ETH是高风险
        execution_risk += 30

    return max(0, min(execution_risk, 100))


def calculate_risk_score(realized_stats: Dict[str, Any], v3_snapshot: Dict[str, Any], v2_reserves: Dict[str, Any],
                         whale_metrics: Dict[str, Any], cex_net_inflow_wei: float, gas_price_wei: int,
                         is_profitable_after_gas: bool) -> Dict[str, Any]:
    """
    综合计算套利机会的风险分数，并提供可解释的风险原因
    """
    # 计算不同类型的风险
    realized_risk = calculate_realized_risk(realized_stats)
    liquidity_risk = calculate_liquidity_risk(v3_snapshot, v2_reserves)
    market_risk = calculate_market_risk(whale_metrics, cex_net_inflow_wei)
    execution_risk = calculate_execution_risk(gas_price_wei, is_profitable_after_gas)

    # 总风险分数
    total_risk = realized_risk + liquidity_risk + market_risk + execution_risk
    total_risk = min(total_risk, 100)

    # 风险原因解释
    risk_reasons = []
    if realized_risk > 0:
        risk_reasons.append(f"Realized risk (volatility, drawdown): {realized_risk}%")
    if liquidity_risk > 0:
        risk_reasons.append(f"Liquidity risk (gap, reserves): {liquidity_risk}%")
    if market_risk > 0:
        risk_reasons.append(f"Market risk (whale sell, CEX inflow): {market_risk}%")
    if execution_risk > 0:
        risk_reasons.append(f"Execution risk (gas, after-gas profitability): {execution_risk}%")

    return {
        "risk_score": total_risk,
        "risk_reasons": risk_reasons
    }


# Example usage:
realized_stats = {
    "realized_vol": 2.5,
    "realized_drawdown": -0.5
}
v3_snapshot = {
    "summary": {
        "gap_is_large": False
    },
    "snapshot": {
        "liquidity": 1000,
        "tick_spacing": 10
    }
}
v2_reserves = {
    "reserve0": 500000,
    "reserve1": 200000
}
whale_metrics = {
    "whale_sell_total": 1000,
    "whale_count_selling": 2
}
cex_net_inflow_wei = 50000000000000000000
gas_price_wei = 10000000000
is_profitable_after_gas = True

risk_analysis_result = calculate_risk_score(realized_stats, v3_snapshot, v2_reserves, whale_metrics,
                                            cex_net_inflow_wei, gas_price_wei, is_profitable_after_gas)

print(risk_analysis_result)