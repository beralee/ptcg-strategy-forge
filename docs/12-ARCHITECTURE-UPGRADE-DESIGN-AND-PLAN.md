# 作者策略架构升级：整回合路线裁决设计与计划

## 结论

猛雷鼓优化已经冻结在 Round 41。Round 42–44 都能修复某条具体录像，但新的 100 局结果分别没有超过 Round 41；这证明剩余问题不是某张牌的分数，而是当前策略只能给眼前动作叠加分数，不能在消耗手贴、Supporter、检索、板凳位或弃牌前比较完整路线。

本阶段新增向后兼容的 `route_candidates`：作者包声明有限、可审计的整回合候选路线，Base 使用公开事实、资源预算、攻击窗口、奖赏推进、续航、资源成本、对手响应风险和不确定性做词典序裁决。裁决后只授权所选路线在当前不可变 option window 中的第一步；成功提交后旧索引立即失效，Host 重新观察并重新裁决。

外部接口始终不变：

```text
agent(raw_observation) -> list[int]
```

没有新增 agent 方法，没有把引擎对象、隐藏信息或执行权交给策略包。

## 为什么单点修复不能收敛

Round 41 是当前正式回滚基线：100 局 42–58，42%。

- Round 42 提高先找猛雷鼓的偏好，只修复固定问题种子，未形成稳定候选。
- Round 43 让巢穴球压过大地之器，两个 20 局样本合计 50%，但新 100 局只有 41%。
- Round 44 把“先建立猛雷鼓”扩展成硬路线，代表性双局由 0–2 改为 1–1，但新 100 局只有 40%。
- 三轮均为 0 policy error、0 invalid output、0 engine rejection、0 fallback；失败不是接口失效，而是路线质量失效。

当前 `turn_routes` 按静态优先级选第一条可执行路线，然后把 step bonus 与所有局部规则相加。它无法回答：

1. 先下碧草面具厄诡椪再手贴，与先找猛雷鼓再手贴，哪条路线更早形成有效攻击？
2. 一次不可逆的手贴、Supporter、检索、弃牌或板凳位，是否破坏下一攻击手？
3. 当前得奖后，对手公开可见的反击或 gust 路线会不会直接结束比赛？
4. 两条路线都合法时，哪条路线整体更好，而不是哪一个动作收到更多局部“投票”？

## 新数据合同

`route_candidates` 是 Competitive Policy IR v2 的可选字段。旧包不包含该字段时，继续使用原 `turn_routes`、typed recipe、soft bonus 和局部规则路径。

每条候选包含：

- 稳定语义身份：`route_id`、goal、owner、bridge、pivot；
- 公开 guard：只能读取 allow-list 事实，不能读取 option 以外的隐藏信息；
- `resource_budget`：Supporter、手贴、撤退、板凳位，以及能力、弃牌和检索的声明成本；
- `value`：`attack_windows`、`prize_progress`、`continuity`、`resource_cost`、`response_risk`、`uncertainty`；
- 有序 typed steps：每个 step 只描述当前窗口的语义匹配、精确数量、terminal 和 checkpoint。

Supporter、手贴、撤退和板凳位有当前公开可用性 gate。能力次数、弃牌数和检索数当前是机会成本声明，不冒充引擎已经证明其未来可用；缺少公开证明的未来步骤仍属于估值，不属于合法性证明。

每个 value component 是安全整数 `base + bounded public terms`。route value 不接受 `option.*` 或 `goal.option.*` term，避免退化成另一套局部动作分数。

## Base 裁决顺序

候选路线只在 guard、资源 gate 和至少一个当前 step 可执行时进入比较。比较顺序固定为：

```text
attack_windows ASC
prize_progress DESC
continuity DESC
resource_cost ASC
response_risk ASC
uncertainty ASC
route_id ASC
```

所选路线的当前 indexes 被排在局部 scorecard 前，但仍必须经过：

```text
terminal -> mandatory -> hard tier -> veto -> cardinality -> deterministic fallback
```

因此 route candidate 不能越过 Base。若所选 step 被 hard tier 或 veto 排除，Base 选择合法 frontier 中的其他动作，并在审计中记录 `route_authority_applied=false`。

## 当前窗口与 checkpoint

route candidate 不保存旧 option index、旧分数或旧证明。一次选择后：

