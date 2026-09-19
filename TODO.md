# PTCG Strategy Forge TODO 闭环

2026-09-19 SDK 更新：已实现本人决策录像下载与严格导入、公开语义模型 profile、Base 授权候选域、真实教师数据资格、BC/ORT 工具、受监督运行与资源排队保护。工作流程见 [录像下载](docs/27-ONLINE-DECISION-TRACES.md)、[语义模型](docs/28-LEARNED-SEMANTIC-ACTOR.md)、[运行稳定性](docs/30-TRAINING-MACHINE-STABILITY.md) 和 [学习型研发入口](skills/ptcg-learned-strategy-pipeline/SKILL.md)。

本次仅提交通用 SDK 与回归测试，不发布策略、训练数据、模型权重或密钥。强度提升、PPO、完整 CABT 对齐及生产验收仍需要独立证据，不能由 SDK 提交宣称完成。

2026-09-16 CLI 完整性复核：已补账号身份自动绑定、临时凭据、远端版本查询/下载/资格等待、参赛管理与本人密钥撤销。此前“可提交”不等于完整 CLI；准确流程及剩余服务/模型缺口见 [无网页开发工作流](docs/26-CLI-ONLY-DEVELOPMENT.md)。生产提交 canary 仍独立保留。

2026-09-16 SDK 0.3.0 提交前验收：170 项测试、独立安装、来源锁和示例工作区通过；
提交文件及历史密钥扫描无发现。见 [GitHub 提交验收](evidence/sdk-github-acceptance-20260916.json)。

2026-09-16 复杂决策续作：新增 [多窗口决策 bench](docs/25-COMPLEX-DECISION-BENCH.md)，52 场景、104 原序/重排变体，完整夹具清单绑定所有未执行后缀。余烬霜幕 0.2.1 修复暗能撤退、顶尖启动及己方实体目标绑定；复杂题库 90/104→104/104，完整链 8/14→14/14，367 工作区场景和两次一致构建通过。两条修复链已有 Godot 实战见证，新种子整局对照另行记录。通用后排动态伤害证明、对手响应树、全局转伤和生产/天梯资格仍未关闭；本轮记录位于 `work/ember-frost-complex-20260916/`。

2026-09-16 余烬霜幕研究：新增可选串行 Godot 整局 bench，支持精确分发包/本机测试包、双座位配对、双方回退审计及当前窗口轨迹校验。使用说明见 [本地引擎 bench](docs/24-LOCAL-ENGINE-BENCH.md)。它仍需本机引擎快照，未关闭通用 engine evaluator、官方规则一致性或生产准入；策略实验记录位于 `work/ember-frost-20260916/`。

本轮冻结 0.2.0：322/322 场景；留出 A 从 10/30 到 16/30，独立榜首复测 B 从 9/20 到 12/20（3 局改善、0 局回退），四类规则 NPC 回归均为 8/8。最终 116 局通过整局和轨迹审计。小样本尚不证明稳定天梯优势；暗能量撤退支付等剩余缺口单列。收据见 `evidence/ember-frost-local-iteration-20260916.json`，完整报告在 `work/ember-frost-20260916/RESULTS.md`。

2026-09-16：正式 HTTP 账号/签名公钥/提交/接收对账接口已部署，公网能力发现、权限边界
和录像读取通过。T47 保留真实开发者账号生产提交验收；原生 BC 与引擎评估仍独立保留。
见 [控制面 CLI](docs/23-CONTROL-PLANE-CLI.md)。

2026-09-09 跨仓库续作：双座位录像系列去重、网页精确资格状态与提交回执、
Godot 模型输入诊断捕获已实现并通过针对性测试。私有控制面授权、公网录像 503、
原生录像到 BC 的跨语言投影和真实引擎评估仍未关闭；详见
[`docs/22-CROSS-REPOSITORY-UPGRADE-PROGRESS.md`](docs/22-CROSS-REPOSITORY-UPGRADE-PROGRESS.md)。

本文只记录工具包建设过程中发现、且属于本项目可解决范围的缺口。产品方 production 私钥、审核批准、A5、Android 和任意新牌组规则一致性是明确的平台权限/产品范围，记录在 `docs/LIMITATIONS.md`，不伪装成本项目可自行关闭的 TODO。

