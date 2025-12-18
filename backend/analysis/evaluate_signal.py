import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional, Union

from web3 import Web3  # 用于 checksum / 合约调用
from backend.config import make_web3
from backend.storage.db import MonitorDatabase, DB_PATH

# ============================================================
# 1) 价格序列获取（支持 pipeline + backfill 两种模式）
# ============================================================

# 最小 ERC20 ABI：decimals/symbol
_ERC20_MIN_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]

_DECIMALS_CACHE: Dict[str, int] = {}
_SYMBOL_CACHE: Dict[str, str] = {}


def _safe_checksum(addr: Optional[str]) -> Optional[str]:
    if not addr or not isinstance(addr, str):
        return None
    try:
        return Web3.to_checksum_address(addr)
    except Exception:
        return None


def _get_token_decimals(w3: Web3, token_addr: str) -> int:
    """读取 token decimals（带缓存）；读不到就兜底 18。"""
    token_addr = Web3.to_checksum_address(token_addr)
    if token_addr in _DECIMALS_CACHE:
        return _DECIMALS_CACHE[token_addr]

    try:
        c = w3.eth.contract(address=token_addr, abi=_ERC20_MIN_ABI)
        d = int(c.functions.decimals().call())
        if d < 0 or d > 36:
            d = 18
        _DECIMALS_CACHE[token_addr] = d
        return d
    except Exception:
        _DECIMALS_CACHE[token_addr] = 18
        return 18


def _get_token_symbol(w3: Web3, token_addr: str) -> str:
    """读取 token symbol（带缓存）；读不到返回空字符串。"""
    token_addr = Web3.to_checksum_address(token_addr)
    if token_addr in _SYMBOL_CACHE:
        return _SYMBOL_CACHE[token_addr]
    try:
        c = w3.eth.contract(address=token_addr, abi=_ERC20_MIN_ABI)
        s = str(c.functions.symbol().call())
        _SYMBOL_CACHE[token_addr] = s
        return s
    except Exception:
        _SYMBOL_CACHE[token_addr] = ""
        return ""


def _trade_to_price_point(
    w3: Web3,
    ts: int,
    amount_in: int,
    amount_out: int,
    token_in_flag: str,
    token0_addr: Optional[str],
    token1_addr: Optional[str],
) -> Optional[Tuple[datetime, float]]:
    """
    将一条 swap trade 变成 (datetime, price)。

    统一口径：输出 price = token0_per_token1（1 token1 值多少 token0）
    - USDC/WETH 且 token0=USDC token1=WETH => 价格就是 USDC per WETH（最常用）
    """
    if ts <= 0 or amount_in <= 0 or amount_out <= 0:
        return None
    if not token0_addr or not token1_addr:
        return None

    token0_addr = _safe_checksum(token0_addr)
    token1_addr = _safe_checksum(token1_addr)
    if not token0_addr or not token1_addr:
        return None

    d0 = _get_token_decimals(w3, token0_addr)
    d1 = _get_token_decimals(w3, token1_addr)

    try:
        if token_in_flag == "token0":
            # token0 in, token1 out
            token0_in = amount_in / (10 ** d0)
            token1_out = amount_out / (10 ** d1)
            if token1_out <= 0:
                return None
            price = token0_in / token1_out
        elif token_in_flag == "token1":
            # token1 in, token0 out
            token1_in = amount_in / (10 ** d1)
            token0_out = amount_out / (10 ** d0)
            if token1_in <= 0:
                return None
            price = token0_out / token1_in
        else:
            return None

        if price <= 0 or price != price:  # NaN 防御
            return None

        # 用 UTC naive datetime（后续统计只需要顺序）
        return (datetime.utcfromtimestamp(int(ts)), float(price))
    except Exception:
        return None


def _guess_chain_from_swap_data(swap_data: List[Dict[str, Any]], default: str = "mainnet") -> str:
    """如果 swap_data 里带了 network 字段，优先用它。"""
    if not swap_data:
        return default
    net = swap_data[0].get("network")
    if isinstance(net, str) and net.strip():
        return net.strip()
    return default


