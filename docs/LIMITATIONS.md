# 明确限制

以下是当前产品/权限边界，不是可以在独立工具包中伪造关闭的工程 TODO：

- 当前可执行支持平台为 Windows x86_64 / Godot 4.6.1。统一 `.ptcgai v2` 的 Forge、原生 CPU ORT、安装和真实 Godot 对局门已在该平台通过；macOS arm64/x86_64 只有构建配置和脚本，尚无实机安装、对局、回放或跨平台审计证据。Android 仍是独立晋升范围。
- scaffold 默认基于 Marnie 模板，并支持八套已审核精确本地 UID 牌组（800018501、646600、800017097、800018499、800018509、800018502、800018880、800052301）；名单外牌组仍需先完成精确卡牌身份、卡源、卡效和规则审查。工作区创建只复用已固定身份和场景起点，不自动继承历史策略的强度或平台声明。
- 玛俐、沙奈朵、多龙和 N 的索罗亚克仍编译 restricted IR v1 可表达的公开当前窗口部分；猛雷鼓已升级 Competitive Policy IR v2，可执行精确数量、逐次语义分配、目标公开能量/ready/debt、奖赏时钟、投影伤害和 field-slot 换位。任意跨窗口条件图与未知公开派生仍保留在蓝图能力边界并 fail closed。
- sealed compiled fast path 已把固定重放加速 21.6×，但它不等于策略强度非劣。当前回滚基线 Round 41 的 fresh 100 为 42%；Round 43/44 的 fresh 100 为 41%/40%，证明局部分数修复不能收敛。`route_candidates` 整回合裁决已通过合成和双运行时合同测试，但尚未完成全量架构回归、性能门或新一轮强度 benchmark；当前不能声称数据包已达到内置经典策略水准。
- `route_candidates.resource_budget` 对 Supporter、手贴、撤退和公开 bench capacity 做当前可用性 gate；`ability_uses`、`discard_cards`、`search_cards` 当前只参与作者声明的机会成本，不是未来动作一定可用的引擎证明。
- `.ptcgai` 使用 `godot_local_card_uid_v1`，`cabt_exportable=false`；它不是 Kaggle/CABT `.tar.gz`。旧 competition `.ptcgbot` 已退出下一代目标，不能通过改扩展名或沿用资格迁入游戏。
- 当前 `.ptcgai` 可执行 v1 规则包，以及 v2 `rules_only`/`rules_with_model`。v2 模型使用固定公开整数张量和冻结 ORT Actor，并只能在 Base 已允许的当前候选域内评分；现有可选 `weights.bin` 不会被重新解释为学习模型。Windows 证据不自动证明 macOS、Android 或 production。
- 开发构建使用公开 test-fixture Ed25519 材料，`execution_trusted=false`、`production_ready=false`。
- 平台 production 签名、release approval、玩家启动、device canary、A5 和信任根由产品维护者控制。
- `publish` 只提交 release，不自动批准或晋升。
- UCIS 目录资格证明每个声明可用的私有卡牌 effect 使用同一 CABT-shaped current-window 操作合同；它不证明全部卡牌规则结果、官方完整卡池或官方 CABT engine parity。
- 九类双引擎 whole-battle operation 回执只证明当前窗口入参、ordered semantic options 和双方接受的 indexes；不声明提交后的 state/log、伤害、KO、随机或终局一致。
- 当前 730 个 effect 中有 1 个动态未登记能力显式 unsupported，不进入 729 个可用 effect；Search capability 仍为 `none`。
- Python 是开发工具依赖，不是 PtcgDAP 玩家设备运行时依赖。
- `StrategyWorkspace.status=ready` 只证明工作区结构与可选 Actor conformance 可进入开发，不等于 `check`、Godot 实战、设备门或 production 通过；Python SDK 也不增加包的运行 authority。
- OS 级断网证据不由本项目声明；本地开发流程本身除发布外不发起网络请求。
- 历史 `.ptcgbot` v2 只有 developer-local runner/qualification；活动 CLI、安装与运行期已经退出，残留源码、合同和测试只保留原 scope 的审计价值。它不再接受新资格，也不证明 `.ptcgai` 模型、Godot/macOS、official native clock/Search、服务端排名或 production。
- Godot core selection A1 的 exact scope 为 `55D3F6B8…9086C`，Search=none、时间为 Godot development profile；它不是完整 official API。
- 私有 ID 的 setup-active 窄合同和九类 whole-battle operation input/index 合同均已通过：55 个唯一 card UID、36 个 attack identity 的 sealed relation、17 种 Option wire shape 静态投影，以及精确搜索/数量、source→target 分配、能力、攻击、伤害分配、撤退/换位、进化和特殊状态的双引擎 live witness。它们只证明声明窗口的入参、有序语义 option 和返回 index 被两端接受；bootstrap、提交后的 state/log/next checkpoint、damage、KO、RNG 和 terminal 仍未比较或声明。不要求 official deck/Card ID equality，也不声称 raw callback byte equality、官方认证或全卡池规则一致。
- 五套 18.0 的完整规则结果 A3 仍保持 `a3_promoted=false`。项目负责人当前验收只要求对应卡操作入参/返回值匹配；伤害、KO、随机、终局、46 项 card/effect boundary scenario、四条 multi-window chain 和 25 个 ordered pair/有界探索属于独立后续范围，不由 input/index 合同冒充。
