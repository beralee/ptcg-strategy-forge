# Changelog

## 2026-08-25 — UCIS generation 1

- 新增 16 原语的 Unified Card Interaction Standard、typed effect IR、Python/GDScript compiler、唯一 current-window owner，以及 797 张卡/730 个 effect 的目录编译和资格门。
- 将 394/394 个旧 interaction builder callsite 收敛到 UCIS；目录达到 unregistered、author-visible legacy、custom prompt、dual authority 和 silent fallback 全零。729 个 effect 声明可用，1 个动态未登记能力显式 unsupported。
- Forge SDK 固定目录/运行时/覆盖/迁移/性能/operation 回执；`doctor` 和 `check` 在运行作者工作区前验证回执链。预编译窗口热路径 10,000 次动态审计未读取磁盘、扫描全卡表或调用子进程。
- 签发九类 official-vs-Godot whole-battle operation input/index 代表性回执；完整规则结果 A3、Search、production/device 和官方认证仍保持独立且未声明。
- 当时新增 generation-locked、无依赖 UCIS runtime SDK 和 `forge ucis catalog/inspect/walkthrough`；历史 `.ptcgbot` 工作区曾自动获得命名化窗口、精确数量、semantic rebind、NUMBER/YES_NO、fallback、奖赏时钟与能量债务 helper。
- 当时更新 Marnie 与历史 competition demo：移除非标准/错配窗口，加入可执行 SDK walkthrough，并把 SDK GREEN 纳入标准 `forge demo` 验收和开发者文档。

## Unreleased

