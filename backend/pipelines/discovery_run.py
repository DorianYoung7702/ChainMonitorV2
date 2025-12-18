# backend/pipelines/discovery_run.py
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import sys, os

# 将 backend 目录添加到 Python 路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.storage.db import MonitorDatabase
from backend.market_loader import load_markets
from backend.sources.dex_screener import DexScreener

# 你原来的 V2 collectors
from backend.collectors.chain_data import fetch_recent_swaps, fetch_arbitrage_opportunities
from backend.collectors.whale_cex import fetch_whale_metrics, fetch_cex_net_inflow
from backend.analysis.evaluate_signal import fetch_price_series, compute_realized_stats

# ----------------------------
# 可选：V3 数据采集（如果文件存在就用）
# ----------------------------
try:
    from backend.collectors.v3_data import (
        fetch_v3_pool_state,
        fetch_v3_liquidity_distribution,
        v3_price_from_sqrtPriceX96,
    )
except Exception:
    fetch_v3_pool_state = None
    fetch_v3_liquidity_distribution = None
    v3_price_from_sqrtPriceX96 = None

# 可选：V3 更高级分析（如果文件存在就用）
try:
    from backend.analysis.v3_analysis import (
        compare_v3_fee_tiers,
        detect_v2_v3_spread,
    )
except Exception:
    compare_v3_fee_tiers = None
    detect_v2_v3_spread = None

# ----------------------------
# 可选：Cross-chain 数据采集（如果文件存在就用）
# ----------------------------
try:
    from backend.collectors.cross_chain_data import build_cross_chain_comparison
except Exception:
    build_cross_chain_comparison = None


OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _wei_to_eth(x: Any) -> float:
    try:
        return float(int(x)) / 1e18
    except Exception:
        return 0.0


def _safe_whale_metrics(x: Any) -> Dict[str, Any]:
    """
    兼容 whale_cex.fetch_whale_metrics 可能返回 dict 或 tuple 的情况。
    pipeline 建议返回 dict：{"whale_sell_total":..., "whale_count_selling":...}
    """
    if isinstance(x, dict):
        return {
            "whale_sell_total": int(x.get("whale_sell_total") or 0),
            "whale_count_selling": int(x.get("whale_count_selling") or 0),
        }
    if isinstance(x, tuple) and len(x) >= 2:
        return {"whale_sell_total": int(x[0] or 0), "whale_count_selling": int(x[1] or 0)}
    return {"whale_sell_total": 0, "whale_count_selling": 0}


def _to_dexscreener_chain_id(chain: str) -> str:
    c = (chain or "").lower()
    if c in ("mainnet", "ethereum", "eth"):
        return "ethereum"
    if c in ("bsc", "binance", "bnb"):
        return "bsc"
    return c


def _find_first_v2_pair(markets: List[Dict[str, Any]]) -> Optional[str]:
    """
    找到 markets.json 里第一个 v2 pool（dex_pool）
    """
    for m in markets:
        if not isinstance(m, dict):
            continue
        if (m.get("type") or "").lower() in ("dex_pool", "dexpool", "pool"):
            pair_addr = m.get("pairAddress") or m.get("pair_address") or m.get("address")
            if pair_addr:
                return str(pair_addr)
    return None


def _find_v3_pools(markets: List[Dict[str, Any]], chain: str) -> List[Dict[str, Any]]:
    """
    找到 markets.json 里 type = dex_pool_v3 的配置
    约定字段：
      - type: dex_pool_v3
      - poolAddress/address: v3 pool 地址
      - fee: 500/3000/10000 (可选)
      - network/mainnet/bsc... (可选，不填就默认当前 chain)
    """
    out: List[Dict[str, Any]] = []
    for m in markets:
        if not isinstance(m, dict):
            continue
        t = (m.get("type") or "").lower()
        if t != "dex_pool_v3":
            continue
        net = (m.get("network") or m.get("chain") or "").lower()
        if net and net != (chain or "").lower():
            continue
        addr = m.get("poolAddress") or m.get("pool_address") or m.get("address")
        if not addr:
            continue
        out.append(m)
    return out


