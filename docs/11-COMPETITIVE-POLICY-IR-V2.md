# Competitive Policy IR v2 架构升级

## 1. 目标与不变边界

本升级解决 `.ptcgai` 能通过安全合同、但无法达到内置经典策略强度的问题。外部接口保持不变：

```text
agent(raw_observation) -> list[int]
```

返回值仍然只能引用当前不可变 `select.option`。v2 不引入 Python/GDScript 作者代码、引擎对象、
callback、ticket、网络或隐藏信息。Base Graph 继续拥有合法性、强制/终局保护、hard tier、veto、
cardinality、fallback、当前窗口重验和最终裁决。

v2 是新增的 data-only 策略表达档；v1 restricted adapter 保持原字节语义和兼容路径。

## 2. 根因

当前作者路径只迁移了 Base Graph v1.8 的安全骨架：单链 IR、七个简单 predicate 和一个排序提示。
它没有迁移权威架构中已经定义的 Goal State、Threat Clock、Macro Intent、资源核算、Future/
Uncertainty 评分和类型化交互。与此同时，Godot 作者 Host 明确关闭经典 DeckStrategy 偏好；当规则
不命中时，策略退化为当前窗口的最小 index。

因此现状不是“规则数量不足”，而是：

```text
内置经典策略：完整公开/引擎状态 -> 牌组计划 + 交互策略 + 数千行评分
作者数据策略：7 个字段匹配 -> 少量排序提示 -> minCount/最小 index fallback
```

## 3. 官方接口对齐

官方 CABT/Kaggle 接口已经可以表达所需能力，无需增加第二个 agent 方法：

- 精确数量：`list[int]` 的长度必须处于 `minCount..maxCount`；它不是固定为 `minCount`。
- 精确子集：列表中的每个 index 指向本次当前窗口的一个 option。
- 分配目标：引擎为下一次 source/target 选择发布新的 option 窗口，agent 重新观察后返回 index。
- 多阶段交互：一次成功选择立即使旧窗口失效；检索、分配、出战、撤退、伤害分配分别重绑定。
- 语义计划：只能跨窗口保留 Goal、稳定身份和资源债务，不能保留旧 index、旧分数或旧证明。

本地 Godot Host 必须复现这套调用语义，而不是把可变基数取满、目标分配或后续交互留给包外的
通用逻辑。

## 4. v2 数据模型

### 4.1 Public Strategic Frame

Host 从 allow-list 构造只读公开 frame。除 v1 字段外，v2 增加：

- 当前 turn/phase、双方剩余奖赏、牌库/手牌/备战数量；
- 己方公开 hand/active/bench/discard 的稳定本地 printing UID；
- 对手公开 active/bench/discard，不包含对手手牌或牌库顺序；
- 场上 Pokémon 的稳定 public serial、remaining HP、prize value、公开附着能量、最小攻击费用、
  attack-ready 和 energy debt；
- 当前 option 的 kind、card/source/target UID 与 serial、attack/ability index、projected damage/KO、
  target prize/readiness/debt、requires-interaction；
- 当前 assignment source、已完成分配数和本窗口 pending allocation；
- `minCount/maxCount`、当前 option fingerprint 和窗口 hash。

所有派生字段必须只依赖公开状态和固定卡表。未知字段、UID 或派生失败会使相应规则不匹配，
不能默认为有利事实。

### 4.2 Goal State 与 Resource Ledger

包声明稳定语义目标，而非未来动作：

```text
acquire -> deploy -> fund -> ready -> execute -> maintain/recover
```

每个 goal 可声明角色 UID、目标就绪数量、每个角色的能量需求、优先级和公开截止时钟。Host 每个
窗口重新计算：

- 已部署/已就绪数量；
- 每个 public serial 的能量缺口；
- goal 总资源债务；
- 当前与下一攻击手连续性；
- 双方还需几个可信攻击窗口结束比赛。

资源账本不会把未知抽牌或牌库顺序当作已有资源。

### 4.3 规则与整数评分

v2 规则由闭合、可移植的数据组成：

