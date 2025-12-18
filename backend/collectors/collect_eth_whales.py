from __future__ import annotations

"""
动态收集 ERC20（默认 WETH）鲸鱼地址，直接写入 markets.json

用法：
    python backend/collectors/collect_eth_whales.py
    python backend/collectors/collect_eth_whales.py --token <ERC20地址> --top 20 --blocks 200000

依赖：
    pip install python-dotenv web3
"""

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

MAINNET_RPC = (
    os.getenv("MAINNET_RPC")
    or os.getenv("ETH_RPC_URL")
    or os.getenv("MAINNET_HTTP_URL")
    or os.getenv("ALCHEMY_MAINNET_RPC")
)

if not MAINNET_RPC:
    raise RuntimeError(
        "请在 .env 中配置 MAINNET_RPC / ETH_RPC_URL / MAINNET_HTTP_URL / ALCHEMY_MAINNET_RPC 之一"
    )

w3 = Web3(Web3.HTTPProvider(MAINNET_RPC))
if not w3.is_connected():
    raise RuntimeError("无法连接以太坊主网，请检查 RPC 地址是否正确、网络是否可达")


def _resolve_markets_path() -> Path:
    """
    兼容：
      - backend/markets.json
      - backend/collectors/markets.json
    """
    p1 = BASE_DIR / "markets.json"
    p2 = BASE_DIR.parent / "markets.json"
    if p1.exists():
        return p1
    if p2.exists():
        return p2
    return p2


MARKETS_PATH = _resolve_markets_path()

# ✅ topic0 必须是 0x 开头
TRANSFER_TOPIC0 = Web3.to_hex(Web3.keccak(text="Transfer(address,address,uint256)"))


def get_latest_block() -> int:
    latest = w3.eth.block_number
    print(f"✅ mainnet 最新区块: {latest}")
    return latest


def _parse_hex_block(x: Any) -> Optional[int]:
    """把 '0x16BABA1' 这种转成 int。"""
    if isinstance(x, str) and x.startswith("0x"):
        try:
            return int(x, 16)
        except Exception:
            return None
    return None


def _is_getlogs_too_large(err: Exception) -> bool:
    """
    判断是否是 -32005 / >10000 results 的 getLogs 超限类错误。
    """
    if not isinstance(err, Exception):
        return False
    msg = str(err).lower()
    if "more than 10000" in msg or "10000 results" in msg:
        return True

    # web3.exceptions.Web3RPCError: {'code': -32005, ...}
    # 有些 provider 会抛 Web3RPCError，内容在 err.args[0] 里是 dict
    if hasattr(err, "args") and err.args:
        obj = err.args[0]
        if isinstance(obj, dict) and obj.get("code") == -32005:
            return True
    return False


def _extract_provider_suggested_range(err: Exception) -> Optional[Tuple[int, int]]:
    """
    从 -32005 报错里解析 provider 建议的 block range，比如：
      {'code': -32005, 'message': 'query returned more than 10000 results. Try with this block range [0x16BABA1, 0x16BAC56].', ...}
      或 data: {'from': '0x16BABA1', 'to': '0x16BAC56'}
    返回 (from_block, to_block) 的 int，如果拿不到就 None
    """
    # 1) 解析 err.args[0] dict
    if hasattr(err, "args") and err.args and isinstance(err.args[0], dict):
        obj = err.args[0]
        data = obj.get("data") or {}
        fb = _parse_hex_block(data.get("from"))
        tb = _parse_hex_block(data.get("to"))
        if fb is not None and tb is not None and fb <= tb:
            return fb, tb

        # message 里也可能包含 [0x..., 0x...]
        msg = str(obj.get("message") or "")
        lb = msg.find("[0x")
        rb = msg.find("]", lb + 1)
        if lb != -1 and rb != -1:
            inside = msg[lb + 1 : rb]
            parts = [p.strip() for p in inside.split(",")]
            if len(parts) == 2:
                fb2 = _parse_hex_block(parts[0])
                tb2 = _parse_hex_block(parts[1])
                if fb2 is not None and tb2 is not None and fb2 <= tb2:
                    return fb2, tb2

    # 2) 兜底：在字符串里找
    s = str(err)
    lb = s.find("[0x")
    rb = s.find("]", lb + 1)
    if lb != -1 and rb != -1:
        inside = s[lb + 1 : rb]
        parts = [p.strip() for p in inside.split(",")]
        if len(parts) == 2:
            fb = _parse_hex_block(parts[0])
            tb = _parse_hex_block(parts[1])
            if fb is not None and tb is not None and fb <= tb:
                return fb, tb

    return None