def _price_series_from_swap_data(
    swap_data: List[Dict[str, Any]],
    chain: str = "mainnet",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[Tuple[datetime, float]]:
    """pipeline 模式：直接用 swap_data 构建价格序列。"""
    if not swap_data:
        return []

    # 如果没传 chain，就尽量从 swap_data 里推断
    chain = chain or _guess_chain_from_swap_data(swap_data, default="mainnet")
    w3 = make_web3(chain)

    st_ts = int(start_time.timestamp()) if start_time else None
    ed_ts = int(end_time.timestamp()) if end_time else None

    out: List[Tuple[datetime, float]] = []
    for x in swap_data:
        ts = int(x.get("timestamp") or 0)
        if st_ts is not None and ts < st_ts:
            continue
        if ed_ts is not None and ts > ed_ts:
            continue

        token_in_flag = str(x.get("token_in") or "")
        if token_in_flag not in ("token0", "token1"):
            continue

        amount_in = int(x.get("amount_in") or 0)
        amount_out = int(x.get("amount_out") or 0)

        token0_addr = x.get("token0_address")
        token1_addr = x.get("token1_address")

        pt = _trade_to_price_point(
            w3=w3,
            ts=ts,
            amount_in=amount_in,
            amount_out=amount_out,
            token_in_flag=token_in_flag,
            token0_addr=token0_addr,
            token1_addr=token1_addr,
        )
        if pt:
            out.append(pt)

    out.sort(key=lambda t: t[0])
    return out


def _price_series_from_db(
    market_id: str,
    start_time: datetime,
    end_time: datetime,
) -> List[Tuple[datetime, float]]:
    """
    backfill/eval 模式：从 SQLite trades 表里按 market_id + 时间窗口取交易，再算价格。

    注意：如果你的 trades 表没这些字段，会直接返回 [] 并打印提示：
      timestamp, amount_in, amount_out, token_in, token0_address, token1_address, network
    """
    st = int(start_time.timestamp())
    ed = int(end_time.timestamp())
    out: List[Tuple[datetime, float]] = []

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                timestamp,
                amount_in,
                amount_out,
                token_in,
                token0_address,
                token1_address,
                COALESCE(network, 'mainnet') as network
            FROM trades
            WHERE market_id = ?
              AND timestamp >= ?
              AND timestamp <= ?
            ORDER BY timestamp ASC
            """,
            (market_id, st, ed),
        )
        rows = cur.fetchall()
    except Exception as e:
        conn.close()
        print(f"⚠️ trades 表结构不匹配或不存在，无法从 DB 生成价格序列：{e}")
        return []
    finally:
        conn.close()

    if not rows:
        return []

    chain = str(rows[0][6] or "mainnet")
    w3 = make_web3(chain)

    for (ts, amount_in, amount_out, token_in, token0_addr, token1_addr, _net) in rows:
        try:
            ts_i = int(ts)
            ai = int(amount_in or 0)
            ao = int(amount_out or 0)
            ti = str(token_in or "")
        except Exception:
            continue

        if ti not in ("token0", "token1"):
            continue

        pt = _trade_to_price_point(
            w3=w3,
            ts=ts_i,
            amount_in=ai,
            amount_out=ao,
            token_in_flag=ti,
            token0_addr=token0_addr,
            token1_addr=token1_addr,
        )
        if pt:
            out.append(pt)

    out.sort(key=lambda t: t[0])
    return out


def fetch_price_series(
    arg1: Union[str, List[Dict[str, Any]]],
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    chain: str = "mainnet",
) -> List[Tuple[datetime, float]]:
    """
    ✅ 双模式兼容：

    A) pipeline 模式（discovery_run）：
        fetch_price_series(swap_data, start_time=None, end_time=None, chain="mainnet")
        - arg1 是 swap_data(list[dict])
        - start_time/end_time 可不传，不传就用全部 swap_data

    B) backfill/eval 模式（本文件 backfill_eval_for_market）：
        fetch_price_series(market_id, start_time, end_time)
        - arg1 是 market_id(str)
        - 必须提供 start_time/end_time
    """
    # A) pipeline：swap_data
    if isinstance(arg1, list):
        return _price_series_from_swap_data(arg1, chain=chain, start_time=start_time, end_time=end_time)

    # B) backfill：market_id
    if isinstance(arg1, str):
        if start_time is None or end_time is None:
            raise TypeError("fetch_price_series(market_id, start_time, end_time) 需要提供 start_time / end_time")
        return _price_series_from_db(arg1, start_time, end_time)

    raise TypeError("fetch_price_series 第一个参数必须是 market_id(str) 或 swap_data(list[dict])")


# ============================================================
# 2) 价格序列 → 收益率 / 波动率 / 回撤
# ============================================================

def compute_realized_stats(prices: List[Tuple[datetime, float]]) -> Dict[str, float]:
    if len(prices) < 2:
        return {
            "realized_return": 0.0,
            "realized_vol": 0.0,
            "realized_drawdown": 0.0,
        }

    prices_sorted = sorted(prices, key=lambda x: x[0])
    ps = [p for _, p in prices_sorted]

    p0 = ps[0]
    p_last = ps[-1]
    realized_return = (p_last / p0 - 1.0) * 100.0

    rets = []
    for i in range(1, len(ps)):
        if ps[i - 1] > 0:
            rets.append(ps[i] / ps[i - 1] - 1.0)

    if len(rets) > 1:
        mean_ret = sum(rets) / len(rets)
        var = sum((r - mean_ret) ** 2 for r in rets) / (len(rets) - 1)
        std = var ** 0.5
        realized_vol = std * (len(rets) ** 0.5) * 100.0
    else:
        realized_vol = 0.0

    max_dd = 0.0
    peak = ps[0]
    for p in ps:
        if p > peak:
            peak = p
        dd = (p / peak - 1.0) * 100.0
        if dd < max_dd:
            max_dd = dd
    realized_drawdown = max_dd

    return {
        "realized_return": realized_return,
        "realized_vol": realized_vol,
        "realized_drawdown": realized_drawdown,
    }


# ============================================================
# 3) 规则：什么算“坏事件”(bad_event)
# ============================================================

def label_bad_event(
    stats: Dict[str, float],
    vol_threshold: float = 40.0,
    dd_threshold: float = -3.0,
) -> int:
    if stats["realized_vol"] >= vol_threshold:
        return 1
    if stats["realized_drawdown"] <= dd_threshold:
        return 1
    return 0


# ============================================================
# 4) 回填评估：risk_levels -> risk_eval
# ============================================================

def backfill_eval_for_market(
    db: MonitorDatabase,
    market_id: str,
    window_minutes: int = 60,
):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT created_at, level
        FROM risk_levels
        WHERE market_id = ?
        ORDER BY created_at ASC
        """,
        (market_id,),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print(f"⚠️ risk_levels 中没有 market_id={market_id} 的记录。")
        return

    for created_at_str, level in rows:
        snapshot_time = datetime.fromisoformat(created_at_str)
        end_time = snapshot_time + timedelta(minutes=window_minutes)

        prices = fetch_price_series(market_id, snapshot_time, end_time)
        if len(prices) < 2:
            print(f"ℹ️ {snapshot_time} ~ {end_time} 没有足够价格数据，跳过。")
            continue

        stats = compute_realized_stats(prices)
        bad = label_bad_event(stats)

        row = {
            "snapshot_time": snapshot_time.isoformat(timespec="seconds"),
            "market_id": market_id,
            "risk_level": int(level),
            "realized_window_minutes": window_minutes,
            "realized_return": stats["realized_return"],
            "realized_vol": stats["realized_vol"],
            "realized_drawdown": stats["realized_drawdown"],
            "bad_event": bad,
        }
        db.save_eval_result(row)
        print(
            f"✅ 写入评估: t={row['snapshot_time']}, "
            f"level={level}, ret={stats['realized_return']:.2f}%, "
            f"vol={stats['realized_vol']:.2f}%, dd={stats['realized_drawdown']:.2f}%, "
            f"bad_event={bad}"
        )