- 新增开发者可查询的支持卡牌快照 `data/developer/supported-cards-v1.json`；它从已资格化 UCIS catalog 机械生成，列出 797 个本地 UID（796 usable、1 explicit unsupported）的交互状态、effect/capability 和源 hash。新工作区 exact-copy 为 `SUPPORTED-CARDS.json`，生成器 `--check`、`doctor` 和回归测试阻止漂移；文档明确交互可用不等于官方完整规则结果、策略模板或跨平台批准。
- 根据一次真实开发者注册→构建→公钥登记→签名→上传流程收紧首发文档：正式工作区必须原样使用后台完整 `developer_id`（包括 `developer-` 前缀），并显式选择独立的短 `package_id`；发布指南新增仓库外密钥、只登记公钥、key ID/指纹/SHA 联合核对、`package_signature_untrusted` 身份前缀排查，以及“已接收/等待资格验证”状态边界。同步增加常见私钥扩展与本地 artifacts 的 Git 忽略防线和文档回归测试。
- 重构面向开发者的交付界面：新增 `forge workspace create/status/inspect/check/build/install/model` 统一生命周期，以及公开 `StrategyWorkspace`/`WorkspaceModel` Python SDK。新入口提供约定默认身份、机器可读 readiness/编辑入口/默认产物/下一步、安全替换 Actor、从严格场景经 public firewall 生成固定张量；旧低层 CLI 保持兼容。README、Quickstart、生成工作区指南、开发者中心、SDK 参考、架构、安全、排障和验收文档统一到工作区心智模型。
- 实现统一 `.ptcgai` 规则与模型开发链：保留 v1 exact 兼容，v2 提供 `rules_only`/`rules_with_model`，Forge 新增规则/模型 scaffold、ORT inspect/import/tensorize/conformance、模型 build/check/install 闭环；Godot Host 通过平台原生 CPU ORT 在 Base 的 hard tier/veto 后受控评分，带 25ms 可取消 deadline、公开张量、当前窗口重绑定和规则/Base fallback。最小 BC→离线 contextual-bandit RL Actor 已在 Windows x86_64 真实 Godot 对局运行；macOS 两架构只有构建入口，尚未声明实机或 production 通过。活动 CLI 已移除 `.ptcgbot` 路径，历史实现仅作不可执行审计记录。
- 新增连续联赛开发者签名闭环：`release-key` 在仓库外生成不可覆盖 Ed25519 密钥，`release-build` 构建账号已登记签名包，`release-resign` 对严格验证的现有 `.ptcgai` 只替换签名并证明 payload 原字节保持不变。公钥 key ID 与服务端派生规则一致，JSON 报告不输出私钥；作者签名不冒充平台 production 批准。
- 将“玛俐的礼盒”晋级到 R53 `5.13.0`：庞克泵感按每只场上玛俐宝可梦恰好 2 能计算并禁止超填；雪妖女、愿增猿资源/转伤和奇树干扰在非终结攻击前完成；后期含羞苞不再抢送出，但也不再从前台被无条件硬撤；诈唬魔/捣蛋小妖只有在没有长毛巨魔候选时才抢养成位。Forge 121/121、Godot 18 exams 两轮 180/180；固定同 seed/换座 100 局为 43–57，相对 1.9.0 的 31–69 提升 12pp，100/100 回放接受且 invalid/error/fallback/rejection 全零。
- 完成 18.0 阿响的火暴兽 `800018880` 对精确玛俐礼盒 `646600@1.8.0` 的 R0–R10 十轮真实 Godot 回放优化。R5 `0.6.0`（88 score + 6 count rules）以 28/28 Forge 场景、确定性双构建和 SHA-256 `26AD9CC…1F1FD` 冻结；固定同 seed/换座 20 局由 R0 5–15 提升到 8–12（25%→40%，+15pp），R7 回退被拒，R6/R8/R9/R10 同分未晋级。独立 fresh 100 局为 28–72（Wilson 95% 20.14%–37.49%），100/100 正常终局与公开回放接受，10,657/10,657 调用成功且 invalid/error/classic-or-same-window-fallback/rejection 全零。exact Godot 门、审核 Owner 与 BattleSetup 可见/可选/可开局通过；只声明 Windows 本地开发证据，不声明 production、官方 CABT parity 或统计显著优势。
- 升级“玛俐的礼盒”至 1.9.0：复盘真实录像 `match_20260827_234816_561101`，修复庞克泵感把 `assignment_source` 误认成 `search` 而只填 1 能量、愿增猿按场上数量而非当前合法能力数规划且反复铺向可治疗吉雉鸡、210 伤害非致死时抢跑、暗影子弹后排目标窗口类型错配，以及反击捕捉器/老大未优先本回合精确两奖击倒。新增叶伊布 ex 后排 100 治疗 capability、当前合法愿增猿计数、集中击倒与精确 gust 事务、子窗口开发轨迹记录；95 条 score 规则、5 条 count 规则、5 个事务、94/94 strict 场景，确定性归档 SHA-256 `BDC7C096…3DB20`，exact Godot 1.9.0 绑定和公共伤害规划回归通过。同种子/换座 20 局 package-only A/B 为 1.8.0 6–14、1.9.0 7–13，40/40 合法终局与回放接受；只声明行为修复且未观察到回退，不声明小样本强度提升。
- 升级“玛俐的礼盒”至 1.8.0：依据牌组 `646600` 的当前原始响应恢复 4 张派帕与 2 张深钵镇，移除误置的 4 张阿响的冒险与 2 张桌台市；保留经审核的 `CSV7C_057 → CSV9.5C_043` 雪童子本地等价映射。新增派帕道具/宝可梦工具分窗口检索、深钵镇铺场顺序，并根据败局轨迹将老大的指令/反击捕捉器改为只在前场实际可攻击时消耗。91/91 严格场景、确定性双构建与 exact Godot 包绑定通过，最终 SHA-256 `209FA7ED…DFD1`。
- 为“玛丽的礼盒”实现 `public_damage_plan_v1` 与 `semantic_transaction_v1`：可信效果 capability registry、稳定公共 Pokémon 序号、两攻击窗口伤害规划、隔离的跨回合事务日志、审计哈希和旧 Host fail-closed；同步 Forge SDK schema/profile/golden vectors 与 Godot Host。
- 历史 1.7.0 候选在 Rule 18.0 玛俐长毛巨魔对局上完成 R4–R7、87/87 严格场景和确定性构建，但后续源锁复核发现其牌表把 4 张派帕/2 张深钵镇误替换成阿响的冒险/桌台市。因此 SHA-256 `4074CB81…D80E5` 只保留为可回滚的历史证据，原 13–7 不再作为精确 `646600` 构筑基线。
- 关闭伤害规划每窗口反复规范化、校验和深拷贝 419 KB capability registry 的性能 Block：加载期一次性编译并按 exact policy/registry hash 密封，失配 fail closed，且不缓存窗口、索引或旧评分。两局实战决策 P95 从 `1111.618 ms` 降至 `51.442 ms`，精确包级两次 100 样本 P95 为 `6.930/7.003 ms`。
- 最终固定 20 局为 13–7（65.0%，Wilson 95% 43.29%–81.88%）；20/20 合法终局与公开回放通过，924/924 调用成功，invalid/error/rejection/classic/stale 全零。该结论只覆盖约定的固定快速侦察，不声明 production、官方 CABT 全规则 parity 或广泛统计优势。