- `channel`: macro / tactical / interaction / future / uncertainty；
- `goal_id`、`goal_stage`、`horizon`、`confidence_milli`；
- 一组 AND 条件；OR 用多条规则表达；
- 常数分和受限整数 feature term；
- 可选的当前窗口 desired-count 规则。

只支持 allow-list fact、闭合比较运算和安全整数。跨语言使用明确的整数截断、总分上限和稳定
tie-break：总分降序、goal priority 降序、当前 option index 升序。无随机 tie-break、浮点排序或
字典遍历依赖。

### 4.4 精确基数

v1 保持 `minCount` fallback。v2 adapter 可以提出：

```text
ordered current indexes + desired_count
```

Base 执行顺序固定为：

```text
legality -> mandatory/terminal -> adapter ordering/count proposal
-> hard tier -> veto -> cardinality proof -> deterministic fallback -> emit
```

Base 只接受 `minCount <= desired_count <= maxCount`，且过滤后仍有足够合法候选的提案。forced
选择不能被 desired-count 改写。无有效提案时使用同窗审计 fallback。

例如庞克泵感公开资源债务为 3 时，策略可以返回三张恶能量对应的 index，而不是 `[]` 或固定取满 5。

### 4.5 逐次分配

card-assignment 不能由通用 target scorer 静默完成。Host 必须对每个待分配 source 生成一次当前
目标窗口，frame 包含：

- source 的公开 UID/serial；
- 每个 target 的 UID/serial、当前能量、attack-ready、energy debt、prize value；
- 本次 effect 已完成的 pending assignment counts。

策略每次只返回当前目标 index。选择后 Host 验证并应用到 pending transaction，再重观察下一分配
窗口。这样可以表达“1 张给当前长毛巨魔、2 张给备用诈唬魔”，但不能缓存三个未来 index。

### 4.6 奖赏时钟

Threat Clock 使用公开事实保守计算：双方剩余奖赏、当前可见目标的 prize value、攻击窗口是否打开、
候选出战者是否 ready 和下一攻击手债务。它是评分/goal deadline 输入，不是越过 Base hard tier 的
证明。

送出选择必须支持如下 metamorphic 翻转：

- 对手剩 2 奖、双奖长毛巨魔未就绪：一奖桥优先；
- 只改变长毛巨魔为立即反击就绪：允许长毛巨魔优先。

### 4.7 整回合候选路线

`turn_routes` 适合表达一条已选路线的当前资源债务，但静态优先级和 additive step bonus 不能比较多条完整路线。新增可选 `route_candidates`，每条声明稳定语义身份、公开 guard、typed resource budget、有序 steps 和六维 route value：

```text
attack_windows ASC
prize_progress DESC
continuity DESC
resource_cost ASC
response_risk ASC
uncertainty ASC
route_id ASC
```

Base 只在 guard、当前公开资源 gate 和至少一个当前 step 可执行时接受候选。所选 route 的第一步在同一 hard tier 内先于局部分数，但 terminal、mandatory、hard tier、veto、cardinality 和 deterministic fallback 仍有最终权限。每次 commit 后重新观察并重新裁决，不保存旧 index、旧 score 或旧 proof。

route value 只接受安全整数和非 option 的公开 fact terms，避免退化成另一套局部动作分数。Supporter、手贴、撤退和板凳位由当前公开 ledger/capacity 检查；能力、弃牌和检索数量当前只作为机会成本声明，不冒充未来合法性证明。

审计必须列出 considered route、稳定拒绝原因、六维值、selected route/step、当前 indexes 和 Base 是否实际应用 route authority。Python 与 Godot 用同一 CABT tree hash 固定 policy/audit hash。

## 5. 双运行时和包兼容

- Python 是 Forge/reference runtime；GDScript 是 Windows 本地执行 baseline。
- 同一 v2 document/frame 必须得到相同 ordered indexes、desired count、matched rules、整数分和
  public audit hash。
- `.ptcgai` 仍只含固定 JSON/CSV/text/weights；v2 不增加可执行成员。
- loader 同时接受 v1 与 v2，manifest 明确策略档；不兼容 host fail closed。
- v1 包不自动升级、不改变 hash、不改变 selection 行为。