def save_report_to_md(report: Dict[str, Any], output_dir: Path = OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"report_{timestamp}.md"
    report_file = output_dir / file_name

    chain = report["chain"]
    start_time = report["start_time"]
    end_time = report["end_time"]

    swap_count = report.get("swap_count", 0)
    price_points = report.get("price_points", 0)
    first_price = report.get("first_price")
    last_price = report.get("last_price")

    stats = report.get("realized_stats", {}) or {}
    whale = report.get("whale_metrics", {}) or {}

    whale_sell_eth = _wei_to_eth(whale.get("whale_sell_total", 0))
    net_inflow_eth = _wei_to_eth(report.get("cex_net_inflow_wei", 0))

    arbs = report.get("arbitrage_opportunities", []) or []
    arb_count = len(arbs)

    warnings: List[str] = report.get("warnings", []) or []

    v3_block = report.get("v3", {}) or {}
    cross_chain = report.get("cross_chain_comparison", {}) or {}

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("# Data Discovery Report\n\n")
        f.write(f"- **Generated**: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"- **Chain**: `{chain}`\n")
        f.write(f"- **Window**: {start_time.isoformat(timespec='seconds')} → {end_time.isoformat(timespec='seconds')}\n\n")

        f.write("## Swap Collection\n")
        f.write(f"- Swaps collected: **{swap_count}**\n")
        f.write(f"- Price points computed: **{price_points}**\n")
        if first_price is not None and last_price is not None:
            f.write(f"- First price (token0 per token1): **{first_price:.6f}**\n")
            f.write(f"- Last  price (token0 per token1): **{last_price:.6f}**\n")
        f.write("\n")

        f.write("## Realized Stats (from swaps)\n")
        f.write(f"- Realized return: **{float(stats.get('realized_return', 0.0)):.4f}%**\n")
        f.write(f"- Realized vol: **{float(stats.get('realized_vol', 0.0)):.4f}%**\n")
        f.write(f"- Max drawdown: **{float(stats.get('realized_drawdown', 0.0)):.4f}%**\n\n")

        f.write("## Whale / CEX Flows\n")
        f.write(f"- Whale sell pressure: **{whale_sell_eth:.6f} ETH**\n")
        f.write(f"- Selling whales: **{int(whale.get('whale_count_selling', 0))}**\n")
        f.write(f"- CEX net inflow: **{net_inflow_eth:.6f} ETH**\n\n")

        f.write("## Arbitrage (cross-pool spread)\n")
        f.write(f"- Opportunities detected: **{arb_count}**\n")
        if arb_count > 0:
            top = arbs[:5]
            f.write("\nTop opportunities (up to 5):\n")
            for i, a in enumerate(top, 1):
                f.write(
                    f"- {i}. pair={a.get('pair')} spread={float(a.get('relative_spread', 0.0))*100:.4f}% "
                    f"low_pool={a.get('low_price_pool')} high_pool={a.get('high_price_pool')} "
                    f"profitable_after_gas={a.get('is_profitable_after_gas_token0', False)}\n"
                )
        f.write("\n")

        # ✅ V3 报告块
        f.write("## Uniswap V3 Snapshot\n")
        if not v3_block:
            f.write("- No V3 pools configured or v3_data not available.\n\n")
        else:
            pools = v3_block.get("pools", []) or []
            f.write(f"- V3 pools scanned: **{len(pools)}**\n")
            for p in pools[:5]:
                f.write(
                    f"- pool={p.get('pool')} fee={p.get('fee')} tick={p.get('tick')} "
                    f"liquidity={p.get('liquidity')} price_token1_per_token0={p.get('price_token1_per_token0')}\n"
                )
            fee_cmp = v3_block.get("fee_tier_comparison")
            if fee_cmp:
                f.write("\n### V3 Fee Tier Comparison\n")
                f.write("```json\n")
                f.write(json.dumps(fee_cmp, indent=2, default=str))
                f.write("\n```\n")
            v2v3 = v3_block.get("v2_v3_spread")
            if v2v3:
                f.write("\n### V2 ↔ V3 Spread\n")
                f.write("```json\n")
                f.write(json.dumps(v2v3, indent=2, default=str))
                f.write("\n```\n")
            f.write("\n")

        # ✅ Cross-chain 报告块
        f.write("## Cross-chain Comparison\n")
        if not cross_chain:
            f.write("- No cross-chain comparison available.\n")
            f.write("- If you want cross-chain bonus: implement backend/collectors/cross_chain_data.py (build_cross_chain_comparison)\n\n")
        else:
            f.write("```json\n")
            f.write(json.dumps(cross_chain, indent=2, default=str))
            f.write("\n```\n\n")

        if warnings:
            f.write("## Warnings\n")
            for w in warnings:
                f.write(f"- {w}\n")
            f.write("\n")

        f.write("## Raw JSON\n")
        f.write("```json\n")
        f.write(json.dumps(report, indent=2, default=str))
        f.write("\n```\n")

    return report_file


def run_discovery(chain: str, hours: int, output_dir: Path = OUTPUT_DIR):
    print(f"Running data discovery for chain: {chain}, over the past {hours} hours")

    # Init DB (often triggers migrations)
    _db = MonitorDatabase()

    markets = load_markets()

    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)

    # 1) swaps (V2)
    swap_data = fetch_recent_swaps(markets, start_time, end_time, chain)

    # 2) whale / cex
    whale_metrics_raw = fetch_whale_metrics(markets, start_time, end_time, chain)
    whale_metrics = _safe_whale_metrics(whale_metrics_raw)

    cex_net_inflow_wei = fetch_cex_net_inflow(markets, start_time, end_time, chain)

    # 3) price series from swaps (NOT DB)
    price_series = fetch_price_series(
        swap_data,
        start_time=start_time,
        end_time=end_time,
        chain=chain,
    )
    stats = compute_realized_stats(price_series)

    first_price = price_series[0][1] if len(price_series) >= 1 else None
    last_price = price_series[-1][1] if len(price_series) >= 1 else None

    # --- source: DexScreener ---
    ds = DexScreener()
    pair_addr = _find_first_v2_pair(markets)
    dexscreener_snapshot = {}
    if pair_addr:
        chain_id = _to_dexscreener_chain_id(chain)
        dexscreener_snapshot = ds.pair(chain_id, pair_addr) or {}

    # 4) arbitrage (V2 cross-pool)
    arbs = fetch_arbitrage_opportunities(markets, start_time, end_time, chain)

    warnings: List[str] = []
    if len(price_series) < 2:
        warnings.append("Not enough price points from swaps to compute meaningful realized stats (need >=2).")
    if any((m.get("address") == "0xYourWhaleAddressHere") for m in markets if isinstance(m, dict)):
        warnings.append("markets.json still contains placeholder whale address 0xYourWhaleAddressHere (it will always be skipped).")

    # ✅ 5) V3：如果 markets.json 配了 dex_pool_v3 且 v3_data 可用，就输出
    v3_report: Dict[str, Any] = {}
    v3_pools = _find_v3_pools(markets, chain)

    if v3_pools and fetch_v3_pool_state is None:
        warnings.append("v3_data.py not importable. Ensure backend/collectors/v3_data.py exists and has required functions.")
    elif v3_pools and fetch_v3_pool_state is not None:
        pool_snapshots: List[Dict[str, Any]] = []
        for m in v3_pools:
            pool_addr = m.get("poolAddress") or m.get("address")
            fee = int(m.get("fee") or 0)
            try:
                st = fetch_v3_pool_state(pool_addr, chain=chain)

                price_t1_per_t0 = None
                if v3_price_from_sqrtPriceX96 and st.get("sqrtPriceX96") is not None:
                    price_t1_per_t0 = v3_price_from_sqrtPriceX96(
                        int(st["sqrtPriceX96"]),
                        int(st.get("decimals0", 18)),
                        int(st.get("decimals1", 18)),
                    )

                row = {
                    "pool": pool_addr,
                    "fee": fee or st.get("fee"),
                    "tick": st.get("tick"),
                    "sqrtPriceX96": st.get("sqrtPriceX96"),
                    "liquidity": st.get("liquidity"),
                    "token0": st.get("token0"),
                    "token1": st.get("token1"),
                    "price_token1_per_token0": price_t1_per_t0,
                }

                # 可选：tick 流动性分布（摘要）
                if fetch_v3_liquidity_distribution:
                    dist = fetch_v3_liquidity_distribution(
                        pool_addr,
                        chain=chain,
                        num_ticks_each_side=200,
                    )
                    if isinstance(dist, dict):
                        row["liquidity_distribution_summary"] = dist.get("summary") or {}

                pool_snapshots.append(row)

            except Exception as e:
                warnings.append(f"V3 pool fetch failed: pool={pool_addr} err={str(e)[:160]}")

        v3_report["pools"] = pool_snapshots

        # 可选：fee tier 对比
        if compare_v3_fee_tiers:
            try:
                v3_report["fee_tier_comparison"] = compare_v3_fee_tiers(pool_snapshots)
            except Exception as e:
                warnings.append(f"compare_v3_fee_tiers failed: {str(e)[:160]}")

        # 可选：V2↔V3 价差
        if detect_v2_v3_spread and pair_addr and pool_snapshots:
            try:
                v3_report["v2_v3_spread"] = detect_v2_v3_spread(
                    v2_pair_address=pair_addr,
                    v3_pools=pool_snapshots,
                    chain=chain,
                )
            except Exception as e:
                warnings.append(f"detect_v2_v3_spread failed: {str(e)[:160]}")

    # ✅ 6) Cross-chain：如果实现了 cross_chain_data.py，就生成跨链对比
    cross_chain_report: Dict[str, Any] = {}
    if build_cross_chain_comparison is not None:
        try:
            cross_chain_report = build_cross_chain_comparison(
                markets=markets,
                start_time=start_time,
                end_time=end_time,
                base_chain=chain,
            ) or {}
        except Exception as e:
            warnings.append(f"cross_chain_comparison failed: {str(e)[:160]}")
    else:
        # 不强制报错，但提示你 bonus 缺口
        pass

    report_data: Dict[str, Any] = {
        "chain": chain,
        "start_time": start_time,
        "end_time": end_time,
        "swap_count": len(swap_data) if isinstance(swap_data, list) else 0,
        "price_points": len(price_series),
        "first_price": first_price,
        "last_price": last_price,
        "realized_stats": stats,
        "whale_metrics": whale_metrics,
        "cex_net_inflow_wei": int(cex_net_inflow_wei or 0),
        "arbitrage_opportunities": arbs,
        "warnings": warnings,
        "dexscreener": dexscreener_snapshot,
        # ✅ 新增
        "v3": v3_report,
        "cross_chain_comparison": cross_chain_report,
    }

    report_path = save_report_to_md(report_data, output_dir=output_dir)
    print(f"✅ Report successfully generated: {report_path.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run data discovery")
    parser.add_argument("--chain", type=str, default="mainnet", help="Blockchain network (e.g., mainnet)")
    parser.add_argument("--hours", type=int, default=24, help="Number of hours of data to analyze")
    args = parser.parse_args()

    run_discovery(args.chain, args.hours)