| ID | 发现的缺口 | 处理结果 | 状态 | 证据 |
|---|---|---|---|---|
| T01 | 工具散落，开发者必须了解主工程目录 | 建立统一 `forge.py`，覆盖创建、构建、校验、模拟、测试、安装、提交和 demo | DONE | `python forge.py --help` |
| T02 | 独立校验缺少模板牌组的精确源 deck/card 数据 | 随 SDK 固定 800018501 及其 28 个 printing 源文件 | DONE | `forge.py doctor` |
| T03 | 原 scaffold 只有一个正向场景 | 增加 10 场景 strict suite | DONE | `evidence/demo-workflow-green.json` |
| T04 | 场景生成不可重复且负例假设不准确 | 场景生成器改为幂等，并使用真实 allow-list/UID 负例 | DONE | `regenerate-demo-scenarios` 连续运行测试 |
| T05 | 没有可证明的优化过程 | 增加错误基线 RED、修正后 GREEN 和选项重排证据 | DONE | `demo/marnie-forge/optimization` |
| T06 | 没有确定性双构建收据 | `demo` 比较两份 archive 的 exact bytes/hash | DONE | SHA-256 `7F53F2DC…D33A` |
| T07 | 发布工具与开发流程分离 | 统一 `publish` 并完成真实 loopback HTTP 提交 | DONE | `evidence/demo-publish-receipt.json` |
| T08 | SDK 来源只能靠目录约定 | 增加 byte-level manifest，拒绝篡改、额外文件和 symlink | DONE | `vendor/ptcgdap-sdk-manifest.json` |
| T09 | 缺少一套从零可执行的开发者文档 | 增加 Quickstart、策略、测试、优化、发布、安全、排障和架构文档 | DONE | `docs/` |
| T10 | 缺少自动化回归入口 | 增加 unittest、PowerShell setup/runner 和 GitHub Actions | DONE | `tests/`、`.github/workflows/ci.yml` |
| T11 | 尚未证明离开当前工作目录仍可运行 | 从 GitHub `v0.1.1` 全新克隆，空环境安装后 doctor、12 项测试和 `cp1252:strict` 完整 demo 全部通过 | DONE | `evidence/clean-clone-acceptance.json` |
| T12 | 新项目和 demo 尚未上传用户 GitHub 空间 | 已创建公共仓库、推送源码并发布带 SHA-256 的 demo asset | DONE | `evidence/github-publication.json` |
| T13 | 根目录缺少面向策略研发 Agent 的权威章程 | 增加 `AGENTS.md`，固定阅读顺序、架构不变量、策略思考法、测试流程、证据口径和本机进程安全 | DONE | `tests.test_forge.ForgeTests.test_root_agent_charter_captures_strategy_and_process_invariants` |
| T14 | 新工作区只给规则文件，没有把 PtcgDAP 多时间尺度策略思考转为可填写研发蓝图 | `new` 生成 `STRATEGY-BLUEPRINT.md`，覆盖 Match Agenda、攻击窗口、Resource Ledger、信息检查点、类型化交互和 metamorphic 场景 | DONE | `tests.test_forge.ForgeTests.test_new_workspace_builds_and_passes_generated_suite` |
| T15 | 作者需要手工串联 build/validate/test，容易漏掉确定性双构建 | 增加 fail-closed `check`，在临时目录双构建、比较 exact bytes/hash、严格校验并跑完整套件，全部通过后才原子写包 | DONE | `evidence/developer-workspace-check.json` |
| T16 | 五套 18.0 策略此前只有内置脚本/胜率报告，没有按作者文档生成可发现的 `.ptcgai` | 固定五套精确 deck/card 来源，增加 `new --deck-id`、牌组专用规则/蓝图/10 场景，双构建验收并接入本地 Godot 开发执行门 | DONE | `evidence/five-v18-package-delivery.json` |
| T17 | restricted v1 只能排序且由 Host/通用逻辑取数量、分配目标，数据包无法执行精确资源与奖赏路线 | 新增 Competitive Policy IR v2：官方 `list[int]` 边界不变，公开目标能量/ready/debt/奖赏/伤害进入 allow-list frame，精确基数与逐次 source→target 窗口由 Base 复验；Python/GDScript 双运行时和猛雷鼓三轮真实引擎验证完成 | DONE | `docs/11-COMPETITIVE-POLICY-IR-V2.md`、`evidence/raging-bolt-competitive-v2-validation.json` |
| T18 | 作者包每个窗口重复 schema/hash 校验、深拷贝和全量 option×rule 扫描，明显慢于内置策略 | 增加 sealed compiled execution plan、公开事实缓存、frame/option 条件拆分和 option-kind 分桶；相同重放 236647 ms→10958 ms（21.6×），strict 与 compiled 逐结果一致 | DONE | `docs/12-ARCHITECTURE-UPGRADE-DESIGN-AND-PLAN.md`、`evidence/competitive-v2-architecture-upgrade.json` |
| T19 | 架构升级后的数据策略仍未达到经典 GDScript 非劣门 | typed recipe、turn ledger、bench capacity 与 `route_candidates` 整回合词典序裁决均已完成；资源预算和奖赏时钟/response-risk 两类路线 flip 已进入 Python/Godot 合同，full Forge 30/30、Godot 17/17、P95 4.070ms、Round41 专用包路径通过。按用户要求暂停猛雷鼓，经典非劣强度门仍待后续恢复 | PENDING | `docs/12-ARCHITECTURE-UPGRADE-DESIGN-AND-PLAN.md`, `evidence/competitive-v2-architecture-upgrade.json` |
| T20 | 历史缺口：曾缺少 Kaggle 风格多文件 Python 包、单一 validator、确定性构建、trace 和开发预资格 | 历史实现过 `.ptcgbot` v2 schema/profile/vectors、canonical ZIP、共享 Bundle owner、RPC/runner、Forge competition CLI、exact Python 3.11.13 runtime、fault/privacy probes 与 A1 release binding；该产品方向现已被 T36 的统一 `.ptcgai` 决策取代，只保留历史证据 | DONE | `docs/14-KAGGLE-STYLE-PTCGBOT-QUICKSTART.md`、`docs/17-UNIFIED-PTCGAI-RULE-AND-MODEL-DESIGN.md` |
| T21 | CABT 11/49/17 wire、non-prompt lifecycle、三类 hash、logs/time/Search 和 one-shot window 没有完整 scoped A1 | 生成 census/Prompt/Lifecycle matrices；实现 Python/Godot current-window、exact mulligan/setup、per-seat logs、Godot time/Search=none 与 whole-match owner；签发 exact core selection A1 scope | DONE | `contracts/ptcgdap/cabt_a1_scope_report_v2.json` |
| T22 | 私有 ID 下的 setup-active 对应卡缺少真实 official-vs-Godot current-window 入参、合法 option 和返回 index 证据 | 完成 55 个唯一卡牌/36 个攻击 identity 的 sealed bridge；Godot 使用正式 event-driven owner/port/engine executor，补齐 `YES_NO/IS_FIRST` 双分支、严格临时私有 60 卡 deck、17 类 Option 静态投影和一条 source-locked setup-active（live type 3）双引擎见证。current-window input/index 串行重复 5/5；bootstrap prefix、稳定公开转移和下一窗口均明确不声明 | DONE | PtcgDAP `evidence/ptcgdap/a3/corresponding_card_operation_qualification_v1.json`、`tests/ptcgdap/test_a3_private_corresponding_card_live.py` |
| T23 | 五套牌所有可达卡效、伤害、KO、随机与终局的完整 full-rule A3 尚无 46 项场景、四条交互链和 25 配置 zero-diff evidence | 基础设施、RNG context、scope、mutation、差分和 gap ledger 已完成；保持 `a3_promoted=false`。项目负责人当前只要求对应卡操作入参/返回值匹配，因此 full-rule 结果一致性是独立后续范围，不阻断 T24 | OUT OF SCOPE | PtcgDAP `evidence/ptcgdap/a3/scenario_coverage_v2.json`、`evidence/ptcgdap/a3/qualification_v2.json` |
| T24 | 对应卡在整场对战中的主阶段操作尚未逐窗口证明入参、ordered legal options 和返回 current-window indexes 匹配 | 已以合法前缀和 official-vs-Godot live witness 覆盖精确搜索/数量、source→target 分配、能力、攻击、伤害分配、撤退/换位、进化与特殊状态九类；两端接受 current-window index，多窗口链 fresh reobserve，公开回执不含私有 locator/官方数字映射且明确不声明 post-state/full-rule A3 | DONE | PtcgDAP `evidence/ptcgdap/a3/corresponding_card_whole_battle_input_index_v1.json` |
| T25 | 每张卡各自沿用 private prompt/builder，无法在架构层证明与 CABT-shaped current-window 合同统一 | 实现 UCIS generation 1：16 原语、typed effect IR、Python/GDScript compiler、唯一 window owner、797 卡/730 effect 目录编译、394/394 legacy callsite 收口、property/composition/live/性能门和 Forge 固定 SDK；729 个 usable effect 全闭包，1 个动态未登记能力显式 unsupported | DONE | `docs/13-KAGGLE-GRADE-DEVELOPER-AND-ENGINE-PARITY-DESIGN.md`、PtcgDAP `evidence/ptcgdap/ucis/ucis_catalog_qualification_v1.json` |
| T26 | UCIS 已实现但开发者仍需手写 raw 数字/稀疏 shape，模板和 Marnie demo 未演示最新精确数量与 fresh rebind 路径 | 增加 generation-locked 无依赖 runtime SDK、`ucis catalog/inspect/walkthrough`、合法标准窗口模板、工作区上手卡和可执行 demo；标准 demo 同时验证 exact-count、reorder、repeated assignment、公开 prize/energy facts 与 unknown fail-closed | DONE | `docs/15-UCIS-SDK-DEVELOPER-GUIDE.md`、`tests/test_ucis_runtime_sdk.py`、`evidence/demo-workflow-green.json` |
| T27 | Kaggle v5.23a 厄诡椪／岩殿居蟹需要迁移到当前 Godot 18.0 卡表并对五套 Rule 策略迭代 | 固定只读 champion 来源与精确 60 卡/19 printing；关闭 Host frame、异构 replay、KO frontier、assignment、Energy Switch、IR preflight 与 double-mulligan 等架构 Block；完成 R0–R3 三轮录像驱动优化和 21/21 场景，交付可在 BattleSetup 选择的 final 1.0.0。独立新 seed 20×5 为 75–25，3995/3995 policy calls 成功、零 invalid/error/fallback/rejection，100/100 录像 hash/envelope/chain 复核一致 | DONE | `docs/16-OGERPON-GODOT-ADAPTATION-FINDINGS.md`、`evidence/ogerpon-godot-adaptation-final.json` |
| T28 | 玩家录像显示 1.0.0 在 7–15 个支援者窗口中从不使用奇树/裁判，并被正向 `end_turn` 规则压制 | 参考 v5.23a 统一 supporter owner 完成三轮：展开债务驱动奇树、奖赏时钟落后驱动裁判、所有正向结束回合分数归零；最终 1.3.0 为 26/26 且双构建一致。经显式授权将 exact SHA 登记为 PtcgDAP Windows built-in development candidate；focused 17/17、BattleSetup 可选可开战。同 seed 100 局由 75–25 到 77–23，新 seed 为 74–26；两组 7960/7960 policy calls 成功且 200/200 replay 独立复核无差异。公开状态变化确认 1.3.0 实际打出裁判 50 次、奇树 6 次 | DONE | `evidence/ogerpon-supporter-three-round-iteration.json`、`work/ogerpon-crustle-supporter-r3/check-report-final.json` |
| T29 | 宁波第 5 名玛俐长毛巨魔需要可信公开伤害计划、跨回合事务、可接受热路径性能和录像驱动策略交付 | 实现 Host capability registry、确定性公共伤害计算、稳定实体序号、语义事务与 fail-closed package gating；把 registry/plan/transaction 改为加载期一次校验的 sealed execution plan，使实战 P95 从 1111.618ms 降至 51.442ms；按用户调整后的 Rule 18.0 玛俐目标完成 R4–R7、87/87 场景和确定性 1.7.0。本地精确包 BattleSetup 可见/可选/可开局，固定双方换位 20 局为 13–7，924/924 调用与 20/20 回放全绿 | DONE | `work/marnies-gift-box-rule-marnie-r7/FINAL-ACCEPTANCE.md`、`work/marnies-gift-box-rule-marnie-r7/ITERATION-LEDGER.md` |
| T30 | 1.3.0 的 200 局仅实际打出奇树 6 次，裁判 50 次，阶段曲线反向偏向裁判 | 1.4.0 已发布到 PtcgDAP Windows development gate，31/31 Forge、26/26 Ogerpon、21/21 serial registry。冻结运行时同 seed A/B：1.3.0 77–23、1.4.0 73–27（-4pp）；fresh 1.4.0 77–23。两组候选 8,336/8,336 calls、200 replay/18,740 帧全绿；实际奇树 45、裁判 63，所有裁判均收敛到前中期目标形态。行为问题关闭，但胜率门未提升，1.3.0 保留回滚 | DONE | `evidence/ogerpon-supporter-stage-curve-r4.json`、`work/ogerpon-crustle-supporter-r4/check-report-final.json` |
| T31 | 玛俐的礼盒 1.7.0 源锁将 4 张派帕/2 张深钵镇误替换为 4 张阿响的冒险/2 张桌台市，且老大/反击捕捉器可在只有后排就绪时被误消耗 | 1.8.0 按牌组 `646600` 原始响应恢复精确 60 张，保留已审核雪童子等价映射；新增派帕双 fresh-window 检索、深钵镇铺场优先级和前场实际可攻击门。最终 91/91 场景、确定性双构建、exact Godot 绑定与本地安装通过 | DONE | `work/marnies-gift-box-rule-marnie-r8-final/FINAL-ACCEPTANCE.md`、`work/marnies-gift-box-rule-marnie-r8-final/SOURCE-LOCK.md` |
| T32 | 1.8.0 真实录像中庞克泵感只填 1 能量；愿增猿把能力使用次数和场上数量混同，持续把伤害铺到可被叶伊布 ex 治疗的吉雉鸡；非致死 210 伤害压过精确两奖 gust，且暗影子弹目标窗口和开发轨迹不完整 | 1.9.0 在 owning layer 修复 `assignment_source` 精确债务、当前合法愿增猿计数、叶伊布后排治疗响应风险、集中击倒、精确反击捕捉器/老大事务、`attack_target` 绑定和 count→target 子决策记录。最终 94/94 strict 场景、Python/Godot 双实现回归、确定性构建和 exact Windows 开发绑定通过 | DONE | `work/marnies-gift-box-rule-marnie-r9/REPLAY-ISSUE-LEDGER.md`、`work/marnies-gift-box-rule-marnie-r9/FINAL-ACCEPTANCE.md` |
| T33 | 18.0 阿响的火暴兽 `800018880` 缺少可安装数据策略，以及对阵玛俐礼盒 `646600@1.8.0` 的十轮真实录像驱动优化 | 已固定 Limitless 18880 / Godot 800018880 的精确 60 卡与 26 printing，完成 R0–R10 十轮同 seed/换座 Godot 回放迭代。R5 `0.6.0` 以 28/28 Forge 场景和确定性 SHA `26AD9CC…1F1FD` 冻结；固定 20 局由 R0 5–15 提升为 8–12（+15pp），后续同分不晋级且 R7 回退被拒。独立 fresh 100 局为 28–72（Wilson 95% 20.14%–37.49%），100/100 终局/回放接受、10,657/10,657 调用成功、invalid/error/fallback/rejection 全零；exact Godot 门、审核 Owner 与 BattleSetup 可选可开局通过 | DONE | `evidence/ethans-typhlosion-vs-marnie-ten-round.json`、`work/ethans-typhlosion-r5/FINAL-ACCEPTANCE.md`、`work/ethans-typhlosion-r5/build/check-report-final.json` |
| T34 | 最新玛俐礼盒录像显示攻击前漏做雪妖女/愿增猿/奇树，庞克泵感目标被误解为取完恶能，且后期含羞苞与送出进化线优先级回归 | R53 `5.13.0` 将庞克泵感固定为每只场上玛俐宝可梦恰好 2 能；愿增猿在公开可转伤时先于非终结攻击且覆盖最后奖赏；含羞苞后期不抢送出但不被无条件硬撤；有长毛巨魔候选时中段/基础线不抢位。最终 Forge 121/121、Godot 18 exams 两轮 180/180；同 seed/换座 100 局 43–57，相对 1.9.0 的 31–69 为 +12pp，100 回放和全部调用审计干净 | DONE | `work/marnies-gift-box-rule-marnie-r43/FINAL-ACCEPTANCE.md`、PtcgDAP `evidence/ptcgdap/godot_v18_marnie_gift_box_r53_pre_attack_continuity_20260829.md` |
| T35 | 默认 Forge 包只有公开 test-fixture 签名，无法作为开发者账号的上传所有权证明 | 新增不可覆盖的 `release-key`、`release-build`、`release-resign`；key ID 与服务端按公钥 SHA-256 派生规则一致，报告不含私钥，重签保持 payload 原字节，42/42 Forge 回归通过 | DONE | `tests/test_forge.py`、`src/ptcg_strategy_forge/release_signing.py` |
| T36 | 规则开发与 BC/RL 模型被拆成 `.ptcgai`/`.ptcgbot` 两套制品，模型无法安全安装到游戏且开发入口分裂 | 已实现统一 `.ptcgai v2`、rules/model scaffold、模型检查/导入/张量化/一致性命令、冻结 ORT Actor、Base 受控裁决、25ms 可取消 deadline、规则 fallback、平台路径安装与 Windows x86_64 原生 Godot 实战；最小 BC→离线 contextual-bandit RL 包完成 55 次策略成功、38 次 ORT 推理、30 次模型改选且零 fallback/非法输出。活动 CLI 已移除 `.ptcgbot`；macOS arm64/x86_64 仅有构建入口，三平台同字节实机门仍待外部设备关闭 | PARTIAL | `docs/17-UNIFIED-PTCGAI-RULE-AND-MODEL-DESIGN.md`、`examples/minimal-bc-rl-marnie/`、PtcgDAP `evidence/ptcgdap/minimal_bc_rl_model_battle_windows_20260830.json` |
| T37 | 开发能力按 package/UCIS/model/check 等底层概念分散，创建参数冗长，公开 Python 包只暴露窗口 helper，文档把历史证据和首条成功路径混在一起 | 新增 `forge workspace create/status/inspect/check/build/install/model` 主生命周期、公开 `StrategyWorkspace`/`WorkspaceModel` SDK、约定默认身份和产物路径、工作区状态/下一步报告、安全 Actor 替换与场景 firewall 张量化；README、Quickstart、开发者中心、SDK 参考、架构/安全/排障/验收文档和生成工作区指南改用同一开发者语言，底层命令保持兼容 | DONE | `tests/test_developer_sdk.py`、`docs/00-DEVELOPER-HUB.md`、`docs/18-DEVELOPER-SDK-REFERENCE.md` |
| T38 | 首次真实注册上传中，开发者容易把显示名或去掉 `developer-` 前缀的十六进制部分当作 `author_id`；完整 ID 又会让默认 `package_id` 超长，且服务端可能把身份查找失败表现为签名不可信 | 仓库与静态开发者文档统一为“复制完整 ID + 显式短 package ID + 仓库外私钥 + 只登记公钥 + resign + 上传回执”路径；增加联合排查、上传前清单、密钥忽略规则和文档回归，明确已接收与资格通过的状态边界 | DONE | `docs/05-PUBLISHING.md`、`docs/07-TROUBLESHOOTING.md`、`tests/test_forge.py` |
| T39 | 开发者包没有一份可直接查询的“游戏当前支持哪些卡”文件，UCIS 原始合同过大且容易把交互可用误解为完整规则/模板支持 | 从 qualification-locked UCIS catalog 机械生成 `data/developer/supported-cards-v1.json`，新工作区复制为 `SUPPORTED-CARDS.json`；固定 797 条本地 UID、usable/status、effect/capability 和源 hash，doctor/测试拒绝缺失与漂移，并单独说明 identity、规则结果和平台 non-claim | DONE | `tools/build_developer_supported_cards.py`、`docs/19-SUPPORTED-CARDS.md`、`tests/test_forge.py` |