def _get_logs_range(token: str, frm: int, to: int) -> List[Dict[str, Any]]:
    """
    单次 get_logs，抛异常交给上层处理。
    """
    return w3.eth.get_logs(
        {
            "fromBlock": frm,
            "toBlock": to,
            "address": token,
            "topics": [TRANSFER_TOPIC0],
        }
    )


def fetch_transfer_logs_via_rpc(
    token: str,
    start_block: int,
    end_block: int,
    initial_step: int = 5000,
    min_step: int = 64,
    max_tries_per_range: int = 10,
) -> List[Dict[str, Any]]:
    """
    用 eth_getLogs 扫描 ERC20 Transfer 日志。
    ✅ 处理两类情况：
      - 常规：按 step 扫描
      - 超限(-32005)：优先使用 provider “建议区间”，否则二分缩小
    """
    token = Web3.to_checksum_address(token)
    logs: List[Dict[str, Any]] = []

    print(
        f"📡 通过 RPC 扫描 Transfer 日志: token={token}, blocks=[{start_block}, {end_block}], step={initial_step}"
    )

    step = initial_step
    current = start_block

    while current <= end_block:
        target_to = min(current + step - 1, end_block)

        frm = current
        to = target_to
        tries = 0

        while True:
            tries += 1
            print(f"  · 扫描区块区间 [{frm}, {to}] ... ", end="", flush=True)
            try:
                part = _get_logs_range(token, frm, to)
                print(f"ok, 本段日志数={len(part)}")
                logs.extend(part)
                current = to + 1  # ✅ 成功推进
                break

            except Exception as e:
                print(f"⚠️ {type(e).__name__}: {e}")

                if not _is_getlogs_too_large(e):
                    # 非超限类错误：跳过这一段，继续
                    print("  ❌ 非 10000 限制类错误，跳过该段继续。")
                    current = to + 1
                    break

                # 超限类错误：优先用 provider 给的建议区间
                suggested = _extract_provider_suggested_range(e)
                if suggested:
                    sf, st = suggested
                    # provider 建议区间通常更小且可执行
                    sf = max(sf, frm)
                    st = min(st, to)
                    if sf <= st and (sf != frm or st != to):
                        print(f"  ↪️ 使用 provider 建议区间重试: [{sf}, {st}]")
                        frm, to = sf, st
                        continue

                # 否则做二分缩小
                if frm >= to:
                    print("  ❌ 已无法继续缩小（frm>=to），跳过该块。")
                    current = to + 1
                    break

                width = to - frm + 1
                if width <= min_step:
                    print(f"  ❌ 区间宽度已<=min_step({min_step})仍超限，跳过该段。")
                    current = to + 1
                    break

                mid = (frm + to) // 2
                print(f"  ↪️ 超限，二分缩小：先尝试左半 [{frm}, {mid}]")
                to = mid

                if tries >= max_tries_per_range:
                    print("  ❌ 单段重试次数过多，跳过该段继续。")
                    current = target_to + 1
                    break

        # 自适应：如果经常超限，可以把 step 慢慢调小（可选）
        # 这里保持简单，不动 step；你也可以根据需要动态调整 step。

    print(f"✅ 共收集 Transfer 日志 {len(logs)} 条")
    return logs


