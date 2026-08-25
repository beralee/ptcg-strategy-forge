# 明确限制

以下是当前产品/权限边界，不是可以在独立工具包中伪造关闭的工程 TODO：

- 支持平台为 Windows x86_64 / Godot 4.6.1；Android 尚未进入作者策略自助路径。
- scaffold 默认基于 Marnie 模板，并支持五套已审核 18.0 精确本地 UID 牌组（800018501、800017097、800018499、800018509、800018502）；名单外牌组仍需先完成精确卡牌身份、卡源、卡效和规则审查。
- 玛俐、沙奈朵、多龙和 N 的索罗亚克仍编译 restricted IR v1 可表达的公开当前窗口部分；猛雷鼓已升级 Competitive Policy IR v2，可执行精确数量、逐次语义分配、目标公开能量/ready/debt、奖赏时钟、投影伤害和 field-slot 换位。任意跨窗口条件图与未知公开派生仍保留在蓝图能力边界并 fail closed。
- sealed compiled fast path 已把固定重放加速 21.6×，但它不等于策略强度非劣。当前回滚基线 Round 41 的 fresh 100 为 42%；Round 43/44 的 fresh 100 为 41%/40%，证明局部分数修复不能收敛。`route_candidates` 整回合裁决已通过合成和双运行时合同测试，但尚未完成全量架构回归、性能门或新一轮强度 benchmark；当前不能声称数据包已达到内置经典策略水准。
- `route_candidates.resource_budget` 对 Supporter、手贴、撤退和公开 bench capacity 做当前可用性 gate；`ability_uses`、`discard_cards`、`search_cards` 当前只参与作者声明的机会成本，不是未来动作一定可用的引擎证明。
- `.ptcgai` 使用 `godot_local_card_uid_v1`，`cabt_exportable=false`；它不是 Kaggle/CABT `.tar.gz` 或竞争服务 `.ptcgbot`。
- 开发构建使用公开 test-fixture Ed25519 材料，`execution_trusted=false`、`production_ready=false`。
- 平台 production 签名、release approval、玩家启动、device canary、A5 和信任根由产品维护者控制。
- `publish` 只提交 release，不自动批准或晋升。
- UCIS 目录资格证明每个声明可用的私有卡牌 effect 使用同一 CABT-shaped current-window 操作合同；它不证明全部卡牌规则结果、官方完整卡池或官方 CABT engine parity。
- 九类双引擎 whole-battle operation 回执只证明当前窗口入参、ordered semantic options 和双方接受的 indexes；不声明提交后的 state/log、伤害、KO、随机或终局一致。
- 当前 730 个 effect 中有 1 个动态未登记能力显式 unsupported，不进入 729 个可用 effect；Search capability 仍为 `none`。
- Python 是开发工具依赖，不是 PtcgDAP 玩家设备运行时依赖。
- OS 级断网证据不由本项目声明；本地开发流程本身除发布外不发起网络请求。
- `.ptcgbot` v2 当前只有 developer-local runner/qualification。按项目负责人决定，本地 user-private oracle 研究不再以外部授权作为技术暂停条件；但官方 bundle 仍不复制、不发布、不上传、不进入 Forge SDK 或公共托管服务，official native clock/Search 和服务端排名资格也未声明。
- Godot core selection A1 的 exact scope 为 `55D3F6B8…9086C`，Search=none、时间为 Godot development profile；它不是完整 official API。
- 私有 ID 的 setup-active 窄合同和九类 whole-battle operation input/index 合同均已通过：55 个唯一 card UID、36 个 attack identity 的 sealed relation、17 种 Option wire shape 静态投影，以及精确搜索/数量、source→target 分配、能力、攻击、伤害分配、撤退/换位、进化和特殊状态的双引擎 live witness。它们只证明声明窗口的入参、有序语义 option 和返回 index 被两端接受；bootstrap、提交后的 state/log/next checkpoint、damage、KO、RNG 和 terminal 仍未比较或声明。不要求 official deck/Card ID equality，也不声称 raw callback byte equality、官方认证或全卡池规则一致。
- 五套 18.0 的完整规则结果 A3 仍保持 `a3_promoted=false`。项目负责人当前验收只要求对应卡操作入参/返回值匹配；伤害、KO、随机、终局、46 项 card/effect boundary scenario、四条 multi-window chain 和 25 个 ordered pair/有界探索属于独立后续范围，不由 input/index 合同冒充。
