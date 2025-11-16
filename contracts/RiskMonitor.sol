// contracts/RiskMonitor.sol
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title RiskMonitor
 * @dev 链上市场风险监控合约
 * - 管理员/keeper 更新市场风险等级
 * - 用户配置自己关心的市场和风险阈值（0~3）
 * - 当风险达到阈值时，可触发链上告警事件
 */
contract RiskMonitor is Ownable {
    /// @dev 风险等级：0=正常,1=注意,2=警告,3=高危
    struct MarketRisk {
        uint8 level;
        uint256 lastUpdate;
        bool exists;
    }

    struct UserConfig {
        uint8 thresholdLevel;  // 从多少级开始告警
        bool autoAlert;        // 是否开启自动告警
        bool exists;
    }

    /// @dev 市场 ID 通常用 keccak256("UNISWAP_USDC_WETH") 之类
    mapping(bytes32 => MarketRisk) public markets;
    /// @dev 用户针对某个市场的监控配置
    mapping(address => mapping(bytes32 => UserConfig)) public userConfigs;

    /// @dev 被授权可以更新风控的 keeper（你的 Python 监控脚本）
    address public keeper;

    event MarketRegistered(bytes32 indexed marketId);
    event RiskUpdated(bytes32 indexed marketId, uint8 level, uint256 timestamp);
    event UserConfigUpdated(
        address indexed user,
        bytes32 indexed marketId,
        uint8 thresholdLevel,
        bool autoAlert
    );
    event AlertTriggered(
        address indexed user,
        bytes32 indexed marketId,
        uint8 level,
        uint256 timestamp
    );
    event KeeperChanged(address indexed oldKeeper, address indexed newKeeper);

    modifier onlyKeeperOrOwner() {
        require(msg.sender == keeper || msg.sender == owner(), "Not keeper/owner");
        _;
    }

    /**
     * @dev 构造函数
     * @param _keeper 初始 keeper 地址（通常先设为部署者）
     *
     * 注意：这里显式调用 Ownable(msg.sender)，满足 OpenZeppelin v5 的构造函数要求
     */
    constructor(address _keeper) Ownable(msg.sender) {
        keeper = _keeper;
        emit KeeperChanged(address(0), _keeper);
    }

    function setKeeper(address _keeper) external onlyOwner {
        emit KeeperChanged(keeper, _keeper);
        keeper = _keeper;
    }

    /// @dev 注册一个需要监控的市场（比如某个 DEX 池）
    function registerMarket(bytes32 marketId) external onlyOwner {
        require(!markets[marketId].exists, "Market already exists");
        markets[marketId] = MarketRisk({
            level: 0,
            lastUpdate: block.timestamp,
            exists: true
        });
        emit MarketRegistered(marketId);
    }

    /// @dev Keeper/Owner 更新市场风险等级
    function updateRisk(bytes32 marketId, uint8 newLevel) external onlyKeeperOrOwner {
        require(markets[marketId].exists, "Market not registered");
        require(newLevel <= 3, "Invalid level");

        markets[marketId].level = newLevel;
        markets[marketId].lastUpdate = block.timestamp;

        emit RiskUpdated(marketId, newLevel, block.timestamp);
    }

    /// @dev 用户设置自己关注某个市场的阈值和是否自动告警
    function setUserConfig(
        bytes32 marketId,
        uint8 thresholdLevel,
        bool autoAlert
    ) external {
        require(markets[marketId].exists, "Market not registered");
        require(thresholdLevel <= 3, "Invalid threshold");

        userConfigs[msg.sender][marketId] = UserConfig({
            thresholdLevel: thresholdLevel,
            autoAlert: autoAlert,
            exists: true
        });

        emit UserConfigUpdated(msg.sender, marketId, thresholdLevel, autoAlert);
    }

    /// @dev 用户主动检查当前市场风险并决定是否触发告警
    function checkAndAlert(bytes32 marketId) external {
        UserConfig memory config = userConfigs[msg.sender][marketId];
        require(config.exists, "No config for user");
        MarketRisk memory m = markets[marketId];
        require(m.exists, "Market not registered");

        if (m.level >= config.thresholdLevel) {
            emit AlertTriggered(msg.sender, marketId, m.level, block.timestamp);
        }
    }

    /// @dev keeper 或 owner 可以帮助用户触发告警（例如监控脚本检测到异常）
    function triggerAlertForUser(address user, bytes32 marketId)
        external
        onlyKeeperOrOwner
    {
        UserConfig memory config = userConfigs[user][marketId];
        require(config.exists, "No config for user");
        MarketRisk memory m = markets[marketId];
        require(m.exists, "Market not registered");

        if (m.level >= config.thresholdLevel && config.autoAlert) {
            emit AlertTriggered(user, marketId, m.level, block.timestamp);
        }
    }
}