import os
import time
from dotenv import load_dotenv
from web3 import Web3

from config import load_risk_monitor_contract
from db import MonitorDatabase
from chain_data import fetch_recent_swaps

load_dotenv()

UNISWAP_V2_USDC_WETH = "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc"
MARKET_ID = Web3.keccak(text="UNISWAP_USDC_WETH")


def compute_risk_level(trades: list[dict]) -> int:
    if not trades:
        return 0

    total_volume = sum(t["amount_in"] for t in trades)
    count = len(trades)

    if count < 5:
        return 0
    avg_volume = total_volume / count

    if avg_volume > 10**22 and count > 50:
        return 3
    elif avg_volume > 10**21 and count > 30:
        return 2
    elif avg_volume > 10**20 and count > 10:
        return 1
    else:
        return 0


def send_update_risk_tx(w3, contract, level: int):
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise RuntimeError("请在 .env 中配置 PRIVATE_KEY（建议用测试网私钥）")

    account = w3.eth.account.from_key(private_key)
    nonce = w3.eth.get_transaction_count(account.address)

    tx = contract.functions.updateRisk(MARKET_ID, level).build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "gas": 300_000,
            "maxFeePerGas": w3.eth.gas_price,
        }
    )

    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    print(f"📨 发送 updateRisk 交易: {tx_hash.hex()}")
    return tx_hash.hex()


def monitor_loop(
    network: str = "sepolia",
    poll_interval: int = 60,
    blocks_back: int = 2000,
):
    db = MonitorDatabase()
    w3, contract = load_risk_monitor_contract(network)
    last_level = None

    while True:
        print("\n=== 开始新一轮监控 ===")
        trades = fetch_recent_swaps(
            pair_address=UNISWAP_V2_USDC_WETH,
            blocks_back=blocks_back,
            network="mainnet",
        )
        db.save_trades(trades)

        level = compute_risk_level(trades)
        print(f"当前计算风险等级: {level}")
        db.save_risk_level(market_id=MARKET_ID.hex(), level=level, source="local")

        if last_level is None or level != last_level:
            print(f"风险等级从 {last_level} 变为 {level}，调用合约更新...")
            send_update_risk_tx(w3, contract, level)
            last_level = level
        else:
            print("风险等级无变化，不调用合约")

        print(f"⏳ 等待 {poll_interval} 秒后进行下一轮...")
        time.sleep(poll_interval)


if __name__ == "__main__":
    monitor_loop()
