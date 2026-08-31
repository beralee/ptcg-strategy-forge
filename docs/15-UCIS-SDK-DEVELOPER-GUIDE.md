# UCIS SDK 开发者指南

UCIS SDK 把 49 种选择上下文、17 种稀疏 option、精确数量和窗口失效规则封装成一组小而严格的 Python API。开发者仍然只实现：

```text
agent(raw_observation) -> list[int]
```

SDK 不执行引擎动作，也不持有 ticket。它只解析当前不可变 `select.option`，帮助策略按语义找到本窗口的索引，并在输入形状未知时 fail closed。

## 五分钟确认环境

```powershell
.\setup.ps1
.\forge.ps1 doctor
.\forge.ps1 workspace status demo\marnie-forge
.\forge.ps1 workspace inspect demo\marnie-forge
.\forge.ps1 ucis walkthrough
```

每个新工作区还会得到 `SUPPORTED-CARDS.json`，它是 `data/developer/supported-cards-v1.json` 的 exact copy。开发者可以先按 `card_uid` 检查目标卡是否 `usable`，再用本页 API 处理它产生的 current-window；详情见[支持卡牌清单](19-SUPPORTED-CARDS.md)。

日常开发用 `workspace inspect`；需要检查整个 UCIS generation 或运行教学向量时再使用三个底层 `ucis` 子命令：

- `catalog`：当前 generation、16 个原语、729 个可用 effect、unsupported 清单和资格 hash；
- `walkthrough`：运行精确取 3、option 重排、重复分配、能量债务、奖赏时钟和未知 shape 拒绝；
- `inspect`：把一个场景显示为命名化 context/option 和公开事实，不回显 `raw_observation`、Search token 或隐藏数据。

## 统一 `.ptcgai` 如何使用 SDK

| 模式 | SDK 使用方式 | 状态/运行位置 |
|---|---|---|
| `rules_only` | 用 `forge ucis inspect/catalog/walkthrough` 理解并测试窗口，再把规则写入 adapter | 当前已实现；Godot Host/Base Graph |
| `rules_with_model` | 同一 UCIS/public frame 生成固定整数张量、presence/mask；冻结 ORT Actor 只输出当前候选分数与精确数量 | Forge/reference 与 Windows Godot ORT/Host/Base 已实现；macOS 实机门待完成 |

下一代只有 `.ptcgai` 制品。规则与模型共享 UCIS generation、命名、稀疏 option shape 和 current-window 不变量；模型路径不会扩大规则/Base authority。历史 `.ptcgbot` Python SDK 已退出目标路径，迁移说明见 [旧 `.ptcgbot` 退出与迁移](14-KAGGLE-STYLE-PTCGBOT-QUICKSTART.md)。

## 从一个合法窗口开始

当前 Forge helper 的等价可执行窗口示例是：

```python
from pathlib import Path

from ptcg_strategy_forge.ucis_runtime import SelectionWindow, semantic_key

_DECK = [int(value) for value in Path("deck.csv").read_text(encoding="ascii").splitlines()]
_SEARCH_TARGET = semantic_key("CARD", area=2, index=20, playerIndex=0)


def agent(raw_observation):
    select = raw_observation.get("select")
    if select is None and raw_observation.get("current") is None:
        return list(_DECK)

    window = SelectionWindow.parse(raw_observation)
    if window.context_name == "TO_HAND":
        return window.rebind([_SEARCH_TARGET])
    return window.first_legal()
```

初始牌组 callback 返回的是 60 个 Card ID；只有其后的 selection callback 返回 current option indexes。这两个返回域不能混用。

## 常用 API

### 命名构造测试 option

不用记忆 `OptionType.CARD == 3` 或稀疏字段集合：

```python
from ptcg_strategy_forge.ucis_runtime import option

candidate = option("CARD", area=2, index=20, playerIndex=0)
number = option("NUMBER", number=3)
yes = option("YES")
```

缺字段、多字段、非整数或未知 option name 都会给出稳定 `UcisRuntimeError`。

### 精确数量

对 `0..5` 检索准确取 3 张：

```python
indexes = window.choose_exact(
    3,
    lambda candidate: candidate.option_type_name == "CARD"
    and candidate.field("index") in {10, 30, 50},
)
```

`choose_exact` 保留引擎给出的 option 顺序，检查数量上限，并拒绝候选不足。`choose_up_to(limit, predicate)` 用于确实允许少取的窗口；它仍必须满足本窗口 `minCount`。

### 语义重绑定和重复分配

跨 callback 只保存语义目标，不保存旧 index：

```python
target = semantic_key("CARD", area=3, index=1, playerIndex=0)


def choose_assignment(raw_observation):
    # 每次 callback 都重新 parse；不要缓存旧 SelectionWindow。
    fresh_window = SelectionWindow.parse(raw_observation)
    return fresh_window.rebind([target])
```

如果下一窗口 option 重排，`rebind` 会返回新的 index；目标缺失时返回 `ucis_runtime_semantic_rebind_missing`，不会悄悄选择别的对象。`audit_fingerprint` 只用于当前窗口审计，不是跨窗口身份。

