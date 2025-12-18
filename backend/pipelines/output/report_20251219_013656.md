# Data Discovery Report

- **Generated**: 2025-12-19T01:36:56
- **Chain**: `mainnet`
- **Window**: 2025-12-18T01:25:49 → 2025-12-19T01:25:49

## Swap Collection
- Swaps collected: **1393**
- Price points computed: **1393**
- First price (token0 per token1): **2860.714116**
- Last  price (token0 per token1): **2800.161247**

## Realized Stats (from swaps)
- Realized return: **-2.1167%**
- Realized vol: **12.2050%**
- Max drawdown: **-6.4240%**

## Whale / CEX Flows
- Whale sell pressure: **0.000000 ETH**
- Selling whales: **0**
- CEX net inflow: **70.596986 ETH**

## Arbitrage (cross-pool spread)
- Opportunities detected: **1**

Top opportunities (up to 5):
- 1. pair=0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48-0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 spread=0.0020% low_pool=0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc high_pool=0x397FF1542f962076d0BFE58eA045FfA2d347ACa0 profitable_after_gas=False

## Uniswap V3 Snapshot
- V3 pools scanned: **3**
- pool=0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640 fee=500 tick=196847 liquidity=769904666678958650 price_token1_per_token0=0.00035361620179239606
- pool=0x8ad599c3A0ff1De082011EFDDc58f1908eb6e6D8 fee=3000 tick=196867 liquidity=1364625514342763352 price_token1_per_token0=0.0003543504570403508
- pool=0x7BeA39867e4169DBe237d55C8242a8f2fcDcc387 fee=10000 tick=196843 liquidity=14157134170804375 price_token1_per_token0=0.00035347619724879957

## V3 Executable Arbitrage (V3↔V3)
- Opportunities: **3**

```json
{
  "enabled": true,
  "mode": "deep",
  "chain": "mainnet",
  "pool_count": 3,
  "opportunities": [
    {
      "network": "mainnet",
      "strategy": "v3_v3_deep_sim",
      "pair_token0": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
      "pair_token1": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
      "symbol0": "USDC",
      "symbol1": "WETH",
      "best_buy_pool": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
      "best_sell_pool": "0x8ad599c3A0ff1De082011EFDDc58f1908eb6e6D8",
      "buy_fee": 500,
      "sell_fee": 3000,
      "spot_buy_price_token1_per_token0": 0.0003533917404703498,
      "spot_sell_price_token1_per_token0": 0.0003541252933629931,
      "executable": false,
      "reason": "sell leg incomplete or zero output",
      "buy_leg_debug": {
        "final_sqrtP": 1489024370190550826342759079110017,
        "final_tick": 196840,
        "crossed_ticks": 0,
        "incomplete": false,
        "amount_in_consumed": 10000000000,
        "amount_in_left": 0
      },
      "sell_leg_debug": {
        "final_sqrtP": 1490932759554622166860781865594652,
        "final_tick": 196861,
        "crossed_ticks": 0,
        "incomplete": true,
        "amount_in_consumed": 0,
        "amount_in_left": 3531288644469299456
      },
      "assumptions": {
        "trade_size_token0": 10000.0,
        "max_tick_cross": 80,
        "words_each_side": 6,
        "max_ticks": 800
      }
    },
    {
      "network": "mainnet",
      "strategy": "v3_v3_deep_sim",
      "pair_token0": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
      "pair_token1": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
      "symbol0": "USDC",
      "symbol1": "WETH",
      "best_buy_pool": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
      "best_sell_pool": "0x7BeA39867e4169DBe237d55C8242a8f2fcDcc387",
      "buy_fee": 500,
      "sell_fee": 10000,
      "spot_buy_price_token1_per_token0": 0.0003532496786867313,
      "spot_sell_price_token1_per_token0": 0.00035347619724879957,
      "executable": false,
      "reason": "sell leg incomplete or zero output",
      "buy_leg_debug": {
        "final_sqrtP": 1488726263676667008718774969729242,
        "final_tick": 196836,
        "crossed_ticks": 0,
        "incomplete": false,
        "amount_in_consumed": 10000000000,
        "amount_in_left": 0
      },
      "sell_leg_debug": {
        "final_sqrtP": 1489565725696024625300129341183369,
        "final_tick": 196843,
        "crossed_ticks": 0,
        "incomplete": true,
        "amount_in_consumed": 0,
        "amount_in_left": 3529871961612017006
      },
      "assumptions": {
        "trade_size_token0": 10000.0,
        "max_tick_cross": 80,
        "words_each_side": 6,
        "max_ticks": 800
      }
    },
    {
      "network": "mainnet",
      "strategy": "v3_v3_deep_sim",
      "pair_token0": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
      "pair_token1": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
      "symbol0": "USDC",
      "symbol1": "WETH",
      "best_buy_pool": "0x7BeA39867e4169DBe237d55C8242a8f2fcDcc387",
      "best_sell_pool": "0x8ad599c3A0ff1De082011EFDDc58f1908eb6e6D8",
      "buy_fee": 10000,
      "sell_fee": 3000,
      "spot_buy_price_token1_per_token0": 0.00035347619724879957,
      "spot_sell_price_token1_per_token0": 0.00035412528174754316,
      "executable": false,
      "reason": "sell leg incomplete or zero output",
      "buy_leg_debug": {
        "final_sqrtP": 1470235943101153765542513275140362,
        "final_tick": 196843,
        "crossed_ticks": 0,
        "incomplete": false,
        "amount_in_consumed": 10000000000,
        "amount_in_left": 0
      },
      "sell_leg_debug": {
        "final_sqrtP": 1490932735103029499586285409021978,
        "final_tick": 196861,
        "crossed_ticks": 0,
        "incomplete": true,
        "amount_in_consumed": 0,
        "amount_in_left": 3454003185278932119
      },
      "assumptions": {
        "trade_size_token0": 10000.0,
        "max_tick_cross": 80,
        "words_each_side": 6,
        "max_ticks": 800
      }
    }
  ],
  "best": {},
  "warnings": [
    "V3_ARB_MODE=deep enabled: this will scan ticks and may be slow / hang on some RPCs.",
    "Use FAST mode for pipeline demo; use DEEP mode for offline validation."
  ],
  "assumptions": {
    "gas_units": 320000,
    "gas_price_wei": null,
    "words_each_side": 6,
    "max_ticks": 800
  }
}
```

