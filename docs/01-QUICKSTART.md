# 快速入门

目标：从注册账号取得正式作者身份开始，创建一个工作区，看懂第一个选择，跑完全部门，并得到一个可安装、可签名上传的 `.ptcgai`。

## 先取得正式开发者 ID

登录[线上开发者中心](https://ptcg.skillserver.cn/dist/developers.html)，复制账号页显示的完整开发者 ID。它通常以 `developer-` 开头；粘贴到 Forge 时必须逐字符保留，包括 `developer-` 前缀。显示名称、邮箱、密钥标签和后面的十六进制部分都不能单独代替它。

完整开发者 ID 较长，而 `package_id` 还有独立长度限制。正式项目请另外选择一个简短、稳定且全局唯一的包 ID，例如 `dev.myname.my-strategy`，不要让工具从完整开发者 ID 自动拼接包名。

## 安装和自检

当前本地环境要求 Windows、PowerShell 7、Python 3.13：

```powershell
.\setup.ps1
.\forge.ps1 doctor
```

`setup.ps1` 创建 `.venv`、安装固定依赖并运行 `doctor`。`doctor` 必须通过 Python、vendored SDK byte manifest、UCIS 资格、合同漂移和模板包检查。手工环境可以运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe forge.py doctor
```

## 创建第一个规则工作区

```powershell
$developerId = "<从开发者后台复制的完整 ID>"
.\forge.ps1 workspace create work\my-strategy `
  --author-id $developerId `
  --package-id dev.myname.my-strategy `
  --author-name "你的显示名称"
```

这条命令使用约定默认值：

- `author_id` 等于后台完整 `developer_id`；
- `package_id=dev.myname.my-strategy`；
- `package_version=0.1.0`；
- `strategy_name=My Strategy`；
- `policy_mode=rules_only`；
- 默认审核牌组模板和 10 个严格场景。

本地临时示例可以省略部分展示字段；正式上传工作区必须显式传入 `--package-id`，并建议同时固定 `--package-version`、`--author-name`、`--strategy-name` 和 `--summary`。创建命令不覆盖已有目录。

运行状态页：

```powershell
.\forge.ps1 workspace status work\my-strategy
```

它会告诉你工作区是否 `ready`、应该编辑哪些文件、场景数、默认归档/报告路径和下一条命令。`ready` 仅表示结构可进入开发，不等于场景已经通过。

创建结果还包含 `SUPPORTED-CARDS.json`。先按本地 UID 查询目标卡的 `usable` 与 `interaction_status`，再编写牌组与规则；完整字段和边界见[支持卡牌清单](19-SUPPORTED-CARDS.md)。这份清单不会进入最终 `.ptcgai`，也不能用卡名替代本地 UID。

## 只编辑三个位置

第一次迭代先关注：

1. `STRATEGY-BLUEPRINT.md`：写清 Match Agenda、攻击窗口、资源债务和信息动作后的重观察；
2. `package/policy/adapter.json`：把当前合同可表达的规则、macro 和同层偏好写成 data-only IR；
3. `scenarios/` 与 `scenario-suite.json`：固定 RED→GREEN、option 重排和安全负例。

不要通过修改 Base IR、合同 hash、deck identity 或隐藏输入来让用例变绿。Base Graph 仍拥有合法性和最终裁决。

## 看懂当前窗口

```powershell
.\forge.ps1 workspace inspect work\my-strategy
```

省略场景时检查 suite 第一项；也可以指定：

```powershell
.\forge.ps1 workspace inspect work\my-strategy `
  --scenario scenarios\04-reordered.json
```

报告显示命名化 `select_type/context`、`min/max`、稀疏 options、公开 UID binding、奖赏、能量和 bench 信息，不回显 raw observation。窗口或身份错误时先修场景/身份，不要先改 priority。

## RED→GREEN 迭代

1. 复制最接近的场景；
2. 先写新的 `expected_selected_indexes` 或 suite `expect`，确认现有行为失败；
3. 在 owning layer 做最小规则修改；
4. 增加相同语义但 option 重排的场景；
5. 增加 prerequisite 缺失、mandatory/terminal、hard tier/veto、未知 UID 和隐藏字段负例；
6. 对关键阈值增加一次只改一个公开事实的 metamorphic pair。

开发中运行：

```powershell
.\forge.ps1 workspace check work\my-strategy
```

`check` 会双构建并比较 exact bytes、严格走 Host loader/compile、运行完整场景、验证 UCIS 资格；模型工作区还实际运行 ORT conformance。它不保留临时包，适合迭代。

## 构建和安装

全部 GREEN 后：

```powershell
.\forge.ps1 workspace build work\my-strategy
.\forge.ps1 workspace install work\my-strategy
```

默认输出：

```text
work/my-strategy/build/dev.myname.my-strategy-0.1.0.ptcgai
work/my-strategy/build/workspace-check.json
```

输出不覆盖。已有同版本归档时应提升 `package_version` 或选择新 `--output`；不要静默替换同一 artifact identity。安装只进入 Godot 开发目录，不授予玩家开战、CABT parity 或 production 权限。

## 接入 BC/RL Actor

模型工作区只在创建时增加 `--mode model`：

```powershell
.\forge.ps1 workspace create work\my-model-strategy `
  --author-id $developerId `
  --package-id dev.myname.my-model-strategy `
  --mode model
```

工作区仍有完整规则 adapter 和 10 个安全场景；额外生成：

```text
model-source/actor.onnx
package/model/actor.ort
package/model/model_manifest.json
```

模板 Actor 只证明接口可执行，不代表策略质量。用公开场景查看固定训练输入：

```powershell
.\forge.ps1 workspace model tensorize work\my-model-strategy `
  --scenario scenarios\01-positive.json
```

Forge 先用 CABT parser/public firewall 审核场景，再生成 `competitive_public_actor_i32_v1` 的固定 `int32` frame/options/presence/mask。未知 UID/shape 和隐藏输入 fail closed。

训练循环在 Forge 外运行。Actor 必须是无状态、CPU-only、固定 shape、无 custom op/外部数据/动态下载的 ONNX。训练完成后：

```powershell
.\forge.ps1 workspace model inspect work\my-model-strategy `
  --artifact exports\actor.onnx

.\forge.ps1 workspace model import work\my-model-strategy `
  --source exports\actor.onnx `
  --training-method bc_rl `
  --source-run-id run-001

.\forge.ps1 workspace model conformance work\my-model-strategy
.\forge.ps1 workspace check work\my-model-strategy
```

`workspace model import` 与底层非覆盖 `model import` 不同：它专门用于已有工作区，先在临时位置转换和验证，通过后才替换模板 Actor 与 manifest。模型运行时只能在规则所在 hard tier 内排序，不能覆盖 veto/mandatory/terminal；异常时回到规则/Base。

最小可执行 BC→离线 contextual-bandit RL 参考见 [`examples/minimal-bc-rl-marnie`](../examples/minimal-bc-rl-marnie)。该样例是接入证明，不是 full-game RL 或强度声明。

## 从已审核牌组开始

增加 `--deck-id`：

```powershell
.\forge.ps1 workspace create work\gardevoir `
  --author-id $developerId `
  --package-id dev.example.gardevoir `
  --package-version 1.0.0 `
  --strategy-name "18.0 无碟沙奈朵" `
  --deck-id 800017097
```

当前支持的 ID 见根 [README](../README.md#已审核牌组起点)。该路径写入精确 60 卡、逐 printing 来源 hash、牌组专用 adapter/蓝图和场景。其他牌组必须先做身份与卡源审核。

## 程序化使用

同一生命周期可直接嵌入 Python：

```python
from ptcg_strategy_forge import StrategyWorkspace

workspace = StrategyWorkspace.open("work/my-strategy")
print(workspace.status())
print(workspace.inspect())
report = workspace.build()
```

完整方法和错误码见 [Python SDK 参考](18-DEVELOPER-SDK-REFERENCE.md)。

## 发布前

开发构建通过后，账号密钥、登记签名和提交步骤见[安装与发布](05-PUBLISHING.md)。`author_id` 必须与登录账号 `developer_id` 逐字符一致，包括 `developer-` 前缀；私钥不进入仓库、包或 JSON 报告。开发者签名证明账号持钥，不等于 production 批准。
