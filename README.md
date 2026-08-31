# PTCG Strategy Forge

PTCG Strategy Forge 是独立的 `.ptcgai` 策略开发工具包。开发者在一个工作区里完成规则编写、BC/RL Actor 导入、公开窗口检查、场景验收、确定性构建和本地安装，不需要检出 PtcgDAP 游戏仓库。

策略边界始终是：

```text
agent(raw_observation) -> list[int]
```

返回值只能引用当前不可变 `select.option`。包是数据，不执行 Python/GDScript，不读取隐藏信息，也不能越过 Base Graph 的 legality、mandatory/terminal、hard tier、veto、fallback 和最终裁决。

第一次使用先读[开发者中心](docs/00-DEVELOPER-HUB.md)；准备上传到连续联赛时，先在[线上开发者中心](https://ptcg.skillserver.cn/dist/developers.html)注册并复制页面显示的完整开发者 ID。显示名称不是开发者 ID，复制时必须保留 `developer-` 前缀。

## 四步跑通

当前本地工具链要求 Windows、PowerShell 7 和 Python 3.13。

```powershell
.\setup.ps1
.\forge.ps1 doctor

$developerId = "<从开发者后台复制的完整 ID>"
.\forge.ps1 workspace create work\my-strategy `
  --author-id $developerId `
  --package-id dev.example.my-strategy
.\forge.ps1 workspace status work\my-strategy
```

服务端生成的开发者 ID 较长，因此正式工作区应显式给出简短、稳定且全局唯一的 `--package-id`。`package_id` 是策略身份，不需要也不应复制完整开发者 ID。

编辑生成的 `STRATEGY-BLUEPRINT.md`、`package/policy/adapter.json` 和 `scenarios/`，然后：

```powershell
.\forge.ps1 workspace inspect work\my-strategy
.\forge.ps1 workspace check work\my-strategy
.\forge.ps1 workspace build work\my-strategy
.\forge.ps1 workspace install work\my-strategy
```

`build` 会采用工作区身份生成默认产物，例如 `build/dev.example.my-strategy-0.1.0.ptcgai`，同时写出 `build/workspace-check.json`。工具不覆盖已有工作区、归档或证据。

正式上传还需要在仓库外生成私钥、把公开 JSON 中的 `public_key_base64` 登记到当前账号，再用同一私钥执行 `release-resign`。浏览器永远不需要私钥。完整可复制流程见[安装与发布](docs/05-PUBLISHING.md)。

## 选择规则或模型

两条开发方式最终都是同一种 `.ptcgai v2`：

| 目标 | 创建命令 | 运行时边界 |
|---|---|---|
| 纯规则 | `workspace create ... --mode rules` | `rules_only`，受限/Competitive IR |
| BC/RL/混合模型 | `workspace create ... --mode model` | `rules_with_model`，冻结 CPU ORT Actor + 必需规则 fallback |

模型训练方法不是运行时类型。Forge 不负责训练循环，只固定公开张量、Actor 合同、导入检查和运行裁决。训练后用工作区命令安全替换模板 Actor：

```powershell
.\forge.ps1 workspace model inspect work\my-strategy `
  --artifact work\my-strategy\model-source\actor.onnx

.\forge.ps1 workspace model import work\my-strategy `
  --source work\my-strategy\model-source\actor.onnx `
  --training-method bc_rl `
  --source-run-id my-training-run

.\forge.ps1 workspace model tensorize work\my-strategy `
  --scenario scenarios\01-positive.json

.\forge.ps1 workspace model conformance work\my-strategy
```

导入流程先在临时位置检查 ONNX、转换 ORT 并跑 conformance，通过后才替换 `package/model/actor.ort` 和对应 manifest。模型只在规则选定的 hard tier 内评分；异常、超时、未知 UID/shape 或输出非法时回到本窗口规则/Base fallback。

可执行的最小 BC→离线 contextual-bandit RL 示例在 [`examples/minimal-bc-rl-marnie`](examples/minimal-bc-rl-marnie)。它证明接入链路，不声明模型强度、full-game RL 或 production 资格。

## 一个工作区里有什么

```text
my-strategy/
  README.md                  日常命令
  STRATEGY-BLUEPRINT.md      Match Agenda、路线和信息检查点
  UCIS-SDK.md                当前窗口上手卡
  SUPPORTED-CARDS.json       当前游戏卡牌/交互资格清单
  package/
    strategy_package.json    包身份和能力声明
    deck/                    精确牌组与本地 UID
    policy/adapter.json      开发者规则入口
    policy/policy_ir.json    Base/受限 IR
    model/                   model 模式才有冻结 Actor
  scenarios/                 RED→GREEN 与安全负例
  scenario-suite.json
  model-source/              model 模式的训练导出源
  build/                     验收报告和 `.ptcgai`
```

根仓库的同源文件是 [`data/developer/supported-cards-v1.json`](data/developer/supported-cards-v1.json)。当前快照列出 797 个本地 UID 条目，其中 796 个 `usable=true`，1 个明确 unsupported；`usable` 只表示声明的 UCIS 交互路径可用，不代表官方完整规则结果一致、已有策略模板或卡名翻译身份。

开发者通常只编辑蓝图、adapter、场景；模型工作区再更新 Actor。包格式、Base IR、安全合同和 vendored SDK hash 不是普通策略调参面。

## Python SDK

CLI 和 Python SDK 共享同一个工作区对象：

```python
from ptcg_strategy_forge import StrategyWorkspace

workspace = StrategyWorkspace.create(
    "work/my-strategy",
    author_id="<从后台复制的完整 developer_id>",
    package_id="dev.example.my-strategy",
    mode="rules",
)

print(workspace.status())
print(workspace.inspect())
report = workspace.build()
```

模型入口是 `workspace.model.inspect/import_actor/tensorize/conformance`。稳定类型、错误码和方法合同见 [Python SDK 参考](docs/18-DEVELOPER-SDK-REFERENCE.md)。UCIS 的窗口级 `SelectionWindow`、`PublicBattleFacts` 等 API 继续公开，不需要从内部 `scripts/` 导入。

## 命令分层

日常开发优先使用 `workspace`：

| 命令 | 开发者问题 |
|---|---|
| `workspace create` | 创建规则或模型工作区 |
| `workspace status` | 应该编辑什么、还缺什么、产物在哪里 |
| `workspace inspect` | 当前场景到底是什么窗口和公开事实 |
| `workspace check` | 源码能否通过全部门，不写产物 |
| `workspace build` | 验收后生成确定性包和报告 |
| `workspace install` | 构建（若需要）并安装开发包 |
| `workspace model ...` | 检查、导入、张量化和验证 Actor |

`new/build/validate/simulate/test/check/install`、`ucis ...` 和顶层 `model ...` 仍保留给已有脚本和底层诊断。`release-key/release-build/release-resign/publish` 属于发布流程；它们不会把开发包提升为 production。

运行 `python forge.py --help` 或 `python forge.py workspace --help` 查看完整参数。

## 已审核牌组起点

`workspace create --deck-id <id>` 可从已固定身份和卡源的牌组开始：

| deck id | 牌组 |
|---:|---|
| `800018501` | 玛俐长毛巨魔 |
| `646600` | 玛俐的礼盒 |
| `800017097` | 无碟沙奈朵 |
| `800018499` | 多龙巴鲁托 |
| `800018509` | 猛雷鼓厄诡椪 |
| `800018502` | N 的索罗亚克 |
| `800018880` | 阿响的火暴兽 |
| `800052301` | 厄诡椪／岩殿居蟹迁移 |

其他牌组必须先审核精确 deck/card identity 和本地 UID，不能只改显示名。已有策略证据和回放结果是参考，不是新工作区的自动能力。

## 当前交付状态

- `.ptcgai v1` 保持字节兼容；新工作区默认 v2 `rules_only` 或 `rules_with_model`。
- Windows x86_64 已有规则/原生 CPU ORT 的 Forge 与真实 Godot 开发见证。
- macOS arm64/x86_64 有构建入口，但实机安装、对局与回放门尚未完成。
- Android、GPU/CoreML、有状态模型和 production 均不在当前已通过范围。
- 旧 `.ptcgbot`/Python competition 运行期已退出活动产品路径，只保留历史审计证据。

完整声明边界见[明确限制](docs/LIMITATIONS.md)和[统一规则/模型设计](docs/17-UNIFIED-PTCGAI-RULE-AND-MODEL-DESIGN.md)。

## 文档按任务阅读

- [开发者中心](docs/00-DEVELOPER-HUB.md)：从目标选择路径、文件和命令。
- [快速入门](docs/01-QUICKSTART.md)：从空目录到第一个包。
- [策略包与裁决](docs/02-PACKAGE-AND-POLICY.md)：包里有什么，谁拥有最终权力。
- [场景测试](docs/03-SCENARIO-TESTING.md)：RED→GREEN、重排和负例。
- [调试与优化](docs/04-DEBUGGING-AND-OPTIMIZATION.md)：从失败报告定位 owning layer。
- [安装与发布](docs/05-PUBLISHING.md)：本地开发安装与账号签名。
- [安全与隐私](docs/06-SECURITY-AND-PRIVACY.md)：公开输入和 fail-closed 边界。
- [故障排查](docs/07-TROUBLESHOOTING.md)：稳定错误码。
- [架构](docs/08-ARCHITECTURE.md)：Host/Base、SDK 快照和运行时。
- [策略思考](docs/09-STRATEGY-THINKING.md)：从牌组计划到可验证规则。
- [工作区验收](docs/10-WORKSPACE-CHECK.md)：双构建和 acceptance report。
- [UCIS SDK](docs/15-UCIS-SDK-DEVELOPER-GUIDE.md)：current-window API。
- [支持卡牌清单](docs/19-SUPPORTED-CARDS.md)：如何查询本地 UID、交互状态和声明边界。
- [Python SDK 参考](docs/18-DEVELOPER-SDK-REFERENCE.md)：`StrategyWorkspace` API。
- [明确限制](docs/LIMITATIONS.md)：不能从当前证据推出什么。

更早的架构、Kaggle/CABT、迁移和牌组专项设计仍保留在 `docs/11`–`17`，但不是第一次开发的必读入口。

## 来源、证据与许可

vendored PtcgDAP SDK 的每个文件固定在 [`vendor/ptcgdap-sdk-manifest.json`](vendor/ptcgdap-sdk-manifest.json)；`doctor` 会拒绝缺失、篡改、额外文件和 symlink。开发包使用 test-fixture 或开发者账号签名，不等于平台批准。

项目使用 Apache License 2.0；vendored 组件来源见 [NOTICE](NOTICE)。
