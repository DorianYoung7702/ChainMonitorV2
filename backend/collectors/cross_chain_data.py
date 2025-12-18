# backend/collectors/cross_chain_data.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.sources.dex_screener import DexScreener


# ============================================================
# 1) 基础：Chain / Token / Bridge 配置
# ============================================================

def _norm_chain(chain: str) -> str:
    c = (chain or "").strip().lower()
    if c in ("mainnet", "ethereum", "eth"):
        return "ethereum"
    if c in ("bsc", "bnb", "binance"):
        return "bsc"
    if c in ("polygon", "matic"):
        return "polygon"
    if c in ("arbitrum", "arb"):
        return "arbitrum"
    if c in ("optimism", "op"):
        return "optimism"
    if c in ("base",):
        return "base"
    return c


@dataclass
class BridgeRoute:
    name: str
    from_chain: str
    to_chain: str
    fixed_fee_usd: float = 0.0
    variable_fee_bps: float = 0.0
    eta_seconds: int = 900


def _default_token_map() -> Dict[str, Dict[str, str]]:
    return {
        "USDC": {
            "ethereum": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "bsc": "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
        },
        "WETH": {
            "ethereum": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "bsc": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
        },
    }


def load_token_map() -> Dict[str, Dict[str, str]]:
    env_json = (os.getenv("CROSS_CHAIN_TOKEN_MAP_JSON") or "").strip()
    env_path = (os.getenv("CROSS_CHAIN_TOKEN_MAP_PATH") or "").strip()

    base = _default_token_map()

    try:
        if env_json:
            obj = json.loads(env_json)
            if isinstance(obj, dict):
                base.update(obj)
        elif env_path and os.path.exists(env_path):
            obj = json.loads(open(env_path, "r", encoding="utf-8").read())
            if isinstance(obj, dict):
                base.update(obj)
    except Exception:
        pass

    return base


def load_bridge_routes() -> List[BridgeRoute]:
    env_json = (os.getenv("CROSS_CHAIN_BRIDGE_ROUTES_JSON") or "").strip()
    env_path = (os.getenv("CROSS_CHAIN_BRIDGE_ROUTES_PATH") or "").strip()

    routes: List[BridgeRoute] = []
    raw: Any = None

    try:
        if env_json:
            raw = json.loads(env_json)
        elif env_path and os.path.exists(env_path):
            raw = json.loads(open(env_path, "r", encoding="utf-8").read())
    except Exception:
        raw = None

    if isinstance(raw, list):
        for x in raw:
            if not isinstance(x, dict):
                continue
            routes.append(
                BridgeRoute(
                    name=str(x.get("name") or "bridge"),
                    from_chain=_norm_chain(str(x.get("from_chain") or "")),
                    to_chain=_norm_chain(str(x.get("to_chain") or "")),
                    fixed_fee_usd=float(x.get("fixed_fee_usd") or 0.0),
                    variable_fee_bps=float(x.get("variable_fee_bps") or 0.0),
                    eta_seconds=int(x.get("eta_seconds") or 900),
                )
            )

    if not routes:
        routes = [
            BridgeRoute(name="default_bridge", from_chain="ethereum", to_chain="bsc", fixed_fee_usd=5.0, variable_fee_bps=10.0, eta_seconds=900),
            BridgeRoute(name="default_bridge", from_chain="bsc", to_chain="ethereum", fixed_fee_usd=3.0, variable_fee_bps=10.0, eta_seconds=900),
        ]

    return routes


def _get_float_env(key: str, default: float) -> float:
    v = (os.getenv(key) or "").strip()
    if not v:
        return float(default)
    try:
        return float(v)
    except Exception:
        return float(default)


def _get_trade_size_usd() -> float:
    return _get_float_env("CROSS_CHAIN_TRADE_SIZE_USD", 10000.0)


def _time_risk_bps(eta_seconds: int) -> float:
    per_min = _get_float_env("CROSS_CHAIN_TIME_RISK_BPS_PER_MIN", 1.0)
    mins = max(0.0, float(int(eta_seconds or 0)) / 60.0)
    return per_min * mins


def _get_gas_cost_usd(chain_id: str) -> float:
    cid = _norm_chain(chain_id)
    key = f"GAS_COST_USD_{cid.upper()}"
    v = (os.getenv(key) or "").strip()
    if v:
        try:
            return float(v)
        except Exception:
            pass
    if cid == "ethereum":
        return 8.0
    if cid == "bsc":
        return 0.3
    return 2.0


# ============================================================
# 2) DexScreener：定位同一交易对在不同链上的 pool
# ============================================================

def _addr_lower(x: str) -> str:
    return (x or "").strip().lower()


