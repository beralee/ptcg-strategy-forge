# PTCG Strategy Forge TODO 闭环

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
| T20 | 缺少 Kaggle 风格多文件 Python 包、单一 validator、确定性构建、trace 和开发预资格 | 实现 `.ptcgbot` v2 schema/profile/vectors、canonical ZIP、共享 Bundle owner、RPC/runner、Forge competition CLI、exact Python 3.11.13 runtime、fault/privacy probes 与 A1 release binding | DONE | `docs/14-KAGGLE-STYLE-PTCGBOT-QUICKSTART.md`、`tests/test_competition_forge_v2.py` |
| T21 | CABT 11/49/17 wire、non-prompt lifecycle、三类 hash、logs/time/Search 和 one-shot window 没有完整 scoped A1 | 生成 census/Prompt/Lifecycle matrices；实现 Python/Godot current-window、exact mulligan/setup、per-seat logs、Godot time/Search=none 与 whole-match owner；签发 exact core selection A1 scope | DONE | `contracts/ptcgdap/cabt_a1_scope_report_v2.json` |
| T22 | 私有 ID 下的 setup-active 对应卡缺少真实 official-vs-Godot current-window 入参、合法 option 和返回 index 证据 | 完成 55 个唯一卡牌/36 个攻击 identity 的 sealed bridge；Godot 使用正式 event-driven owner/port/engine executor，补齐 `YES_NO/IS_FIRST` 双分支、严格临时私有 60 卡 deck、17 类 Option 静态投影和一条 source-locked setup-active（live type 3）双引擎见证。current-window input/index 串行重复 5/5；bootstrap prefix、稳定公开转移和下一窗口均明确不声明 | DONE | PtcgDAP `evidence/ptcgdap/a3/corresponding_card_operation_qualification_v1.json`、`tests/ptcgdap/test_a3_private_corresponding_card_live.py` |
| T23 | 五套牌所有可达卡效、伤害、KO、随机与终局的完整 full-rule A3 尚无 46 项场景、四条交互链和 25 配置 zero-diff evidence | 基础设施、RNG context、scope、mutation、差分和 gap ledger 已完成；保持 `a3_promoted=false`。项目负责人当前只要求对应卡操作入参/返回值匹配，因此 full-rule 结果一致性是独立后续范围，不阻断 T24 | OUT OF SCOPE | PtcgDAP `evidence/ptcgdap/a3/scenario_coverage_v2.json`、`evidence/ptcgdap/a3/qualification_v2.json` |
| T24 | 对应卡在整场对战中的主阶段操作尚未逐窗口证明入参、ordered legal options 和返回 current-window indexes 匹配 | 已以合法前缀和 official-vs-Godot live witness 覆盖精确搜索/数量、source→target 分配、能力、攻击、伤害分配、撤退/换位、进化与特殊状态九类；两端接受 current-window index，多窗口链 fresh reobserve，公开回执不含私有 locator/官方数字映射且明确不声明 post-state/full-rule A3 | DONE | PtcgDAP `evidence/ptcgdap/a3/corresponding_card_whole_battle_input_index_v1.json` |
| T25 | 每张卡各自沿用 private prompt/builder，无法在架构层证明与 CABT-shaped current-window 合同统一 | 实现 UCIS generation 1：16 原语、typed effect IR、Python/GDScript compiler、唯一 window owner、797 卡/730 effect 目录编译、394/394 legacy callsite 收口、property/composition/live/性能门和 Forge 固定 SDK；729 个 usable effect 全闭包，1 个动态未登记能力显式 unsupported | DONE | `docs/13-KAGGLE-GRADE-DEVELOPER-AND-ENGINE-PARITY-DESIGN.md`、PtcgDAP `evidence/ptcgdap/ucis/ucis_catalog_qualification_v1.json` |
| T26 | UCIS 已实现但开发者仍需手写 raw 数字/稀疏 shape，模板和 Marnie demo 未演示最新精确数量与 fresh rebind 路径 | 增加 generation-locked 无依赖 runtime SDK、`ucis catalog/inspect/walkthrough`、合法标准窗口模板、工作区上手卡和可执行 demo；标准 demo 同时验证 exact-count、reorder、repeated assignment、公开 prize/energy facts 与 unknown fail-closed | DONE | `docs/15-UCIS-SDK-DEVELOPER-GUIDE.md`、`tests/test_ucis_runtime_sdk.py`、`evidence/demo-workflow-green.json` |

完成规则：只有证据文件和外部状态都可复核时才能把 `PENDING` 改为 `DONE`；不能仅因代码已写就关闭。
