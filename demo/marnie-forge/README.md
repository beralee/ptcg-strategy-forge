# Marnie Forge 可执行 demo

这个目录同时演示两层开发体验：

1. `package/`、`scenarios/` 和 `scenario-suite.json`：data-only `.ptcgai` 的 RED→GREEN、Base 裁决和 10 场景验收；
2. `sdk_walkthrough.py`：UCIS 当前窗口 SDK 的精确数量、语义重绑定、重复分配、公开奖赏/能量事实和 unknown shape 拒绝。

从 Forge 根目录运行：

```powershell
.\forge.ps1 ucis inspect --scenario demo\marnie-forge\scenarios\01-positive.json
.\forge.ps1 ucis walkthrough
.\forge.ps1 demo --output "$env:TEMP\ptcg-strategy-forge-demo"
```

`demo` 必须同时证明：错误 adapter 基线 RED、最终 10/10 GREEN、两次 `.ptcgai` 构建 exact bytes 相同、严格 Host 校验通过，以及 UCIS SDK walkthrough GREEN。

阅读顺序：

- [`sdk_walkthrough.py`](sdk_walkthrough.py)：直接可运行的 SDK 代码；
- [`scenarios/01-positive.json`](scenarios/01-positive.json)：合法 `EVOLVES_TO` CARD 窗口；
- [`scenarios/04-reordered.json`](scenarios/04-reordered.json)：同一语义目标移动到新 index；
- [`optimization/README.md`](optimization/README.md)：adapter RED→GREEN；
- [`package/README.md`](package/README.md)：包权限和身份边界。

所有结果均为 development-only。demo 不执行引擎动作，不授予 production、完整规则 A3 或官方认证。