- 根据 1.3.0 的 200 局公开录像补做并发布支援者阶段曲线 1.4.0：奇树规则不再等待太晶珠/捕虫套装/宝可领航员入口全部消失，无就绪攻击手且存在能量债务时可在前中期主动重启；对手进入三奖以内且我方仍有至少三奖时增加后期压手线。裁判移除对手手牌数硬门，只保留前六回合、对手至少四奖、我方攻击时钟落后的干扰线，并在对手三奖以内计负分。最终为 67 score + 6 count rules、31/31 strict 场景、双构建 SHA-256 `3B4E78A1…DFFB8`；exact 包已登记 PtcgDAP Windows development gate，当前 Ogerpon 26/26、serial registry 21/21。同 seed package-only A/B 为 1.3.0 77–23、1.4.0 73–27（-4pp），fresh 1.4.0 为 77–23；两组 1.4.0 共 150–50、8,336/8,336 calls、200 replay/18,740 帧全绿。实际奇树 45、裁判 63，裁判全部为前中期目标形态；行为问题关闭但胜率不宣称提升，1.3.0 保持回滚版本。首次 fresh 脏局另关闭了引擎复用 PokemonSlot 容器时的 Host 实体换根 bug，脏批次未计入胜率。
- 针对真实厄诡椪／岩殿居蟹玩家录像完成新的支援者三轮迭代：R1 让 6 手牌但无成型攻击线时使用奇树；R2 以公开奖赏时钟和对手大手牌驱动裁判干扰并加入重排/单事实翻转；R3 移除所有正向 `end_turn` 规则，把危险进化与能量转移改为否决错误动作。最终 1.3.0 为 65 score + 6 count rules、26/26 strict 场景、双构建 SHA-256 `B8134330…C40CA`。经用户显式授权，exact bytes 已登记并内置到 PtcgDAP Windows development gate；focused 17/17、BattleSetup 与真实 Host 通过。同 seed 100 局从 75–25 到 77–23，新 seed 为 74–26；两组 7960/7960 policy calls 成功、200/200 replay 独立复核 0 差异，公开状态变化确认实际打出裁判 50 次、奇树 6 次。仍不声明 production、官方 CABT parity 或统计强度保证。
- 完成 Kaggle v5.23a 厄诡椪／岩殿居蟹 `800052301` 的精确 Godot 18.0 迁移：60 卡/19 printing 来源锁、Competitive v2 策略蓝图、R0–R3 三轮录像驱动优化、65 score + 6 count rules、21/21 strict 场景和确定性 final 1.0.0 `.ptcgai`。
- 在 owning layer 关闭真实 Host frame、异构 replay identity、effectively-KO frontier、assignment source/effect continuity、Energy Switch UCIS、超 64 rule IR preflight 与同步 double-mulligan pending authority 等 Block；最终独立新 seed 20×5 为 75–25，3995/3995 policy calls 成功，100/100 录像 hash/envelope/frame chain 复核一致，且本地 BattleSetup 可选择并开战。
- 历史实现 Kaggle 风格 `.ptcgbot` v2 developer toolchain：严格 schema/vectors、canonical ZIP、单一 Bundle owner、RPC/runner、Forge competition CLI、exact CPython 3.11.13 runtime lock、公开 trace、fault/privacy probes 和开发预资格；该方向现已被统一 `.ptcgai` 设计取代，保留为历史记录。
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