def logs_to_tx_like(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    txs: List[Dict[str, Any]] = []
    for log in logs:
        topics = log.get("topics") or []
        data = log.get("data") or "0x"
        if len(topics) < 3:
            continue

        try:
            t1 = topics[1]
            t2 = topics[2]
            t1h = t1.hex() if hasattr(t1, "hex") else Web3.to_hex(t1)
            t2h = t2.hex() if hasattr(t2, "hex") else Web3.to_hex(t2)

            from_addr = "0x" + t1h[-40:]
            to_addr = "0x" + t2h[-40:]

            if isinstance(data, (bytes, bytearray)):
                value = int.from_bytes(data, "big")
            else:
                value = int(str(data), 16)
        except Exception:
            continue

        txs.append({"from": from_addr, "to": to_addr, "value": str(value)})
    return txs


def aggregate_whales(
    txs: List[Dict[str, Any]],
    min_volume_wei: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}
    for tx in txs:
        try:
            value = int(tx.get("value") or 0)
        except Exception:
            continue
        if value <= 0:
            continue

        from_addr = (tx.get("from") or "").lower()
        to_addr = (tx.get("to") or "").lower()

        for addr in (from_addr, to_addr):
            if not addr or addr == "0x0000000000000000000000000000000000000000":
                continue
            s = stats.setdefault(addr, {"volume": 0, "tx_count": 0})
            s["volume"] += value
            s["tx_count"] += 1

    if min_volume_wei is not None:
        stats = {a: v for a, v in stats.items() if v["volume"] >= min_volume_wei}

    print(f"📈 完成地址聚合，候选地址数: {len(stats)}")
    return stats


def pick_top_whales(stats: Dict[str, Dict[str, Any]], top_n: int = 10) -> List[Tuple[str, Dict[str, Any]]]:
    whales = sorted(stats.items(), key=lambda kv: kv[1]["volume"], reverse=True)[:top_n]
    print(f"🏆 选出前 {len(whales)} 名鲸鱼地址:")
    for i, (addr, v) in enumerate(whales, start=1):
        print(f"  #{i} {addr} | volume={v['volume']} Wei | tx_count={v['tx_count']}")
    return whales


def _load_markets_file(path: Path) -> tuple[list[dict[str, Any]], bool]:
    if not path.exists():
        raise RuntimeError(f"{path} 不存在，请先创建基础 markets.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw, False
    if isinstance(raw, dict) and isinstance(raw.get("markets"), list):
        return raw["markets"], True
    raise RuntimeError('markets.json 格式不支持，期望是数组或 {"markets": [...]} 结构')


def _dump_markets_file(path: Path, markets: list[dict[str, Any]], wrapped: bool):
    raw = {"markets": markets} if wrapped else markets
    path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    print(f"💾 已更新 {path}，当前 markets 总条数: {len(markets)}")


def update_markets_with_whales(
    whales: List[Tuple[str, Dict[str, Any]]],
    token_address: str,
    network: str = "mainnet",
):
    markets, wrapped = _load_markets_file(MARKETS_PATH)

    filtered: list[dict[str, Any]] = []
    removed = 0
    for m in markets:
        t = (m.get("type") or "").lower()
        label = (m.get("label") or "").upper()
        meta = m.get("meta") or {}
        is_auto = label.startswith("AUTO_WHALE_") or (meta.get("source") == "collect_eth_whales")
        if t in ("whale_eth", "whale") and is_auto:
            removed += 1
            continue
        filtered.append(m)

    print(f"🧹 已清理旧的自动鲸鱼条目 {removed} 个，剩余 {len(filtered)} 条 markets。")

    ts = int(time.time())
    for idx, (addr, v) in enumerate(whales, start=1):
        filtered.append(
            {
                "label": f"AUTO_WHALE_{idx}",
                "address": addr,
                "type": "whale_eth",
                "network": network,
                "meta": {
                    "source": "collect_eth_whales",
                    "token": token_address,
                    "rank": idx,
                    "volume_wei": str(v["volume"]),
                    "tx_count": int(v["tx_count"]),
                    "timestamp": ts,
                },
            }
        )

    _dump_markets_file(MARKETS_PATH, filtered, wrapped)


def main():
    parser = argparse.ArgumentParser(description="动态收集 ERC20 鲸鱼地址并写入 markets.json")
    parser.add_argument("--token", type=str, default=DEFAULT_WETH, help="要分析的 ERC20 Token 地址，默认主网 WETH")
    parser.add_argument("--blocks", type=int, default=200_000, help="回溯多少区块范围（默认 200k）")
    parser.add_argument("--top", type=int, default=10, help="选出前多少名鲸鱼地址（默认 10）")
    parser.add_argument(
        "--min-volume-eth",
        type=float,
        default=0.0,
        help="过滤最小累计成交额（按 18 decimals 换算，WETH/ETH 适用），比如 50 表示 ≥50",
    )
    parser.add_argument("--step", type=int, default=5000, help="初始扫描步长（默认 5000），爆 10k 就会自动缩")
    args = parser.parse_args()

    token = Web3.to_checksum_address(args.token)
    latest = get_latest_block()
    start = max(0, latest - args.blocks)

    raw_logs = fetch_transfer_logs_via_rpc(
        token=token,
        start_block=start,
        end_block=latest,
        initial_step=max(64, int(args.step)),
    )

    tx_like = logs_to_tx_like(raw_logs)

    min_volume_wei = None
    if args.min_volume_eth and args.min_volume_eth > 0:
        min_volume_wei = int(args.min_volume_eth * 10**18)

    stats = aggregate_whales(tx_like, min_volume_wei=min_volume_wei)
    whales = pick_top_whales(stats, top_n=args.top)

    update_markets_with_whales(whales, token_address=token, network="mainnet")


if __name__ == "__main__":
    main()