def _pair_has_tokens(pair_obj: Dict[str, Any], token_a: str, token_b: str) -> bool:
    a = _addr_lower(token_a)
    b = _addr_lower(token_b)

    base = pair_obj.get("baseToken") or {}
    quote = pair_obj.get("quoteToken") or {}

    base_addr = _addr_lower(str(base.get("address") or ""))
    quote_addr = _addr_lower(str(quote.get("address") or ""))

    return (base_addr == a and quote_addr == b) or (base_addr == b and quote_addr == a)


def _pick_best_pair(pairs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    best = None
    best_liq = -1.0
    for p in pairs:
        liq = p.get("liquidity") or {}
        liq_usd = float(liq.get("usd") or 0.0)
        if liq_usd > best_liq:
            best_liq = liq_usd
            best = p
    return best


def find_pair_on_chain_via_dexscreener(
    ds: DexScreener,
    chain_id: str,
    token_a_addr: str,
    token_b_addr: str,
) -> Optional[Dict[str, Any]]:
    cid = _norm_chain(chain_id)

    resp = ds.token_pairs(token_a_addr) or {}
    pairs = resp.get("pairs") or []
    if not isinstance(pairs, list):
        return None

    candidates: List[Dict[str, Any]] = []
    for p in pairs:
        if not isinstance(p, dict):
            continue
        if _norm_chain(str(p.get("chainId") or "")) != cid:
            continue
        if _pair_has_tokens(p, token_a_addr, token_b_addr):
            candidates.append(p)

    return _pick_best_pair(candidates)


# ============================================================
# 3) 跨链对比与套利粗筛
# ============================================================

def _pick_route(routes: List[BridgeRoute], from_chain: str, to_chain: str) -> BridgeRoute:
    f = _norm_chain(from_chain)
    t = _norm_chain(to_chain)
    for r in routes:
        if _norm_chain(r.from_chain) == f and _norm_chain(r.to_chain) == t:
            return r
    return BridgeRoute(name="unknown_bridge", from_chain=f, to_chain=t, fixed_fee_usd=0.0, variable_fee_bps=0.0, eta_seconds=900)


def build_cross_chain_snapshot(
    pair_symbol_a: str,
    pair_symbol_b: str,
    chains: List[str],
) -> Dict[str, Any]:
    token_map = load_token_map()
    routes = load_bridge_routes()
    ds = DexScreener()

    sym_a = (pair_symbol_a or "").strip().upper()
    sym_b = (pair_symbol_b or "").strip().upper()

    warnings: List[str] = []

    if sym_a not in token_map:
        warnings.append(f"token map missing: {sym_a}. Please add it to CROSS_CHAIN_TOKEN_MAP_JSON/PATH.")
    if sym_b not in token_map:
        warnings.append(f"token map missing: {sym_b}. Please add it to CROSS_CHAIN_TOKEN_MAP_JSON/PATH.")

    out: Dict[str, Any] = {"pair": f"{sym_a}-{sym_b}", "chains": {}, "arbitrage": [], "warnings": warnings}

    # 1) 每条链抓主池快照
    for ch in chains:
        cid = _norm_chain(ch)

        addr_a = (token_map.get(sym_a) or {}).get(cid)
        addr_b = (token_map.get(sym_b) or {}).get(cid)
        if not addr_a or not addr_b:
            out["chains"][cid] = {"available": False, "reason": "token mapping missing", "chain": cid}
            continue

        pair_item = find_pair_on_chain_via_dexscreener(ds, cid, addr_a, addr_b)
        if not pair_item:
            out["chains"][cid] = {"available": False, "reason": "pair not found via DexScreener", "chain": cid}
            continue

        liq = pair_item.get("liquidity") or {}
        vol = pair_item.get("volume") or {}
        txns = pair_item.get("txns") or {}

        price_usd = float(pair_item.get("priceUsd") or 0.0)

        out["chains"][cid] = {
            "available": True,
            "chain": cid,
            "dex_id": pair_item.get("dexId"),
            "pair_address": pair_item.get("pairAddress"),
            "url": pair_item.get("url"),
            "price_usd": price_usd,
            "liquidity_usd": float(liq.get("usd") or 0.0),
            "volume_h24": float(vol.get("h24") or 0.0),
            "volume_h6": float(vol.get("h6") or 0.0),
            "volume_h1": float(vol.get("h1") or 0.0),
            "txns_h24": txns.get("h24"),
            "txns_h6": txns.get("h6"),
            "txns_h1": txns.get("h1"),
            "labels": pair_item.get("labels"),
            "base_token": pair_item.get("baseToken"),
            "quote_token": pair_item.get("quoteToken"),
        }

    # 2) 跨链套利粗筛（低价 -> 高价）
    chain_items = [(cid, info) for cid, info in (out["chains"] or {}).items() if isinstance(info, dict) and info.get("available")]
    if len(chain_items) >= 2:
        for i in range(len(chain_items)):
            for j in range(len(chain_items)):
                if i == j:
                    continue
                c_from, a = chain_items[i]
                c_to, b = chain_items[j]

                p_from = float(a.get("price_usd") or 0.0)
                p_to = float(b.get("price_usd") or 0.0)
                if p_from <= 0 or p_to <= 0:
                    continue

                gross = (p_to - p_from) / p_from
                if gross <= 0:
                    continue

                gross_bps = gross * 10000.0

                route = _pick_route(routes, c_from, c_to)
                bridge_fixed = route.fixed_fee_usd
                bridge_var_bps = route.variable_fee_bps
                eta = route.eta_seconds

                gas_usd = _get_gas_cost_usd(c_from) + _get_gas_cost_usd(c_to)

                trade_size = _get_trade_size_usd()
                fixed_fee_bps = (bridge_fixed / max(trade_size, 1e-9)) * 10000.0
                gas_bps = (gas_usd / max(trade_size, 1e-9)) * 10000.0

                slippage_buffer_bps = _get_float_env("CROSS_CHAIN_SLIPPAGE_BUFFER_BPS", 20.0)
                time_risk_bps = _time_risk_bps(eta)

                total_cost_bps = fixed_fee_bps + bridge_var_bps + gas_bps + slippage_buffer_bps + time_risk_bps
                net_bps = gross_bps - total_cost_bps

                out["arbitrage"].append(
                    {
                        "pair": out["pair"],
                        "from_chain": c_from,
                        "to_chain": c_to,
                        "buy_price_usd": p_from,
                        "sell_price_usd": p_to,
                        "gross_spread_bps": gross_bps,
                        "net_spread_bps": net_bps,
                        "assumptions": {
                            "trade_size_usd": trade_size,
                            "bridge": {
                                "name": route.name,
                                "fixed_fee_usd": bridge_fixed,
                                "variable_fee_bps": bridge_var_bps,
                                "eta_seconds": eta,
                            },
                            "gas_cost_usd_total": gas_usd,
                            "cost_components_bps": {
                                "bridge_fixed_fee_bps": fixed_fee_bps,
                                "bridge_variable_fee_bps": bridge_var_bps,
                                "gas_bps": gas_bps,
                                "slippage_buffer_bps": slippage_buffer_bps,
                                "time_risk_bps": time_risk_bps,
                            },
                        },
                    }
                )

        out["arbitrage"].sort(key=lambda x: float(x.get("net_spread_bps") or -1e9), reverse=True)

    return out


# ============================================================
# ✅ Pipeline entry: discovery_run.py will call this
# ============================================================

def build_cross_chain_comparison(
    markets: List[Dict[str, Any]],
    start_time: Any,
    end_time: Any,
    base_chain: str = "mainnet",
) -> Dict[str, Any]:
    """
    discovery_run.py 需要的入口函数。

    默认行为（保证可跑）：
    - 对比 USDC/WETH
    - 链：base_chain + bsc（也可用 env 覆盖）
      CROSS_CHAIN_CHAINS="ethereum,bsc,arbitrum"
    - 也可用 env 覆盖对比交易对：
      CROSS_CHAIN_PAIRS="USDC-WETH,USDT-WETH"
    """
    _ = markets
    _ = start_time
    _ = end_time

    chains_env = (os.getenv("CROSS_CHAIN_CHAINS") or "").strip()
    if chains_env:
        chains = [c.strip() for c in chains_env.split(",") if c.strip()]
    else:
        chains = [_norm_chain(base_chain), "bsc"]

    pairs_env = (os.getenv("CROSS_CHAIN_PAIRS") or "").strip()
    if pairs_env:
        pairs = [p.strip() for p in pairs_env.split(",") if p.strip()]
    else:
        pairs = ["USDC-WETH"]

    results: Dict[str, Any] = {
        "chains": chains,
        "pairs": [],
        "notes": {
            "source": "DexScreener (free public API)",
            "gas_cost_usd_overrides": "Set GAS_COST_USD_ETHEREUM / GAS_COST_USD_BSC to tune net spread",
            "bridge_overrides": "Set CROSS_CHAIN_BRIDGE_ROUTES_JSON/PATH to tune bridge cost & ETA",
        },
    }

    for p in pairs:
        if "-" not in p:
            continue
        a, b = p.split("-", 1)
        results["pairs"].append(build_cross_chain_snapshot(a.strip(), b.strip(), chains))

    # 额外：把“最优机会”提出来，报告更直观
    best = None
    best_net = -1e18
    for item in results["pairs"]:
        arbs = item.get("arbitrage") or []
        for arb in arbs:
            net = float(arb.get("net_spread_bps") or -1e18)
            if net > best_net:
                best_net = net
                best = arb
    results["best_opportunity"] = best or {}

    return results