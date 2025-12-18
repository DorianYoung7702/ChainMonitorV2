# DeFi Market Monitor（Blockchain Data Discovery）

本项目是对 **Lindenshore Technical Assessment: Blockchain Data Discovery** 的实现：使用**免费/公开 RPC**连接链上，采集并本地存储数据，进行分析，并在 README 中解释「为什么选这份数据、发现了什么、可以怎么用」。 [oai_citation:0‡Lindenshore_Technical_Assessment__Blockchain_Data_Discovery.pdf](sediment://file_0000000087b071fd980815c3453ab3a6)

---

## 1. 我选择的数据集是什么？为什么它有价值？

我选择以 **Ethereum Mainnet（可扩展到 BSC 等 EVM 链）** 为主要研究对象，聚焦 **DEX 交易与流动性状态**，覆盖：

- **Uniswap V2：Swap 事件（交易流）**  
  用于构建短窗口价格序列、计算已实现波动率/回撤，并用于跨池价差与可执行套利评估。
- **Uniswap V3：Pool 状态（slot0/liquidity）+ 局部 tick 分布（tickBitmap window）**  
  用于理解**集中流动性**导致的价格敏感性（滑点/深度）以及不同 fee tier 的结构差异（500/3000/10000）。这属于题目鼓励的“advanced mechanics（例如 Uniswap v3 集中流动性）”方向。 [oai_citation:1‡Lindenshore_Technical_Assessment__Blockchain_Data_Discovery.pdf](sediment://file_0000000087b071fd980815c3453ab3a6)
- **跨链对比（Ethereum vs BSC）**：同一“经济意义上的交易对”（如 USDC-ETH/WETH）在不同链上的 **USD price、liquidity、volume、txns**，再估算跨链净价差。属于题目 bonus 的“Cross-chain comparisons”。 [oai_citation:2‡Lindenshore_Technical_Assessment__Blockchain_Data_Discovery.pdf](sediment://file_0000000087b071fd980815c3453ab3a6)
- **风险侧信号**：CEX 净流入、巨鲸卖出压力（用于辅助解释短周期价格/风险）

为什么有价值：  
这类数据直接对应题目例子中的 **DEX 交易、套利/MEV 信号**，且链上可审计、实时性强；它能同时支持 **套利机会发现** 与 **风险分析**（波动、回撤、流动性变化、跨链迁移成本）。 [oai_citation:3‡Lindenshore_Technical_Assessment__Blockchain_Data_Discovery.pdf](sediment://file_0000000087b071fd980815c3453ab3a6)

---

## 2. 项目能做什么（产出与报告结构）

运行后会生成一个 **Markdown 报告**（`backend/pipelines/output/report_*.md`），核心模块包括：

1. **Swap Collection（V2）**：窗口内 swap 数、价格点、首尾价  
2. **Realized Stats**：已实现收益、波动率、最大回撤（来自 swaps 价格序列）
3. **Whale / CEX Flows**：巨鲸卖出计数/总量、CEX 净流入
4. **Arbitrage（V2 跨池价差）**：跨池 spread + 是否覆盖 gas
5. **Uniswap V3 Snapshot**：多个 fee tier 的 slot0/tick/liquidity/price
6. **V3 Executable Arbitrage（V3↔V3）**：对 V3 pool 进行可执行套利筛选（fast/deep）
7. **Cross-chain Comparison**：跨链 USD 价格对比 + 成本假设下的净价差

题目要求的“working script + README 说明如何运行/采集什么/学到了什么”在本项目中由 `discovery_run.py` 驱动并通过报告落地。 [oai_citation:4‡Lindenshore_Technical_Assessment__Blockchain_Data_Discovery.pdf](sediment://file_0000000087b071fd980815c3453ab3a6)

---

## 3. 你可以从最新报告里讲出的关键发现（面试叙述模板）

> 以下用你最近一份报告（USDC/WETH）能直接支撑的叙述方式来写，面试时照这个结构讲即可。

### 3.1 市场行为（短窗口）
- 价格在 1 小时窗口内上行（首尾价提升），同时 realized vol 在几个百分点量级，说明短时段波动并不低；max drawdown 为负，体现途中回撤存在（“上行但有明显回撤”）。

### 3.2 交易/资金流（风险侧）
- CEX 净流入为正：可解释为“资产从链上回流到交易所”的风险信号之一（潜在卖压准备），也可作为风险模型的特征输入。
- Whale 卖出为 0：说明你当前巨鲸识别阈值/样本窗口下未捕捉到大额卖出，但不代表没有大资金（需要结合阈值设置与地址覆盖）。

### 3.3 V2 跨池套利（结果是“机会存在但不赚钱”）
- 报告检测到跨池 spread，但 **profitable_after_gas=False**：  
  说明**微小价差被手续费 + gas 吃掉**，这是链上套利的常态结论之一（“发现价差 ≠ 可执行盈利”）。

### 3.4 V3 fee tier 结构（你“用 V3 数据”的价值点）
- 同一交易对在不同 fee tier 的 `liquidity` 差异巨大：通常 0.05%/0.3% 档会更深，1% 档更浅；这意味着：
  - 小单可能在低费池更划算
  - 大单更依赖深度（滑点更关键）
- 你已经把 V3 的 **tick/slot0/liquidity** 拉到报告里，这是分析“集中流动性导致滑点/冲击成本”的基础。

### 3.5 V3↔V3 套利（目前结论：净价差为负）
- 你的 V3 可执行套利模块给出 gross spread，但 net spread（含手续费+gas）为负：  
  这很好解释为 **fee tier 差异 + gas 成本** 使得“看起来有价差，但不可执行盈利”。

### 3.6 跨链对比（Ethereum vs BSC）
- 你已能得到两个链上的 `price_usd/liquidity/volume/txns`，并输出 gross/net spread。  
- 当前示例净价差为负：说明在你设定的桥费、gas、滑点缓冲、时间风险等假设下，跨链套利不划算（这是非常合理的结论）。

---

## 4. 如何应用这些数据（Arb / MEV / Risk 的落地方式）

题目明确希望你说明应用方向（如 arbitrage、MEV detection、risk analysis）。 [oai_citation:5‡Lindenshore_Technical_Assessment__Blockchain_Data_Discovery.pdf](sediment://file_0000000087b071fd980815c3453ab3a6)  
你可以按下面三条讲（即使你只做了其中两条，也能说得完整）：

### 4.1 套利（Arbitrage）
- **发现层**：基于多池/多链的价格快照计算 spread（你已实现 V2 跨池、V3↔V3、跨链对比）
- **可执行层**：引入手续费、gas、（跨链）桥费/时间风险/滑点缓冲，输出 net spread 与 best route（你已有成本拆分假设）
- **风控层**：如果 CEX 净流入/波动突然放大，可对套利策略降频或提高阈值（避免高波动期被滑点吞噬）

### 4.2 MEV Detection（下一步增强点）
你当前采集了 swaps + pool state，这是 MEV 检测的基础数据，但要实现“检测算法”，通常需要：
- 同块多笔 swap 的模式识别（sandwich/backrun）
- 交易排序与价格冲击回撤形态
- 进一步可接入 tx trace/mempool（更硬核，但不是必须）

> 建议：在 README 里把 MEV 写成“已具备数据基础 + 下一步计划”，并给出你会如何做候选识别（规则/特征）。

### 4.3 风险分析（Risk Analysis）
利用你已有数据，可以构建轻量风险评分：
- realized vol、drawdown（市场风险）
- V3 流动性深度（流动性风险）
- CEX 净流入（潜在抛压）
- 价差与失败的“可执行套利”（市场效率/拥堵与成本压力的侧面指标）

---

## 5. 项目结构（关键文件）

- `backend/pipelines/discovery_run.py`  
  主入口：拉取 swaps/flows/v3 状态/套利/跨链对比，生成报告（Markdown + Raw JSON）。
- `backend/config.py`  
  RPC 配置与 `make_web3()`：从 `.env` 读取各链 RPC URL。
- `backend/collectors/v3_data.py`  
  V3 池状态（slot0/liquidity/fee/tickSpacing）与 tickBitmap window 扫描。
- `backend/analysis/arbitrage_v3_exec.py`  
  V3↔V3 套利（fast 筛选 + 可扩展 deep tick-level 仿真）。

---

## 6. 运行方式

### 6.1 环境准备
- Python 3.10+（建议 3.12 与你当前一致）
- 安装依赖
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt