# backend/db.py

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Union  # [修改]

# 统一使用这个数据库文件
DB_PATH = Path(__file__).resolve().parent / "defi_monitor.db"


class MonitorDatabase:
    def __init__(self, db_path: Union[Path, str] = DB_PATH):  # [修改] 兼容 Python 3.9+
        self.db_path = str(db_path)
        # 加上 check_same_thread=False，方便 Flask / 监控脚本复用同一个类
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        c = self.conn.cursor()

        # 1) DEX swap 明细
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                block_number INTEGER,
                tx_hash TEXT UNIQUE,
                token_in TEXT,
                token_out TEXT,
                amount_in TEXT,     -- 大整数，统一按字符串存
                amount_out TEXT,    -- 同上
                gas_used TEXT,      -- 同上
                gas_price TEXT,     -- 同上
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 2) 风险等级时间序列（给前端画图）
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS risk_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT,
                level INTEGER,
                source TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 3) 风险指标（原始指标）
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS risk_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT,
                dex_volume INTEGER,
                dex_trades INTEGER,
                whale_sell_total INTEGER,
                whale_count_selling INTEGER,
                cex_net_inflow INTEGER,
                pool_liquidity INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.conn.commit()
        self._migrate_schema()  # [新增] 平滑升级 trades 表字段/索引

    # ------------------------------------------------------------------
    # Schema Migration（不破坏已有数据库文件）
    # ------------------------------------------------------------------
    def _migrate_schema(self):
        """[新增] 对已有数据库做平滑迁移：给 trades 表补充可分析字段。"""
        try:
            c = self.conn.cursor()

            # trades 表新增列：pair/network/token 地址（用于分析与导出）
            c.execute("PRAGMA table_info(trades)")
            cols = {row[1] for row in c.fetchall()}

            def _add_col(name: str, ddl: str):
                if name not in cols:
                    print(f"🛠️ [DB] 迁移：trades 增加列 {name}")
                    c.execute(ddl)

            _add_col("pair_address", "ALTER TABLE trades ADD COLUMN pair_address TEXT")
            _add_col("network", "ALTER TABLE trades ADD COLUMN network TEXT")
            _add_col("token0_address", "ALTER TABLE trades ADD COLUMN token0_address TEXT")
            _add_col("token1_address", "ALTER TABLE trades ADD COLUMN token1_address TEXT")

            # 常用索引（加速按 pair/时间窗口查询）
            c.execute("CREATE INDEX IF NOT EXISTS idx_trades_pair_block ON trades(pair_address, block_number)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(timestamp)")

            self.conn.commit()
        except Exception as e:
            print(f"⚠️ [DB] schema 迁移失败（可忽略，但建议检查）：{e}")

    # ------------------------------------------------------------------
    # 交易明细
    # ------------------------------------------------------------------
    def save_trades(self, trades: List[Dict[str, Any]]):
        if not trades:
            return

        with self.conn:
            c = self.conn.cursor()
            c.executemany(
                """
                INSERT OR IGNORE INTO trades(
                    tx_hash,
                    timestamp,
                    block_number,
                    token_in,
                    token_out,
                    amount_in,
                    amount_out,
                    gas_used,
                    gas_price,
                    pair_address,
                    network,
                    token0_address,
                    token1_address
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        t["tx_hash"],
                        int(t["timestamp"]),
                        int(t["block_number"]),
                        t["token_in"],
                        t["token_out"],
                        str(t["amount_in"]),
                        str(t["amount_out"]),
                        str(t.get("gas_used", 0)),
                        str(t.get("gas_price", 0)),
                        t.get("pair_address"),
                        t.get("network"),
                        t.get("token0_address"),
                        t.get("token1_address"),
                    )
                    for t in trades
                ],
            )

    # ------------------------------------------------------------------
    # 风险等级（给前端用）
    # ------------------------------------------------------------------
    def save_risk_level(self, market_id: str, level: int, source: str = "local"):
        c = self.conn.cursor()
        c.execute(
            """
            INSERT INTO risk_levels (market_id, level, source)
            VALUES (?, ?, ?)
            """,
            (market_id, int(level), source),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # 风险指标（给前端/报告用）
    # ------------------------------------------------------------------
    def save_metrics(self, market_id: str, metrics: Dict[str, Any]):
        """
        metrics 示例:
        {
            "dex_volume": int,
            "dex_trades": int,
            "whale_sell_total": int,
            "whale_count_selling": int,
            "cex_net_inflow": int,
            "pool_liquidity": int,
        }
        """
        dex_volume = int(metrics.get("dex_volume", 0) or 0)
        dex_trades = int(metrics.get("dex_trades", 0) or 0)
        whale_sell_total = int(metrics.get("whale_sell_total", 0) or 0)
        whale_count_selling = int(metrics.get("whale_count_selling", 0) or 0)
        cex_net_inflow = int(metrics.get("cex_net_inflow", 0) or 0)
        pool_liquidity = int(metrics.get("pool_liquidity", 0) or 0)

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO risk_metrics (
                    market_id,
                    dex_volume,
                    dex_trades,
                    whale_sell_total,
                    whale_count_selling,
                    cex_net_inflow,
                    pool_liquidity
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    market_id,
                    dex_volume,
                    dex_trades,
                    whale_sell_total,
                    whale_count_selling,
                    cex_net_inflow,
                    pool_liquidity,
                ),
            )