# PTCG Strategy Forge

PTCG Strategy Forge 是一个独立的 Windows 策略开发者工具包。它把纯数据 `.ptcgai` 作者策略所需的 SDK、合同、命令、文档、测试场景、完整 demo 和发布客户端放在一个仓库中；开发者不需要另外检出 PtcgDAP 主工程。

项目仓库：[github.com/beralee/ptcg-strategy-forge](https://github.com/beralee/ptcg-strategy-forge)；稳定发布：[PTCG Strategy Forge v0.1.1](https://github.com/beralee/ptcg-strategy-forge/releases/tag/v0.1.1)。

当前稳定工作流是：

```text
环境自检 → 创建策略工作区 → 编写受限规则 → 确定性构建
→ 严格校验 → RED→GREEN 场景测试 → 本地安装 → 提交 release
```

策略的公共边界始终是：

```text
agent(raw_observation) -> list[int]
```

返回值只能是当前不可变 `select.option` 窗口中的索引。策略包不能执行 Python/GDScript、访问 Godot 对象或读取对手隐藏信息；Base Graph 保留合法性、强制/终局保护、veto、fallback 和最终裁决权。

先按交付目标选择路径：

| 我要开发 | 从哪里开始 | 能力边界 |
|---|---|---|
| 本地游戏可加载的 data-only 策略 | `forge new`，生成 `.ptcgai` | 受限/Competitive IR；Godot Host/Base 最终裁决 |
| Kaggle 风格多文件 Python 策略 | `forge competition init`，生成 `.ptcgbot` | developer-local Python runner；不可直接安装进游戏 |

两条路径共享 UCIS current-window 合同。第一次接触项目时先运行 `forge ucis walkthrough`，它会用可执行例子说明精确数量、option 重排、重复分配、奖赏时钟、能量债务和 fail-closed。

## 立即开始

要求 Windows、PowerShell 7 和 Python 3.13：

```powershell
.\setup.ps1
.\forge.ps1 doctor
.\forge.ps1 ucis catalog
.\forge.ps1 ucis walkthrough
```

创建自己的策略工作区：

```powershell
.\forge.ps1 new `
  --output work\my-strategy `
  --package-id dev.example.my-strategy `
  --package-version 0.1.0 `
  --author-id example.author `
  --author-name "Example Author" `
  --strategy-name "My Strategy"
```

构建、校验和测试：

```powershell
.\forge.ps1 build `
  --source work\my-strategy\package `
  --output work\my-strategy\build\my-strategy.ptcgai

.\forge.ps1 validate `
  --package work\my-strategy\build\my-strategy.ptcgai

.\forge.ps1 test `
  --package work\my-strategy\build\my-strategy.ptcgai `
  --suite work\my-strategy\scenario-suite.json
```

日常推荐用一条命令完成双构建、确定性比较、严格校验和整套场景，并且只在全部通过后写出包：

```powershell
.\forge.ps1 check `
  --workspace work\my-strategy `
  --output work\my-strategy\build\my-strategy.ptcgai `
  --report work\my-strategy\build\check-report.json
```

新工作区还会生成 `STRATEGY-BLUEPRINT.md`，引导开发者先写清 Match Agenda、攻击窗口、资源债务、信息动作后的重观察和类型化交互，再把当前合同可表达的部分编译成 adapter 规则。默认工作区来自已审核的 Marnie 18.0 模板；`new --deck-id` 还可生成五套已审核 18.0 精确本地 UID 工作区：玛俐长毛巨魔 `800018501`、无碟沙奈朵 `800017097`、多龙巴鲁托 `800018499`、猛雷鼓厄诡椪 `800018509`、N 的索罗亚克 `800018502`。其他牌组仍必须先建立并审核精确身份、卡源和 manifest，不能只改显示名。

Competitive Policy IR v2 保持官方 `agent(raw_observation) -> list[int]` 调用形式不变，并把列表长度解释为当前窗口的精确合法数量。Host 对检索、弃牌、出战、撤退、效果、分配和伤害窗口逐次重观察；公开目标能量、攻击就绪、资源债务、奖赏价值与投影伤害可用于 data-only 规则，Base 仍负责合法性与最终裁决。架构与迁移门见 `docs/11-COMPETITIVE-POLICY-IR-V2.md`。

当前 Host 还提供 sealed compiled fast path：完整 policy 验证在加载期完成，每个窗口只运行已封存的公开事实/规则计划。固定重放从 236.647 秒降到 10.958 秒（21.6×），平均作者决策从 819.485 ms 降到 26.211 ms。性能问题已经从“不可玩”降到可用，但猛雷鼓对经典 GDScript 的两个独立 20 局样本为 45%/40%，尚未达到 47% 强度门。设计、实现状态和下一阶段见 [架构升级设计与计划](docs/12-ARCHITECTURE-UPGRADE-DESIGN-AND-PLAN.md)。

完整步骤见 [快速入门](docs/01-QUICKSTART.md)。

另有一条严格分域的 Kaggle 风格 Python 开发预览：`forge.ps1 competition ...` 可创建多文件 `.ptcgbot` v2、做确定性双构建、公开 trace 和 developer-local prequalification。它固定 CPython 3.11.13、A1 scope、Search=none 与资源/隐私故障门，不可安装到玩家游戏，也不声称 official engine 或 production sandbox。见 [`.ptcgbot` v2 快速入门](docs/14-KAGGLE-STYLE-PTCGBOT-QUICKSTART.md)。

`competition init` 会把无依赖、generation-locked 的 `src/submission/ucis.py` 放进新工程；开发者可用名称解析 Context/Option、精确选择数量、按 semantic key 在新窗口重绑定，并读取公开 prize clock/energy debt。完整 API 见 [UCIS SDK 开发者指南](docs/15-UCIS-SDK-DEVELOPER-GUIDE.md)。

## 可执行命令

| 命令 | 用途 |
|---|---|
| `doctor` | 验证 Python、SDK 快照、UCIS generation/目录资格/性能与 operation 回执、合同漂移和模板包 |
| `ucis catalog/inspect/walkthrough` | 查看能力闭包、检查命名化公开窗口并运行 SDK 上手示例 |
| `new` | 创建不可覆盖的策略工作区；可用 `--deck-id` 选择已审核 18.0 牌组 |
| `build` | 生成确定性、test-fixture 签名的 `.ptcgai` |
| `validate` | 用运行 Host 的同一编译入口严格校验 |
| `simulate` | 在一个公开当前窗口上执行策略并输出裁决证据 |
| `test` | 运行正向、负向、重排、forced、veto 和隐私套件 |
| `check` | 双构建并比较 exact bytes，严格校验后运行完整工作区套件 |
| `install` | 严格校验后安装到 Godot 开发包目录 |
| `publish` | 通过 HTTPS 或显式 loopback 向策略平台提交 release |
| `demo` | 完整验证基线 RED、最终 GREEN、双构建和严格校验 |
| `regenerate-demo-scenarios` | 确定性重建 demo 的 10 个场景 |
| `competition <subcommand>` | 创建、测试、构建、trace、重放和预资格 `.ptcgbot` v2 |

运行 `python forge.py <command> --help` 查看精确参数。

## 可复核 demo

[`demo/marnie-forge`](demo/marnie-forge) 严格遵循本文档的 RED→GREEN 流程：

- 错误基线把关键手牌 UID 写错，主场景实际选择 `[0]`，因此断言失败；
- 修正策略匹配 `forge.morgrem.evolve`，主场景选择 `[1]`；
- 10 个场景覆盖正向命中、关键卡缺失、错误目标、option 重排、mandatory、terminal、hard tier、veto、未知 UID 和隐藏信息污染；
- SDK walkthrough 额外覆盖 `0..5` 精确取 3、重复 source→target 新窗口重绑定、公开奖赏/能量事实和未知 shape 拒绝；
- 两次构建的 archive 字节完全一致；
- 最终 demo 包已通过真实本地 HTTP release 提交。

发布包：[`strategy-forge-marnie-demo-1.0.0.ptcgai`](demo/releases/strategy-forge-marnie-demo-1.0.0.ptcgai)；也可从 [GitHub Release](https://github.com/beralee/ptcg-strategy-forge/releases/download/v0.1.1/strategy-forge-marnie-demo-1.0.0.ptcgai) 下载。

```text
package_id     dev.beralee.marnie-forge-demo
version        1.0.0
SHA-256        7F53F2DC698B0290DFC46C5E439B02439E4849B9522235B547EE5649EDA0D33A
scenarios      10 / 10
signature      test_fixture_only
production     false
```

证据见 [`evidence/demo-workflow-green.json`](evidence/demo-workflow-green.json) 和 [`evidence/demo-publish-receipt.json`](evidence/demo-publish-receipt.json)。

## 文档地图

- [快速入门](docs/01-QUICKSTART.md)
- [策略包与裁决模型](docs/02-PACKAGE-AND-POLICY.md)
- [场景测试](docs/03-SCENARIO-TESTING.md)
- [调试与优化](docs/04-DEBUGGING-AND-OPTIMIZATION.md)
- [安装与发布](docs/05-PUBLISHING.md)
- [安全与隐私](docs/06-SECURITY-AND-PRIVACY.md)
- [故障排查](docs/07-TROUBLESHOOTING.md)
- [架构与 SDK 来源](docs/08-ARCHITECTURE.md)
- [从牌组思路到可验证策略](docs/09-STRATEGY-THINKING.md)
- [工作区一键验收](docs/10-WORKSPACE-CHECK.md)
- [Competitive Policy IR v2](docs/11-COMPETITIVE-POLICY-IR-V2.md)
- [架构升级设计、实现与后续计划](docs/12-ARCHITECTURE-UPGRADE-DESIGN-AND-PLAN.md)
- [Kaggle 级开发、CABT A1 与五牌组 A3 详细设计/实施状态](docs/13-KAGGLE-GRADE-DEVELOPER-AND-ENGINE-PARITY-DESIGN.md)
- [Kaggle 风格 `.ptcgbot` v2 快速入门](docs/14-KAGGLE-STYLE-PTCGBOT-QUICKSTART.md)
- [UCIS SDK 开发者指南](docs/15-UCIS-SDK-DEVELOPER-GUIDE.md)
- [明确限制](docs/LIMITATIONS.md)
- [实施 TODO 闭环](TODO.md)

## 权限边界

开发包使用公开 test-fixture 签名，仅用于开发、影子验证和提交测试。`publish` 成功表示平台接受了一个 `submitted` release，不代表玩家可启动、production 签名、官方 CABT 一致性或 A5 晋升。生产批准和信任根由平台维护者掌握，工具包不会伪造这些权限。

SDK 快照的每个文件都固定在 [`vendor/ptcgdap-sdk-manifest.json`](vendor/ptcgdap-sdk-manifest.json) 中；`doctor` 会拒绝缺失、篡改、额外未登记文件或 symlink。

当前 UCIS generation 1 固定 16 个交互原语和完整 49×17 CABT-shaped current-window census。PtcgDAP 目录中的 797 张卡/730 个 effect 已分为 265 个 compiled、464 个 automatic 和 1 个 explicit unsupported；729 个声明可用 effect 与 394/394 个旧交互入口均由单一 UCIS owner 管理。`doctor`/`check` 会在作者代码或场景执行前验证目录资格、热路径无 I/O 性能回执及九类代表性双引擎 operation input/index 回执。

## 许可

本项目使用 Apache License 2.0。 vendored PtcgDAP 组件的来源和归属见 [NOTICE](NOTICE)。
