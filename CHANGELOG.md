# Changelog

## 2026-08-25 — UCIS generation 1

- 新增 16 原语的 Unified Card Interaction Standard、typed effect IR、Python/GDScript compiler、唯一 current-window owner，以及 797 张卡/730 个 effect 的目录编译和资格门。
- 将 394/394 个旧 interaction builder callsite 收敛到 UCIS；目录达到 unregistered、author-visible legacy、custom prompt、dual authority 和 silent fallback 全零。729 个 effect 声明可用，1 个动态未登记能力显式 unsupported。
- Forge SDK 固定目录/运行时/覆盖/迁移/性能/operation 回执；`doctor` 和 `check` 在运行作者工作区前验证回执链。预编译窗口热路径 10,000 次动态审计未读取磁盘、扫描全卡表或调用子进程。
- 签发九类 official-vs-Godot whole-battle operation input/index 代表性回执；完整规则结果 A3、Search、production/device 和官方认证仍保持独立且未声明。
- 新增 generation-locked、无依赖 UCIS runtime SDK 和 `forge ucis catalog/inspect/walkthrough`；`.ptcgbot` 新工作区自动获得命名化窗口、精确数量、semantic rebind、NUMBER/YES_NO、fallback、奖赏时钟与能量债务 helper。
- 更新 Marnie 与 competition demo：移除非标准/错配窗口，加入可执行 SDK walkthrough，并把 SDK GREEN 纳入标准 `forge demo` 验收和开发者文档。

## Unreleased

- 实现 Kaggle 风格 `.ptcgbot` v2 developer toolchain：严格 schema/vectors、canonical ZIP、单一 Bundle owner、RPC/runner、Forge competition CLI、exact CPython 3.11.13 runtime lock、公开 trace、fault/privacy probes 和开发预资格。
- 生成 CABT 11/49/17/12/12/5/24 census 与 Prompt/Lifecycle matrices，实现三类 hash、immutable one-shot window、exact setup/mulligan、per-seat logs、Search=none/time profile，并把 exact core selection A1 scope `55D3F6B8…9086C` 绑定到 runtime/build/qualification receipt。
- 在 PtcgDAP 实现五牌组 A3 scope/closure generator、唯一 RandomEventPort 与 conditioned tape、双 adapter 协议、evidence-only semantic entity relation、lockstep/first-divergence/minimizer、Python/Godot 六类 mutation canary、46 项 capability coverage、25 配置资格账本以及独立 review/rollback receipt owner。
- 按项目负责人最终范围，以 PtcgDAP 私有 UID 为权威，不再要求五套牌或 Card ID 与官方列表逐项相等；官方 raw callback 与 Godot private frame 分域留证，缺失/歧义对应关系 fail closed。
- 完成 event-driven Godot adapter、一次性外部决策端口、正式 owner/engine executor 接线和 `YES_NO/IS_FIRST` 开局窗口；RandomEventPort 记录 source card/attack/effect/phase/pre-state context。
- 建立 55 个唯一对应卡、36 个攻击 identity 的 sealed bridge，覆盖 17 种 Option wire shape 的静态双运行时投影和 Host shape 校验；一条 source-locked 对应卡的 setup-active（live type 3）current-window 入参、唯一 option 和返回 `[0]` 接受一致，串行重复 5/5，签发窄范围 `setup_active_corresponding_card_input_index_contract`。bootstrap prefix、稳定公开转移和下一窗口明确 `not_claimed`；主阶段其余类型/交互尚未获得双引擎 live witness，不能扩写为整场操作对齐。
- 完整五牌组 full-rule A3 仍固定 `a3_promoted=false`；按项目负责人最新范围，它是独立后续目标，不阻断对应卡 whole-battle input/index 合同，也不由后者冒充。

- 增加根级 `AGENTS.md`，把 PtcgDAP 的当前窗口、重观察、Base authority、攻击窗口和信息纪元原则转为本项目研发规范。
- `new` 生成工作区 README 与 `STRATEGY-BLUEPRINT.md`，帮助作者从牌组思路建立可验证规则和场景。
- 增加 `check` 一键验收：确定性双构建、严格 Host-path 校验、完整场景套件和成功后原子输出。
- 补充策略思考与工作区验收文档，并将新增研发体验缺口纳入 TODO 闭环。
- 增加五套已审核 18.0 精确牌组的 `new --deck-id` 工作区生成器、逐牌来源锁、专用蓝图/adapter 和标准 10 场景证明矩阵。
- 交付五个确定性 `.ptcgai`，并记录 PtcgDAP 本地目录发现、受限 IR 执行、精确牌组绑定和战斗准备界面可开战证据。
- 增加 Competitive Policy IR v2，保持官方 `agent(raw_observation) -> list[int]` 不变，同时支持精确合法子集、逐次语义分配、公开目标能量/攻击就绪/资源债务、奖赏时钟、投影伤害与安全整数评分。
- 将 Python reference runtime、Godot Host/runtime、合同向量和 SDK 来源锁同步；Base 仍独占合法性、forced/terminal、hard tier、veto、cardinality、fallback 与最终提交。
- 用 18.0 猛雷鼓厄诡椪完成三轮包侧优化：最终 89 条规则、10 条数量规则、21/21 strict 场景；同种子 100 局对经典 GDScript 为 37–63（相对 8% 基线 +29pp），执行审计 5784/5784 成功、0 非法、0 拒绝。
- 增加 Competitive v2 sealed compiled fast path，把完整 policy 验证移到加载期，并缓存公开事实、拆分 frame/option 条件、按 option kind 分桶；相同重放 236647 ms→10958 ms，平均决策 819.485 ms→26.211 ms，语义一致性和未知 hash fail-closed 回归通过。
- Host 现在把 field-slot 换位也发布为作者当前窗口；Prime Catcher 的对手换位和己方强制换位分别映射为 `opponent_switch/attack_target` 与 `self_switch/send_out`，Base 继续复验合法性。
- 猛雷鼓回滚基线推进到 Round 41（SHA-256 `5DEEC950…57A`），fresh 100 为 42%；Round 43/44 虽修复代表轨迹，fresh 100 退化为 41%/40%。据此冻结单卡分数优化，将 owning layer 明确为整回合多路线裁决。
- Competitive v2 新增向后兼容的 `route_candidates`：公开资源预算、六维词典序 route value、当前第一步 authority、稳定拒绝原因和 Base 应用审计。资源/奖赏时钟 metamorphic flip、option reorder、mandatory/terminal/tier/veto 和 Python/Godot audit hash 一致性均有测试；官方 agent 接口保持不变。

## 0.1.1 - 2026-08-23

- 修复英文 Windows `cp1252` 控制台无法输出中文 JSON 报告的问题。
- 增加 legacy code-page 回归测试，并在相同严格编码条件下完成完整 demo 验证。

## 0.1.0 - 2026-08-23

- 创建独立的 PTCG Strategy Forge 项目和统一 `forge.py` 命令入口。
- 固定并校验 276 个 PtcgDAP SDK、合同、牌组与工具文件。
- 提供创建、构建、校验、模拟、套件测试、安装和发布工作流。
- 提供完整 Marnie RED→GREEN demo、10 个严格场景和确定性 release 包。
- 完成真实本地 HTTP release 提交验证。
- 增加 Windows 环境脚本、开发者文档、安全测试和 GitHub Actions。
