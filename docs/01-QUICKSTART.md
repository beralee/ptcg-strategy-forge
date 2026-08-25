# 快速入门

## 1. 安装

准备 Windows、PowerShell 7 和 Python 3.13，然后在仓库根目录运行：

```powershell
.\setup.ps1
```

脚本会创建 `.venv`、安装固定依赖并运行 `doctor`。也可手工执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe forge.py doctor
```

`doctor` 必须同时通过 Python、SDK byte manifest、合同漂移和模板包严格校验。

然后用两条命令确认当前 UCIS generation 和开发者视图可用：

```powershell
.\forge.ps1 ucis catalog
.\forge.ps1 ucis walkthrough
```

`walkthrough` 应显示精确选择 `[0,2,4]`，重排后的新索引 `[4,2,0]`，并以 `ucis_runtime_option_shape_invalid` 拒绝未知字段。

## 2. 创建工作区

```powershell
.\forge.ps1 new `
  --output work\my-strategy `
  --package-id dev.example.my-strategy `
  --package-version 0.1.0 `
  --author-id example.author `
  --author-name "Example Author" `
  --strategy-name "My Strategy" `
  --summary "Public-window strategy for the reviewed Marnie deck." `
  --report work\my-strategy-new.json
```

`new` 不覆盖现有目录。工作区包含：

```text
my-strategy/
  README.md
  STRATEGY-BLUEPRINT.md
  package/
    strategy_package.json
    README.md
    LICENSE
    deck/deck.csv
    deck/deck_manifest.json
    policy/policy_ir.json
    policy/adapter.json
    policy/config.json
    policy/weights.bin
  scenarios/
    01-positive.json ... 10-hidden-field.json
  scenario-suite.json
  build/
```

`new` 会直接生成与 demo 同等级的 10 场景套件和策略思考蓝图，不需要开发者手工补一个只能跑正例的测试入口。先按[策略思考方法](09-STRATEGY-THINKING.md)填写蓝图，再修改 adapter。

若要从已审核的 18.0 精确牌组开始，增加 `--deck-id`：

```powershell
.\forge.ps1 new `
  --output work\gardevoir `
  --deck-id 800017097 `
  --package-id dev.example.v18.gardevoir `
  --package-version 1.0.0 `
  --author-id example.author `
  --author-name "Example Author"
```

当前支持 `800018501`（玛俐长毛巨魔）、`800017097`（无碟沙奈朵）、`800018499`（多龙巴鲁托）、`800018509`（猛雷鼓厄诡椪）和 `800018502`（N 的索罗亚克）。该路径会写入逐 printing 源哈希、精确 60 卡 manifest、牌组专用 adapter、完整蓝图和 10 个 RED→GREEN/重排/安全场景。

## 3. 先看懂当前窗口

不要从 raw 数字猜 context。检查生成的正向场景：

```powershell
.\forge.ps1 ucis inspect `
  --scenario work\my-strategy\scenarios\01-positive.json
```

报告会显示命名化 `select_type/context`、`min/max`、稀疏 options、公开 UID binding、双方剩余奖赏、当前 active 能量和 bench 空位；它不会回显完整 raw observation 或隐藏字段。若这里不是预期窗口，先修 scenario/identity，不要调整 adapter priority。

## 4. 先运行模板场景

```powershell
.\forge.ps1 build `
  --source work\my-strategy\package `
  --output work\my-strategy\build\v0.ptcgai

.\forge.ps1 simulate `
  --package work\my-strategy\build\v0.ptcgai `
  --scenario work\my-strategy\scenarios\01-positive.json
```

确认报告中：

```text
status=passed
frontier.decision_state=policy_allowed
decision.selected_indexes=[1]
adjudication.selected_source=adapter_proposal
claims.engine_execution=false
claims.production_authority=false
```

## 5. 按 RED→GREEN 修改

1. 复制场景并先修改 `expected_selected_indexes`，证明当前行为失败；
2. 只修改 `package/policy/adapter.json` 中一个规则或 priority；
3. 用新文件名构建，工具不会覆盖旧 archive；
4. `validate` 后运行全部场景；
5. 检查 `matched_rules`、候选淘汰原因和 `selected_source`，不能只看最终 index；
6. 增加 option 重排、mandatory、terminal、hard tier、veto、未知 UID 和隐藏信息负例。

参考 [`demo/marnie-forge`](../demo/marnie-forge) 的完整实现。

其中 [`sdk_walkthrough.py`](../demo/marnie-forge/sdk_walkthrough.py) 单独演示精确数量、语义重绑定、重复分配和 prize-clock/energy-debt；`.ptcgai` 包本身仍是 data-only，不会把 Python 带进 Godot。

## 6. 一键验收、安装和提交

```powershell
.\forge.ps1 check `
  --workspace work\my-strategy `
  --output work\my-strategy\build\v1.ptcgai `
  --report work\my-strategy\build\check-report.json
.\forge.ps1 install --package work\my-strategy\build\v1.ptcgai
```

`check` 的详细通过条件见[工作区一键验收](10-WORKSPACE-CHECK.md)。安装只进入 Godot 开发目录，不授予玩家开战或 production 权限。提交步骤见 [安装与发布](05-PUBLISHING.md)。
