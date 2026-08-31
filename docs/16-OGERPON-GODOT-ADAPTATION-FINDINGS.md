# 厄诡椪／岩殿居蟹 v5.23a：Godot 18.0 迁移、Block 修复与三轮优化

日期：2026-08-25
状态：Windows development Host 端到端完成；最终 `.ptcgai` 可在本地对战设置中选择并运行
权限：development-only；不是 official CABT parity、production approval、Android/A5 或统计强度保证

## 1. 来源与边界

本次只读迁移源为：

`D:\ai\code\ptcgtrain-main\deliverables\ptcgabc_ogerpon_v523a_handoff_20260812`

| 来源制品 | 固定身份 |
|---|---|
| champion `main.py` | `d6580b1a00f7609dee68053acb67f8de3d68bea440a90774677fa25b74313207` |
| `deck.csv` | `66b339a7ef8178dc0095c4369b685acb33a2d6e4fc16b452bb6fb4a5ff048b37` |
| model | `d0e72d029d7ab9fd90537622d9d2a5139b7822bd23f049dede9d594b6cc677d3` |
| Kaggle archive | `e7eea5a7e6f753b62757151f5647e85a9ed99b83f196c98c6a2ca45d01a465cc` |
| submission | `55435118`，33–22（60.0%） |

Kaggle 成绩只用于锁定迁移来源。旧 Python Graph、模型和可执行代码没有进入 `.ptcgai`；最终包仍是数据包，唯一动作边界是：

```text
agent(raw_observation) -> list[int]
```

返回值只引用当前不可变 `select.option`。每次提交后必须重观察、重建公开事实和重绑定语义目标；Base Graph 继续拥有合法性、强制/终局保护、hard tier、veto、cardinality、deterministic fallback 和最终裁决。

## 2. Godot 18.0 牌表适配

Godot 本地 deck ID 为 `800052301`，共 60 张、19 个 printing：

```text
18 CSVE1C_GRA   4 CSV8C_028    2 CSV10C_009   2 CSV10C_010
 1 CSV10C_052   4 CSV8C_182    2 CSVH1aC_008  1 CSVH1C_035
 3 CSV1C_108    3 CSV2C_113    4 CSV9C_181    2 CSV10C_189
 1 CS6aC_120    1 CSV7C_187    2 CSVH1aC_023  4 CSV10C_206
 3 CSV3C_123    1 CSV9C_206    2 CSV10C_219
```

适配使用当前 Godot 卡表可用的奇树等 printing，不要求私有 UID 与官方 Card ID 同域。包内保存每张 Godot 卡源的 raw SHA-256 与 canonical JSON SHA-256；牌组映射、60 卡数量和 19 printing 均由 Forge 与 Godot exact gate 复验。

## 3. 交付身份

| 轮次 | 版本 | archive SHA-256 | strict 场景 | 主要用途 |
|---|---|---|---:|---|
| R0 | 0.1.0 | `6BA5D78C7790212692B821354623FE10A36EF0A6C222BA2C4D61B09261CC310E` | 10/10 | 初始迁移与 20×5 基线 |
| R1 | 0.2.0 | `A2E61810BD2B91915EFFDDB73EBE0B27DD64BEDF3BE0125F4B1172C00A53A3E1` | 13/13 | 修正石居蟹起手进化路线 |
| R2 | 0.3.0 | `A759D05AFAC27AAA41CC8C5D9EC2740AA89D5D5BA7DD69A0769FC5722A2CC468` | 18/18 | 精确能量转移 source→target 路线 |
| R3 | 0.4.0 | `A2C84D69C4F5A69D78E0821B9CE4E404953FF7138EE450C36DA651CE3E8E9423` | 21/21 | 低牌库 Teal Dance 储备门 |
| Final | 1.0.0 | `9531F683F2AB9E0138D8054D3E3813D7378F9F6E5F7F8CAF9C428C3FCAFF8D9F` | 21/21 | 本地游戏与最终 20×5 验收 |

最终包：

