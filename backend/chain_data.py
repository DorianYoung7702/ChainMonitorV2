from typing import List, Dict, Any
from web3 import Web3
from config import make_web3

UNISWAP_V2_PAIR_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount0In", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "amount1In", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "amount0Out", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "amount1Out", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
        ],
        "name": "Swap",
        "type": "event",
    }
]


def fetch_recent_swaps(
    pair_address: str,
    blocks_back: int = 2000,
    network: str = "mainnet",
) -> List[Dict[str, Any]]:
    w3 = make_web3(network)
    pair = w3.eth.contract(address=Web3.to_checksum_address(pair_address), abi=UNISWAP_V2_PAIR_ABI)

    latest = w3.eth.block_number
    from_block = max(0, latest - blocks_back)
    to_block = latest

    swap_event = pair.events.Swap()
    logs = swap_event.get_logs(fromBlock=from_block, toBlock=to_block)

    trades: List[Dict[str, Any]] = []
    for ev in logs:
        args = ev["args"]
        amount0_in = int(args["amount0In"])
        amount1_in = int(args["amount1In"])
        amount0_out = int(args["amount0Out"])
        amount1_out = int(args["amount1Out"])

        if amount0_in > 0:
            token_in = "token0"
            token_out = "token1"
            amount_in = amount0_in
            amount_out = amount1_out
        else:
            token_in = "token1"
            token_out = "token0"
            amount_in = amount1_in
            amount_out = amount0_out

        block = w3.eth.get_block(ev["blockNumber"])
        trades.append(
            {
                "timestamp": block["timestamp"],
                "block_number": ev["blockNumber"],
                "tx_hash": ev["transactionHash"].hex(),
                "token_in": token_in,
                "token_out": token_out,
                "amount_in": amount_in,
                "amount_out": amount_out,
                "gas_used": 0,
                "gas_price": 0,
            }
        )

    print(f"✅ 抓取到 {len(trades)} 笔 Swap 交易")
    return trades