## Cross-chain Comparison
```json
{
  "chains": [
    "ethereum",
    "bsc"
  ],
  "pairs": [
    {
      "pair": "USDC-WETH",
      "chains": {
        "ethereum": {
          "available": true,
          "chain": "ethereum",
          "dex_id": "uniswap",
          "pair_address": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
          "url": "https://dexscreener.com/ethereum/0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
          "price_usd": 2830.85,
          "liquidity_usd": 66736928.3,
          "volume_h24": 39295511.55,
          "volume_h6": 21264219.43,
          "volume_h1": 6373503.95,
          "txns_h24": {
            "buys": 3656,
            "sells": 3351
          },
          "txns_h6": {
            "buys": 1352,
            "sells": 1446
          },
          "txns_h1": {
            "buys": 471,
            "sells": 202
          },
          "labels": [
            "v3"
          ],
          "base_token": {
            "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "name": "Wrapped Ether",
            "symbol": "WETH"
          },
          "quote_token": {
            "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "name": "USD Coin",
            "symbol": "USDC"
          }
        },
        "bsc": {
          "available": true,
          "chain": "bsc",
          "dex_id": "pancakeswap",
          "pair_address": "0xEa26B78255Df2bBC31C1eBf60010D78670185bD0",
          "url": "https://dexscreener.com/bsc/0xea26b78255df2bbc31c1ebf60010d78670185bd0",
          "price_usd": 2830.038,
          "liquidity_usd": 296267.42,
          "volume_h24": 26788.44,
          "volume_h6": 19948.07,
          "volume_h1": 5526.19,
          "txns_h24": {
            "buys": 311,
            "sells": 322
          },
          "txns_h6": {
            "buys": 204,
            "sells": 220
          },
          "txns_h1": {
            "buys": 31,
            "sells": 65
          },
          "labels": [
            "v2"
          ],
          "base_token": {
            "address": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
            "name": "Ethereum Token",
            "symbol": "ETH"
          },
          "quote_token": {
            "address": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            "name": "USD Coin",
            "symbol": "USDC"
          }
        }
      },
      "arbitrage": [
        {
          "pair": "USDC-WETH",
          "from_chain": "bsc",
          "to_chain": "ethereum",
          "buy_price_usd": 2830.038,
          "sell_price_usd": 2830.85,
          "gross_spread_bps": 2.8692194239084357,
          "net_spread_bps": -53.430780576091564,
          "assumptions": {
            "trade_size_usd": 10000.0,
            "bridge": {
              "name": "default_bridge",
              "fixed_fee_usd": 3.0,
              "variable_fee_bps": 10.0,
              "eta_seconds": 900
            },
            "gas_cost_usd_total": 8.3,
            "cost_components_bps": {
              "bridge_fixed_fee_bps": 2.9999999999999996,
              "bridge_variable_fee_bps": 10.0,
              "gas_bps": 8.3,
              "slippage_buffer_bps": 20.0,
              "time_risk_bps": 15.0
            }
          }
        }
      ],
      "warnings": []
    }
  ],
  "notes": {
    "source": "DexScreener (free public API)",
    "gas_cost_usd_overrides": "Set GAS_COST_USD_ETHEREUM / GAS_COST_USD_BSC to tune net spread",
    "bridge_overrides": "Set CROSS_CHAIN_BRIDGE_ROUTES_JSON/PATH to tune bridge cost & ETA"
  },
  "best_opportunity": {
    "pair": "USDC-WETH",
    "from_chain": "bsc",
    "to_chain": "ethereum",
    "buy_price_usd": 2830.038,
    "sell_price_usd": 2830.85,
    "gross_spread_bps": 2.8692194239084357,
    "net_spread_bps": -53.430780576091564,
    "assumptions": {
      "trade_size_usd": 10000.0,
      "bridge": {
        "name": "default_bridge",
        "fixed_fee_usd": 3.0,
        "variable_fee_bps": 10.0,
        "eta_seconds": 900
      },
      "gas_cost_usd_total": 8.3,
      "cost_components_bps": {
        "bridge_fixed_fee_bps": 2.9999999999999996,
        "bridge_variable_fee_bps": 10.0,
        "gas_bps": 8.3,
        "slippage_buffer_bps": 20.0,
        "time_risk_bps": 15.0
      }
    }
  }
}
```

