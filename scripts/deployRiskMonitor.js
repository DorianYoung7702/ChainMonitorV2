// scripts/deployRiskMonitor.js
const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  const deployerAddress = await deployer.getAddress();
  console.log("Deploying contracts with:", deployerAddress);

  const RiskMonitor = await hre.ethers.getContractFactory("RiskMonitor");
  // 构造函数需要一个 keeper 地址，这里直接用部署者
  const riskMonitor = await RiskMonitor.deploy(deployerAddress);

  // ethers v6 用 waitForDeployment()，而不是 deployed()
  await riskMonitor.waitForDeployment();

  const contractAddress = await riskMonitor.getAddress();
  console.log("RiskMonitor deployed to:", contractAddress);

  // 计算一个固定的 marketId：keccak256("UNISWAP_USDC_WETH")
  const marketId = hre.ethers.keccak256(
    hre.ethers.toUtf8Bytes("UNISWAP_USDC_WETH")
  );
  const tx = await riskMonitor.registerMarket(marketId);
  await tx.wait();
  console.log("Registered market UNISWAP_USDC_WETH with id:", marketId);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});