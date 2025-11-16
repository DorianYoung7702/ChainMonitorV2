# DeFi Market Monitor

一个示例项目：结合链上数据分析的市场监控与风险等级上链合约。

## 目录结构

- contracts/RiskMonitor.sol: 风险监控智能合约
- scripts/deployRiskMonitor.js: Hardhat 部署脚本
- backend/: Python 监控与分析代码

## 使用步骤（简要）

1. 安装 Node 依赖并编译合约：

```bash
npm install
npx hardhat compile
```

2. 配置 `.env`（参考 `.env.example`），填好 `SEPOLIA_RPC_URL`、`PRIVATE_KEY` 等。

3. 部署到 Sepolia：

```bash
npm run deploy:sepolia
```

记录输出的合约地址，写入 `.env` 的 `CONTRACT_ADDRESS`。

4. 安装 Python 依赖并运行监控：

```bash
cd backend
pip install -r requirements.txt
python monitor.py
```

监控脚本会：
- 从主网 Uniswap V2 USDC/WETH 池抓取最近一段 Swap 记录
- 根据简单规则计算风险等级 0~3
- 当风险等级变化时，调用 `RiskMonitor.updateRisk` 在测试网更新风险状态
