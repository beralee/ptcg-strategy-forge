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

`new` 会直接生成与 demo 同等级的 10 场景套件，不需要开发者手工补一个只能跑正例的测试入口。

## 3. 先运行模板场景

```powershell
.\forge.ps1 build `
  --source work\my-strategy\package `
  --output work\my-strategy\build\v0.ptcgai

.\forge.ps1 simulate `
  --package work\my-strategy\build\v0.ptcgai `
  --scenario work\my-strategy\scenarios\morgrem-evolve.json
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

## 4. 按 RED→GREEN 修改

1. 复制场景并先修改 `expected_selected_indexes`，证明当前行为失败；
2. 只修改 `package/policy/adapter.json` 中一个规则或 priority；
3. 用新文件名构建，工具不会覆盖旧 archive；
4. `validate` 后运行全部场景；
5. 检查 `matched_rules`、候选淘汰原因和 `selected_source`，不能只看最终 index；
6. 增加 option 重排、mandatory、terminal、hard tier、veto、未知 UID 和隐藏信息负例。

参考 [`demo/marnie-forge`](../demo/marnie-forge) 的完整实现。

## 5. 严格校验、安装和提交

```powershell
.\forge.ps1 validate --package work\my-strategy\build\v1.ptcgai
.\forge.ps1 test --package work\my-strategy\build\v1.ptcgai --suite work\my-strategy\scenario-suite.json
.\forge.ps1 install --package work\my-strategy\build\v1.ptcgai
```

安装只进入 Godot 开发目录，不授予玩家开战或 production 权限。提交步骤见 [安装与发布](05-PUBLISHING.md)。
