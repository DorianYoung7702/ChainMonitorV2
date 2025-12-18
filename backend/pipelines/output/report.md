# Data Discovery Report

- **Generated**: 2025-12-17T23:16:04
- **Chain**: `mainnet`
- **Window**: 2025-12-17T22:15:10 → 2025-12-17T23:15:10

## Swap Collection
- Swaps collected: **82**
- Price points computed: **82**
- First price (token0 per token1): **2934.666571**
- Last  price (token0 per token1): **3007.643651**

## Realized Stats (from swaps)
- Realized return: **2.4867%**
- Realized vol: **3.1386%**
- Max drawdown: **-1.6950%**

## Whale / CEX Flows
- Whale sell pressure: **0.000000 ETH**
- Selling whales: **0**
- CEX net inflow: **-11.459719 ETH**

## Arbitrage (cross-pool spread)
- Opportunities detected: **0**

## Warnings
- markets.json still contains placeholder whale address 0xYourWhaleAddressHere (it will always be skipped).

## Raw JSON
```json
{
  "chain": "mainnet",
  "start_time": "2025-12-17 22:15:10.737584",
  "end_time": "2025-12-17 23:15:10.737584",
  "swap_count": 82,
  "price_points": 82,
  "first_price": 2934.6665714285714,
  "last_price": 3007.643651489639,
  "realized_stats": {
    "realized_return": 2.4867247533863157,
    "realized_vol": 3.1385818129552807,
    "realized_drawdown": -1.69498944233758
  },
  "whale_metrics": {
    "whale_sell_total": 0,
    "whale_count_selling": 0
  },
  "cex_net_inflow_wei": -11459718952591733613,
  "arbitrage_opportunities": [],
  "warnings": [
    "markets.json still contains placeholder whale address 0xYourWhaleAddressHere (it will always be skipped)."
  ],
  "dexscreener": {
    "schemaVersion": "1.0.0",
    "pairs": [
      {
        "chainId": "ethereum",
        "dexId": "uniswap",
        "url": "https://dexscreener.com/ethereum/0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc",
        "pairAddress": "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc",
        "labels": [
          "v2"
        ],
        "baseToken": {
          "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
          "name": "Wrapped Ether",
          "symbol": "WETH"
        },
        "quoteToken": {
          "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
          "name": "USD Coin",
          "symbol": "USDC"
        },
        "priceNative": "3016.5526",
        "priceUsd": "3016.55",
        "txns": {
          "m5": {
            "buys": 0,
            "sells": 0
          },
          "h1": {
            "buys": 47,
            "sells": 34
          },
          "h6": {
            "buys": 101,
            "sells": 93
          },
          "h24": {
            "buys": 517,
            "sells": 489
          }
        },
        "volume": {
          "h24": 2161958.81,
          "h6": 398898.71,
          "h1": 305969.46,
          "m5": 0
        },
        "priceChange": {
          "h1": 2.48,
          "h6": 3.06,
          "h24": 2.7
        },
        "liquidity": {
          "usd": 21997068.99,
          "base": 3646.06079,
          "quote": 10998534
        },
        "fdv": 7807304738,
        "marketCap": 7807304738,
        "info": {
          "imageUrl": "https://cdn.dexscreener.com/cms/images/e7ad3f643e8706e541538413f2afad46f18cafb430606caae3c70c0f7425c16e?width=800&height=800&quality=90",
          "openGraph": "https://cdn.dexscreener.com/token-images/og/ethereum/0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2?timestamp=1765984500000",
          "websites": [],
          "socials": []
        }
      }
    ],
    "pair": {
      "chainId": "ethereum",
      "dexId": "uniswap",
      "url": "https://dexscreener.com/ethereum/0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc",
      "pairAddress": "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc",
      "labels": [
        "v2"
      ],
      "baseToken": {
        "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "name": "Wrapped Ether",
        "symbol": "WETH"
      },
      "quoteToken": {
        "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "name": "USD Coin",
        "symbol": "USDC"
      },
      "priceNative": "3016.5526",
      "priceUsd": "3016.55",
      "txns": {
        "m5": {
          "buys": 0,
          "sells": 0
        },
        "h1": {
          "buys": 47,
          "sells": 34
        },
        "h6": {
          "buys": 101,
          "sells": 93
        },
        "h24": {
          "buys": 517,
          "sells": 489
        }
      },
      "volume": {
        "h24": 2161958.81,
        "h6": 398898.71,
        "h1": 305969.46,
        "m5": 0
      },
      "priceChange": {
        "h1": 2.48,
        "h6": 3.06,
        "h24": 2.7
      },
      "liquidity": {
        "usd": 21997068.99,
        "base": 3646.06079,
        "quote": 10998534
      },
      "fdv": 7807304738,
      "marketCap": 7807304738,
      "info": {
        "imageUrl": "https://cdn.dexscreener.com/cms/images/e7ad3f643e8706e541538413f2afad46f18cafb430606caae3c70c0f7425c16e?width=800&height=800&quality=90",
        "openGraph": "https://cdn.dexscreener.com/token-images/og/ethereum/0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2?timestamp=1765984500000",
        "websites": [],
        "socials": []
      }
    }
  },
  "coingecko": {
    "ethereum": {
      "usd": 3016.61
    }
  }
}
```
