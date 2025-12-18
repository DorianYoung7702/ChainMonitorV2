# backend/collectors/v3_registry.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from web3 import Web3
from backend.config import make_web3

UNISWAP_V3_FACTORY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
        ],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]

# 只内置你当前用得到的 mainnet；其它链建议你显式传 factory_address（避免你踩“地址不一致”坑）
DEFAULT_V3_FACTORY_BY_NETWORK: Dict[str, str] = {
    "mainnet": "0x1F98431c8aD98523631AE4a59f267346ea31F984",  # UniswapV3Factory (Ethereum)
}

ZERO_ADDR = "0x0000000000000000000000000000000000000000"


def resolve_v3_factory_address(network: str, factory_address: Optional[str] = None) -> Optional[str]:
    if factory_address:
        try:
            return Web3.to_checksum_address(factory_address)
        except Exception:
            return None
    n = (network or "").strip().lower()
    addr = DEFAULT_V3_FACTORY_BY_NETWORK.get(n)
    if not addr:
        return None
    try:
        return Web3.to_checksum_address(addr)
    except Exception:
        return None


def get_uniswap_v3_pool_address(
    *,
    network: str,
    token_a: str,
    token_b: str,
    fee: int,
    factory_address: Optional[str] = None,
    w3: Optional[Web3] = None,
) -> Optional[str]:
    """
    返回 Uniswap V3 pool 地址（如果不存在返回 None）
    """
    w3 = w3 or make_web3(network)
    fac = resolve_v3_factory_address(network, factory_address=factory_address)
    if not fac:
        print(f"⚠️ 未找到 {network} 的 V3 factory 地址，请显式传 factory_address")
        return None

    try:
        a = Web3.to_checksum_address(token_a)
        b = Web3.to_checksum_address(token_b)
    except Exception:
        print("⚠️ token 地址不合法")
        return None

    factory = w3.eth.contract(address=fac, abi=UNISWAP_V3_FACTORY_ABI)

    try:
        pool = factory.functions.getPool(a, b, int(fee)).call()
        if not pool or pool.lower() == ZERO_ADDR.lower():
            return None
        return Web3.to_checksum_address(pool)
    except Exception as e:
        print(f"⚠️ getPool 调用失败: {e}")
        return None


def get_v3_fee_tier_pools(
    *,
    network: str,
    token_a: str,
    token_b: str,
    fee_tiers: List[int] = [500, 3000, 10000],
    factory_address: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    一次性拿到多个 fee tier 的 pool 地址，返回：
    [
      {"fee":500, "pool":"0x..."},
      {"fee":3000, "pool":"0x..."},
      ...
    ]
    """
    w3 = make_web3(network)
    out: List[Dict[str, Any]] = []
    for fee in fee_tiers:
        p = get_uniswap_v3_pool_address(
            network=network,
            token_a=token_a,
            token_b=token_b,
            fee=int(fee),
            factory_address=factory_address,
            w3=w3,
        )
        out.append({"fee": int(fee), "pool": p})
    return out