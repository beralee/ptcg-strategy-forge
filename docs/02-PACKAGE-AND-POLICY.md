# 策略包与裁决模型

## 数据包结构

`.ptcgai` 是闭合、确定性的 ZIP 数据包，只允许固定路径。构建器生成 `files.sha256.json` 和 test-fixture `signature.json`；作者不管理私钥。

运行身份是：

```text
package_id + package_version + archive_sha256
```

改变任何可分发行为都应提升版本。显示名不能参与卡牌映射或策略匹配。

新开发者不直接拼装这些路径；`forge workspace create/status/check/build` 和公开 `StrategyWorkspace` SDK 负责工作区生命周期。底层包结构仍是验证与运行合同，不因为开发者门面简化而放宽。

`.ptcgai v2` 有两种模式：

| 模式 | 包内容 |
|---|---|
| `rules_only` | deck + Competitive IR/adapter/config |
| `rules_with_model` | 同一完整规则 fallback + `model/model_manifest.json` + `model/actor.ort` |

不支持 `model_only`。模型不可用时，包必须仍能在同一窗口沿规则/Base 路径裁决。

## 身份域

当前 demo 使用 Windows 本地域：

```text
godot_local_card_uid_v1 = set_code + "_" + card_index
```

例如 `CSV10C_146`。它不是官方 CABT Card ID、卡名、翻译名、图片名或 Godot object ID。`deck.csv` 必须正好 60 张，并与 `deck_manifest.json` 的源 hash 一致。

## 受限策略 IR

推荐执行链：

```text
legality_guard
→ mandatory_terminal_guard
→ macro_proposal
→ hard_tier_filter
→ base_veto
→ deterministic_fallback
→ emit_decision
```

Base owner 负责合法性、强制/终局、hard tier、veto、fallback 和输出。adapter 只能提出公开目标、macro 或同层 tie-break。

## adapter 规则

规则只能匹配当前公开上下文，例如：

```json
{
  "rule_id": "forge.morgrem.evolve",
  "operator": "macro_proposal",
  "reason_code": "public_macro_proposal",
  "goal_stage": "deploy",
  "priority": 0,
  "predicate": {
    "select_type_raw": null,
    "select_context_raw": null,
    "option_type_raw": 3,
    "option_card_id": "CSV10C_146",
    "option_player_index": null,
    "acting_hand_card_id": "CSV10C_147",
    "acting_active_card_id": null
  }
}
```

`null` 表示不参与匹配。priority 越小越靠前；相同 priority 按规则顺序和当前 option index 稳定排序。规则命中并不保证被选择，Base 可以阻止。

## 当前窗口约束

- 只返回当前 option indexes；
- selection 接受后旧窗口立即失效；
- 持久计划只能保存语义目标或稳定身份，不能保存旧 index、旧分数或旧约束；
- 未知字段/枚举必须 fail closed 或进入已审计 fallback；
- adapter 无 engine、ticket、callback 或网络权限。

## UCIS 标准窗口

卡牌效果现在统一走：

```text
CardEffectSpec → InteractionProgram → fresh SelectionWindow
→ agent(...) 返回当前 indexes → Host 验证/提交 → invalidate/reobserve
```

作者不再为卡牌自定义 prompt、Context 数字、option shape 或复合返回命令。当前 generation 固定 49 个 Context、17 个 Option shape 和 16 个领域原语；无法编译的能力显式 unsupported，不会回退到某张卡的私有协议。

使用命名化开发者视图：

```powershell
.\forge.ps1 ucis catalog
.\forge.ps1 ucis inspect --scenario scenarios\01-positive.json
```

当前 UCIS 开发者 helper 提供 `choose_exact`、`choose_up_to`、`rebind`、`choose_number`、`choose_boolean` 和 `first_legal`。完整示例见 [UCIS SDK 开发者指南](15-UCIS-SDK-DEVELOPER-GUIDE.md)。这些 helper 只产生 index proposal；不会改变 Base/Host authority。

## 当前统一规则/模型包

当前只分发 data-only `.ptcgai`，v2 提供 `rules_only` 和 `rules_with_model` 两种 mode；不允许 `model_only`。模型 mode 必须同时携带 Competitive IR fallback 与受审的 `model/actor.ort`，Host 先完成 legality、mandatory/terminal、规则路线、hard tier 和 veto，再允许模型在当前获准候选中输出 `int32 option_scores` 与 `desired_count`。模型异常只在同一窗口降级到规则/Base，不能持有旧窗口 authority。

`.ptcgai v1` loader 与既有 fixture 保持 exact bytes/hash/行为兼容；v1 可选 `weights.bin` 不被重新解释为 v2 模型。v2 的 `model/model_manifest.json`、公开定长张量、Python/Windows 原生 ORT runtime 与 operator profile 已实现；macOS arm64/x86_64 有构建配置但尚无实机对局证据。完整合同与平台状态见[统一 `.ptcgai` 规则与模型策略设计](17-UNIFIED-PTCGAI-RULE-AND-MODEL-DESIGN.md)。