- Forge：`work/ogerpon-crustle-v523a-final/build/ogerpon-crustle-v523a-1.0.0.ptcgai`
- PtcgDAP 内置：`data/ptcgdap/author_strategy_packages/ogerpon-crustle-v523a-1.0.0.ptcgai`
- package ID：`dev.beralee.v18.ogerpon-crustle-v523a`
- runtime：`reviewed_competitive_policy_v2`
- adapter：65 条 score rule、6 条 count rule、长期目标、interaction recipe 与 turn route
- Restricted IR：当 adapter rule 超过 Strategic Trace v2 的 64 macro-ID 上限时，用固定 `competitive.score-rules` 宏引用完整 adapter，而不是截断或跳过预检

Windows development gate 同时固定 R0–R3 作为可重复证据，但本地玩家应选择 `1.0.0`。focused UI 回归证明最终 exact ID/version/hash 在 `BattleSetup` 可见、可选择且 `_author_strategy_start_allowed()` 为真。

## 4. 三轮录像驱动优化

每轮都遵循：固定旧包 → 同种子对照 → 查看公开 trace/replay → 增加 RED/reorder/metamorphic 场景 → 最小策略改动 → GREEN → 构建新版本。没有在局中热换策略，也没有把旧 option index 带入新窗口。

### R1：起手 Ascension 不再错误依赖厄诡椪

录像显示石居蟹具备可用进化攻击时，旧规则仍要求场上已有厄诡椪，导致启动路线被无关前置条件压制。R1 移除该错误依赖，并增加无厄诡椪与 option reorder 场景。

同 seed `62300` 的 4×5 开发集：R0 `12/20`，R1 `13/20`。提升发生在猛雷鼓对局（2/4→3/4），其余四个对局未下降。

### R2：能量转移按公开资源债务精确路由

公开 trace 显示策略需要区分“发起 effect 的 Trainer”和“当前附着能量的拥有者”，并在 source/target 两个 fresh 窗口分别决策。R2 实现：

- 只有岩殿居蟹存在能量债务、场上有厄诡椪、场上草能量达到安全阈值时才出能量转移；
- source 选择已经攻击就绪且过量充能的厄诡椪，避免抽走未满足费用的岩殿居蟹；
- target 选择仍有债务的岩殿居蟹；
- source 与 target 都有 semantic reorder 测试。

同 seed `67300` 的 4×5 开发集：R1 与 R2 都是 `14/20`；R2 policy calls `825`，低于 R1 的 `903`。精确 trace `ogerpon_r2_dragapult_seed54300_energy_switch_trace_fixed.json` 证明 source wire 为 `2/28/5`、target wire 为 `1/22/3`，且实际选择过量充能厄诡椪→岩殿居蟹。

### R3：低牌库停止 Teal Dance

多龙 seed `69300` 的失败录像在牌库仅 3 张时仍使用 Teal Dance，增加 deck-out 风险。R3 将能力门设为 `deck_count > 4`，并增加低牌库、reorder 和 5 张边界场景。

同 seed `67300` 的 4×5 开发集仍为 `14/20`，policy calls 从 R2 `825` 降到 R3 `824`。固定失败种子中低牌库能力已不再被选择，但结果只从 step 160 的 deck-out 延迟到 step 161，未翻胜；该改动因此只声明“关闭错误动作”，不声明“单局修复即提升胜率”。

## 5. 最终 20×5 对战结果

最终矩阵使用全新 seed base `72300`，每个 matchup 10 个成对 seed、候选换座，共 20 局；seat 0 先手，`max_steps=700`，Rule-only 对手。100 局全部终局且有 winner。

| Rule 18.0 对手 | deck ID | 胜负 | 胜率 | candidate seat 0 / 1 | Wilson 95% |
|---|---:|---:|---:|---:|---:|
| 玛俐长毛巨魔 | 800018501 | 17–3 | 85% | 9/10 · 8/10 | 64.0%–94.8% |
| 无碟沙奈朵 | 800017097 | 16–4 | 80% | 6/10 · 10/10 | 58.4%–91.9% |
| 多龙巴鲁托 | 800018499 | 12–8 | 60% | 5/10 · 7/10 | 38.7%–78.1% |
| 猛雷鼓厄诡椪 | 800018509 | 11–9 | 55% | 5/10 · 6/10 | 34.2%–74.2% |
| N 的索罗亚克 | 800018502 | 19–1 | 95% | 9/10 · 10/10 | 76.4%–99.1% |
| 合计 | — | **75–25** | **75%** | 34/50 · 41/50 | — |