## 下一阶段：完整开发迭代闭环

以下条目来自 [下一阶段架构升级提案](docs/20-DEVELOPER-ITERATION-ARCHITECTURE-AND-PLAN.md)，已按下表逐项实施；PARTIAL 仍有未关闭验收门。提案链接是设计依据，不是可执行验收证据。涉及服务端、网页或引擎的部分需各自 owner 实施和提供集成回执；本仓库不以客户端 fixture 通过冒充现网完成。

| ID | 待解决的缺口 | 计划交付 | 状态 | 设计依据 / 待补证据 |
|---|---|---|---|---|
| T40 | SDK 直接导入、仓库外使用、首次父目录创建与依赖安装尚未形成完整首条成功路径 | 标准 wheel、资源打包、规则/模型依赖拆分及纯核心依赖干净虚拟环境安装/doctor 已通过 | DONE | `docs/21-ITERATION-CLI-IMPLEMENTATION.md`、`evidence/iteration-cli-v0.3.json` |
| T41 | 默认安装不能识别源码已变化，报告与版本关联不足，status 缺少证据新鲜度 | 输入摘要、不可覆盖回执、stale 安装阻断、模型缓存及版本/迁移已实现；完整产物事务与历史归档仍待扩展 | PARTIAL | `docs/21-ITERATION-CLI-IMPLEMENTATION.md`、`evidence/iteration-cli-v0.3.json` |
| T42 | 多命令缺少共享任务状态、网络并发限额和重型运行准入 | 录像 jobs 历史、取消/恢复和共享 origin 限额已实现；已增加重型资源门和过期 attempt 隔离；跨进程实机门待补 | PARTIAL | `docs/21-ITERATION-CLI-IMPLEMENTATION.md`、`evidence/iteration-cli-v0.3.json` |
| T43 | 录像仍以单场获取为主，Forge 缺少可恢复批量采集和决策数据能力识别 | 有限最近 60 场、冻结目录、预算/摘要/恢复已实现；两个真实系列按原失败任务恢复成功并校验，完整分页和决策附件仍缺失 | PARTIAL | `docs/23-CONTROL-PLANE-CLI.md`、`evidence/control-cli-20260915.json` |
| T44 | 真实录像到 BC 缺少特征/标签、模型候选域、分片与防泄漏的统一数据合同 | 夹具 BC 特征/标签、候选域、多选、审计/切分/导出已实现；已增加原生录像资格检查和确定性分片；目标模型真实决策适配待完成 | PARTIAL | `docs/21-ITERATION-CLI-IMPLEMENTATION.md`、`evidence/iteration-cli-v0.3.json` |
| T45 | 错误决策解释和录像到回归场景仍需人工串联低层工具 | 已实现 Host explain/规则定位、录像转场景和语义重排；已增加谓词明细、单事实反例、基线比较及 changed/watch；复杂路由解释/自动负例矩阵仍待补 | PARTIAL | docs/20：第 11 节，M3、G09 |
| T46 | BC、Actor、工作区和受控对战之间缺少统一实验记录与命令 | 已实现 BC 基线、checkpoint/恢复、精确 ORT 导出等价与离线比较；真实引擎评估待接入 | PARTIAL | docs/20：第 12 节，M4、EXT06、G08、G11 |
| T47 | 上传身份预检依赖人工，接收回执与后续刷新混杂，资格失败缺少可操作入口 | 正式 HTTP 账号、公钥登记、在线预检、签名提交和精确回执已通过本地服务/独立 CLI 集成并部署；公网能力/权限/录像验收通过，真实开发者账号生产提交 canary 待执行 | PARTIAL | `docs/23-CONTROL-PLANE-CLI.md`、`evidence/control-api-live-20260916.json` |
| T48 | 作者需直接面对 raw 枚举/UID，能力说明在 SDK/CLI/网页重复维护 | 卡牌 UID 搜索/检查已实现；已增加 v1 命名化编译与枚举元数据；已提供编辑器 schema/compile/lint；控制面接入仍待补 | PARTIAL | `docs/21-ITERATION-CLI-IMPLEMENTATION.md`、`evidence/iteration-cli-v0.3.json` |

2026-09-09 扩展验收见 [本地升级回执](evidence/architecture-upgrade-local-20260909.json)：149/149 测试、规则与 BC 模型候选两个工作区均通过双构建/Host/10 场景、独立 wheel 与纯核心依赖安装通过。真实录像 79 个窗口完成资格统计，但没有合格 BC 行；完整架构计划仍未关闭，不能把此回执当成跨仓库联调或 production 完成。

完成规则：只有证据文件和外部状态都可复核时才能把 `PENDING` 改为 `DONE`；不能仅因代码已写就关闭。