# ============================================================
# 5) 汇总性能
# ============================================================

def summarize_performance(
    db: MonitorDatabase,
    market_id: str,
    window_minutes: int = 60,
    high_risk_threshold: int = 2,
):
    rows = db.load_eval_results(market_id, window_minutes)
    if not rows:
        print("⚠️ risk_eval 中暂无数据，请先跑 backfill_eval_for_market。")
        return

    buckets: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        lvl = int(r["risk_level"])
        b = buckets.setdefault(
            lvl,
            {"n": 0, "sum_vol": 0.0, "sum_dd": 0.0, "sum_ret": 0.0, "bad_count": 0},
        )
        b["n"] += 1
        b["sum_vol"] += r["realized_vol"]
        b["sum_dd"] += r["realized_drawdown"]
        b["sum_ret"] += r["realized_return"]
        b["bad_count"] += int(r["bad_event"])

    print("\n=== 按风险等级的实际表现 ===")
    for lvl in sorted(buckets.keys()):
        b = buckets[lvl]
        n = b["n"]
        print(
            f"Level {lvl}: 样本数={n}, "
            f"平均波动率={b['sum_vol']/n:.2f}%, "
            f"平均最大回撤={b['sum_dd']/n:.2f}%, "
            f"平均收益率={b['sum_ret']/n:.2f}%, "
            f"坏事件发生率={b['bad_count']/n*100:.1f}%"
        )

    tp = fp = tn = fn = 0
    for r in rows:
        lvl = int(r["risk_level"])
        bad = int(r["bad_event"])
        pred_alert = int(lvl >= high_risk_threshold)
        if pred_alert == 1 and bad == 1:
            tp += 1
        elif pred_alert == 1 and bad == 0:
            fp += 1
        elif pred_alert == 0 and bad == 0:
            tn += 1
        elif pred_alert == 0 and bad == 1:
            fn += 1

    print("\n=== 高风险告警 (level >= %d) 的效果 ===" % high_risk_threshold)
    print(f"TP={tp}, FP={fp}, TN={tn}, FN={fn}")
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    print(f"精确率(Precision) = {precision:.2f}")
    print(f"召回率(Recall)    = {recall:.2f}")


if __name__ == "__main__":
    db = MonitorDatabase(DB_PATH)
    MARKET_ID_HEX = "0xf8aef9bb697ca70b8d1b632a3f78532b1ad5f66e2643890ce09c75ce7e313c74"
    backfill_eval_for_market(db, MARKET_ID_HEX, window_minutes=60)
    summarize_performance(db, MARKET_ID_HEX, window_minutes=60, high_risk_threshold=2)