1. Host 提交当前合法 `list[int]`；
2. 旧窗口立即失效；
3. draw/search/reveal/random/assignment 等 checkpoint 触发重新观察；
4. runtime 用新的公开 frame 重新计算所有候选；
5. 只允许保留作者文档中的稳定身份、goal 和资源债务语义。

这与官方 Kaggle/CABT 的单一 agent callback 完全一致；精确数量仍由返回列表长度表达。

## 可审计证据

每次决策的 `turn_contract.route_candidate_adjudication` 记录：

- 所有被考虑的 route；
- guard、资源不足或无当前 step 的稳定拒绝原因；
- 每条可接受 route 的六维整数值；
- 被选中的 route/step 和当前 indexes；
- Base 最终是否应用了 route authority。

Python 与 Godot 现在都使用 `cabt_tree_hash_v1/public_observation` 计算 policy/audit hash。新 conformance vector 同时锁定 `selected_indexes` 和 `audit_hash`，不再只比较动作结果。

## 已实现范围

- Forge/reference Python runtime：schema、验证、route adjudicator、资源 gate、词典序裁决、审计和 Base 交接；
- PtcgDAP Python runtime：与 Forge 源文件字节一致；
- PtcgDAP Godot runtime：strict/compiled 两条路径一致；
- 合同 schema/profile/vectors/bundle 已刷新；
- 两类跨牌组合成证据：资源可用性翻转、奖赏时钟/对手响应风险翻转；
- option reorder、mandatory、terminal、hard tier、veto 和 current-window-only 约束已覆盖；
- Godot competitive focused suite 17/17 通过；250 次 compiled route decision 的 P95 为 4.070 ms，低于 50 ms 门。

当前合同哈希：

```text
schema  C3835C23C62C13F0191A281302F408288F982FE70F0387B0A9D466538CF81879
profile 737CF28BF83D9CF270266B163DDFCDE03B6645D0BDE7012B54906BEE6CE723FF
vectors AEA98005727EEF0016687AB18A26E72608EDEE10697373B2E26C17ACBCF799FA
bundle  1D7864C1828CEE1965E8C1A766155A716C2FC35C7AB2206BEDE4386F42793BD7
```

## 验收计划

架构验收与策略强度验收继续分开。

### 架构验收

1. 完整 Forge/Host Python、Godot、package loader 和 SDK provenance 测试；
2. 新旧 Competitive v2 包都能加载，Round 41 回滚包保持可发现与可执行；
3. strict/compiled、Python/Godot 的选择与审计哈希一致；
4. route candidates 的 positive、missing prerequisite、reorder、mandatory、terminal、tier、veto、unknown UID、hidden field、checkpoint 和 metamorphic flip 全部通过；
5. compiled route adjudicator 保持开发目标 P95 < 50 ms；当前 focused witness 为 4.070 ms；
6. 不启动胜率 benchmark，直到上述门全部关闭。

### 强度验收

架构门关闭后，先为至少两种不同牌组/场景族编译 route candidates，再回到猛雷鼓：

1. 保留 Round 41 为旧架构基线；
2. 新架构候选先跑两个独立小样本；
3. 两个样本都达到预注册 47% 后，才运行 fresh 100；
4. 正式结果必须绑定同一 exact package hash，并保持 0 error/invalid/rejection/fallback；
5. 未达到门则保留负证据，不再用局部大分数追逐单个 seed。

## 权限、已知限制与回滚

本阶段证明 data-only route contract、Forge public-window simulation 和本地 Godot runtime 行为；不证明 official CABT engine parity、production approval、Android/A5 或与经典策略非劣。

截至当前验收，Forge full regression 30/30、Host Python competitive/contract 21/21、Godot competitive 17/17、SDK snapshot/doctor、Round 41 competitive package 专用 load/owner/setup 路径均通过。五包通用 owner 套件存在既有 setup-option 波动，隔离复验的失败对象从沙奈朵变为玛俐；Round 41 专用 competitive owner 测试两次均通过。该波动记录为已知外部测试问题，不用它伪造全套 5/5，也不阻断 route contract 本身的结论。

当前游戏回滚包仍为：

```text
strategy_id beralee.raging-bolt-ogerpon.18.0.competitive-v2-round41
archive_sha256 5DEEC95080A537B9BF10B4744050A2C53690486B057E556FBC11E3F55BEDA57A
```

关闭 `route_candidates` 只影响新比赛；旧包继续走兼容路径，不热换进行中 owner，不删除用户策略，也不静默回落到经典 GDScript。
