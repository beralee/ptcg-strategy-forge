# 框架使用

以下路径相对实际 Forge 根目录。先核对当前 `--help` 和源码；框架维护入口为 `src/ptcg_strategy_forge/strategy_base.py`，运行裁决仍由锁定的 `competitive_policy_v2.py` 拥有。

## 工作区入口

```powershell
.\.venv\Scripts\python.exe tools/strategy_base.py init --workspace work/my-strategy
.\.venv\Scripts\python.exe tools/strategy_base.py audit --workspace work/my-strategy --report work/my-strategy/base/audit-r1.json
.\.venv\Scripts\python.exe tools/strategy_base.py compile --workspace work/my-strategy --output work/my-strategy/base/candidate-r1
```

`init` 不覆盖已有目录，保存 `base/adapter.json`、`base/plan.json` 和牌表/SDK 摘要锁。它不替换已有策略。未解决的考虑事项使 `audit` 退出 2、`compile` 拒绝；明确 `gap` 可编译，但始终保留缺口。输出目录不可覆盖。

编译产物是候选 `adapter.json` 和编译报告，还不是可安装包。将 adapter 应用到本轮候选工作区的 `package/policy/adapter.json`，运行聚焦场景及 `forge workspace check`。编译输入使用冻结的 `base/adapter.json`，因此重复编译不会把新路线不断叠加到自己身上。

基础规则也需修改时，在版本化候选中编辑 `base/adapter.json`，审查 diff 后用公开 `document_sha256()` 更新计划的 `base_adapter_sha256`，使所有后续验收失效并重跑。牌表或 SDK 改变时，在新候选工作区重新初始化并迁移已审核计划，不能只改来源锁逃过漂移。

## 可执行数据与规划记录

`plan.json` 的 `lines` 是作者期路线集合。一条 line 含：

- `line_id` 和现存的 `goal_id/owner_goal_id/bridge_goal_id/pivot_goal_id`；
- `when`：整条路线共用的公开谓词；
- `phases`：每阶段有 `phase_id/when/budget/value/steps`。

每个阶段编译成一个原生 `route_candidate`，ID 为 `<line_id>.<phase_id>`；总数受当前 SDK 的 32 条限制。步骤使用同一原生 `route_step`，`checkpoint=true`。原生 step 列表是本阶段按顺序尝试的**当前可执行提案**，不是将来必定按列表执行的命令队列。

不要把阶段位置当作执行状态。比如“贴能 → 撤退 → 选攻击手 → 攻击”：

| 当前阶段 | 必须重新证明 | 本窗口起的预算 |
|---|---|---|
| 支付 | 前排确实卡住、同一后排攻击手精确付费、贴能能支付前排撤退 | 手贴 1、撤退 1；弃能成本单列 |
| 撤退 | 当前真的存在合法撤退选项、目标仍可用 | 手贴 0、撤退 1 |
| 选攻击手 | 当前换位窗口、正确所属方与实体、目标仍有精确费用 | 已付额度都为 0 |
| 攻击 | 当前攻击选项、伤害或其他效果具有经过证明的价值 | 已付额度都为 0 |

目标消失、能量变化、抽牌未得到预期组件时，后缀退出或改选；不能靠上一窗口“计划过”继续执行。路线排序跨阶段可能改变，这正是重规划。

## 作者 API


`goal.option.matches_target` 仅说明身份匹配，不能证明已付费。换位/出战优先使用 `goal.option.pivots_ready_target` 检查实际目标实体的完整 requirement；不把“后排存在付费同名角色”拼接到另一个目标上。特殊能量仍要额外检查其印刷条件，不能把 requirement 的 UID 数量检查误认为通用能量语义求解。

```python
from ptcg_strategy_forge import StrategyBase, ResourceBudget, RouteValue
from ptcg_strategy_forge.strategy_base import route_step, route_candidate

plan = StrategyBase.draft(adapter)
# 审核考虑事项并填入 lines；predicate 使用当前 SDK 的 fact/op/value/card_uid。
result = StrategyBase.compile(adapter, plan, allowed_card_uids=exact_deck_uids)
candidate_adapter = result.adapter
```

`ResourceBudget`：`supporter_uses/manual_attachments/retreats/bench_slots` 由运行时检查额度；`ability_uses/discard_cards/search_cards` 只是声明成本，必须另有公开条件证明资源。`RouteValue` 顺序为攻击窗口升序、奖赏推进降序、连续性降序、成本/响应风险/不确定性升序，最后 route ID 确定性打破平局。

事实和 UID 由真实 SDK 编译器验证，未知字段/UID、越界数量、重复路线、关闭检查点和旧 adapter 摘要被拒绝。合法 schema 仍不能证明作者 guard 的卡牌语义正确；费用、卡效和分支完整性由聚焦场景与实际引擎补证。

`implemented` 的 `evidence` 只能引用真实存在的 `rule:ID`、`count:ID`、`goal:ID`、`route:ID`、`turn:ID`、`interaction:ID` 或 `damage:ID`。这些是实现定位；不要把“引用存在”解释成验收成功。

## 何时升级框架

把三层分开：牌组 UID/阈值/路线偏好属于策略；可在多个牌组重用的作者编译、覆盖和反思能力属于 Forge Base 框架；缺少公开事实或运行语义属于 SDK/Host。

本框架没有增加任意条件图搜索、对手响应求解器、特殊能量通用求解器或全局最优指示物分配。任务需要这些能力时记录明确接口缺口，按最早责任层增加 RED 证据；维护 vendored SDK 时遵守受审来源和机械刷新，不单改快照或手改 hash。

通用分阶段路线、当前窗口重绑定与资源门的可执行示例见 `tests/test_strategy_base.py`；它们是公开窗口测试夹具，不是参赛策略。
