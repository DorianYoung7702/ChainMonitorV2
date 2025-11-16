import os
from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
from pathlib import Path

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent

def make_web3(network: str = "mainnet") -> Web3:
    if network == "mainnet":
        rpc = os.getenv("ETH_RPC_URL")
    elif network == "sepolia":
        rpc = os.getenv("SEPOLIA_RPC_URL")
    else:
        raise ValueError(f"未知网络: {network}")

    if not rpc:
        raise RuntimeError(f"{network} 的 RPC 未在 .env 中配置")

    w3 = Web3(Web3.HTTPProvider(rpc))

    if network == "sepolia":
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    if not w3.is_connected():
        raise RuntimeError(f"无法连接 {network} 节点: {rpc}")

    print(f"✅ 已连接 {network}, 最新区块: {w3.eth.block_number}")
    return w3


def load_risk_monitor_contract(network: str = "sepolia"):
    w3 = make_web3(network)
    contract_address = os.getenv("CONTRACT_ADDRESS")
    if not contract_address:
        raise RuntimeError("请在 .env 中配置 CONTRACT_ADDRESS")

    artifact_path = ROOT_DIR / "artifacts" / "contracts" / "RiskMonitor.sol" / "RiskMonitor.json"
    if not artifact_path.exists():
        raise RuntimeError(f"找不到合约 ABI 文件: {artifact_path}, 请先运行 npx hardhat compile")

    with open(artifact_path, "r", encoding="utf-8") as f:
        artifact = json.load(f)

    abi = artifact["abi"]
    contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi)
    return w3, contract
