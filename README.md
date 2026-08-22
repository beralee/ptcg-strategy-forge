# PTCG Strategy Forge

PTCG Strategy Forge 是一个独立的 Windows 策略开发者工具包。它把纯数据 `.ptcgai` 作者策略所需的 SDK、合同、命令、文档、测试场景、完整 demo 和发布客户端放在一个仓库中；开发者不需要另外检出 PtcgDAP 主工程。

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

## 立即开始

要求 Windows、PowerShell 7 和 Python 3.13：

```powershell
.\setup.ps1
.\forge.ps1 doctor
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

新工作区来自已审核的 Marnie 18.0 本地 UID 牌组模板。更换牌组不是改显示名：必须先建立并审核精确的本地卡牌身份、卡源和牌组 manifest。

完整步骤见 [快速入门](docs/01-QUICKSTART.md)。

## 可执行命令

| 命令 | 用途 |
|---|---|
| `doctor` | 验证 Python、SDK 快照、合同漂移和模板包 |
| `new` | 创建不可覆盖的策略工作区并设置作者/包身份 |
| `build` | 生成确定性、test-fixture 签名的 `.ptcgai` |
| `validate` | 用运行 Host 的同一编译入口严格校验 |
| `simulate` | 在一个公开当前窗口上执行策略并输出裁决证据 |
| `test` | 运行正向、负向、重排、forced、veto 和隐私套件 |
| `install` | 严格校验后安装到 Godot 开发包目录 |
| `publish` | 通过 HTTPS 或显式 loopback 向策略平台提交 release |
| `demo` | 完整验证基线 RED、最终 GREEN、双构建和严格校验 |
| `regenerate-demo-scenarios` | 确定性重建 demo 的 10 个场景 |

运行 `python forge.py <command> --help` 查看精确参数。

## 可复核 demo

[`demo/marnie-forge`](demo/marnie-forge) 严格遵循本文档的 RED→GREEN 流程：

- 错误基线把关键手牌 UID 写错，主场景实际选择 `[0]`，因此断言失败；
- 修正策略匹配 `forge.morgrem.evolve`，主场景选择 `[1]`；
- 10 个场景覆盖正向命中、关键卡缺失、错误目标、option 重排、mandatory、terminal、hard tier、veto、未知 UID 和隐藏信息污染；
- 两次构建的 archive 字节完全一致；
- 最终 demo 包已通过真实本地 HTTP release 提交。

发布包：[`strategy-forge-marnie-demo-1.0.0.ptcgai`](demo/releases/strategy-forge-marnie-demo-1.0.0.ptcgai)

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
- [明确限制](docs/LIMITATIONS.md)
- [实施 TODO 闭环](TODO.md)

## 权限边界

开发包使用公开 test-fixture 签名，仅用于开发、影子验证和提交测试。`publish` 成功表示平台接受了一个 `submitted` release，不代表玩家可启动、production 签名、官方 CABT 一致性或 A5 晋升。生产批准和信任根由平台维护者掌握，工具包不会伪造这些权限。

SDK 快照的每个文件都固定在 [`vendor/ptcgdap-sdk-manifest.json`](vendor/ptcgdap-sdk-manifest.json) 中；`doctor` 会拒绝缺失、篡改、额外未登记文件或 symlink。

## 许可

本项目使用 Apache License 2.0。 vendored PtcgDAP 组件的来源和归属见 [NOTICE](NOTICE)。