## 6. 实施计划与退出门

### A. 合同 RED

先增加失败测试：

1. `min=0,max=5`、公开债务 3，期望选择 3 个；
2. option 重排后仍选择同三张语义卡；
3. 三次 assignment 窗口得到 1+2 分配，旧窗口重放被拒绝；
4. target 当前能量只改变 1，选择翻转；
5. 对手剩余奖赏/候选 prize/readiness 的桥接选择翻转；
6. mandatory、terminal、hard-tier、veto、unknown UID、隐藏字段和非法 desired count 全部 fail closed；
7. Python/GDScript golden vector 完全一致。

### B. Runtime v2

实现 public frame、goal/resource/threat 派生、整数规则 evaluator 和 Base cardinality v2；保留 v1 路径。

### C. Host 交互

让 setup、main、search、discard、send-out、retreat、effect target、assignment、damage allocation 和
optional-zero 都通过作者当前窗口；每次选择后重观察。Host 记录 policy call/success、fallback、invalid、
assignment 和 desired-count telemetry。

### D. Forge

升级 `new/build/validate/simulate/test/check`，提供 v2 scaffold、schema 校验、派生事实调试、逐候选分数、
count/assignment 场景和双构建证据。v1 demo 继续通过。

### E. 猛雷鼓验收

架构完成后才构建猛雷鼓 v2 包。最低验收：

- 精确能量账本、攻击阈值、Sada/Ogerpon 时机、下一攻击手连续性和类型化 interaction 有场景；
- 0 invalid / 0 policy error / 0 stale / 0 hidden leak / 0 engine rejection；
- 同一 paired seeds 下与升级前包有显著提升；
- 与经典猛雷鼓直接对战达到预先固定的非劣门，而不是用五包安全场景通过率代替胜率；
- 报告明确区分 public-window、Godot engine、official CABT parity 和 production authority。

## 7. 明确不做

- 不把经典 GDScript 当作作者包 fallback；
- 不把 raw `GameState` 或 Godot 对象交给策略；
- 不以显示名、翻译名或模糊卡名作为身份；
- 不允许 adapter 改写 forced、legality、hard tier 或 veto；
- 不因一份蓝图写得完整就声称运行时已经实现；
- 不以胜率豁免安全、窗口、包完整性或跨运行时一致性。

## 8. 2026-08-24 实现状态

精确数量、typed assignment、目标公开能量/ready/debt、奖赏时钟、typed interaction recipe、公开 turn ledger、bench capacity、hard `turn_routes`、soft `turn_bonus_contracts` 和 sealed compiled fast path 均已实现。固定双局从 236647 ms 降到 10958 ms；平均作者决策 819.485 ms→26.211 ms，P95 1121.872 ms→35.668 ms。

Round 41 的 fresh 100 为 42%；Round 43/44 虽修复代表轨迹，fresh 100 只有 41%/40%。因此不再优化猛雷鼓局部分数，owning layer 升级为整回合多候选路线裁决。

`route_candidates` 已在 Forge Python、Host Python 和 Godot strict/compiled runtime 实现。资源可用性翻转、奖赏时钟/response-risk 翻转、option reorder、mandatory、terminal、hard tier、veto 和跨语言 audit hash 已有 executable evidence；Godot competitive focused suite 为 17/17，250 次 compiled route decision P95 为 4.070 ms。当前合同 bundle 为 `1D7864C1828CEE1965E8C1A766155A716C2FC35C7AB2206BEDE4386F42793BD7`。

架构全量回归、SDK 来源锁、Round 41 专用 package owner 路径和 route fast-path P95 门均已关闭。五包通用 owner 套件仍有既有 setup-option 波动：连续隔离运行分别在沙奈朵和玛俐包失败，而 Round 41 competitive 专用路径稳定通过，因此不把该波动归因于本架构。按用户要求暂停猛雷鼓，不运行新胜率 benchmark，也不声称达到经典策略水准。完整设计、负证据、验收和回滚见 `docs/12-ARCHITECTURE-UPGRADE-DESIGN-AND-PLAN.md`。