## Raw JSON
```json
{
  "chain": "mainnet",
  "start_time": "2025-12-18 01:25:49.921163",
  "end_time": "2025-12-19 01:25:49.921163",
  "swap_count": 1393,
  "price_points": 1393,
  "first_price": 2860.714116123999,
  "last_price": 2800.161246750444,
  "realized_stats": {
    "realized_return": -2.116704672873715,
    "realized_vol": 12.204953840522995,
    "realized_drawdown": -6.4240465496479775
  },
  "whale_metrics": {
    "whale_sell_total": 0,
    "whale_count_selling": 0
  },
  "cex_net_inflow_wei": 70596985934272197260,
  "arbitrage_opportunities": [
    {
      "pair": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48-0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
      "network": "mainnet",
      "low_price_pool": "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc",
      "high_price_pool": "0x397FF1542f962076d0BFE58eA045FfA2d347ACa0",
      "low_price_token1_per_token0": 354354174.35355544,
      "high_price_token1_per_token0": 354361269.1490421,
      "relative_spread": 2.00217635353995e-05,
      "low_reserve0": 10641295054027,
      "low_reserve1": 3770787322922311006168,
      "high_reserve0": 928254248122,
      "high_reserve1": 328937353457501752515,
      "strategy": "v2_cross_pool_executable",
      "is_profitable_after_gas_token0": false,
      "fee_bps": 30,
      "gas_units": 240000,
      "gas_price_wei": 692650909,
      "gas_cost_wei": 166236218160000,
      "best_direction": "",
      "best_buy_pool": "",
      "best_sell_pool": "",
      "best_path_in": "",
      "best_amount_in_token0": 0,
      "best_amount_out_token0": 0,
      "best_mid_token1": 0,
      "best_profit_token0": 0,
      "best_profit_after_gas_token0": 0,
      "best_direction_token1": "",
      "best_buy_pool_token1": "",
      "best_sell_pool_token1": "",
      "best_path_in_token1": "",
      "best_amount_in_token1": 0,
      "best_amount_out_token1": 0,
      "best_mid_token0_from_token1": 0,
      "best_profit_token1": 0
    }
  ],
  "warnings": [],
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
        "priceNative": "2822.03899",
        "priceUsd": "2822.038",
        "txns": {
          "m5": {
            "buys": 2,
            "sells": 3
          },
          "h1": {
            "buys": 60,
            "sells": 59
          },
          "h6": {
            "buys": 241,
            "sells": 232
          },
          "h24": {
            "buys": 634,
            "sells": 503
          }
        },
        "volume": {
          "h24": 1735043.52,
          "h6": 1141931.95,
          "h1": 340957.96,
          "m5": 4366.65
        },
        "priceChange": {
          "m5": 0.06,
          "h1": -3.95,
          "h6": -1.1,
          "h24": -1.55
        },
        "liquidity": {
          "usd": 21282595.32,
          "base": 3771.904,
          "quote": 10638135
        },
        "fdv": 7320775309,
        "marketCap": 7320775309,
        "info": {
          "imageUrl": "https://cdn.dexscreener.com/cms/images/e7ad3f643e8706e541538413f2afad46f18cafb430606caae3c70c0f7425c16e?width=800&height=800&quality=90",
          "openGraph": "https://cdn.dexscreener.com/token-images/og/ethereum/0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2?timestamp=1766079300000",
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
      "priceNative": "2822.03899",
      "priceUsd": "2822.038",
      "txns": {
        "m5": {
          "buys": 2,
          "sells": 3
        },
        "h1": {
          "buys": 60,
          "sells": 59
        },
        "h6": {
          "buys": 241,
          "sells": 232
        },
        "h24": {
          "buys": 634,
          "sells": 503
        }
      },
      "volume": {
        "h24": 1735043.52,
        "h6": 1141931.95,
        "h1": 340957.96,
        "m5": 4366.65
      },
      "priceChange": {
        "m5": 0.06,
        "h1": -3.95,
        "h6": -1.1,
        "h24": -1.55
      },
      "liquidity": {
        "usd": 21282595.32,
        "base": 3771.904,
        "quote": 10638135
      },
      "fdv": 7320775309,
      "marketCap": 7320775309,
      "info": {
        "imageUrl": "https://cdn.dexscreener.com/cms/images/e7ad3f643e8706e541538413f2afad46f18cafb430606caae3c70c0f7425c16e?width=800&height=800&quality=90",
        "openGraph": "https://cdn.dexscreener.com/token-images/og/ethereum/0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2?timestamp=1766079300000",
        "websites": [],
        "socials": []
      }
    }
  },
  "v3": {
    "pools": [
      {
        "pool": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
        "fee": 500,
        "tick": 196847,
        "sqrtPriceX96": 1489860689437739399056495825653045,
        "liquidity": 769904666678958650,
        "token0": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "token1": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "symbol0": "USDC",
        "symbol1": "WETH",
        "decimals0": 6,
        "decimals1": 18,
        "price_token1_per_token0": 0.00035361620179239606
      },
      {
        "pool": "0x8ad599c3A0ff1De082011EFDDc58f1908eb6e6D8",
        "fee": 3000,
        "tick": 196867,
        "sqrtPriceX96": 1491406674526787031938642395198866,
        "liquidity": 1364625514342763352,
        "token0": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "token1": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "symbol0": "USDC",
        "symbol1": "WETH",
        "decimals0": 6,
        "decimals1": 18,
        "price_token1_per_token0": 0.0003543504570403508
      },
      {
        "pool": "0x7BeA39867e4169DBe237d55C8242a8f2fcDcc387",
        "fee": 10000,
        "tick": 196843,
        "sqrtPriceX96": 1489565725696024625300129341183369,
        "liquidity": 14157134170804375,
        "token0": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "token1": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "symbol0": "USDC",
        "symbol1": "WETH",
        "decimals0": 6,
        "decimals1": 18,
        "price_token1_per_token0": 0.00035347619724879957
      }
    ]
  },
  "v3_executable_arbitrage": {
    "enabled": true,
    "mode": "deep",
    "chain": "mainnet",
    "pool_count": 3,
    "opportunities": [
      {
        "network": "mainnet",
        "strategy": "v3_v3_deep_sim",
        "pair_token0": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "pair_token1": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "symbol0": "USDC",
        "symbol1": "WETH",
        "best_buy_pool": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
        "best_sell_pool": "0x8ad599c3A0ff1De082011EFDDc58f1908eb6e6D8",
        "buy_fee": 500,
        "sell_fee": 3000,
        "spot_buy_price_token1_per_token0": 0.0003533917404703498,
        "spot_sell_price_token1_per_token0": 0.0003541252933629931,
        "executable": false,
        "reason": "sell leg incomplete or zero output",
        "buy_leg_debug": {
          "final_sqrtP": 1489024370190550826342759079110017,
          "final_tick": 196840,
          "crossed_ticks": 0,
          "incomplete": false,
          "amount_in_consumed": 10000000000,
          "amount_in_left": 0
        },
        "sell_leg_debug": {
          "final_sqrtP": 1490932759554622166860781865594652,
          "final_tick": 196861,
          "crossed_ticks": 0,
          "incomplete": true,
          "amount_in_consumed": 0,
          "amount_in_left": 3531288644469299456
        },
        "assumptions": {
          "trade_size_token0": 10000.0,
          "max_tick_cross": 80,
          "words_each_side": 6,
          "max_ticks": 800
        }
      },
      {
        "network": "mainnet",
        "strategy": "v3_v3_deep_sim",
        "pair_token0": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "pair_token1": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "symbol0": "USDC",
        "symbol1": "WETH",
        "best_buy_pool": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
        "best_sell_pool": "0x7BeA39867e4169DBe237d55C8242a8f2fcDcc387",
        "buy_fee": 500,
        "sell_fee": 10000,
        "spot_buy_price_token1_per_token0": 0.0003532496786867313,
        "spot_sell_price_token1_per_token0": 0.00035347619724879957,
        "executable": false,
        "reason": "sell leg incomplete or zero output",
        "buy_leg_debug": {
          "final_sqrtP": 1488726263676667008718774969729242,
          "final_tick": 196836,
          "crossed_ticks": 0,
          "incomplete": false,
          "amount_in_consumed": 10000000000,
          "amount_in_left": 0
        },
        "sell_leg_debug": {
          "final_sqrtP": 1489565725696024625300129341183369,
          "final_tick": 196843,
          "crossed_ticks": 0,
          "incomplete": true,
          "amount_in_consumed": 0,
          "amount_in_left": 3529871961612017006
        },
        "assumptions": {
          "trade_size_token0": 10000.0,
          "max_tick_cross": 80,
          "words_each_side": 6,
          "max_ticks": 800
        }
      },
      {
        "network": "mainnet",
        "strategy": "v3_v3_deep_sim",
        "pair_token0": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "pair_token1": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "symbol0": "USDC",
        "symbol1": "WETH",
        "best_buy_pool": "0x7BeA39867e4169DBe237d55C8242a8f2fcDcc387",
        "best_sell_pool": "0x8ad599c3A0ff1De082011EFDDc58f1908eb6e6D8",
        "buy_fee": 10000,
        "sell_fee": 3000,
        "spot_buy_price_token1_per_token0": 0.00035347619724879957,
        "spot_sell_price_token1_per_token0": 0.00035412528174754316,
        "executable": false,
        "reason": "sell leg incomplete or zero output",
        "buy_leg_debug": {
          "final_sqrtP": 1470235943101153765542513275140362,
          "final_tick": 196843,
          "crossed_ticks": 0,
          "incomplete": false,
          "amount_in_consumed": 10000000000,
          "amount_in_left": 0
        },
        "sell_leg_debug": {
          "final_sqrtP": 1490932735103029499586285409021978,
          "final_tick": 196861,
          "crossed_ticks": 0,
          "incomplete": true,
          "amount_in_consumed": 0,
          "amount_in_left": 3454003185278932119
        },
        "assumptions": {
          "trade_size_token0": 10000.0,
          "max_tick_cross": 80,
          "words_each_side": 6,
          "max_ticks": 800
        }
      }
    ],
    "best": {},
    "warnings": [
      "V3_ARB_MODE=deep enabled: this will scan ticks and may be slow / hang on some RPCs.",
      "Use FAST mode for pipeline demo; use DEEP mode for offline validation."
    ],
    "assumptions": {
      "gas_units": 320000,
      "gas_price_wei": null,
      "words_each_side": 6,
      "max_ticks": 800
    }
  },
  "cross_chain_comparison": {
    "chains": [
      "ethereum",
      "bsc"
    ],
    "pairs": [
      {
        "pair": "USDC-WETH",
        "chains": {
          "ethereum": {
            "available": true,
            "chain": "ethereum",
            "dex_id": "uniswap",
            "pair_address": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
            "url": "https://dexscreener.com/ethereum/0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
            "price_usd": 2830.85,
            "liquidity_usd": 66736928.3,
            "volume_h24": 39295511.55,
            "volume_h6": 21264219.43,
            "volume_h1": 6373503.95,
            "txns_h24": {
              "buys": 3656,
              "sells": 3351
            },
            "txns_h6": {
              "buys": 1352,
              "sells": 1446
            },
            "txns_h1": {
              "buys": 471,
              "sells": 202
            },
            "labels": [
              "v3"
            ],
            "base_token": {
              "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
              "name": "Wrapped Ether",
              "symbol": "WETH"
            },
            "quote_token": {
              "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
              "name": "USD Coin",
              "symbol": "USDC"
            }
          },
          "bsc": {
            "available": true,
            "chain": "bsc",
            "dex_id": "pancakeswap",
            "pair_address": "0xEa26B78255Df2bBC31C1eBf60010D78670185bD0",
            "url": "https://dexscreener.com/bsc/0xea26b78255df2bbc31c1ebf60010d78670185bd0",
            "price_usd": 2830.038,
            "liquidity_usd": 296267.42,
            "volume_h24": 26788.44,
            "volume_h6": 19948.07,
            "volume_h1": 5526.19,
            "txns_h24": {
              "buys": 311,
              "sells": 322
            },
            "txns_h6": {
              "buys": 204,
              "sells": 220
            },
            "txns_h1": {
              "buys": 31,
              "sells": 65
            },
            "labels": [
              "v2"
            ],
            "base_token": {
              "address": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
              "name": "Ethereum Token",
              "symbol": "ETH"
            },
            "quote_token": {
              "address": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
              "name": "USD Coin",
              "symbol": "USDC"
            }
          }
        },
        "arbitrage": [
          {
            "pair": "USDC-WETH",
            "from_chain": "bsc",
            "to_chain": "ethereum",
            "buy_price_usd": 2830.038,
            "sell_price_usd": 2830.85,
            "gross_spread_bps": 2.8692194239084357,
            "net_spread_bps": -53.430780576091564,
            "assumptions": {
              "trade_size_usd": 10000.0,
              "bridge": {
                "name": "default_bridge",
                "fixed_fee_usd": 3.0,
                "variable_fee_bps": 10.0,
                "eta_seconds": 900
              },
              "gas_cost_usd_total": 8.3,
              "cost_components_bps": {
                "bridge_fixed_fee_bps": 2.9999999999999996,
                "bridge_variable_fee_bps": 10.0,
                "gas_bps": 8.3,
                "slippage_buffer_bps": 20.0,
                "time_risk_bps": 15.0
              }
            }
          }
        ],
        "warnings": []
      }
    ],
    "notes": {
      "source": "DexScreener (free public API)",
      "gas_cost_usd_overrides": "Set GAS_COST_USD_ETHEREUM / GAS_COST_USD_BSC to tune net spread",
      "bridge_overrides": "Set CROSS_CHAIN_BRIDGE_ROUTES_JSON/PATH to tune bridge cost & ETA"
    },
    "best_opportunity": {
      "pair": "USDC-WETH",
      "from_chain": "bsc",
      "to_chain": "ethereum",
      "buy_price_usd": 2830.038,
      "sell_price_usd": 2830.85,
      "gross_spread_bps": 2.8692194239084357,
      "net_spread_bps": -53.430780576091564,
      "assumptions": {
        "trade_size_usd": 10000.0,
        "bridge": {
          "name": "default_bridge",
          "fixed_fee_usd": 3.0,
          "variable_fee_bps": 10.0,
          "eta_seconds": 900
        },
        "gas_cost_usd_total": 8.3,
        "cost_components_bps": {
          "bridge_fixed_fee_bps": 2.9999999999999996,
          "bridge_variable_fee_bps": 10.0,
          "gas_bps": 8.3,
          "slippage_buffer_bps": 20.0,
          "time_risk_bps": 15.0
        }
      }
    }
  }
}
```