执行审计：

- `100/100` terminal，`100/100` winner，0 failure/dirty/step-cap；
- `3995/3995` policy calls 成功；
- 0 invalid output、0 policy error、0 classic fallback、0 same-window fallback、0 engine rejection；
- `100/100` public replay accepted；独立复核 100 个文件的 artifact SHA-256、match envelope、frame-chain root 与 frame count，差异为 0。

正式报告：

- `D:\ai\code\PtcgDAP\artifacts\deck_training\ogerpon_final_1_0_0_20x5_one_shot_clean.json`
- `D:\ai\code\PtcgDAP\artifacts\deck_training\ogerpon_final_1_0_0_representatives_one_shot_clean\`

R0 的独立旧 seed 基线为 `73–27`（13/15/11/14/20）。最终 `75–25` 使用不同 seed，只能说明最终包在该预注册新矩阵上的结果，不能把 +2 胜场解释成严格因果提升。每个对局仅 20 场，Wilson 区间也表明样本较小。

## 6. 架构 Block 台账

本轮先记录、后经用户授权修复。所有 Block 都在 owning layer 做 RED→GREEN，没有用牌名特判或静默 fallback 掩盖。

| ID | 根因 | 架构修复与证据 | 状态 |
|---|---|---|---|
| GODOT-OGER-001 | Host competitive-v2 frame 多出 validator 禁止字段 | v2 author projection 对齐冻结 exact schema，并用真实 Host frame 直入同一 compiled policy 预检 | RESOLVED |
| GODOT-OGER-002 | public replay 固定单一 baseline，不能表达五个异构 Rule 对手 | envelope/participant 绑定 exact Rule deck/strategy identity；100 份异构录像通过 hash-chain capture | RESOLVED |
| GODOT-OGER-003 | deck raw hash 受 CRLF/LF 影响 | Forge 按 PtcgDAP 源字节 vendoring，raw/canonical 双校验 | RESOLVED |
| GODOT-OGER-004 | 同 ID/version 不同 archive 导致 catalog identity conflict | 保持同版本不可变；迭代使用新版本，旧冲突制品只作 RED 证据 | RESOLVED |
| GODOT-OGER-005 | `send_out` frontier 暴露 effectively-KO Bench | option 生产与 engine commit 共用 effective-HP/KO 合法性；补 KO+健康、reorder 和 fail-closed 回归 | RESOLVED |
| GODOT-OGER-006 | Rule Trainer interaction 只有粗粒度 UCIS 错误，且 Brock bool mode 不匹配 | 诊断绑定 effect/source/entrypoint/compiler code；bool mode 归一到标准 YES_NO wire | RESOLVED |
| GODOT-OGER-007 | Phantom Dive/伤害分配按名义 HP 而非 effective HP，产生长循环/脏局 | 公开 option 与 Rule 决策使用同一 effective-HP 语义；最终 100 局无 step-cap | RESOLVED |
| GODOT-OGER-008 | assignment target 窗口丢失 originating effect source identity | fresh 窗口保留 effect source UID，同时每一步重新绑定当前合法 target | RESOLVED |
| GODOT-OGER-009 | assignment source 看不到当前附着能量的 owner/能量/ready/debt | Host 从附着卡反查冻结 owner slot 并发布公开 `target_*` profile | RESOLVED |
| GODOT-OGER-010 | Energy Switch 使用非标准 source/target wire | source=`ATTACHED_CARD/SWITCH_ENERGY_CARD/ENERGY_CARD`，target=`CARD/ATTACH_TO/CARD`；compiler 与真实 trace 双证据 | RESOLVED |
| GODOT-OGER-011 | 65 条 adapter rule 超过 IR 64 macro-ID 上限；Forge 曾跳过 IR 预检而 Godot fail closed | 超限 IR 使用固定聚合宏；Forge/Godot preflight 都先编译 IR 再编译 adapter；65-ID 负控按 `package_policy_unsupported` 拒绝 | RESOLVED |
| GODOT-OGER-012 | Headless bridge 从最后一条 MULLIGAN 日志推断待处理提示，在双方同步 mulligan 后制造幽灵窗口 | `GameStateMachine` 成为 durable one-shot pending-decision authority；bridge 只读 snapshot，不再从历史日志猜测；合法数量提交后重复调用被拒，非法输出不消费窗口 | RESOLVED |

首次 final 运行因 GODOT-OGER-012 在 72 局后按 dirty gate 停止，报告保留为
`ogerpon_final_1_0_0_20x5.json`。三个固定种子修复后均 2/2 clean，随后从空输出目录重跑全部 100 局；没有把首次 72 局与后续结果拼接。

## 7. 已知限制与后续方向

- 这是 Godot 4.6.1 Windows development Host 证据，不是官方 CABT 引擎、卡牌 ID、RNG 或整场规则 parity。
- `.ptcgai` 是 unsigned development built-in candidate；production signing、社区发布审批、Android/A5 和 clean-install device acceptance 未在本任务声明。
- 20 局/对局适合发现路线错误，不足以给出窄置信区间；强度推广应使用更大、预注册且独立的 seed 集。
- Godot 测试退出时仍报告既有 ObjectDB/resource leak 警告；本轮所有相关 runner exit code 为 0，仍建议单独做资源生命周期清理。
- 录像证明公开轨迹、身份与完整性，不授予引擎控制、隐藏信息、Search capability 或 production authority。

## 8. 回滚

策略回滚只需在新对局中停用 final exact package 或选择已固定的 R0–R3；当前对局不热换，用户包不删除。Host/interaction 修复若回退，真实 Host preflight、KO frontier、Energy Switch compiler、double-mulligan 和 100× replay/hash gates 会重新 RED，阻止重新声明 clean benchmark。

## 9. 2026-08-26 支援者专项三轮

玩家侧三份录像共同证明平台正常发布奇树/裁判 option、Supporter 可用且 Host 0 error/0 invalid/0 fallback；旧 1.0.0 的策略规则却把两张支援者分别锁在 `self.hand_count <= 4`，同时给未充能石居蟹与不安全能量转移局面的 `end_turn` 赋 11000/15500 正分。故 owning layer 为 adapter，不是卡效或平台执行器。

专项 R1 1.1.0 用 `goal.ready_count == 0 && goal.energy_debt > 0` 驱动奇树，真实失败形状中的 6 手牌不再否决展开。R2 1.2.0 用 `threat.tempo_margin <= -1`、对手大手牌和支援者可用性驱动裁判，并用 option reorder 与只改变奖赏时钟的 metamorphic pair 证明行为翻转。R3 1.3.0 删除所有正向 `end_turn` 规则，把不安全能量转移改为对 Item 本身计负分，同时加入低牌库奇树负门。

最终开发包为 `work/ogerpon-crustle-supporter-r3/build/ogerpon-crustle-supporter-r3-1.3.0-checked.ptcgai`，SHA-256 `B813433007BCC1A516376D2C95E4911999B4B4B5A804BD5EE1329799280C40CA`；65 score rules、6 count rules、正向 end-turn rules 为 0，严格场景 26/26，双构建字节一致。此段记录的是获得相邻仓库修改授权前的阶段性边界：当时只声明 Forge public-window 与严格 Host 编译，尚未运行新包的 Godot 整局、同 seed 胜率或 BattleSetup 选择；该 pending 状态已由下方 §10 的显式授权与引擎证据取代。

## 10. 1.3.0 Windows development 发布与整局终验

用户于 2026-08-26 显式授权发布新版本并查看胜率。Forge 的 exact archive bytes 被复制到
`D:\ai\code\PtcgDAP\data\ptcgdap\author_strategy_packages\ogerpon-crustle-v523a-supporter-r3-1.3.0.ptcgai`，源与安装文件均为 83,275 bytes、SHA-256 `B813433007BCC1A516376D2C95E4911999B4B4B5A804BD5EE1329799280C40CA`；没有覆盖 1.0.0。Windows development gate 新增 exact ID/version/hash，策略仍是 unsigned、development-only。

Godot focused suite 先以“1.3.0 候选缺失、archive hash 为 null”得到 16 pass / 1 fail 的 RED；登记 exact package 后为 17/17 GREEN。真实 catalog、BattleSetup 选择、start allowed、reviewed policy bind 与真实 Host setup frame 均直接使用 1.3.0，而不是 benchmark 私有旁路。

同 seed base `72300` 的严格对照保持 engine/rules/Host/catalog 哈希一致：

| Rule 对手 | 1.0.0 | 1.3.0 | 差值 |
|---|---:|---:|---:|
| 玛俐长毛巨魔 | 17–3 | 18–2 | +1 |
| 无碟沙奈朵 | 16–4 | 15–5 | -1 |
| 多龙巴鲁托 | 12–8 | 13–7 | +1 |
| 猛雷鼓厄诡椪 | 11–9 | 12–8 | +1 |
| N 的索罗亚克 | 19–1 | 19–1 | 0 |
| 合计 | **75–25（75%）** | **77–23（77%）** | **+2pp** |

1.3.0 的独立新 seed base `82300` 为 16–4、12–8、15–5、11–9、20–0，合计 **74–26（74%）**。两组共 151–49（75.5%）；同 seed 用于版本对照，新 seed 用于独立复验。每个 matchup 仍只有 20 局，不能把 +2pp 或 200 局汇总冒充稳定统计优势。

两组执行审计均 clean：`7960/7960` policy calls 成功；invalid output、policy error、classic fallback、same-window fallback、engine rejection 全为 0；200/200 terminal/winner/public replay accepted。独立冻结 CSP validator 复核 200 文件、18,185 帧的 raw artifact SHA-256、match envelope、frame chain、frame count 与 exact participant identity，差异为 0。

公开录像还验证了“实际打出”，而不只是规则匹配：跟踪候选方支援者 card serial 首次进入弃牌区，并要求同一帧满足卡效后的公开手牌形状。1.0.0 在同 seed 100 局实际为裁判 3 次、奇树 7 次；1.3.0 同 seed 为裁判 31 次、奇树 4 次，新 seed 为裁判 19 次、奇树 2 次，两组共裁判 50 次、奇树 6 次，未分类事件 0。玩家最初录像的 0 次问题因此被整局证据关闭，但结果也表明本轮增量主要来自“落后时干扰对方”的裁判路线，而不是提高奇树总频次。

一次用于抓取 developer trace 的 seed `72308` 单独重跑在正式开局前因 `setup_option_missing` 被 Host preflight 拒绝，执行局数为 0；其报告 `ogerpon_supporter_1_3_0_marnie_seed72308_trace.json`（SHA-256 `C0FCBF0A5E14982462EB775DBC6411681C09D0A596262CD6DE3796899325F8CD`）只保留为 fail-closed 诊断，未进入任何胜率或支援者次数。实际打出证据改由 200 份 accepted public replay 的公开卡区与效果形状完成。

正式报告：

- `D:\ai\code\PtcgDAP\artifacts\deck_training\ogerpon_supporter_1_3_0_same_seed72300_20x5_clean.json`（SHA-256 `C4DC7CE83F0AA50941B926B68ECBE7354249B50A778A64296237E90ECAEB5173`）；
- `D:\ai\code\PtcgDAP\artifacts\deck_training\ogerpon_supporter_1_3_0_same_seed72300_replays\`；
- `D:\ai\code\PtcgDAP\artifacts\deck_training\ogerpon_supporter_1_3_0_fresh_seed82300_20x5_clean.json`（SHA-256 `430E73134FDCCB724754D2F707187BDAA1CD9CFE2924F64212A8AF71C28CC6BA`）；
- `D:\ai\code\PtcgDAP\artifacts\deck_training\ogerpon_supporter_1_3_0_fresh_seed82300_replays\`。

回滚身份仍是 1.0.0 / `9531F683F2AB9E0138D8054D3E3813D7378F9F6E5F7F8CAF9C428C3FCAFF8D9F`；只在新对局选择旧版本，不删除 1.3.0，也不热换进行中的对局。本轮没有 commit、push、production signing、社区市场发布、Android/A5 或 official CABT engine parity 声明。

## 11. 1.4.0 奇树／裁判阶段曲线发布与终验

1.3.0 的两组 200 局虽然已解决“完全不使用支援者”，但公开录像只确认奇树 6 次、裁判 50 次；规则报告中奇树命中过 33 个窗口，说明问题已经从“没有候选”变成“候选仍被错误路线压住”。直接根因是奇树展开线要求太晶珠、捕虫套装和宝可领航员三个道具入口全部消失，而裁判在对手只剩三奖时仍保持正分。

1.4.0 将支援者改为公开阶段与场面债务联合判断：

- `main.iono-self-brick-reset`：没有就绪攻击手、仍有能量债务、支援者可用且牌库大于 6 时计 24000；删除三个道具入口必须为零的硬门，因此前中期卡手时可以先用奇树重启。
- `main.iono-late-prize-lock`：我方至少三奖、对手至多三奖且牌库安全时计 23000，表达奇树随奖赏推进增强的后期压手价值。
- `main.judge-early-prize-disruption`：只在前六回合、对手至少四奖、我方攻击时钟落后且支援者可用时计 14500；不再把对手手牌数量当作硬门。
- `main.avoid-judge-late-game`：对手进入三奖以内时为裁判计 -24000；低牌库奇树负门继续保留。

RED 是 `adapter_version` 仍为 5 且没有阶段规则；GREEN 为两个定向测试 2/2。新场景覆盖有低收益太晶珠仍用奇树、后期奇树、option reorder、后期裁判 hold 和低牌库奇树 hold，最终 31/31。唯一 1.4.0 archive 为 85,056 bytes，SHA-256 `3B4E78A16EB2C238CD9CFB29CA29B8CF44E0D7D99822CA9C1ECD90A2651DFFB8`，双构建字节一致。

经用户显式授权，exact bytes 已复制到 `D:\ai\code\PtcgDAP\data\ptcgdap\author_strategy_packages\ogerpon-crustle-v523a-supporter-r4-1.4.0.ptcgai`，源／安装大小与 SHA 完全一致，并登记 Windows development gate。未登记时 focused 为 17/20，三项失败正好是 exact archive、BattleSetup 与真实 Host；登记后 20/20，加入 dirty replay 诊断及共享工作树新增门禁后当前最终 Ogerpon suite 26/26。真实 catalog、BattleSetup start、reviewed policy 和 Host setup frame 均通过。

冻结运行时、同 seed base `72300` 的 package-only A/B 为：1.3.0 五对局 18/15/13/12/19、合计 77–23；1.4.0 为 15/13/13/13/19、合计 73–27，即 **-4pp**。两边 replay envelope 的 engine/rules/card catalog/Host contract/runtime manifest/evaluation profile、seed 与 seat identity 相同，仅 exact package participant 不同。独立 seed base `92300` 的 1.4.0 为 17/13/15/12/20、合计 77–23；两个候选组共 150–50（75.0%）。因此本轮不能声明胜率升级。

实际打出数据证明阶段行为已修正：同 seed 奇树由 4 次升至 29 次，其中后期压奖 25、前中期解卡手 3；裁判由 31 次变为 29 次，且从 11 次目标前中期／9 次后期／11 次其他，收敛为 29 次全部目标前中期。独立 seed 奇树 16、裁判 34；两组共奇树 45、裁判 63，未分类 0。8,336/8,336 policy calls 成功，invalid/error/fallback/rejection 全零；200/200 replay、18,740 帧逐文件验证差异 0。

首次 fresh 运行在 exact seed `95308` fail closed 为 `pokemon_entity_projection_failed`，96-replay 脏批次未计胜率。复现显示策略此前 14/14 次选择成功，owning layer 是 Godot Host 实体生命周期：换前台时引擎复用 `PokemonSlot` 容器，旧根实体没有换代。最小修复只允许“旧实体退休且公开根卡变化”时签发新序号，同根退休引用仍拒绝；registry 20/21 RED→21/21 GREEN，exact pair 2/2 terminal、58/58 calls、2 replay / 146 帧零差异，之后从新目录完整重跑 100 局通过。

结论必须拆开：支援者阶段行为问题关闭；同 seed 胜率门回撤。1.4.0 是已发布的 Windows development 观察版本，1.3.0 / `B8134330…C40CA` 保持直接回滚身份。全量 Forge 回归仍为 46/59；13 个失败来自当前脏工作区 Competitive v2 slot 合同与旧测试帧的 `invalid_public_frame`，未被本轮冒充 GREEN 或顺手修复。本轮没有 commit、push、production signing、社区市场发布、Android/A5 或 official CABT parity 声明。机器证据见 `evidence/ogerpon-supporter-stage-curve-r4.json` 与 PtcgDAP `evidence/ptcgdap/ogerpon_supporter_stage_curve_r4_v1.json`。