### NUMBER、YES/NO 和 fallback

```python
return window.choose_number(3)
return window.choose_boolean(True)
return window.first_legal()
```

`first_legal()` 是确定性的最小数量 fallback；它不越过当前窗口，也不拥有引擎合法性。`.ptcgai` 的最终 fallback 仍由 Base Graph 管理。

### 公开奖赏时钟和能量债务

```python
from ptcg_strategy_forge.ucis_runtime import PublicBattleFacts

facts = PublicBattleFacts.parse(raw_observation)
debt = facts.acting_active_energy_debt(required_units=2)
our_clock = facts.acting_attack_windows_to_win(prizes_per_attack=2)
their_clock = facts.opponent_attack_windows_to_win(prizes_per_attack=1)
```

这些值只使用公开 `current`：奖赏剩余数量、场上能量单位、bench 空位、牌库和手牌数量。SDK 不推测对手手牌、牌序、盖奖内容、攻击费用或未来合法动作；`required_units` 和 `prizes_per_attack` 必须来自作者已经审核的公开策略语义。

## 推荐测试矩阵

每个关键策略至少提交：

1. 正向语义目标；
2. 候选缺失；
3. 精确数量上下界；
4. 相同语义的 option 重排；
5. 信息动作后新窗口重新解析；
6. 只改变奖赏、能量或 HP 一个事实的 metamorphic flip；
7. unknown context/option/额外字段 fail closed；
8. 隐藏字段和私有 sentinel 拒绝；
9. deterministic fallback；
10. 两次构建 exact bytes 相同。

可直接复制 [`demo/marnie-forge/sdk_walkthrough.py`](../demo/marnie-forge/sdk_walkthrough.py)，再运行：

```powershell
.\forge.ps1 ucis walkthrough
.\forge.ps1 demo --output "$env:TEMP\ptcg-forge-demo"
```

模型工作区优先使用以下命令：

```powershell
.\forge.ps1 workspace model inspect work\my-strategy
.\forge.ps1 workspace model tensorize work\my-strategy --scenario scenarios\01-positive.json
.\forge.ps1 workspace model import work\my-strategy --source exports\actor.onnx --training-method bc_rl --source-run-id run-001
.\forge.ps1 workspace model conformance work\my-strategy
.\forge.ps1 workspace build work\my-strategy
```

工作区 `model import` 会先在临时位置验证，再替换模板 Actor；底层 `model import` 保持非覆盖语义，主要用于独立 artifact 诊断。tensor SDK 复用 current-window 的 parse、firewall、presence、semantic key、fresh rebind 和 public facts 语义，并由 `competitive_public_actor_i32_v1` 固定输入名称、`int32` dtype、shape、padding/mask 和 hash。它不会把 Python runtime 复制进作者包。完整合同见[统一 `.ptcgai` 规则与模型策略设计](17-UNIFIED-PTCGAI-RULE-AND-MODEL-DESIGN.md)。

完整工作区 Python 门面见 [Python 开发者 SDK 参考](18-DEVELOPER-SDK-REFERENCE.md)。

## 稳定错误和排查顺序

| 错误 | 含义 | 先检查 |
|---|---|---|
| `ucis_runtime_select_shape_invalid` | SelectData 缺字段或混入未知字段 | generation/fixture 是否漂移 |
| `ucis_runtime_context_type_mismatch` | context 与 select type 不匹配 | 不要把 YES/NO header 配 CARD options |
| `ucis_runtime_option_shape_invalid` | option 稀疏字段不精确 | 用 `option("NAME", ...)` 构造测试数据 |
| `ucis_runtime_cardinality_invalid` | min/max 与候选数不合法 | 当前窗口数量合同 |
| `ucis_runtime_not_enough_matches` | 精确选择目标不足 | predicate、公开身份和路线前置条件 |
| `ucis_runtime_semantic_rebind_missing` | 新窗口没有原语义目标 | 重新规划或显式 fallback，不复用旧 index |
| `ucis_runtime_public_state_invalid` | 奖赏/能量事实所需公开 state 不完整 | callback lifecycle 与 A1 scope |

先运行 `doctor` 和 `ucis catalog` 排除 SDK/合同漂移，再用 `ucis inspect` 看命名化窗口，最后检查策略 predicate。不要先改 priority 掩盖身份或窗口错误。

## 能力与声明边界

UCIS generation 1 覆盖 49/49 Context、17/17 Option shape、16 个交互原语和 729 个声明可用 effect；1 个动态未登记能力显式 unsupported。九类代表性双引擎证据只证明 current-window input、ordered semantic options 和双方接受的 indexes。

SDK 不证明提交后的 state、damage、KO、RNG、terminal、完整规则 A3、Search、production sandbox、Android/device acceptance 或策略强度。统一 v2 与 Windows ORT Actor 有独立可执行证据，但当前 SDK 仍不证明 macOS 实机能力。完整边界见[明确限制](LIMITATIONS.md)。
