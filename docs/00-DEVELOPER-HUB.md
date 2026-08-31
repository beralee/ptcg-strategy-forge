# 开发者中心

这页是 PTCG Strategy Forge 的任务导航。日常开发围绕一个 `StrategyWorkspace` 展开；`.ptcgai` 包格式、UCIS、Base Graph 和 ORT 是工作区背后的合同，不需要先全部学会。要上传连续联赛，第一步是在[线上开发者中心](https://ptcg.skillserver.cn/dist/developers.html)注册并复制完整开发者 ID，包括 `developer-` 前缀。

## 先选择你的目标

| 我要做什么 | 第一条命令 | 接着读 |
|---|---|---|
| 从零写规则策略 | `forge workspace create PATH --author-id ID --package-id SHORT_ID` | [快速入门](01-QUICKSTART.md)、[策略思考](09-STRATEGY-THINKING.md) |
| 接入 BC/RL Actor | 增加 `--mode model` | [快速入门的模型部分](01-QUICKSTART.md#接入-bcrl-actor)、[统一模型合同](17-UNIFIED-PTCGAI-RULE-AND-MODEL-DESIGN.md) |
| 看懂一次选择 | `forge workspace inspect PATH` | [UCIS SDK](15-UCIS-SDK-DEVELOPER-GUIDE.md) |
| 查询游戏支持卡牌 | 打开工作区 `SUPPORTED-CARDS.json` | [支持卡牌清单](19-SUPPORTED-CARDS.md) |
| 修复失败测试 | `forge workspace check PATH` | [场景测试](03-SCENARIO-TESTING.md)、[调试](04-DEBUGGING-AND-OPTIMIZATION.md) |
| 在代码里集成 Forge | `from ptcg_strategy_forge import StrategyWorkspace` | [Python SDK 参考](18-DEVELOPER-SDK-REFERENCE.md) |
| 安装或上传 | `forge workspace build PATH` | [安装与发布](05-PUBLISHING.md) |
| 迁移旧 `.ptcgbot` | 不改扩展名，重新导出规则/Actor | [退出与迁移](14-KAGGLE-STYLE-PTCGBOT-QUICKSTART.md) |

本文中的 `forge` 表示仓库根目录下的 `.\forge.ps1`；跨平台或自动化脚本可使用 `python forge.py`。

## 唯一日常生命周期

```text
注册/复制完整 ID → create → status → edit → inspect → check → build
                                      ↑          |              |
                                      └── 修复 ──┘              v
                         登记公钥 ← 生成本机密钥 → resign → upload → qualification
```

`author_id`、`package_id` 和显示名称是三个不同字段：`author_id` 必须逐字符等于后台 `developer_id`；`package_id` 由作者选择短且稳定的策略身份；显示名称只用于展示。不要从显示名称猜 ID，也不要从完整开发者 ID 自动拼一个超长 `package_id`。

| 阶段 | 命令 | 结果 |
|---|---|---|
| create | `workspace create` | 非覆盖地生成完整规则/模型工作区 |
| status | `workspace status` | 显示身份、模式、场景数、编辑入口、缺口、默认产物和下一步 |
| edit | 编辑蓝图、adapter、场景和可选 Actor | 只修改工作区源码，不直接操作游戏 |
| inspect | `workspace inspect` | 命名化展示一个公开当前窗口，不回显 raw observation |
| check | `workspace check` | 双构建、exact bytes、Host 校验、场景、UCIS 和可选模型门 |
| build | `workspace build` | 只有全部门通过才写 `.ptcgai` 和 JSON 报告 |
| install | `workspace install` | 严格校验后进入平台解析的 Godot 用户数据目录 |

旧的 `new/build/validate/simulate/test/check/install` 仍是兼容的底层命令。新开发者不需要手工拼接它们；需要单步诊断或维持既有 CI 时再使用。

## 工作区就是开发产品

工作区不是解压后的随意目录。它把开发者关心的四个视图放在一起：

| 视图 | 编辑入口 | 回答的问题 |
|---|---|---|
| 策略 | `STRATEGY-BLUEPRINT.md` | 怎么赢、资源给谁、何时重规划 |
| 行为 | `package/policy/adapter.json` | 当前公开窗口如何表达目标和偏好 |
| 证据 | `scenarios/`、`scenario-suite.json` | 哪些正例、负例和重排证明了行为 |
| 模型 | `model-source/`、`package/model/` | 训练产物是否符合公开无状态 Actor 合同 |
| 卡牌资格 | `SUPPORTED-CARDS.json` | 本地 UID 的交互路径是否可用或明确 unsupported |

Base IR、包 manifest、精确 deck identity 和合同 hash 是受控层。只有在升级合同、牌组身份或发布版本时才直接修改；普通策略迭代不应借修改这些文件绕过失败。

运行 `workspace status` 可以随时得到机器可读的同一张地图：

```json
{
  "status": "ready",
  "package": {"policy_mode": "rules_only"},
  "scenarios": {"count": 10},
  "edit": {
    "strategy": "STRATEGY-BLUEPRINT.md",
    "rules": "package/policy/adapter.json",
    "scenarios": "scenarios/"
  },
  "outputs": {
    "artifact": "build/<package>-<version>.ptcgai",
    "report": "build/workspace-check.json"
  }
}
```

`ready` 只表示结构和可选 Actor conformance 可进入开发；完整行为是否接受仍由 `check` 决定。

## 规则与模型共享一条产品路径

`rules_only` 和 `rules_with_model` 都构建 `.ptcgai v2`。BC、RL、BC→RL 和 hybrid 只记录为非权威 provenance，不形成不同运行时。

模型模式有三条额外约束：

1. 包必须保留 Competitive IR 规则 fallback，不支持 `model_only`；
2. Actor 只能读取公开整数张量，输出当前 options 的分数和 `desired_count`；
3. Host 先应用 mandatory/terminal、hard tier 和 veto，模型不能获得旧窗口或跨层 authority。

因此，模型开发也从规则场景开始：先证明 fallback 和安全门，再用同一场景生成张量、训练、导入 Actor，并重新运行 `check`。

## CLI 还是 Python SDK

两者不是两套能力：

| 使用场景 | 建议入口 |
|---|---|
| 人工开发、CI shell、证据 JSON | `forge workspace ...` |
| IDE/Notebook/内部工具集成 | `StrategyWorkspace` |
| 只解析 current-window | `SelectionWindow` / `PublicBattleFacts` |
| 合同和运行时维护 | 底层 `ucis`、`model`、`validate` 命令 |

SDK 公开导出只来自 `ptcg_strategy_forge`。不要让开发者代码依赖 `tools/` 或 `scripts/ai/ptcgdap/`；这些是 Forge 内部和受锁 SDK 快照。

## 验收声明怎么读

Forge 把以下声明分开：

- public-window simulation：工作区场景和 Python Host 路径通过；
- Godot engine witness：指定平台真实游戏加载和对局通过；
- CABT alignment：限定输入/index 或规则差分范围有证据；
- device acceptance：具体 OS/架构安装、对局和回放通过；
- production approval：平台签名、审核和权限通过。

`workspace check/build` 只自动关闭第一项以及包/模型合同门。当前 Windows 有独立 Godot 证据；macOS、Android 和 production 状态见[明确限制](LIMITATIONS.md)。

## 继续深入

建议按遇到的问题渐进阅读：

1. [快速入门](01-QUICKSTART.md)：第一个可构建工作区；
2. [策略包与裁决](02-PACKAGE-AND-POLICY.md)：包和 authority；
3. [场景测试](03-SCENARIO-TESTING.md)：证据矩阵；
4. [策略思考](09-STRATEGY-THINKING.md)：多时间尺度路线；
5. [UCIS SDK](15-UCIS-SDK-DEVELOPER-GUIDE.md)：窗口和语义重绑定；
6. [Python SDK](18-DEVELOPER-SDK-REFERENCE.md)：程序化工作区；
7. `docs/11`–`17`：Competitive IR、历史架构、CABT/迁移和统一模型设计。
