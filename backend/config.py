# backend/config.py
from __future__ import annotations

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

# web3 v7+ 与旧版本 POA middleware 兼容
try:
    from web3.middleware import ExtraDataToPOAMiddleware as _POA_MIDDLEWARE  # v7+
except ImportError:
    from web3.middleware import geth_poa_middleware as _POA_MIDDLEWARE  # v6-

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent

# ✅ Web3 实例缓存：避免 pipeline 内重复建 HTTP session（更快、更不容易卡）
_W3_CACHE: dict[str, Web3] = {}


def _norm_network(network: str) -> str:
    n = (network or "").strip().lower()
    if n in ("mainnet", "ethereum", "eth"):
        return "mainnet"
    if n in ("sepolia",):
        return "sepolia"
    if n in ("bsc", "bnb", "binance"):
        return "bsc"
    if n in ("polygon", "matic"):
        return "polygon"
    if n in ("arbitrum", "arb"):
        return "arbitrum"
    if n in ("optimism", "op"):
        return "optimism"
    if n in ("base",):
        return "base"
    return n


def _rpc_env_key(network: str) -> str:
    # 统一你的 env key 命名（你可以按这个补 .env）
    return {
        "mainnet": "ETH_RPC_URL",
        "sepolia": "SEPOLIA_RPC_URL",
        "bsc": "BSC_RPC_URL",
        "polygon": "POLYGON_RPC_URL",
        "arbitrum": "ARBITRUM_RPC_URL",
        "optimism": "OPTIMISM_RPC_URL",
        "base": "BASE_RPC_URL",
    }.get(network, "")


def _is_poa_chain(network: str) -> bool:
    # 常见需要 POA middleware 的链
    return network in ("sepolia", "bsc", "polygon")


def make_web3(network: str = "mainnet") -> Web3:
    net = _norm_network(network)

    # ✅ cache hit
    if net in _W3_CACHE:
        return _W3_CACHE[net]

    env_key = _rpc_env_key(net)
    if not env_key:
        raise ValueError(f"未知网络: {network}（norm={net}），请在 config.py 里补充 RPC 映射")

    rpc = (os.getenv(env_key) or "").strip()
    if not rpc:
        raise RuntimeError(f"{net} 的 RPC 未在 .env 中配置（缺少 {env_key}）")

    # ✅ 防卡死：HTTP 超时（秒）。建议 15~30
    timeout = int((os.getenv("RPC_TIMEOUT") or "20").strip())

    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": timeout}))

    # ✅ 正确注入 POA middleware
    if _is_poa_chain(net):
        w3.middleware_onion.inject(_POA_MIDDLEWARE, layer=0)

    # ✅ web3 新版本 is_connected 是方法
    if not w3.is_connected():
        raise RuntimeError(f"无法连接 {net} 节点: {rpc}")

    # 这里打印很好，用于你面试演示；如果嫌吵可改成受 env 控制
    print(f"✅ 已连接 {net}, 最新区块: {w3.eth.block_number}")

    # ✅ cache store
    _W3_CACHE[net] = w3
    return w3


def load_risk_monitor_contract(network: str = "sepolia"):
    w3 = make_web3(network)

    contract_address = (os.getenv("CONTRACT_ADDRESS") or "").strip()
    if not contract_address:
        raise RuntimeError("请在 .env 中配置 CONTRACT_ADDRESS")

    artifact_path = ROOT_DIR / "artifacts" / "contracts" / "RiskMonitor.sol" / "RiskMonitor.json"
    if not artifact_path.exists():
        raise RuntimeError(f"找不到合约 ABI 文件: {artifact_path}，请先运行 npx hardhat compile")

    with open(artifact_path, "r", encoding="utf-8") as f:
        artifact = json.load(f)

    abi = artifact["abi"]
    contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi)
    return w3, contract