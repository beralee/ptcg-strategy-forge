# Kaggle 级社区策略开发、CABT 接口对齐、统一卡牌交互规范与引擎一致性详细设计

## 0. 文档控制

| 字段 | 值 |
|---|---|
| 文档状态 | `implemented / UCIS catalog scoped pass / representative whole-battle operation input-index pass` |
| 日期 | 2026-08-25 |
| 适用仓库 | `ptcg-strategy-forge`、`PtcgDAP`；`ptcgabc` 只读 oracle |
| 目标工作 | W1 Kaggle 式开发包与 SDK；W2 CABT observation/select/window A1 与统一卡牌交互规范；W3 五套 18.0 代表性向量及独立 A3 |
| 非目标 | 不部署服务、不开放外部作者、不改变 `.ptcgai` 生产权限、不修改只读 `ptcgabc` oracle |
| 公共策略边界 | official: `agent(raw_observation) -> list[int]`; Godot: `agent(standardized_cabt_projection) -> list[int]` |
| 当前权威声明 | `.ptcgbot` v2 developer-local 工具链和 Godot core selection A1 scoped pass 保持有效；UCIS generation 1、全卡目录 closure、729 个声明可用 effect、394/394 legacy callsite 单一 UCIS authority、性能门和九类代表性 whole-battle operation input/index 已签发精确回执；1 个动态未登记能力显式 unsupported 且不进入可用集；完整规则结果 A3、production、Android/device 与官方认证不在当前声明中 |

本文是三项工作的实施级主设计。它把“开发者像参加 Kaggle 一样写 Python 策略”“本地 Host 逐窗口精确控制”和“Godot 规则结果与官方 native engine 一致”拆成三条独立证据链。任何一条通过都不能替代另外两条。

### 0.1 项目负责人最终范围决定（规范性，覆盖旧的 W0/official-ID 假设）

本项目是独立开源、学习研究用途。项目负责人已明确决定：本地私有 oracle 的研究比较不以取得“官方授权”作为本工程的技术暂停条件；但官方 binary/source/card-data 仍不进入开源发行物、Forge SDK、公共 evidence 或托管服务。该决定是项目范围和证据分域约束，不是官方背书或法律结论。

卡牌身份以 PtcgDAP 私有 identity scheme `set_code + "_" + card_index` 为权威。无需满足以下条件：

- 五套牌与官方 Card ID 列表逐项相等；
- 五套牌是官方 exact ordered 60；
- 私有卡牌 ID 与官方数字 ID 相等；
- 私有卡表完全覆盖官方卡表。

对于两侧确有同一对应 printing/effect surface 的卡牌，必须建立显式、来源锁定、缺失即失败的 correspondence bridge。跨引擎只比较当前卡牌操作合同：

```text
当前 acting seat
+ select type/context/min/max/remain
+ ordered semantic options
+ 策略返回且由两端接受的当前窗口 indexes
```

项目负责人当前验收只要求上述 operation input/index surface。bootstrap prefix、提交后的规则状态转移、日志、下一 checkpoint、伤害、KO、随机和终局属于独立 full-rule A3；除非另有逐项证据，不得从 index acceptance 推导这些结果一致。

官方原始 callback 与 Godot 私有 frame 分别保存，不要求也不声称 byte-equal。官方数字 ID 及 private bundle locator 只进入 ignored trusted-private evidence；公开 evidence 只保留 hash、数量、结论与 non-claims。

W3 因此拆成三个独立资格：

1. `setup_active_corresponding_card_input_index_contract`：只覆盖 setup-active 的 current-window 入参、合法 option 语义和返回 index 被两端接受；不要求整副官方 deck identity，不声明提交后的稳定公开转移。该窄切片已经签发。
2. `corresponding_card_whole_battle_input_index_contract`：覆盖对应卡在实际对战中可达的主阶段选择窗口，包括精确搜索/数量、source→target 分配、能力、攻击、伤害分配、撤退/换位、进化和特殊状态。每类必须有合法前缀与双引擎 live witness；17-type 静态投影不能替代。九类已通过并由 `corresponding_card_whole_battle_input_index_v1.json` 签发；该回执仍不声明提交后的规则状态。
3. `research_private_id_corresponding_card_a3`：五套牌所有可达卡效、伤害、KO、随机与终局结果的完整规则 A3。它是独立后续资格，不是项目负责人当前“只验操作入参/返回值”范围的完成门，也不得由任一 input/index 合同冒充。

本地研究不设置外部批准门；“必须 exact official 60/60”只适用于另行定义的 official-ID/deck-identity certification 分支，不阻断私有 ID 对应卡 input/index 合同。official runtime/card-data 的复制、发布或托管仍是不同产品范围，不能由本地研究结论自动获得权限。

### 0.2 架构方向修订：身份私有，交互协议标准化（规范性）

PtcgDAP 不再以“每张卡各自定义一套私有 prompt/frame/返回协议”为长期架构。所有产生玩家选择的卡牌、攻击、特性和规则效果，都必须实现同一套 **Unified Card Interaction Standard（UCIS）**，再由唯一的 Selection Window owner 投影为当前锁定 CABT generation 的标准 `select.type/context/min/max/remain + ordered options`。策略返回值始终只是当前 immutable option list 的 `list[int]`。

该决定严格分开三个平面：

| 平面 | 权威 | 规范性结论 |
|---|---|---|
| 身份平面 | PtcgDAP 私有 `set_code + "_" + card_index`、match-local entity lineage | 不改成官方数字 Card ID；跨引擎时只通过 source-locked correspondence bridge 建立语义关系 |
| 交互平面 | 锁定 official source census + UCIS generation | 每张卡只能声明标准 typed interaction primitive/program；不得自定义 author-visible 字段、context 数字、option shape、数量编码或返回格式 |
| 规则执行平面 | PtcgDAP engine legality、effect resolver、DecisionPort | 卡牌提供效果参数与语义意图；引擎拥有合法性、候选生成、顺序、current-window binding、一次性提交、自动结算和 reobserve |

“与官方形状一致”指当前锁定 generation 的操作入参、字段 presence、ordered option 语义、数量编码、chooser 和 index acceptance 可建立证据；不指两侧对象、私有 UID、原始 JSON bytes 或完整规则结果天然相同，也不构成官方背书。

旧的卡牌私有协议只允许作为迁移输入存在于引擎内部兼容层，不能继续成为策略 SDK、`.ptcgai`、`.ptcgbot`、公开 evidence 或新卡实现的合同。迁移完成后必须以目录级 gate 证明“零卡牌自建 prompt、零私有 wire 外泄、零旧协议双重 authority”，而不是通过人工逐张验收来获得总体架构结论。

本段记录规范形成时的架构决定；其后实现与资格状态以 §13 的精确回执为准，不能仅凭本文文字提升声明等级。

---

## 1. 结论与核心决策

最终产品保留两个严格分域的策略制品：

| 制品 | 执行位置 | 表达能力 | 安全模型 | 身份域 |
|---|---|---|---|---|
| `.ptcgbot` | CABT 比赛/开发 Runner 的隔离 Python runtime | 可执行 Python、有限本地资源、状态机、搜索或模型 | 第三方代码沙箱；本设计只覆盖包和本地 SDK，不关闭生产沙箱 | official CABT Card ID / Attack ID / serial |
| `.ptcgai` | 玩家 Godot 设备 | data-only restricted/competitive IR | 无任意作者代码；Host/Base 最终裁决 | Godot local UID 或受审 official domain |

不得把 `.ptcgbot` 直接安装到玩家游戏，也不得把 `.ptcgai` 的有限表达力描述成 Kaggle Python 自由度。未来若需要把比赛策略带到玩家设备，必须生成新的 `.ptcgai` release，并以独立的行为一致性、签名和设备证据绑定；比赛名次本身不授予玩家执行权。

本设计接受以下架构决策：

1. `.ptcgbot v2` 使用确定性、多文件、纯 Python 源码加不可执行资源的包格式；首版不允许作者携带 native wheel、DLL、EXE、安装器或比赛时动态安装依赖。
2. Python 依赖由冻结 runtime profile 预装，profile 固定 Python ABI、SDK、依赖集合、资源限制和 capability；包不能自我扩大权限。
3. official native lane 将官方 acting-seat raw callback 作为权威输入；Godot lane 只能合成已声明、已认证的 CABT 字段，绝不猜测未知字段或伪造 Search token。
4. 每个玩家决策都必须由同一 immutable current-window 生命周期承载；策略只返回当前有序 option 的 index。
5. W2 关闭接口 A1；W3 只在固定 Card ID/规则/随机能力范围内关闭 A3。A1 与 A3 分开报告。
6. 五套 18.0 牌组是首个私有 ID 对应卡研究范围。operation input/index 合同只要求每个纳入声明的本地 printing 具有显式、source-locked、非名称猜测的官方对应关系；exact official 60-card deck 与全 Card ID equality 仅属于更高层 full-rule/official-ID certification 分支。本地 deck ID 或显示名本身不构成对应证据。
7. 排名资格要求策略在相同 observation transcript 上可重放确定；允许开发态探索非确定策略，但不得进入 `official_verified` 分母。
8. `search_begin_input` 是显式 capability。official lane 可在 profile 开启时透传当前 callback 的 opaque token；Godot 默认 `none`，绝不生成替代 token。
9. UCIS 是 PtcgDAP 所有卡牌交互的唯一标准：`CardEffectSpec -> InteractionProgram -> InteractionStep -> SelectionWindow`。卡牌实现不得直接构造策略 frame、调用 Host、持有 option index 或执行 engine action。
10. official raw enum、sparse field presence、option ordering 和 lifecycle callsite 是标准 wire 的来源权威；UCIS 的领域原语只是编译输入，不得发明第五种数量编码或复合返回命令。
11. 新卡接入以“编译到已认证原语并通过目录 closure”为默认路径；只有 official source census 出现全新的选择形状、数量语义或 lifecycle，才新增 UCIS generation，而不是为该卡加私有特例。
12. 五套 18.0 牌组降为首批代表性 conformance vectors 和真实可达性证明，不再充当 PtcgDAP 全卡牌架构本身。按卡人工场景只用于卡牌特有参数、阈值和规则语义；协议正确性按标准原语、组合与性质测试关闭。

---

## 2. 权威来源与版本锁

### 2.1 来源优先级

冲突时使用以下顺序：

1. 当前本地研究隔离范围内取得的实际 competition callback、native serializer wire 和受审 replay；
2. `PtcgDAP/docs/ptcgdap/SOURCE_LOCK.json` 固定的官方 competition bundle exact bytes；
3. 受审 production module 和 CABT environment schema；
4. 官方 sample submission、`cg/api.py` 的 dataclass/注释；
5. `ptcgabc` Base Graph、packager 和只读本地 oracle；
6. PtcgDAP/Forge 合同和设计；
7. 当前 Godot 行为，仅作为迁移输入，不是官方事实。

当 Python dataclass/注释与 native wire 不一致时，actual callback/serializer 优先。例如 native wire 中存在但 Python dataclass 未声明的字段，必须按 raw golden 处理；不能为了适配 TypedView 删除。

### 2.2 当前固定官方来源

| 来源 | SHA-256 | 用途 |
|---|---|---|
| official bundle manifest | `9728A4409F2D8378F161E6BF33A871186C583CEAD3222372A5C4E092C5CB356C` | 60 个官方文件的来源锁 |
| sample `main.py` | `CD434298FFC02788D8BE9621E576687DA7CDC1FE4BE731E34AD686C6B9D8367A` | 单一 agent 入口 |
| official `cg/api.py` | `593F1298E52A635F90F8F505A52113E9AF114F444C293404E37906F18EE06CED` | observation/select/enum/API |
| native `ApiJson.h` | `FA405A0421AD09FBAE6E3922BD73A0A07333B17790DEA7E8FD90C1B97F326851` | option wire 顺序与稀疏字段 |
| native `ToJson.h` | `84EE63939863493520EBE29E8CA717217EBF90191829EA80D1349942AA867602` | observation wire |
| native `Types.h` | `C5A9AD65B1221FC9B6ED09E5F56C6BD7EC325117CC2247592164ABE698BAD0A8` | native enum |
| CABT environment source | `83966930D12DA5D8F725AC70314BF1B58B842180277437DC4EA7DC6CEEA0D176` | Kaggle callback 生命周期 |

任何实现工作开始前必须重新运行来源漂移检查。发现官方 bundle、production module 或 schema 更新时，创建新 contract generation；不得在旧赛季或旧证据上静默解释新字段。

### 2.3 seeded engine 权限

`ptcgabc/local_engine/seeded_cabt_engine` 和 deterministic search SDK 是开发扩展，不是官方 runtime capability。它们可以用于可重复测试，但不能单独授予 `official engine parity`：

- 锁定官方 `cg.dll` identity 为 `A3A401D0F5CCC3474B9C8A7A2431920C4B728D28105A510AA6927AD6283E5CF7`；
- 当前 seeded derivative identity 为 `C932B8667506BAF6C5F8E573962647EF133547E79D75ACF6DC741E9AA69CBB6C`；它增加 `StableSearchSeed`、`BattleStartSeeded`、`BattleForkContinuation` 等扩展入口，必须作为不同 engine generation；
- 无随机微场景优先使用未修改官方 binary/source；
- 使用 seeded extension 的报告必须固定 patch/source/build hash，并声明 `seeded-development-oracle`；
- 随机相关 A3 只有在 RNG hook 被证明不改变除随机输入以外的语义，或由官方可复核轨迹提供相同随机事实时，才可晋升；
- 不可控随机分支保持 `unsupported-random-capability`，不能用大量胜率近似替代逐步一致。

Oracle 分级必须写入每份 A3 evidence：

| Oracle | 当前 identity | 权限边界 |
|---|---|---|
| 未修改官方 CABT DLL | `A3A401D0...E5CF7` | 仅在许可范围内作为 official semantic oracle；没有已证明的 deterministic seed API |
| 本地 seeded derivative | `C932B866...CBB6C` | 可重复开发 oracle；不能单独签发 official A3 |
| Godot candidate | exact scope manifest | 被验证对象，不是 oracle |

seeded 证据必须固定官方父源码/binary hash、全部 patch 及 hash、compiler/linker/build flags、derivative binary hash、patch purity 结论和允许的声明等级。

### 2.3.1 可复用证据的上限

| 现有证据 | 可以复用 | 不能证明 |
|---|---|---|
| PTCGABC exact rerun | 同一 seeded CABT engine 下按原 seed/action 重建轨迹 | CABT 与 Godot 一致 |
| replay-review verifier | action/reward/status/select/logs/current 的逐步比较 | 完整 observation、private state 或双规则引擎一致 |
| Tanishi first-divergence | 同一 CABT state 下两个策略的首个 action 差异 | 两个规则引擎的首个 state 差异 |
| Marnie source-locked fixture | 官方窗口、字段、option、lifecycle 样本 | 卡效、伤害或 terminal 规则一致 |
| PtcgDAP D091 replay diagnostic | Godot replay 完整性和少量 binding | official CABT parity |
| `ScenarioStateSnapshot` | Godot 场景恢复和诊断 | 语言中立 canonical A3 snapshot |

任何实施计划必须从这些上限继续构建，不能通过重命名既有工具将 A1/A3 视为已完成。

### 2.4 W0 — 本地研究范围与分发隔离门

项目负责人已明确：本项目是自有开源、学习研究工程，本地读取已安装官方模拟器用于接口研究不以取得外部“官方授权”作为工程暂停条件。W0 的技术职责因此是固定研究边界和防止私有来源混入开源交付，而不是等待第三方审批。

```text
W0-01 固定项目负责人本地研究范围决定和 oracle/source identities
W0-02 官方 binary/source/card data 只从用户指定的本机 private path 读取
W0-03 不复制、不上传、不缓存进 Forge SDK、不写入公共 evidence
W0-04 公共制品只包含自有实现、公开合同、脱敏计数/hash/结论
W0-05 CI、SDK、容器、备份和 evidence 增加 private-source rejection/locator-redaction gate
```

本地 operation I/O 比较允许直接使用用户安装的 private bundle；这不要求 official Card ID 与 PtcgDAP UID 相等，也不要求完整官方卡表或 exact official 60。只有 source-locked correspondence bridge 可以把两侧同一 printing/attack/ability 放入比较域。

以下动作仍不属于本轮授权范围：发布/复制/上传/容器化官方 runtime 或 card data，开放 public official-engine 托管服务，把官方数字映射写入公共 SDK/evidence，或声称官方背书。若未来要做这些产品动作，必须另行取得项目负责人明确指示；它们不阻断当前本地研究实现。

---

## 3. 目标系统与 authority 分层

```text
Strategy Project
  src/**/*.py + deck.csv + resources/** + project metadata
                |
                v
     deterministic .ptcgbot v2 builder
                |
       CompetitionBundleV2 owner
                |
       immutable archive SHA-256
                |
        qualification executor

Official lane                         Godot lane
exact framework RawEnvelope           engine DecisionPort typed payload
preserve unknown/missing/order         versioned allow-list CabtProjection
        |                                      |
        +---- policy input, with lane capability -----+
                               |
                    agent(observation) -> list[int]
                               |
                    current-window validator
                               |
Host-private SelectionWindowBinding / one-shot commit / ticket
session + acting seat + generation + private target + hashes
never added to official raw observation or public policy input
                               |
                    reobserve + per-seat logs
```

这里存在两种明确且不可混称的策略输入：official lane 的 `raw_observation`，以及 Godot lane 的 `certified_cabt_projection`。只有前者可称为 exact official callback；后者只能在其 A1 scope 内声明 CABT-aligned。`to_observation_class()` 一类 TypedView 只是作者便利视图，不拥有 raw authority。

Authority 必须保持：

```text
engine legality
  > current-window owner
  > output sanitizer/cardinality
  > private binding/ticket
  > one-shot executor
  > policy proposal
```

策略、trace、route、semantic intent、测试 fixture 和 replay 都不拥有 engine command authority。

---

# 4. W1 — Kaggle 式 `.ptcgbot v2` 与开发者 SDK

## 4.1 当前基线和缺口

当前 `.ptcgbot v1` 是确定性 ZIP，只允许 `manifest.json`、`main.py`、`deck.csv`。它已经拥有 archive/hash、author/version、60-card deck、AST entrypoint、大小和危险路径验证，以及本地申请、上传、paired match、排行和 public replay 功能证据。

但 v1 不能承载多文件 Base Graph、作者公共库、结构化查表数据或受控模型；没有冻结的作者 runtime/依赖合同和与 qualification 完全同构的开发 CLI。AST 只能证明可解析且有顶层 `agent`，不能证明第三方 Python 安全。

v2 必须只有一个共享 `CompetitionBundleV2` 合同 owner，负责路径扫描、manifest/content/runtime closure、canonical archive 和 release handle。Builder、CLI、HTTP quarantine、store、Worker extractor、qualification 和 agent runner 只能调用该 owner，禁止继续复制 `required files`、manifest keys 或解压规则。

## 4.2 v2 包拓扑

```text
manifest.json
deck.csv
runtime-lock.json
content-manifest.json
src/
  submission/
    __init__.py
    main.py
    ... pure Python modules
resources/
  ... inert, typed, hash-pinned data
```

### 4.2.1 文件规则

- 所有路径使用 UTF-8 NFC、`/` 分隔、相对路径；拒绝空段、`.`、`..`、绝对路径、盘符、反斜杠、控制字符、尾随点/空格和大小写折叠冲突。
- 拒绝目录 entry、symlink、hardlink 表示、重复 entry、加密 ZIP、data descriptor 异常、重叠 member、ZIP bomb、未知压缩算法和 CRC/stream 错误。
- `src/**` 仅允许 `.py` 和显式 UTF-8；`resources/**` 不能被 Python import 路径包含。
- `manifest.json`、`runtime-lock.json`、`content-manifest.json` 使用 duplicate-key-rejected canonical JSON，无 float、无 Unicode 隐式归一化。
- `deck.csv` 精确 60 行十进制 official Card ID；空白、注释、别名、显示名和本地 UID 均拒绝。
- archive entries 按 canonical UTF-8 path bytes 排序。首版使用 `ZIP_STORED`，固定 timestamp、creator system、permissions、flags；无 extra field/comment/encryption/data descriptor/Zip64。两次构建必须在 Windows/Linux 得到 exact bytes 相同。
- 拒绝 Windows drive/UNC/ADS、反斜杠、NUL/control、Unicode normalization/casefold collision、尾随点/空格、Windows reserved device name、local-header/central-directory 不一致。
- `ptcgbot.toml`、tests、scenarios、蓝图和开发日志属于作者工程，不进入比赛包。

### 4.2.2 资源规则

`content-manifest.json` 闭合 `src/**` 和 `resources/**` 的每个文件；每项记录：

```text
path
sha256
bytes
kind = python_source | resource
media_type
loader_capability
executable
```

源码项为 `kind=python_source, executable=true`；资源项为 `kind=resource, executable=false`。所有 archive entry 必须恰好被 closure 覆盖，禁止 `.pyc`、wheel、`.pth`、`sitecustomize.py`、共享库、可执行文件和作者提供的 `cg`/平台 SDK 保留模块名。

首版允许 JSON、CSV、文本、受限数值张量等明确格式；默认拒绝 `pickle`、`marshal`、`joblib`、宏文档、共享库和任何反序列化可执行格式。张量 loader 必须关闭 object/pickle 模式。模型格式只有在 runtime profile 声明对应只读 loader、operator/shape/size 上限和失败回退时才允许。scanner 不在服务进程反序列化作者资源。

## 4.3 v2 manifest

建议核心结构：

```text
document_type = ptcgdap_competition_strategy_v2
schema_version = 2

identity:
  strategy_id
  release_version
  author_id
  display_name
  summary

deck:
  path = deck.csv
  sha256
  card_count = 60
  card_id_domain = official_cabt_card_id

runtime:
  kind = cabt_python_agent_v2
  entrypoint = submission.main:agent
  runtime_lock_path = runtime-lock.json
  runtime_lock_sha256
  content_manifest_path = content-manifest.json
  content_manifest_sha256
  source_manifest_sha256
  resource_manifest_sha256
  runtime_profile_id
  runtime_profile_sha256
  python_abi
  sdk_contract_sha256

compatibility:
  environment = cabt
  engine_family = official_cabt
  engine_build_sha256
  observation_contract_sha256
  card_catalog_sha256
  required_capabilities

qualification:
  profile_id
  profile_sha256
  deterministic_replay_required
```

`runtime-lock.json` 由平台发布并固定/签名，作者包只能携带 exact copy；不能自定义 runtime。作者只声明需求；qualification owner 决定是否满足。manifest 不能改变网络、mount、CPU、内存、PID、timeout、Search 或 dependency allow-list。

现有文档中若已经把“三文件包的 canonical archive”称为 `.ptcgbot v2`，实施前必须拆成两个独立版本维度：`bundle schema generation` 和 `canonical ZIP profile generation`，避免旧三文件包与本设计多文件 v2 同名。

## 4.4 Runtime 与依赖合同

每个 runtime profile 固定：

- OS/architecture、Python exact version/ABI、SDK exact hash；
- 可导入标准库策略和预装第三方包 exact versions/hashes；
- `sys.path`、entrypoint import 规则、working directory；
- locale、timezone、UTF-8、`PYTHONHASHSEED`；
- import、单次 callback、整场 time-bank、CPU/RAM/thread/PID/file/stdout/stderr 限额；
- network、subprocess、filesystem、clock、entropy 和 Search capability；
- timeout、exception、invalid output、OOM、crash 的稳定 fault taxonomy；
- runtime/profile 失败时的 match 判罚；不得回落到另一个策略 owner。

首版不在包内携带 dependency wheel。若未来允许，必须新建 v3 capability 和独立 native-code threat model，不能放宽 v2。

dependency profile 由平台固定每个预装 artifact hash；比赛启动时禁止 `pip install`、user site、`.pth` 和环境继承。作者纯 Python 模块只能从 package `src/` 导入。静态 import allow-list 只作兼容提示，不能代替 sandbox；NumPy/BLAS/OpenMP 线程数和 RNG 行为属于 runtime profile。

Python 静态扫描不是安全边界。`eval`、动态 import、反射和标准库组合无法由 AST 完整判定；真正安全性属于后续生产 sandbox。W1 只能签发 `developer-local-qualified`，不能签发 Internet 多租户安全。

## 4.5 Agent 生命周期

- 每个 seat 每场创建 fresh 进程；模块只 import 一次，比赛结束销毁。
- 初始 callback 的 `select == null && current == null` 时返回 exact 60 Card ID deck；之后输出域为 current option index。
- 允许进程内保存公开语义记忆，但 observation/window 变化后旧 index、score、binding、constraint、proof 均无 authority。
- 返回必须是内建 `list`，每项为内建 `int`，拒绝 bool/IntEnum/float/string；index 唯一且保持顺序。
- `agent` 必须是同步普通函数；async function、generator function、coroutine/generator result 均在 qualification 阶段拒绝。
- `minCount <= len(result) <= maxCount`；每项落在当前 option 范围。
- terminal 无新选择时不得伪造 callback 或动作。
- 相同 transcript 重放确定性是 `official_verified` 资格门。非确定策略可在 `developer_local` 运行，但不能进入正式统计。

虽然公开 Python 函数始终返回 `list[int]`，Host/RPC 内部必须使用判别式返回域，禁止把两者都命名为 generic `indexes`：

```text
call_kind = deck_bootstrap
  response_domain = official_card_ids
  result 必须逐项等于 release 中签名的 deck.csv

call_kind = selection
  response_domain = current_option_indexes
  result 按 current window 验证
```

deck bootstrap 不创建 option binding/ticket，selection result 不能被 deck validator 接受。RPC audit、fault code、time budget 和 replay 必须保留该 domain，避免 60 个 Card ID 被误当 60 个 option index。

## 4.6 开发者 CLI 和工程模板

统一入口建议提供：

| 命令 | 责任 |
|---|---|
| `init` | 生成 v2 工程、示例 agent、测试、蓝图和 deck 模板 |
| `doctor` | 检查 runtime、SDK、engine、catalog、contract、磁盘和权限 |
| `check` | schema、路径、source/resource closure、deck、两次 exact build |
| `run` | 使用 exact runtime/profile 运行单局或 paired seat/seed |
| `test` | 执行 current-window 场景、metamorphic 和 fault tests |
| `trace` | 输出逐 callback 决策、耗时、option fingerprint 和错误分类 |
| `replay` | 打开失败局并定位 first policy divergence |
| `build` | 原子生成 `.ptcgbot` 和 build receipt |
| `prequalify` | 执行与服务端同版本开发预检，固定 `authority=development_only` |

模板必须包含 `src/submission/main.py`、`deck.csv`、`tests/`、`scenarios/`、`STRATEGY-BLUEPRINT.md`、项目配置、runtime lock 和 README。CLI 不要求开发者手算 hash。

trace 分为本地 private diagnostic 和可分享 public trace。前者仍默认剥离 Search token并收紧权限；后者必须经过 public allow-list，不含隐藏牌、原始异常文本、环境路径或凭据。服务器错误反馈只返回稳定错误码、decision ordinal、select 摘要和必要源码位置。

### 4.6.1 UCIS 开发者视图

Forge SDK 从同一 UCIS generation 生成只读 enum/types、sparse option parser、semantic option helpers、public fact derivation、capability catalog 和 scenario builders。开发者仍然编写 `agent(raw_observation) -> list[int]`；helper 只能把当前 raw window 解析为 typed view、按稳定语义重绑定 index，不能隐藏额外 engine 命令或返回复合 plan。

`doctor/check/trace` 必须显示当前 `contract_generation / ucis_registry_hash / catalog_scope_hash / supported primitives / unsupported capabilities`。策略若引用当前 lane 不支持的 capability，构建或 qualification 在运行前给出稳定错误；不能等真实牌局静默回退。模板应示范：

- 从当前 observation 计算攻击手能量债务和 prize clock；
- 对 `0..N` search 返回精确子集长度；
- 在 repeated assignment 中每个新窗口重新解析目标和 remaining debt；
- option reorder 后按 semantic fingerprint 找到新 index；
- unknown enum/field、缺失 identity 或 unsupported capability 时 fail closed。

`.ptcgai` restricted IR 使用同一 public fact vocabulary 和 primitive catalog，但仍受 data-only/Base authority 限制；`.ptcgbot` 的 Python 表达力不能反向扩大 `.ptcgai` 的权限。

## 4.7 Qualification 顺序

```text
archive structural validation
-> canonical manifest and exact hash closure
-> deck/catalog/format/rules legality validation
-> isolated import/entrypoint validation
-> official initial callback
-> known current-window probes
-> repeated transcript determinism
-> paired-seat CABT smoke
-> resource/time/output caps
-> privacy/network/filesystem negative probes
-> immutable qualification receipt
```

包验证失败不得解压到共享路径或执行源码。qualification scratch 按 release/attempt 隔离，结束后清理；receipt 只保存公开 hash、资源摘要和稳定错误码。

牌组门不止检查 60 个正整数，还必须绑定赛季 format、official card catalog、重复上限/特殊构筑规则、禁限卡和至少一个可 setup 的基础宝可梦。`deck.csv` 输出顺序必须与 bootstrap callback 精确一致。

## 4.8 v1 兼容与迁移

- v1/v2 通过 `document_type + schema_version + runtime.kind` 封闭 dispatch；禁止 v2 validator 猜测 v1。
- 已有 v1 release 保持 immutable；迁移生成新 version、新 archive hash、新 qualification。
- v1 `main.py` 可机械放入 `src/submission/main.py`，但只有 v2 builder 重算 manifest 后才是 v2。
- 赛季/profile 绑定允许的 runtime generations；旧比赛不使用新 runtime 重解释。
- 关闭 v2 feature 只阻止新 upload/qualification，不删除已存在 archive/replay。

## 4.9 W1 工作包与退出门

| ID | 工作包 | 关键退出门 |
|---|---|---|
| W1-00 | local-research/distribution isolation | 本地私有研究可执行；official binary/source/card-data 不进入开源包、公共 evidence 或托管服务；任何未来分发/托管另立资格 |
| W1-01 | v2 schema/profile/vector/bundle | 正向、未知键、错误类型、版本漂移 vectors 全通过 |
| W1-02 | canonical path/source/resource closure | traversal、Unicode/case collision、symlink、bomb、duplicate 全拒绝 |
| W1-03 | deterministic builder/canonical ZIP profile | Windows/Linux 两次构建 exact bytes/hash 相同 |
| W1-04 | shared BundleV2 owner + validator dispatch | Builder/API/Worker/Runner 对同 vectors 结论一致；v1 不变 |
| W1-05 | pinned runtime/SDK | ABI、依赖、capability、limits 有完整 manifest/hash |
| W1-06 | local runner 与 trace | official callback 全程运行；首个错误窗口可定位 |
| W1-07 | qualification | import、determinism、paired smoke、resource/privacy/fault 全绿 |
| W1-08 | developer template/docs | 仓库外 clean workspace 可从 init 到 valid archive |

W1 总门：W1-00 的本地研究/分发隔离已通过；两个仓库外 clean-machine witness 使用同一 SDK 从创建、测试、构建到本地 qualification；服务器用同一 archive/profile 重验得到相同公开结果。生产第三方代码隔离和 official runtime/card-data 分发不在本门。

---

# 5. W2 — 官方 CABT Observation/Select/Window A1 对齐

## 5.1 官方选择模型 census

当前锁定官方 `cg/api.py` 定义：

- 11 个 `SelectType`：MAIN、CARD、ATTACHED_CARD、CARD_OR_ATTACHED_CARD、ENERGY、SKILL、ATTACK、EVOLVE、COUNT、YES_NO、SPECIAL_CONDITION；
- 49 个 `SelectContext`（0..48），覆盖 setup、移动、检索/弃牌、伤害/治疗、进退化、附着/拆除、技能/攻击顺序、数量、Yes/No 和特殊状态；
- 17 个 `OptionType`（0..16）；
- enum 尾部允许未来追加。

接口对齐不能只按“setup/main/effect”粗粒度声明。必须生成机器可读 census，并为每个 raw enum 值记录官方来源、wire shape 和支持状态。

### 5.1.1 49 Context 的规范映射

| Context | SelectType | 合法 OptionType |
|---|---|---|
| `0 MAIN` | `MAIN` | `PLAY, ATTACH, EVOLVE, ABILITY, DISCARD, RETREAT, ATTACK, END` |
| `1..25`：`SETUP_ACTIVE_POKEMON, SETUP_BENCH_POKEMON, SWITCH, TO_ACTIVE, TO_BENCH, TO_FIELD, TO_HAND, DISCARD, TO_DECK, TO_DECK_BOTTOM, TO_PRIZE, NOT_MOVE, DAMAGE_COUNTER, DAMAGE_COUNTER_ANY, DAMAGE, REMOVE_DAMAGE_COUNTER, HEAL, EVOLVES_FROM, EVOLVES_TO, DEVOLVE, ATTACH_FROM, ATTACH_TO, DETACH_FROM, LOOK, EFFECT_TARGET` | `CARD` | `CARD` |
| `26 DISCARD_ENERGY_CARD` | `ATTACHED_CARD` | `ENERGY_CARD` |
| `27 DISCARD_TOOL_CARD` | `ATTACHED_CARD` | `TOOL_CARD` |
| `28 SWITCH_ENERGY_CARD` | `ATTACHED_CARD` | `ENERGY_CARD` |
| `29 DISCARD_CARD_OR_ATTACHED_CARD` | `CARD_OR_ATTACHED_CARD` | `CARD, TOOL_CARD, ENERGY_CARD` |
| `30..33`：`DISCARD_ENERGY, TO_HAND_ENERGY, TO_DECK_ENERGY, SWITCH_ENERGY` | `ENERGY` | `ENERGY` |
| `34 SKILL_ORDER` | `SKILL` | `SKILL` |
| `35 ATTACK, 36 DISABLE_ATTACK` | `ATTACK` | `ATTACK` |
| `37 EVOLVE` | `EVOLVE` | `EVOLVE` |
| `38 DRAW_COUNT, 39 DAMAGE_COUNTER_COUNT, 40 REMOVE_DAMAGE_COUNTER_COUNT` | `COUNT` | `NUMBER` |
| `41 IS_FIRST, 42 MULLIGAN, 43 ACTIVATE, 44 FIRST_EFFECT, 45 MORE_DEVOLVE, 46 COIN_HEAD` | `YES_NO` | `YES, NO` |
| `47 AFFECT_SPECIAL_CONDITION, 48 RECOVER_SPECIAL_CONDITION` | `SPECIAL_CONDITION` | `SPECIAL_CONDITION` |

这张表是当前锁定 generation 的全集，不是永久假设。任何新增 raw enum 都使旧 generation 停止签发完整 A1，直到重新 census、实现和验证。

### 5.1.2 17 OptionType 的稀疏 wire

| OptionType | 必须出现的字段 |
|---|---|
| `NUMBER=0` | `type, number` |
| `YES=1`, `NO=2` | `type` |
| `CARD=3` | `type, area, index, playerIndex` |
| `TOOL_CARD=4` | `CARD` 字段加 `toolIndex` |
| `ENERGY_CARD=5` | `CARD` 字段加 `energyIndex` |
| `ENERGY=6` | `type, area, index, playerIndex, energyIndex, count` |
| `PLAY=7` | `type, index` |
| `ATTACH=8`, `EVOLVE=9` | `type, area, index, inPlayArea, inPlayIndex` |
| `ABILITY=10`, `DISCARD=11` | `type, area, index` |
| `RETREAT=12`, `END=14` | `type` |
| `ATTACK=13` | `type, attackId` |
| `SKILL=15` | `type, cardId, serial`；合法允许 `(0,0)` |
| `SPECIAL_CONDITION=16` | `type, specialConditionType` |

字段要求是 sparse presence 合同：missing、`null`、零值不是同义。返回 index 的顺序保持作者顺序，不得排序；`SKILL_ORDER` 是有规则意义的 ordered multi-select。

### 5.1.3 完整 observation census

W2-01 不能停在 11/49/17，还要固定：

- framework envelope：`step`、`remainingOverageTime` 及 exact raw observation；
- `Observation` 四字段、`SelectData` 十字段及每字段的 missing/null/value；
- `State`、`PlayerState`、`Pokemon`、`Card` 的 actual wire；
- 12 `AreaType`、12 `EnergyType`、5 `SpecialConditionType`；
- 24 `LogType` 及各自稀疏字段、正向/反向公开规则；
- Search 的 `SearchState/searchId/error/search_begin_input` 生命周期；
- actual callback 与 Python API 注释的差异清单。

已知 golden 必测差异包括：native `Pokemon.playerIndex` 实际存在但 Python dataclass 未声明；`contextCard` 由 serializer 的实际 presence 决定，并不只限于注释所举的 `ACTIVATE`。census 输出必须包含 source hash、callsite、raw example、presence rule 和 generation。

### 5.1.4 Unified Card Interaction Standard（UCIS）

UCIS 是 PtcgDAP 卡牌效果与策略窗口之间唯一的语言中立合同。它不是另一套对外 wire，也不是把官方 Card ID 复制进私有卡表；它把所有卡牌效果编译到 official-shaped current-window 原子上，并保证所有作者看到同一种 observation/select/index 规则。

规范数据流为：

```text
source-locked official census ──> UCIS Registry / Generation
                                      |
private CardEffectSpec ──> Interaction Compiler
                                      |
                                InteractionProgram
                                      |
engine public state ──> legality/query owner ──> InteractionStep
                                      |
                         Standard SelectionWindow
                                      |
                    agent(observation) -> list[int]
                                      |
                  validator / private binder / executor
                                      |
                         invalidate -> reobserve
```

UCIS 分为两级，禁止混淆：

1. **wire 原子**：严格对应当前 census 的 11 个 `SelectType`、49 个 `SelectContext`、17 个 `OptionType`、四种数量编码及 lifecycle；这是策略真正接收和返回的标准表面。
2. **领域编排原语**：描述 Search、Move、Assign、Distribute、Pay、Retreat、Switch、Evolve、Activate、Attack、ResolveKO 等多窗口语义。它们必须由 compiler 展开为一个或多个 wire 原子；每次只能发布一个 current window，commit 后必须重新观察才能继续。

首个 UCIS generation 至少注册以下领域原语；表中的 wire 只是允许编译目标，最终 raw context 由 Registry 与 effect spec 共同决定：

| 领域原语 | 标准 wire 原子 | 关键语义 |
|---|---|---|
| `ChooseCardSet` | CARD / CARD_OR_ATTACHED_CARD | zone/predicate、ordered subset、min/max、optional-zero |
| `ChooseAttachedCardSet` | ATTACHED_CARD / CARD_OR_ATTACHED_CARD | owner/source、energy/tool subtype、当前 attachment binding |
| `ChooseEnergyUnits` | ENERGY | energy card 与 units 分离、`count`、remaining cost/debt |
| `ChooseSkillOrder` | SKILL | ordered multi、真实 entity 或合法 `(0,0)` special skill |
| `ChooseAttack` | ATTACK | official Attack identity + private source binding，支持 copy/granted context |
| `ChooseEvolution` | EVOLVE / CARD contexts | from/to/stack、合法 stage 与 current target |
| `ChooseNumber` | COUNT | NUMBER option，不把数字编码成 list length |
| `ChooseBoolean` | YES_NO | YES/NO、mandatory/optional、真实 chooser |
| `ChooseSpecialCondition` | SPECIAL_CONDITION | affect/recover context 与合法 condition set |
| `SearchAndMove` | 一个或多个 CARD windows | search/look/reveal、精确数量、目的区域、shuffle/信息 checkpoint |
| `AssignOrDistribute` | repeated CARD/ENERGY windows | source→target、逐项债务、fresh target legality、合法停止 |
| `PayCost` | CARD/ATTACHED_CARD/ENERGY/COUNT | discard/detach/energy-unit/number cost，先付费后效果 |
| `RetreatOrSwitch` | MAIN + CARD/ATTACHED_CARD/ENERGY | retreat declaration、费用、目标、effect switch/gust/send-out |
| `ActivateOrPlay` | MAIN + typed continuation | play/ability/stadium/tool/supporter 前置、once flag、后续选择链 |
| `AttackAndTarget` | MAIN/ATTACK + typed continuation | attack declaration、target/counter allocation、复制攻击 context |
| `ResolveKnockout` | CARD/COUNT + lifecycle | simultaneous KO、prize selection、promotion、terminal priority |

Registry 不允许通过“万能 `CustomInteraction` + 任意 JSON”逃逸。若表中组合不能准确表达 source census 中的新形状，必须新增有 typed schema、owner、negative gates 和 generation migration 的标准原语。

`InteractionProgram` 至少包含：

```text
program_kind / capability_ids / source_effect_ref
chooser_rule / visibility_rule / lifecycle_anchor
ordered InteractionStep[]
continuation_rule / stop_rule / information_checkpoints
contract_generation / compiler_generation / source_hash
```

每个 `InteractionStep` 至少声明：

```text
select_type_raw / context_raw
source_zone_query / candidate_predicate / target_predicate
option_encoder / option_order_owner
quantity_encoding / min_rule / max_rule / remaining_debt_rule
public_context_projection / private_binding_recipe
commit_command_kind / next_checkpoint_rule
unsupported_if / capability_ids
```

实施时的语言中立 owner boundary 固定为：

```text
compile_effect(effect_spec, ucis_generation) -> CompiledInteractionProgram
begin_program(compiled_program, effect_instance_ref) -> ProgramInstance
next_step(program_instance, current_engine_state) -> WindowDraft | AUTO | COMPLETE | UNSUPPORTED
issue_window(window_draft, acting_seat) -> SelectionWindow + PrivateBinding
commit(window_id, indexes) -> ACCEPTED | REJECTED
advance_after_reobserve(program_instance, fresh_engine_state) -> next_step
```

`compile_effect` 是无对局状态的确定性构建步骤；`next_step` 才能读取当前 engine public facts/legality，且不得自行提交动作；`issue_window/commit` 由唯一 DecisionPort owner 实现。`ProgramInstance` 只能保存 effect instance、stable semantic refs、已支付数量和 remaining debt，不能保存 option index、Godot object 或旧 WindowDraft。

卡牌只允许提供 `CardEffectSpec` 的公开规则参数，例如来源区域、卡牌/能量 predicate、上限、目标约束、伤害债务、是否 optional、效果持续期和后续步骤。以下权力只属于 engine/registry，卡牌代码不得覆盖：

- raw `SelectType/SelectContext/OptionType` 的注册与 wire schema；
- acting chooser、合法候选全集和 official order；
- min/max/remain 的最终值及 mandatory/terminal 保护；
- option 到 Godot object/command 的 private binding；
- index validation、one-shot ticket、commit、rollback 和 reobserve；
- hidden/public 投影、Search token、log cursor 和 evidence hash。

UCIS 编译不变量：

1. 一项效果若不能完全编译到当前 generation，状态必须为 `unsupported_interaction_shape`；不得退回旧私有 prompt。
2. 卡牌实现和 strategy adapter 都不能缓存或返回跨窗口 index；program 只保留稳定 semantic identity、goal 和 debt。
3. 候选、顺序、数量和 chooser 全由当前公开状态与 engine legality 重新计算；card text、显示名或本地对象 ID 不是 authority。
4. missing、`null`、零值、enum raw 值和 option list order 全部保真；unknown 新值触发 generation drift/fail closed。
5. optional-zero、ordered multi、ENERGY units、COUNT number 和 repeated assignment 使用 §5.6 的官方既有编码，不能新增 `desired_count`、`targets[]` 或“整套计划”作为 wire 字段。
6. 每个 commit 只消费当前 step；任何 draw/reveal/search/shuffle/coin/公开响应后 continuation 必须从 fresh observation 重建。
7. author policy 只能选择当前 option；Base/Host/engine 永远保有合法性和最终裁决权。

### 5.1.5 卡牌实现规范、目录闭包与静态门

每张会产生选择的卡牌、攻击、特性和 Trainer 效果必须登记一个或多个 `CardEffectSpec`，并在构建时生成 `card_uid -> effect -> capability -> InteractionProgram` 目录。无选择的纯自动效果也要登记 `automatic_resolution` capability，以便证明它不会偷偷创建作者窗口。

目录构建必须执行静态检查：

- 禁止卡牌脚本直接调用 UI、Host、DecisionPort、policy adapter 或 action executor；
- 禁止卡牌脚本创建自定义 context number、自由文本 prompt、未注册 option 字段或自定义返回对象；
- 禁止在卡牌状态中存 option index、window handle、engine ticket 或 callback；
- 禁止把 hidden card、牌库顺序、face-down prize、engine object 或 RNG 内部状态投影给策略；
- 禁止新卡依赖 legacy private adapter schema；
- 每个 effect 必须完全编译、明确 `automatic_resolution`，或以稳定错误码列为 unsupported，不能静默跳过。

目录 closure 报告至少给出：总卡牌/效果数、产生选择的效果数、成功编译数、automatic 数、unsupported 数、legacy custom prompt 数、未登记数、按 UCIS primitive/capability 的覆盖与 source hashes。`legacy custom prompt > 0`、`unregistered > 0` 或未解释 compile failure 时，不得声明“PtcgDAP 卡牌统一实现标准规范”。

### 5.1.6 来源生成、generation 与整体性扩展

UCIS Registry 由只读 source census 生成或校验，而不是手抄常量。生成器至少提取 enum raw 值、稀疏 option shape、context/type 关系、数量编码、chooser/callsite、presence rule、lifecycle 和 representative raw vectors，并输出 source hash、generator hash 与 generation ID。

扩展算法是：

```text
新增/更新卡牌
-> 编译 CardEffectSpec
-> 若全部 capability 已在 UCIS Registry：只增加目录项和语义参数测试
-> 若出现未知官方交互形状：停止编译并生成 drift report
-> 复核 official source/callsite
-> 新增原语或组合规则、提升 contract generation
-> 全量重跑原语、组合、目录 closure 和代表性 live vectors
```

因此总体对齐的单位是“协议 generation + 原语/组合 closure + 卡牌目录 closure”，不是“人工验完 N 张卡”。卡牌数量增长只应线性增加 declarative spec 和少量卡牌语义用例；它不能线性增加协议实现分叉。official binary/source/card data 仍只在本地私有研究环境使用，公开制品只保留自主实现的 schema、生成结果允许公开的部分、hash 和非侵权证据摘要。

## 5.2 RawEnvelope、TypedView 与策略输入

### 5.2.1 Official native lane

- Host 保存 framework RawEnvelope 的 exact JSON tree：key/value/type/list order、未知字段和 missing/null/value 三态；
- acting-seat 官方 raw callback 是 `.ptcgbot` 输入 authority；
- `step`、`remainingOverageTime` 等 framework extras 保持来源值；
- `search_begin_input` 仅在 capability 开启时原样、短暂交给该 callback；不得落盘、打印或进入 public evidence；
- private replay container 不能整体进入策略，只有官方为该 seat 生成的 observation。
- 不先转成 dataclass 再交给策略；TypedView 丢弃的 extras/unknown field 仍保留在 raw 输入。

### 5.2.2 Godot aligned lane

- 使用 allow-list 正向构造已声明 CABT 字段；
- 不生成官方未提供的字段、不用本地对象 ID/显示名猜 official identity；
- 当前 contract 未知的 field/enum 进入 Host-private quarantine，策略走 stable fail-closed；若 official source hash 漂移，则暂停该 generation 的 A1，不能声称 Godot “透传”了未知官方字段；
- 只有经过 contract refresh 的新增公开字段才进入 policy；
- `search_begin_input = null`，capability `none`。

### 5.2.3 `.ptcgai` lane

数据包继续接收 public projection/typed facts，而非任意 raw engine state；它不因 `.ptcgbot` raw lane 存在而扩权。

### 5.2.4 三类 hash

不能使用一个含义模糊的 `observation_hash`：

1. `engine_semantic_hash`：对 `select/current/logs` 的 canonical semantic surface 计算，供双 Host 对比；排除 wall-clock、Search token 和 Host-private 字段。
2. `callback_binding_hash`：Host-private，绑定 exact callback、acting seat、generation、framework step/time、window order；Search token仅以会话内 HMAC/存在性参与，绝不保存明文。
3. `policy_input_hash`：对策略实际收到的输入计算；official lane 包含 framework extras，Godot/`.ptcgai` 是各自声明的 public projection。

三个 hash 都记录 schema generation 和 canonicalizer hash，互相不得替代。wall-clock 漂移不能被误报为规则差异，Search token也不能泄露到公开证据。

## 5.3 Immutable SelectionWindow

统一语言中立结构至少包含：

```text
contract_generation
session_id / match_generation / seat
engine_semantic_hash / callback_binding_hash / policy_input_hash
window_id / window_generation
select.type_raw / context_raw
minCount / maxCount
remainDamageCounter / remainEnergyCost
ordered option raw fields + fingerprints
authorized deck / contextCard / effect
incremental log cursor/hash
time budget summary
capability profile hash
```

其中 `session_id/window_id/ticket/private target` 只存在于 Host-private `SelectionWindowBinding`，不能塞进 official observation 或 Godot policy projection。Option fingerprint 覆盖实际 populated 的全部官方字段和 missing/null/value 状态，不加入 Godot object、command、ticket 或显示文本。fingerprint 只用于审计和重绑定；策略仍返回官方 index。

## 5.4 Current-window 生命周期

```text
engine reaches decision checkpoint
-> owner captures exact state once
-> build ordered options and public observation
-> issue immutable window
-> call policy once
-> validate output type/cardinality/range/unique/order
-> mark accepted; bind every index to exact current private option
-> create one-shot ticket
-> revalidate session/seat/hash/window/order/generation
-> mark committed; execute atomically once
-> invalidate window and ticket
-> collect incremental logs
-> reobserve and obtain public witness before declaring executed
```

非法输出、异常或超时整单丢弃，只能从同一 current window 计算确定性合法 fallback。结构错误、`len(option) < minCount` 或无法维持引擎不变量时必须阻断，不制造 index。

`accepted`、`bound`、`committed`、`public-witness` 是四个不同状态。只有下一 observation/log witness 已出现，外部报告才可称动作已执行。chooser 必须来自 native `selectPlayer`/Godot DecisionPort，不能假设等于 turn player、effect owner 或 card controller；`enemySelect`、trigger order 和 KO promotion 都可能改变 chooser。

## 5.5 Prompt Coverage Matrix

新增由官方 census 生成、可机器验证的矩阵。每个 `SelectContext` 至少包含：

| 字段 | 说明 |
|---|---|
| `select_type_raw` / `context_raw` | 官方 raw identity |
| `context_name` / `select_type_name` | 当前 generation 的可读名称，raw 数值仍是 authority |
| `official_wire_source` | actual callsite、native serializer、golden callback 定位和 source hash |
| `trigger_owner` | setup/turn/effect/attack/KO 等最早引擎 owner及 occurrence phase |
| `chooser_roles` | native `selectPlayer`、turn player、effect owner、controller、affected player分别记录 |
| `option_shape` | 允许的 OptionType 与 populated fields |
| `option_order_owner` | 谁定义官方有序列表 |
| `quantity_encoding` | result length、NUMBER、ENERGY count/debt、repeated window 或 fixed cardinality |
| `cardinality_rule` | min/max、ordered multi、optional-zero、repeat/stop/automatic-skip |
| `public_projection` | 当前 seat 可见字段及 provenance |
| `deck/current/presence` | `select.deck`、`current.looking`、`contextCard/effect` 的顺序和 presence rule |
| `private_binding` | index 到 engine target/command 的 Host-private 绑定 |
| `executor` | one-shot 执行 owner |
| `next_checkpoint` | commit 后如何 reobserve |
| `expected_logs` | per-seat selection-to-selection 公开日志和 post-commit witness |
| `capabilities` | Search/manual-coin/normal-battle/time profile、card/effect capability |
| `reachable_fixtures` | official golden、Godot micro、dual-runtime、reorder/metamorphic witness |
| `four_statuses` | projection / validation / execution / log 独立状态 |
| `support_status` | 四态全绿才是 aligned；否则 pending / unsupported / known-difference |
| `negative_gates` | stale、reorder、cross-seat、hidden、unknown 等 |
| `generation` | source/engine/catalog hash 和最后复核 generation |

矩阵缺行、重复 context、来源 hash 漂移或 `aligned` 无 witness 时，A1 报告构建失败。

### 5.5.1 非 Prompt Lifecycle Coverage Matrix

Prompt Matrix 不覆盖 bootstrap、自动阶段和 terminal，必须另有一张机器可验证矩阵，按官方 setup call chain/golden trajectory固定：

1. 每 seat fresh process/session；
2. initial callback 精确为 `select=null,current=null,logs=[],search_begin_input=null`，返回域是 exact 60 official Card IDs；
3. 双方 deck 验证后才启动 engine，并由 engine shuffle；
4. `IS_FIRST` 由 seat 0 选择，不由 Host 随机代替；
5. 双方初始手牌；
6. mulligan 三分支：有 Basic 自动继续；无 Basic 且无 setup Doll 自动重抽；无 Basic 但有 setup Doll 发布 `MULLIGAN`；
7. `SETUP_ACTIVE_POKEMON` 精确一张；失败方重新 shuffle/draw/setup；
8. prize 自动放置，不制造作者选择窗口；
9. mulligan 受益方以 `DRAW_COUNT` 的 NUMBER 选择 `0..mulliganCount`；
10. active 提交后 fresh reobserve，再发布 optional `SETUP_BENCH_POKEMON`，`min=0,max=min(candidate_count,bench_capacity)`；
11. turn start、draw、MAIN；effect/attack 多窗口链；turn end 与 Pokémon Check；
12. KO、prize、promotion、win check；
13. terminal 不为 RESULT log 额外调用 agent，不伪造 END；
14. dispose/reset 清零 seat cursor、Search state、serial registry、window/ticket。

当前 Godot Host 的 setup 预选 bench、强制全选 bench、mulligan 固定抽一张等行为都只能列为 migration blocker，不能进入 A1 golden。

## 5.6 PTCG 多阶段交互设计

本节所有交互都必须由 UCIS 领域编排原语产生。卡牌代码只提交 effect spec 和参数，不得绕过 compiler 直接创建窗口；Selection Window owner 每一步都从当前 engine state 和 legality 生成标准 wire 原子。

为了让策略能表达精确 PTCG 计划，standardized observation 必须从 official acting-seat public surface 逐项提供或可确定性推导以下 `PublicInteractionFacts`：

- 当前 source/effect、chooser、候选实体的 current-window semantic reference；
- 每只公开宝可梦当前附着的能量卡、能量单位/属性、攻击费用、撤退费用和合法 attack readiness；
- 当前 search/payment/assignment 的初始上限、已完成数量、remaining debt、可停止条件和当前合法目标；
- 双方剩余奖赏数、公开可判定的候选奖赏价值、active/bench/Rule Box 状态；
- damage counters、HP、特殊状态、bench capacity、once-per-turn/turn restriction 等影响当前合法性的公开事实。

这些是对 official raw observation/current/select 的 allow-list typed view 或纯函数派生，不是新增 official wire 字段。若某事实不能从 acting seat 的当前公开输入确定，就不得补入策略输入或用于 author rule；engine 可在 private legality/binding 中使用它，但不能泄露。Forge/Base 可据此计算“当前攻击手缺 1、备用攻击手缺 2、总检索 3”和“对手剩 2 奖、候选分别送 1/2 奖且是否立即可攻击”等语义债务，最后仍必须编译为当前标准 option indexes。

以下交互必须拆成官方粒度窗口，不能由通用逻辑一次性猜完：

- setup active 后重新观察，再选择 0..N bench；
- 牌库检索的精确数量、有序子集、optional-zero；
- source→target、逐张能量/工具、逐次伤害指示物分配；
- retreat 的目标与被弃能量；
- switch/gust/send-out/KO promotion；
- evolve from/to、devolve 和 evolution stack；
- attack/ability/effect target；
- skill/effect order；
- draw/damage/heal/remove count；
- Yes/No、coin choice、特殊状态选择；
- 同时 KO、奖赏领取、胜负检查和下一 active 的正确时序。

每次 reveal、draw、search、shuffle、coin、随机目标或对手公开响应都是 information checkpoint。只能保留稳定语义 goal/identity/debt，必须丢弃旧 index/score/proof。

精确数量必须编译为官方已有的四种编码，不能发明“数量+整套分配”的复合命令：

1. 普通 multi-select 用返回列表长度表达，如 `min=0,max=5` 返回三个 index；
2. COUNT 选择一个 `NUMBER.number`；
3. ENERGY 以 `Option.count` 表示能源单位，并结合 `remainEnergyCost`；
4. 迭代分配每次只选当前 source/target，提交后重观察；满足债务后在允许 `min=0` 的 fresh window 返回 `[]` 停止。

Competitive v2 的 `desired_count` 只能作为 UCIS compiler 的内部语义债务，不是 official wire。玛俐“取 3 张并按 1+2 分配”应编译为“当前 multi-select 返回 3 个 index + 后续逐次 assignment window”；每一步重新计算目标能量债务并绑定 `(area,index,playerIndex)`，不能由通用逻辑取满 5 张，也不能把五张都自动堆到第一个目标。face-down prize 只能保留位置身份，不能补出 Card ID。普通 coin 由 engine 处理并产生日志；`COIN_HEAD` 仅在官方 Search `manual_coin=true` 等真实 capability 下出现，Host 不得自行制造。

## 5.7 身份合同

三类官方身份分开：

- official Card ID：printing identity；
- official Attack ID：不能用本地 attack index/name/text 合成；
- per-match serial：物理卡实体，进化堆和移动后保持官方定义的连续性。

Godot bridge 还需内部 entity continuity，但不得进入 CABT Option。UCIS 内部使用 `SemanticEntityRef(domain, private_uid, lineage, current_location)` 分开稳定语义身份和当前窗口位置；只有符合 public projection 的部分可进入 observation。每个认证 printing 建立 exact bridge record：official Card ID、Godot UID、source/card-effect hash、可见字段映射和支持状态。缺失或多义映射为 `unsupported`。标准化交互协议不要求、也不允许把私有 UID 改写为 official Card ID。

`CARD/ENERGY/TOOL` 的 `area/index` 是当前窗口位置身份，不稳定；只有同 observation 的 public serial 或 Host-private binding 才能关联实体。official `ATTACK` option 公开 wire 只有 `attackId`，native 私下的 `srcAttackId/benchIndex` 等执行信息必须由 DecisionPort 以 ordinal-private binding 保存，禁止从 attackId 猜复制攻击来源。`SKILL(cardId=0,serial=0)` 是合法特殊状态排序项，只有真实 Card entity 才要求正值。

## 5.8 Logs、Search、reset、terminal 与 time bank

- 维护 `log_cursor[seat]`；当前 callback 的 logs 是该 seat 自己上次成功收到 callback 后的有序公开事件；
- 游标只在 callback 成功发布给该 seat 后推进，不在 engine action、accept 或 commit 时推进；
- opponent draw/move 使用 `DRAW_REVERSE/MOVE_CARD_REVERSE` 等官方反向日志，不泄露 Card ID/serial；
- accepted/bound/committed/public-witness 必须属于同一 window；无下一公开 witness 不能声称 executed；
- 新 match 重置 session、serial registry、window generation、所有 seat log cursor、time ledger 和策略进程；
- initial callback 是 deck Card ID 输出域，不与 action index 混用；
- terminal 或无 select 时按官方 lifecycle，不自动制造 END/index；
- terminal 后 replay owner 可保留 RESULT，但不为投递 RESULT 伪造 agent callback；
- unknown field/enum 不崩溃，保留 raw 并 fail closed；不映射成最接近旧值。

Search 是独立 capability：token 是 callback-scoped opaque ASCII；`search_begin` 使用本次 observation，由策略填写预测隐藏区，不是 oracle；Search observation 的 `search_begin_input=null`，以 branch-local `searchId` 标识；`search_step/release/end` 不能使用真实 match ticket，不能推进真实 log cursor。token 不落盘、不打印、不进入公开 hash。official runner 可声明 `search=official_native`；Godot 默认 `search=none`。

`step/remainingOverageTime` 属于 framework envelope，不属于 `cg.api.Observation` dataclass。锁定 profile 的基线参数为 `actTimeout=0, remainingOverageTime=600, runTimeout=2000, episodeSteps=10000000`；exact profile 仍需 hash 固定。official lane 原样传数值、不舍入；Godot 只能声明自身 `time_profile`，不能伪称官方 clock。wall-clock 不进入 engine semantic hash；import/Search/callback 如何计费由 profile 决定，Search 不得重置预算。timeout、OOM、crash 使用稳定 fault taxonomy。

## 5.9 A1/UCIS 测试模型

协议测试按 **raw context、领域原语、组合链和目录 closure** 四个正交维度生成，不以人工逐张卡测试代替。每个 `SelectContext` 至少覆盖，而不是只按 family 抽样：

1. 单选正向；
2. `min=0` optional-zero；
3. 可变数量与 exact max；
4. ordered multi；
5. semantic option reorder；
6. missing prerequisite / empty source；
7. wrong target / wrong seat；
8. stale / replay / cross-session / cross-seat；
9. mandatory / terminal / all-options-required；
10. unknown enum / sparse option / unknown field；
11. hidden sentinel / private object / Search token leak；
12. executor reject / partial apply rollback；
13. commit 后 reobserve 与日志边界；
14. 只改变一个公开事实的 metamorphic decision/window flip。

必测 golden/metamorphic vectors 还包括：`minCount 0→1` 的 `[]` 翻转；只重排 option 时语义不变但 index 改变；只改变 special-energy `count/remainEnergyCost`、bench capacity、damage debt、`enemySelect`、`contextCard/effect` 时相应窗口/chooser/binding 翻转；合法 `SKILL(0,0)`；非 ACTIVATE 的真实 `contextCard`；`looking=[null,...]`；opponent reverse log；iterative ENERGY；setup Doll mulligan；active 后 fresh optional bench。

UCIS 还必须有以下整体性测试：

1. **编译性质**：任意合法 `CardEffectSpec` 只能生成 Registry 中的 step；illegal/unknown spec 稳定 fail closed；编译结果 canonical/deterministic。
2. **原语性质**：候选 soundness/completeness、cardinality、order、chooser、visibility、binding、one-shot、reobserve 逐原语覆盖。
3. **组合性质**：对 Search→Assign、Pay→Attack、KO→Prize→Promote 等有限状态机做 pairwise/高风险 n-wise 覆盖；information checkpoint 必须断开旧 binding。
4. **变形性质**：option reorder、min/max、energy debt、bench capacity、damage debt、prize clock、ready state、enemySelect 每次只改一个公开事实并证明预期窗口或 index 翻转。
5. **模糊与突变**：unknown enum/field、sparse presence、重复/越界 index、stale handle、cross-seat、hidden injection、错误 order/chooser/executor 的 mutation canary 必须被捕获。
6. **目录性质**：全卡牌 effect catalog 构建必须无未登记、无新 legacy prompt、无 silent fallback；unsupported 必须有 capability 和原因。
7. **代表性实卡向量**：五套 18.0 卡组及高风险卡用于证明组合真实可达和参数语义，不承担穷举协议空间的职责。

测试分五层：schema/property+fuzz、Python/GDScript conformance、catalog compiler/linter、Godot headless integration、official-wire live/replay witness。只有合成测试不能关闭 Host 执行；只有五套牌绿也不能关闭全目录架构门。

### 5.9.1 Coverage ledger 与分母

不得只报告“通过了多少张卡”。每个 generation 同时发布以下不可互相替代的分母：

| 指标 | 分子 / 分母 | 完成门 |
|---|---|---|
| `wire_context_coverage` | 四态全绿 Context / census Context | 当前 generation 49/49；新增 enum 后自动扩大 |
| `wire_option_coverage` | sparse shape 全绿 OptionType / census OptionType | 当前 generation 17/17 |
| `lifecycle_coverage` | 全绿 lifecycle row / census lifecycle row | 100%，含 setup/KO/terminal/reset |
| `primitive_contract_coverage` | 正向+负向+边界+metamorphic 全绿原语 / Registry 原语 | 100% |
| `composition_edge_coverage` | 已验证状态边 / 预注册 pairwise + 高风险 n-wise 状态边 | 100%，新增组合显式扩分母 |
| `catalog_compile_closure` | compiled + automatic + explicit unsupported effects / discovered effects | 100%，且 unregistered/silent fallback 为 0 |
| `catalog_usable_closure` | fully compiled supported effects / 声明为可用的 effects | 100%，unsupported 不计入可用集 |
| `legacy_elimination` | UCIS-owned interaction callsites / 全 interaction callsites | 100%，author-visible legacy/custom prompt 为 0 |
| `representative_live_coverage` | live 通过的预注册 vector / 五套牌 capability vectors | 100% 才签 W3 operation scope |

任何分母的生成器、source hash、catalog hash 或 capability matrix 漂移都会使相关 receipt 失效。单个卡牌、单套牌或胜率通过不能缩小分母；explicit unsupported 可以关闭 catalog discovery，但不能进入 usable 或 aligned set。

## 5.10 W2 工作包与退出门

| ID | 工作包 | 关键退出门 |
|---|---|---|
| W2-01 | official enum/wire/lifecycle census generator | Observation/State/11/49/17/Area/Energy/Condition/24 Logs/Search、sparse fields、actual-wire drift |
| W2-02 | Prompt + Lifecycle Coverage Matrix | 49 contexts 与所有非 Prompt 生命周期行全有来源、owner、四态和 witness |
| W2-03 | RawEnvelope/TypedView profiles | official passthrough 与 Godot allow-list 分域、hidden/Search 零泄漏 |
| W2-04 | SelectionWindow/fingerprint/hash | 三类 hash 分域；Python/Godot action一致；missing/null/value 保真 |
| W2-05 | identity bridge | 首批 Card/Attack/serial closure，零名称猜测 |
| W2-06 | setup/turn/mulligan/prize/send-out | initial/reset/terminal 和 reobserve 通过 |
| W2-07 | MAIN/attack/retreat | option order、binding、one-shot executor 通过 |
| W2-08 | search/discard/payment/assignment | exact subset/count/order/target 通过 |
| W2-09 | damage/heal/evolve/status/order/count/yes-no | 剩余 context 全覆盖 |
| W2-10 | logs/time/Search/fault | per-seat cursor、budget、Search隔离、capability 和 atomic failure 通过 |
| W2-11 | whole-match dual-host witness | 双座位完整 lifecycle，0 invalid/stale/leak/classic fallback |
| W2-12 | A1 scope report | 所有声明 context 的 projection/validation/execution/log 四态全绿 |
| W2-13 | UCIS Registry、schema 与 compiler | `CardEffectSpec -> InteractionProgram -> SelectionWindow` 唯一通路；标准 wire 原子与领域编排原语有 generation/hash |
| W2-14 | card catalog compiler/linter | 全卡牌 effect closure；零未登记、零新私有 prompt、零 author-visible legacy wire；unsupported 显式 |
| W2-15 | property/fuzz/composition conformance | 原语性质、关键组合、reorder/metamorphic、hidden/stale/mutation gates 全绿 |

A1 分范围签发：

| 级别 | 证明范围 |
|---|---|
| `A1.0 Source/Schema` | actual source、enum、sparse wire 和 drift detection |
| `A1.1 Observation` | raw envelope、current visibility、missing/null/unknown |
| `A1.2 Window` | cardinality、order、fingerprint、validator、private binding |
| `A1.3 Lifecycle` | bootstrap、chooser、多窗口、reset、terminal |
| `A1.4 Logs` | per-seat slice、redaction、commit/witness |
| `A1.T` | exact time profile、计费和 fault |
| `A1.S` | Search=`official_native` 或 `none` |

A1 报告必须列出 `contract_generation/source hashes/contexts raw set/option types/lifecycle rows/Search capability/time profile/four_statuses/unsupported/known-difference`。UCIS 报告另列 `registry/compiler/catalog hashes、primitive coverage、composition coverage、catalog totals、compiled/automatic/unsupported/legacy/unregistered counts`。允许声明“A1 pass for contexts {...}, Search=none, time_profile=X”。只有 0..48 的四态和全部 Lifecycle rows 全绿，才能声明“当前锁定 CABT core selection interface 完整对齐”；只有 W2-13..15 与目录门同时全绿，才能再声明“PtcgDAP 卡牌统一实现 UCIS”；只有 Search 也有真实 bridge 才能声明 `A1+Search`。

### 5.10.1 实现迁移关闭记录

初始 RED 基线包含四项：Projector 只覆盖少量 Option 且拒绝非空引用；Author owner 使用自定义编号/字符串猜 Context；setup 预缓存 bench、强制全选和固定 mulligan；Python/Godot validator 拒绝合法 `SKILL(0,0)`。当前 generation 已通过完整 17 Option 稀疏 shape、显式 raw Context、fresh optional setup-bench/mulligan lifecycle、引用 presence 和 `SKILL(0,0)` conformance vectors 关闭这些基线问题。它尚未证明 UCIS compiler、全卡牌 catalog closure 或 legacy private protocol 清零；W2-13..15 是本次修订新增的未实现工作包。

关闭记录只支撑 scope `55D3F6B8DCD6BD3386277E90D062A705DCE9321EBBACB753B1B59F4A13B9086C` 的 core selection A1；Competitive v2 的 `desired_count`、energy debt 或 assignment 派生能力仍不作为 CABT A1 证据，Search 仍为 `none`。

---

# 6. W3 — 五套 18.0 对应卡的操作 I/O 对齐与独立 full-rule A3

## 6.1 认证范围

首批候选 deck IDs：

```text
800018501  玛俐的长毛巨魔
800017097  沙奈朵
800018499  多龙
800018509  猛雷鼓
800018502  N 的索罗亚克
```

这些是本地 deck source identity，不是 official CABT deck identity。对应卡 operation scope 以私有 UID 为权威：每个纳入声明的 printing/attack/ability 必须建立 source-locked bridge，保存双方原始身份并通过语义关系比较，缺失、歧义或 name-only mapping 即 fail closed；不要求五副牌与官方 deck/Card ID 列表 60/60 相等。为了构造合法 live 前缀，可以为单个对应卡使用独立的合法微型测试牌组；该牌组只提供到达 authority，不会被宣称为五套牌的官方等价物。trainer、energy、tool、stadium及其调用的公开选择窗口按实际可达性进入 operation I/O coverage。

在 UCIS 架构中，这五套牌是首批 **代表性 conformance vectors**：它们用于验证检索、精确数量、多目标分配、攻击/能力、伤害分配、进化、换位、特殊状态、KO/奖赏等高风险原语组合能在真实牌局中到达。它们不是五套孤立的 private adapter，也不定义 UCIS 全集。某张代表卡通过只证明该 vector；全卡牌标准化仍由 W2 catalog closure 证明。

项目负责人当前要求的正式范围定义为：

```text
OperationIOScope =
  OracleProvenance
  × GodotBuild
  × PrivateDeckSourceSet
  × CorrespondingCardAndAttackIdentityClosure
  × UCISRegistryCompilerGeneration
  × PrimitiveAndCompositionVectorSet
  × PromptScope
  × CurrentWindowInputProjection
  × AcceptedIndexContract
  × AdapterComparatorGeneration
```

独立的 full-rule 结果资格才使用：

```text
FullRuleA3Scope =
  OperationIOScope
  × ExactLegalTrajectorySet
  × EffectAndRuleCapabilityClosure
  × PublicTransitionAndLogSurface
  × RandomCapability
  × TerminalOutcomeSurface
```

认证 scope manifest 固定：

```text
official bundle/engine/module hashes（trusted-private 只保留 hash）
Godot commit + dirty-worktree content manifest
Godot private deck/card source hashes
sealed corresponding Card/Attack/Ability relation hash
UCIS registry/compiler/catalog scope hash
SelectContext scope
ordered OptionType/current-window input coverage
adapter/comparator/action protocol hashes
known differences and unsupported list
```

任一 operation row 的 `known-difference` 或 `unsupported` 都会从 input/index aligned set 中删除该 row。只有 current-window input 和相同 index 在两端均被接受，才能晋升该 operation row；提交后的 state/log/next checkpoint 不在当前 row 的结论中。若未来重新打开 full-rule A3，任何可达路径中的差异都会按独立资格处理。

## 6.2 双 Engine Adapter

定义语言中立测试接口：

```text
create(scope_manifest)
start(match_spec) -> Checkpoint
next_checkpoint() -> Checkpoint
commit(window_handle, indexes) -> TransitionWitness
semantic_snapshot(view, capability)
random_events_since(cursor)
terminal_result()
dispose()
```

adapter 不允许调用者任意 `observe(seat)`。官方 engine 只在当前 `selectPlayer` 的决策 checkpoint 发布 acting-seat callback；非 acting seat 没有并行可调用窗口。`Checkpoint` 至少包含：

```text
kind = INITIAL_DECK | SELECTION | TERMINAL
transition_ordinal / callback_ordinal / acting_seat
raw_actor_observation / raw_observation_hash
window_handle / generation
select header / ordered raw options / option fingerprints
incremental log slice / semantic public snapshot
random event cursor / diagnostic capability mask
```

显式状态机为 `CREATED → STARTED → WAITING_SELECTION → COMMITTED → INVALIDATED → NEXT_CHECKPOINT|TERMINAL → DISPOSED`。每个 handle 只 commit 一次，并再次验证 session、seat、generation、observation hash、window hash 和 option order。

实现：

- `OfficialCabtEngineAdapter`：调用锁定 official native API；seeded extension 使用独立 capability ID；
- `GodotHeadlessEngineAdapter`：通过正式 engine decision owner，而不是测试直接改 GameState；
- adapter 不归一化掉真实差异。canonicalization 只处理表示等价，不重排 option、不翻译 identity、不补默认值。

任意 private GameState 注入只允许进入独立 `ScenarioBootstrapAdapter`，不得进入 whole-match adapter 或冒充 official legal trajectory。

## 6.3 差分驱动协议

input/index operation row：

```text
分别以合法前缀到达同一声明的语义 lifecycle anchor
-> 比较 acting seat/select header/current-window operation fields
-> 比较 ordered semantic options 和 fingerprints
-> if any mismatch: stop before action
-> resolve one semantic intent independently against both current windows
-> require same ordered indexes only after option parity
-> validate/commit once in each engine
-> require both engines accept the current-window indexes
-> stop; transition/log/next checkpoint are not part of this row
```

anchor 不能只写 `type/context/seat`。它还必须锁定 lifecycle occurrence、先攻选择、当前 setup/main/KO 子阶段、必要的公开前置事实，以及目标实体的 match-local lineage；若这些事实不可同时证明，则该 live row 失败，不能通过“在两端分别找到任意同形窗口”获得绿色。

独立 full-rule A3 的每一步才扩展为：

```text
capture both callbacks
-> compare lifecycle/select/current/logs
-> compare ordered options and fingerprints
-> if any mismatch: stop before action
-> resolve one semantic intent independently against both current windows
-> require same ordered indexes only after option parity
-> validate/commit once in each engine
-> capture execution witness
-> compare next state/logs/window
```

不能在 option 已不同后继续提交相同 index；那会把首差异污染成后续规则差异。

驱动模式：

1. `semantic-script`：动作由 `SemanticCardRef/SemanticPokemonRef/SemanticZoneRef/SemanticAttackRef`、count/order 描述；两侧分别绑定本地 serial，禁止要求数值相等；
2. `exact-index`：只有 ordered option 已全等时使用；
3. `policy-driven`：同一冻结 `.ptcgbot` 产生动作，用于完整局，但不替代前两种诊断模式。

跨引擎 entity relation 只允许有证据的 match-local alpha-renaming：官方 Card ID/Attack ID 与私有 UID/attack ordinal 分域保存，经 source-locked bridge 对应，绝不要求数值相等；card serial 通过 exact deck occurrence、zone movement 和 event lineage 建双射；duplicate printing 暂不可区分时保留 equivalence class；不得按 card name、slot name 或 current zone 猜配。official Pokémon serial 可能随进化顶层卡变化，Godot stable slot 不能直接冒充。每个 checkpoint 同时保留 raw per-engine fingerprint、entity-bijection hash 和映射后的 semantic fingerprint。只有 semantic option fingerprint 序列完全一致才可提交动作。

## 6.4 快照与隐私

A3 的“每步”定义为：从一个合法 agent callback/selection checkpoint，经一次 accepted selection 和全部自动规则处理，到下一个 callback 或 terminal checkpoint 的语义转换一致；不是 C++/GDScript 指令级内部状态一致。

### 6.4.1 Public parity snapshot

- callback lifecycle；
- current public state；
- select type/context/count/remain；
- ordered options；
- incremental logs；
- damage/status/KO/prize/result 的公开表现。

这是 A3 必须零未解释差异的 authority surface。A3 声明限定在 engine 发布的决策边界 callback/select/incremental logs/可视 current 与终局语义，不因测试 instrumentation 扩大官方 surface。

### 6.4.2 Trusted diagnostic snapshot

只在隔离测试目录保存，用于定位：

- zone order/count、hidden deck/prize identities；
- card entity/serial、evolution stack；
- attached energy/tool/other attachments；
- HP/damage/status、continuous/replacement effects；
- turn flags、once-per-turn usage、pending effect stack；
- RNG cursor/input、win-condition state。

公开报告只输出域级 hash、差异路径分类和脱敏摘要。官方引擎若需 instrumentation 才能取得 private snapshot，instrumentation patch 必须 source-locked、证明只读且不改变语义；即便如此，pending effect stack、RNG cursor 和内部 flags 仍只作 diagnostic，不授予 official A3 authority。

canonical snapshot 每字段都标记 `comparable | diagnostic-only | unavailable`。它必须保留 missing/null/zero、所有有序数组和整数语义；不按本地化名称比较；区分 damage amount 与 damage-counter count、owner 与 controller；记录 evolution stack、attachments、effect lifetime、once flags。现有 Godot `ScenarioStateSnapshot` 含本地名称、完整 CardData/对象等，只能作场景恢复输入，不能直接成为语言中立 A3 schema。

## 6.5 RNG 设计

RNG 是 W3 前置架构，不是跑整局时再补的参数。实施前必须盘点 Godot 的 deck shuffle、coin、随机伤害/状态/目标和每个 card effect RNG 调用；任何 effect 内部重新 `randomize()`、独立创建 RNG、依赖全局调用顺序或无法记录 source/ordinal 的路径都先标为 `rng-owner-not-aligned`。

目标是唯一 `RandomEventPort`；shuffle、coin、random-card/order/target、随机 damage/status 和所有 effect 都必须经过它。事件至少记录：

```text
event_ordinal / event_kind / acting_seat
source Card/Attack/effect identity
population fingerprint / requested count
outcome or permutation
pre-state hash / owner generation
```

测试 random tape 只能在受审 seam 注入，必须证明不改变 RNG 调用次数、顺序、范围或后续状态。Godot 和 seeded derivative 的“相同整数 seed”不能自动推导为相同随机序列。

随机能力分级：

| 等级 | 能力 | 可作的声明 |
|---|---|---|
| R0 | 从认证 checkpoint 到下一 checkpoint 无随机，且到达该 checkpoint 的前缀有合法构造证明/官方轨迹锚 | 可直接 official-vs-Godot A3 |
| R1 | 官方轨迹给出已发生随机事实 | 可验证相同前后状态，不声称 seed control |
| R2A | official/seeded oracle 产生 random tape，Godot消费同一 tape | 仅 `conditioned-on-random-facts parity` |
| R2B | 两端 PRNG、seed、消费顺序全部一致 | 可声明 same-seed parity；需逐项证明 |
| R3 | 官方 runtime 正式、可审计地暴露 seed/random-control API | 可在声明 generation 内完整随机 A3 |
| RX | 无法对齐 | `unsupported-random-capability` |

不得通过重试直到随机结果相同、修改牌库顺序但不记录、或忽略 coin/shuffle 差异获得绿色报告。

即使目标卡效本身无随机，开局 shuffle/prize/setup 前缀仍可能随机；微场景必须证明合法 pre-state 构造、绑定官方轨迹锚，或把随机事实条件化为明确输入，不能仅凭“当前动作无随机”归为 R0。

Search RNG 是独立 capability，不能与真实 match 的 shuffle/coin RNG 混用。当前 Godot 多处独立 RNG/现场 `randomize()` 是 W3-03 RED 基线；统一 RandomEventPort 前不得运行完整随机 A3。

## 6.6 PTCG 规则高风险域

认证不能只按卡名清单，必须覆盖效果机制：

- 伤害计算顺序：基础伤害、弱点、抗性、攻防修正、保护、bench damage/counter；
- 能量单位与卡数量分离、特殊能量、多单位支付、弃能顺序；
- evolution stack、devolve、HP/状态/附着保留或移除；
- continuous、replacement、prevent、once-per-turn 和跨回合 effect；
- first-turn attack/Supporter、retreat、stadium/tool 唯一性与使用标志；
- search/look/reveal/shuffle/top/bottom/deck order 与公开范围；
- simultaneous KO、奖赏价值、奖赏领取、deck-out、无 active 和多胜负条件的结算顺序；
- switch/gust/bench capacity、Tera/bench protection、target legality；
- attack/ability copy、granted attack、effect order、optional effect；
- special condition 在 between-turns 的处理与恢复；
- 对手公开信息和 acting-seat perspective。

每个机制建立 capability ID，并映射到 UCIS 原语/组合；同一 capability 的 window 生成、数量、chooser、binding 和 lifecycle 只能有一个 engine owner。Card ID 只有其全部被触发 capability 已编译、其卡牌特有规则参数测试通过，才进入 certified set；协议原语本身不为每张卡复制实现。

五套牌的最小高风险矩阵如下；实际 scope 由 exact 60 和传递调用闭包生成，不能用本表删减：

| 牌组 | 必须认证的关键机制 |
|---|---|
| 玛俐长毛巨魔 | 庞克泵感 `0..5` 精确检索、逐张多目标分配与 shuffle；暗影子弹 active/bench damage；谢米保护；雪妖女 Pokémon Check 双方 counters/simultaneous KO；愿增猿移动 counters；含羞苞跨回合物品锁 |
| 沙奈朵 | 精神拥抱任意次数、弃牌区能量、属性目标、附着后 20 damage 且不能自 KO；飘飘球/吼叫尾按自身 damage；勇气护符 HP/失效；莉莉艾的皮皮对龙弱点覆盖；愿增猿 counters 移动 |
| 多龙 | 幻影潜袭 200 damage 与六个 bench counters 任意分配；谢米/Tera 对 damage 与 counters 的不同保护；摔角鹰人入场 counters；沙铃仙人掌反伤；多龙奇 top-2/hand/bottom order；TM 退化与 simultaneous KO |
| 猛雷鼓 | 极雷轰从任意己方宝可梦弃任意数量 basic energy、来源/顺序和 `70×`；碧草之舞 attach+draw；奥琳博士/赤松多源多目标；猫头夜鹰的 Tera prerequisite 与最多两张 Trainer；百变怪首回合 replacement；梦幻复制；零之大空洞 bench capacity；顶尖捕捉器双向 switch；灼伤/自伤/coin |
| N 的索罗亚克 | 交易的 discard cost/once/draw；暗夜王牌复制 bench N Pokémon attack 及 attacker context；达摩狒狒复制后的弃能/bench damage；莱希拉姆按 copying attacker counters；N 的 PP 提升剂、N 的城堡、逆转能量条件 |

跨牌组 capability 必须显式覆盖：damage、counter placement、counter movement；Rule Box/Tera/Ancient/Marnie/N/Psychic/Dragon tags；Tera 与谢米 bench protection；Fairy Zone 弱点覆盖；Stadium replacement/失效/bench overflow；tool 失效导致 HP/KO；attack-copy context；simultaneous KO/prize/no-active/deck-out 优先级；between-turns/Pokémon Check 顺序。

## 6.7 原语、组合与卡牌语义场景合同

每个 UCIS 原语/组合场景以及必要的 card/effect 语义场景记录：

```text
scenario_id / scope hash
exact pre-state construction proof
acting seat and current lifecycle
semantic action
expected current window
selection
expected state delta
expected logs
expected next window or terminal
random capability
construction authority
public/private evidence classification
```

最低场景集：正向、缺前置、错误目标、上下限、空/不足 source、bench full、deck/prize edge、exact KO 与差 10、同名不同 printing、option reorder、mandatory/optional、连续两次窗口、未知/unsupported。关键阈值使用只改变一个事实的 metamorphic pair。

场景生成规则：

- wire/cardinality/chooser/order/stale/hidden 等通用行为由原语 property/fuzz suite 一次性覆盖，不为每张卡复制；
- Search→Assign、Retreat→Pay→Switch、KO→Prize→Promote 等组合由 InteractionProgram 状态机生成 pairwise 和高风险 n-wise 场景；
- 每张卡只补它独有的规则参数、predicate、阈值、持续期和 capability 组合场景；
- catalog 中每个产生选择的 effect 至少绑定一个已绿原语/组合 vector，未绑定即 compile/qualification failure；
- 五套牌 live witness 证明代表性组合可达，但不能用牌组胜率或少量成功轨迹替代协议性质测试。

`construction authority` 只能取：

```text
official-legal-prefix
official-recorded-trajectory-prefix
seeded-oracle-legal-prefix
instrumented-derived-snapshot
godot-synthetic-only
```

只有合法 official prefix 或适用许可下的官方轨迹能直接支撑 official A3。instrumented/synthetic scenario 可发现规则 bug，但不能单独晋升。official battle API 不具备任意 private snapshot restore，因此每个双端微场景必须提供合法到达前缀，不能假定可向未修改 official binary 注入 Godot state。

## 6.8 验证金字塔

1. **标准 wire/原语层**：11/49/17、数量、chooser、order、binding、visibility、stale/hidden 的 property/fuzz/metamorphic；
2. **编译与目录层**：每个 card/effect 完整编译或显式 unsupported，静态禁止 custom prompt/legacy wire；
3. **交互链层**：search→discard→assignment→attack、KO→prize→send-out 等多窗口组合；
4. **代表性实卡层**：五套牌的卡牌特有参数、阈值和高风险 capability vector；
5. **固定整局层**：五套牌两座位、预注册 action scripts/random capability；
6. **有界差分探索**：在 certified action frontier 中生成合法短序列，优先覆盖未访问状态边；
7. **回归语料层**：每个历史首差异最小化为永久 fixture；
8. **策略对局层**：只作为实际可达性和性能补充，不替代规则一致性。

完整局 scope 固定为 10 个不同牌组组合×两个 seat order，加 5 个 mirror，共 25 个 exact ordered deck-pair 配置；每副牌至少在 seat 0/1。random tapes 按 capability edge 覆盖选择，不按任意 seed 数量凑样本。覆盖账本记录每个可达 effect、prompt、KO、terminal 和 random-event edge。

bounded exploration 每一步只能从两侧当前窗口的 semantic action intersection 选择；frontier 一旦不同立即记录首差异并停止，不能继续污染轨迹。

## 6.9 First-divergence 和最小化

开发运行状态：`aligned | unexplained_difference | harness_error | dirty_or_incomplete | unsupported`。最终 certification ledger 才收敛为 `aligned | known-difference | unsupported`；存在 unexplained、harness error 或 dirty case 时不生成 A3 artifact。

稳定差异分类：

```text
oracle_provenance_diff
lifecycle_diff
observation_visibility_diff
contract_shape_diff
option_field_presence_diff
option_generation_diff
option_order_diff
cardinality_diff
legality_diff
entity_lineage_diff
zone_order_diff
evolution_stack_diff
binding_or_execution_diff
random_schedule_diff
random_outcome_diff
damage_diff
damage_counter_diff
status_lifetime_diff
continuous_or_replacement_diff
once_per_turn_flag_diff
log_diff
ko_resolution_diff
prize_resolution_diff
promotion_diff
terminal_diff
harness_or_canonicalization_diff
```

`known-difference` 必须在测试前登记 exact scope、预期 diff fingerprint、owner、原因、期限和退出条件；不能在失败后临时改名。它若在五套牌可达路径中，则相关 capability 不属于 aligned set。

报告保存最后一致 checkpoint、差异发生在 action 前或 commit 后、双端 raw/semantic hash、entity-bijection hash、random cursor、raw presence diff、semantic intent 与两侧 indexes、oracle/adapter/comparator/scope hash。私有值只进隔离 artifact，公开报告只给域 hash。

最小化顺序是：在首差异截断全部后缀；最小化到达首差异的动作前缀；简化 semantic choices/数量/random tape；只有双端 ScenarioBootstrap 都能合法重建时才裁剪 board entities。每次保持同一分类和 provenance；exact 60 deck 不得为缩小 reproducer 非法删卡。

## 6.10 晋升与回滚

一个 full-rule Card/capability 只有在以下条件全部满足时才能晋升；这组门不阻断当前 operation input/index row：

- 项目负责人本地研究范围、oracle/source provenance 和 public/private evidence 分域通过；
- 两侧各自 exact self-rerun 通过；mutation canary 故意注入 option reorder、damage、log、serial、RNG、terminal 错误时 harness 全部捕获；
- catalog 为纳入声明的每张私有卡生成唯一 source-locked correspondence closure，且合法测试轨迹和全 effect/rule dependency closure 完整；不要求私有五副牌与官方数字 ID 列表相等；
- identity/effect source closure；
- 原子与边界场景全绿；
- 所有可达 SelectContext/Lifecycle rows 已在 W2 A1 aligned 范围；
- public parity zero unexplained diff；
- random capability 明确；
- Python/Godot comparator 结果一致；
- evidence manifest、first-divergence corpus 和 known gaps 可复核。
- 25 个 ordered deck-pair 配置满足预注册覆盖，bounded exploration 零 dirty/harness/unexplained；
- private evidence 隔离与 public projection 复核；独立 PTCG 规则、差分架构审查和 rollback drill 通过。

任一来源、engine、card data、effect code、comparator 或 contract hash 变化，相关 scope 自动退回 `needs-requalification`。回滚是选择上一完整 scope manifest，不删除新负证据、不把 known difference 改名隐藏。

canonicalizer、comparator 或 entity relation generation 变化会使全部相关结果 `needs-requalification`，不能只重跑曾失败卡牌。seeded derivative 单独全绿时，对外最多声明 `seeded-development-oracle aligned`。

## 6.11 W3 工作包与退出门

| ID | 工作包 | 关键退出门 |
|---|---|---|
| W3-00 | 项目范围、oracle class、source/patch/build provenance | 本地研究范围通过；official/seeded/Godot身份和允许声明封闭；不把授权或官方 ID equality 作为技术门 |
| W3-01 | 五副私有 deck source 与对应 printing/attack/ability bridge | 私有 UID 权威、显式 source-locked bridge、缺失/歧义/name-only 零容忍；无需 official 60/60 equality |
| W3-02 | scope/capability/entity-bijection matrix | 卡×当前窗口交互×identity profile 机器可审计；full-rule 随机/效果矩阵分域 |
| W3-03 | RandomEventPort/event tape/RNG capability | 全 RNG callsite 单一 owner；无 effect-local randomize；R0..RX受审 |
| W3-04 | authority/diagnostic snapshot schema + canonicalizer | 字段 capability、presence/order保真，不归一化真实差异 |
| W3-05 | 双 Engine Adapter/self-replay | event-driven checkpoint/commit/terminal/dispose 与两侧 exact self-rerun |
| W3-06 | lockstep driver/semantic action binder | serial分域；semantic frontier不同即停止；reorder可诊断 |
| W3-07 | first-divergence/minimizer/mutation canaries | 故意错误全捕获；差异稳定最小复现 |
| W3-08 | UCIS 原语/组合 + 对应卡语义 scenarios | 通用协议性质不逐卡复制；每个声明 row 有合法前缀、current-window input、ordered options、index acceptance 和负例 |
| W3-09 | representative whole-battle operation coverage | 五套牌作为代表性向量覆盖精确数量、逐次分配、能力、攻击、伤害分配、撤退/换位、进化、特殊状态等 live 窗口；不要求 post-state parity，也不代替全目录门 |
| W3-10 | 独立 full-rule 差分（后续） | 只有重开结果一致性目标时才要求 25 配置、状态/日志/终局和 bounded exploration |
| W3-11 | evidence/独立 review/promotion+rollback | input/index 与 full-rule 使用不同 receipt、maximum claim 和 rollback；不得相互晋升 |

当前 W3 总门只允许在 scope 内所有声明的对应卡 operation row 均为 `input-index-aligned` 时签发 `corresponding_card_whole_battle_input_index_contract`。它不得签发“全卡牌统一标准”资格；后者必须由 W2-13..15 的 UCIS/compiler/catalog closure 单独证明。只有独立 full-rule scope 的所有可达 capability 均为 `aligned` 时，才可另行声明 `A3 pass for <exact scope manifest hash>`；任何时候都不得简写为“Godot 已与官方完全一致”。

---

# 7. 跨工作合同

## 7.1 版本绑定

一个可评测 release 必须同时固定：

```text
.ptcgbot archive hash
runtime profile hash
SDK/observation/select contract hash
UCIS registry/compiler/catalog hash
official engine/module/catalog hash
deck content hash
qualification profile/receipt hash
W2 A1 scope hash
W3 A3 scope hash（如声明 Godot parity）
```

任何 hash drift 都创建新 release/profile/scope，不热换进行中的 match。

## 7.2 错误码分域

错误至少分为：

- `package_*`：ZIP/manifest/source/resource/deck；
- `runtime_*`：import/dependency/ABI/resource/process；
- `policy_*`：exception/timeout/output/determinism；
- `window_*`：shape/cardinality/stale/reorder/seat；
- `interaction_compile_*`：unknown primitive/invalid spec/unsupported shape/legacy bypass；
- `catalog_*`：unregistered effect/incomplete closure/custom prompt/unsupported capability；
- `binding_*` / `execution_*`：ticket/atomic apply/engine reject；
- `parity_*`：contract/identity/option/rule/log/RNG/terminal；
- `authority_*`：错误地请求 Search、production、device 或 official 权限。

同一根因在 Python、Godot、CLI、qualification 和报告中使用相同稳定码。

## 7.3 数据分级

| 数据 | 策略可见 | 可公开 | 可持久化 |
|---|---|---|---|
| acting-seat official observation | 是 | 仅经 public projector | public trace 可存允许字段 |
| `search_begin_input` | capability 开启时当前 callback | 否 | 否 |
| opponent hidden/deck order/face-down prize | 否 | 否 | 仅隔离 private diagnostic |
| private engine snapshot | 否 | 否 | 隔离、限时、hash evidence |
| public parity snapshot/replay | 是/可派生 | 是 | 是，完整 hash chain |
| author source/package | 自己可见 | 按发布政策 | content-addressed private storage |

## 7.4 性能原则

先通过合同和规则一致性，再优化吞吐。性能优化不得缓存旧窗口 authority、跳过 reobserve、复用跨 match mutable state、弱化 hash/validation 或把本地失败转成远程 fallback。

UCIS 的运行时路径必须是预编译 registry lookup + 当前状态 legality query + 稀疏 projection，不得在每个 decision 反射扫描全部卡表、启动子进程、读取磁盘 schema 或调用外部 Forge。卡牌目录、InteractionProgram、predicate bytecode/IR 和 option encoder 应在 build/load 阶段校验并缓存为 immutable generation；当前窗口只计算本次 effect 的候选。性能基准分别报告 compiler/build cost 与 per-window runtime cost，不能通过回退 classic GDScript 策略或减少验证获得速度。

## 7.5 旧私有卡牌协议迁移

迁移采用 generation 级 strangler，不允许长期双重 authority：

1. **Inventory**：扫描全部 card/effect、Host 和 adapter callsite，生成 legacy prompt/context/option/return-field 账本，记录调用卡牌、可达性、数量语义、目标语义和 owner。
2. **Classify**：把每个 legacy callsite 映射到现有 UCIS wire 原子/领域组合；不能映射的条目输出 `unsupported_interaction_shape` 或 protocol gap，不做卡牌特例。
3. **Compile**：将卡牌改为 declarative `CardEffectSpec`；compatibility translator 只能存在于 engine-private migration layer，输出必须通过同一 UCIS validator，策略不可见 legacy 字段。
4. **Shadow**：在不执行第二份动作的前提下，同时生成 legacy 与 UCIS semantic window，比较 chooser、header、ordered options、cardinality 和 binding fingerprint；差异即 RED。不得 dual commit。
5. **Cut over by capability**：同一 capability 的全部 callsite、性质测试和代表性 live vector 通过后，整组切到 UCIS；不能按策略包选择不同协议。
6. **Close catalog**：全目录重新编译，要求 `unregistered=0`、`legacy_author_visible=0`、`custom_prompt_builder=0`、`silent_fallback=0`；unsupported 保持显式且不能进入可用卡池资格。
7. **Delete authority**：移除 legacy public schema/adapter 分支和写入口；只保留只读迁移 fixture 到一个有期限的 generation。回滚选择上一完整 engine/UCIS generation，不在新 generation 内重新打开逐卡 legacy fallback。

迁移不是“挨个手工对比完所有宝可梦”。人工工作集中在 inventory 中无法自动分类的少数新交互形状和卡牌特有规则语义；其余卡牌通过 spec 生成、catalog compilation、property suite 与 representative vectors 批量关闭。

---

# 8. 实施顺序与依赖

```text
M0 Source/Scope Freeze
  W0 local-research/distribution isolation
  W1-01 package proposal
  W2-01 official census
  W3-01 private deck source / corresponding-card bridge closure plan
        |
M1 Standard Contract Foundation
  W1-02..05
  W2-02..05
  W2-13 UCIS registry/schema/compiler
  W3-02..05
        |
M2 Catalog Migration and Window Ownership
  W2-14 legacy inventory / CardEffectSpec migration / catalog closure
  W2-06..10
  W3-06..09
        |
M3 Conformance and Interface Promotion
  W2-15 property/fuzz/composition conformance
  W2-11..12 => A1 scoped pass
  W2-13..15 => UCIS catalog-scoped pass
        |
M4 Engine Differential
  W3-10..11 => A3 five-deck scoped pass
        |
M5 Developer Preview
  W1-06..08 using exact A1/A3 scope
```

包 schema 可以先开发，但 W1 Runner 不能在 W2 前声称 Godot interface aligned，不能在 W3 前声称 Godot rule aligned。

### 8.1 预计修改所有者（实施时）

| 层 | 主仓库 | 预期制品 |
|---|---|---|
| v2 package/schema/builder/SDK | PtcgDAP + Forge vendored snapshot | schema/profile/vectors、builder、validator、CLI、templates |
| official source refresh | PtcgDAP，ptcgabc 只读 | SOURCE_LOCK、generated census、drift reports |
| UCIS registry/compiler/catalog linter | PtcgDAP；Forge vendored contract | generated schemas、typed IR、effect compiler、legacy inventory、catalog closure |
| window/Host/identity/log | PtcgDAP | language-neutral contracts、Python/GDScript owners、Godot integration |
| card/deck author data | Forge + PtcgDAP | private UID deck、source-locked bridge、declarative effect/capability manifests |
| engine differential | PtcgDAP，ptcgabc oracle | adapters、comparator、scenarios、reports |
| SDK distribution | Forge | reviewed snapshot、doctor/check、developer docs |

---

# 9. 开发流程与证据要求

每个行为工作包执行：

1. 检查 dirty worktree，记录并保护用户改动；
2. 固定 source/contract/scope hash；
3. 在最早 owner 层添加 RED 测试；
4. 确认 RED 原因属于该工作包；
5. 最小实现；
6. option reorder、negative gates、hidden sentinel、unknown-field 和 metamorphic pair；
7. targeted tests，再跑受影响 full lane；
8. 生成 exact evidence、known gaps、rollback identity；
9. 同步 TODO、architecture、status、changelog 和 Forge SDK manifest。

重型 benchmark/差分探索串行运行，遵守本机 Python 进程和内存门。A1/A3 合同测试优先于胜率。

---

# 10. 最终验收定义

## 10.1 W1 完成

- 仓库外开发者从 clean workspace 创建多文件策略；
- local runner 接收真实 official callback；
- 两次构建 exact bytes 相同；
- qualification 与服务端对同 archive/profile 结果相同；
- trace 能定位首个 policy/window fault；
- v1 无回归；
- 不声称 production sandbox。

## 10.2 W2 完成

- 当前锁定的完整 Observation/State/enum/sparse Option/24 Logs/Search wire 有 census；
- 49 Context 的 Prompt Matrix 与所有非 Prompt Lifecycle rows 机器可验证；
- UCIS Registry/typed IR/compiler 是所有卡牌选择交互的唯一生成路径；CardEffectSpec 不能绕过 engine owner 创建 prompt、option 或执行动作；
- 全卡牌目录 closure 为 `unregistered=0`、`legacy_author_visible=0`、`custom_prompt_builder=0`、`silent_fallback=0`；无法表达的效果显式 unsupported，不进入可用卡池资格；
- 标准原语、关键组合、catalog compiler 的 property/fuzz/metamorphic/mutation suite 全绿，并有代表性实卡 live vectors；
- 所有声明 context 的 projection/validation/execution/log 四态均有 Godot owner、binding、reobserve 和 witness；
- initial/setup/mulligan/prize/reset/per-seat logs/time/terminal 生命周期对齐；
- Python/Godot contract/hash/action 一致；
- 0 hidden leak、0 stale/replay/cross-seat acceptance、0 classic fallback；
- 按 A1.0..A1.4/A1.T/A1.S 与 UCIS generation/catalog scope 分别签发 exact receipt；Search=none 时不称完整官方 API，目录 closure 不等于 full-rule A3。

## 10.3 W3 完成

- 五套私有牌源锁定，以 private UID 为权威；所有纳入声明的对应 Card/Attack/Ability bridge 唯一、source-locked、缺失/歧义/name-only fail closed；不要求官方完整卡表或 60/60 ID equality；
- 五套牌只作为代表性 UCIS capability/composition vectors；不得生成五套 deck-specific public adapter，也不得用其通过替代 W2 全目录 closure；
- 每个声明的实际可达 operation row 均有合法前缀、acting seat/lifecycle anchor、select header、ordered semantic options 和相同 current-window indexes 双端接受证据；
- 覆盖精确数量、逐次 source→target 分配、能力、攻击、伤害分配、撤退/换位、进化、特殊状态及五套牌实际触发的其他选择窗口；
- 旧 handle、重复/越界 index、option reorder、错误 seat、未知/歧义 identity 和 hidden-field 注入全部 fail closed；
- 签发 exact `corresponding_card_whole_battle_input_index_contract` scope/receipt、source hashes、known gaps 和 rollback identity；
- 不把 bootstrap prefix、post-state、logs、next checkpoint、伤害/KO/随机/终局写入该合同。若未来要求 full-rule A3，再独立完成 46 项场景、交互链、25 配置、zero-unexplained-diff 和规则/架构复核。

## 10.4 对外可用声明

三项全部通过后，只允许如下表述：

> 社区开发者可以使用 Kaggle 风格 Python `agent(raw_observation) -> list[int]` 开发、调试和构建确定性 `.ptcgbot`。PtcgDAP 卡牌效果统一编译到已公布 generation 的 UCIS，Godot Host 对当前锁定 CABT 选择接口达到 A1；在已公布的五套 18.0 私有 UID 对应卡 scope 内，Godot 与 source-locked 官方模拟器在声明的 current-window operation input、ordered legal options 和返回 indexes 上对齐。

仍不得声称：Kaggle 官方背书、全卡池官方一致、提交后的规则状态/伤害/KO/随机/终局 A3、生产第三方代码沙箱、Android/A5、`.ptcgbot` 可直接安装到玩家设备，或策略强度达到经典 AI。

---

# 11. 风险、决策默认值与暂停条件

| 风险/决策 | 默认选择 | 重新打开条件 |
|---|---|---|
| 作者依赖 | 预装 pinned runtime；v2 不带 wheels | 纯 Python/资源不能满足已测策略，并完成 native threat/ABI 设计 |
| 模型资源 | 只允许显式 inert format/loader；拒绝 pickle | 有受审 operator/shape/loader 和 sandbox 证据 |
| Search | official capability 显式开；Godot none | 有真实 bridge 和独立 conformance/security evidence |
| 随机策略 | developer-local 可用；official_verified 要 transcript deterministic | 赛制接受并记录可复核 RNG API |
| operation I/O 首批范围 | 五套 18.0 私有 deck 中具有 source-locked bridge 的对应卡及实际可达选择窗口 | 不能为通过而隐藏未覆盖 row；无 bridge 的卡保持 unsupported，不要求官方完整卡表或 deck equality |
| unknown enum/field | preserve raw、fail closed | 官方来源 refresh 后新增 generation |
| official seeded parity | seeded 只作开发 oracle | RNG hook 纯度与 official runtime capability 有直接证据 |
| 新卡交互 | 编译到现有 UCIS 原语/组合 | 只有 source census 证明出现全新 official interaction shape 才提升 generation |
| legacy 私有协议 | 只作限期 engine-private 迁移输入 | catalog closure 后删除写入口；不接受长期双 authority 或 deck-specific fallback |
| 卡牌规模 | spec generation + catalog/property closure | 只对无法自动分类的全新形状或卡牌特有规则做人工设计 |

以下情况必须暂停并请求方向：

- 实施范围从本地私有研究扩展到 official runtime/card-data 分发、托管或官方认证；
- 纳入 operation 对齐声明的对应卡无法建立唯一 source-locked printing/effect bridge；
- 目标 Python 依赖要求 native code，超出 v2 threat model；
- official source 出现现有 UCIS 无法表达的新选择形状，而来源/callsite 无法确定；
- legacy inventory 发现同一卡效存在无法确定的双 owner，无法在不改变规则语义的情况下选择 authority；
- Godot 与官方在基础规则上出现需要重写引擎的大范围差异；
- 随机能力无法获得可复核输入却要求作完整 A3 声明；
- 实施需要修改只读 `ptcgabc` oracle、发布、部署、安装 production 包或开放外部作者。

---

# 12. 多专家评审记录

本轮由三个独立 agent 做只读评审，主 agent 汇总并修改本设计；任何 reviewer 都未改代码。

| Reviewer role | 初审结论与主要反对意见 | 已采纳修改 | Closure |
|---|---|---|---|
| W1 平台架构/开发者体验 | 原草案未把 competition-use-only 许可作为前置；deck bootstrap 与 selection 返回域混名；builder/API/worker/runner 易重复校验；canonical ZIP/runtime/dependency/trace/迁移约束不足 | 新增 W0；判别式 RPC 返回域；单一 `CompetitionBundleV2` owner；runtime/content manifest；`ZIP_STORED` canonical profile；sync agent、deck legality、prequalify 与 public/private trace | developer-local 实现与 conformance 通过；official runner 受 W0 约束 |
| W2 CABT/PTCG 合同 | 原草案只有架构轮廓，缺完整 wire census、49×17 映射、non-prompt lifecycle、三类 hash、per-seat logs 和 scoped A1；Competitive v2 不能冒充 official CABT | 加入完整 mapping/sparse shape；actual wire 优先级；Raw/Projection/Host-private 三层；Prompt+Lifecycle matrices；四种数量编码；Search/time 独立 capability；A1.0..A1.S；列出四个当前 RED blocker | exact scope `55D3F6B8…9086C` 的 core selection A1 通过；Search=none，非完整 official API |
| W3 差分架构/PTCG 规则 | 五个 deck ID 不足以定义 A3；seeded derivative 不能冒充 official；adapter/serial/RNG/snapshot/first-divergence/coverage 晋升门过宽 | 定义 `A3Scope` 效果闭包；oracle/provenance 分级；event-driven adapter；semantic entity relation；唯一 RandomEventPort；逐牌高风险矩阵；construction authority；25 配置；mutation canary 和严格 A3 gate | 基础设施和负向资格证据已实现；W0、identity closure 与 RNG source context 阻断 A3 |

未采纳意见：无。所有会改变 authority、证据等级或实施先后顺序的意见均已进入正文；纯措辞建议合并到现有定义中。

§0.1 已关闭本地研究的项目范围决定：无需再等待外部授权或五套 exact official ordered 60 才能验证私有 ID 对应卡 operation 合同。官方托管/分发与 full-rule/official-ID certification 仍是独立分支；它们不会扩大本轮公开证据和产品 authority。

### 12.1 2026-08-25 架构修订记录

项目负责人批准“私有身份不变、卡牌操作协议统一标准化”的方向。本修订据此把原先以五套牌/逐卡 operation row 为中心的实施方式调整为：official source census 驱动的 UCIS Registry、typed effect IR/compiler、唯一 window owner、全卡牌 catalog closure、原语/组合 property testing，以及五套牌代表性 live vectors。该修订改变后续实现门和可用声明，但没有修改代码，也没有回溯提升任何已有 evidence。

§12 表格记录的是前一版设计的独立评审，不自动构成 UCIS 修订的 reviewer sign-off。进入代码实施前，应再按平台架构、CABT wire/lifecycle、PTCG effect/compiler、迁移与安全四个角色复核 UCIS 原语完备性、owner boundary、目录分母和 rollback；评审产生的修改必须回写本文后才开始 M1。

## 13. 实施结果与资格记录（UCIS generation 1）

本节是实现后的状态记录。机器可读合同和回执优先于文字；任一 source、registry、catalog、compiler、Host owner 或对应关系 hash 漂移，相关声明自动退回 `needs-requalification`。

### 13.1 已实现范围

- W0/W1 保持原有分域：Forge 的 `.ptcgbot` v2 和 `.ptcgai` developer-local 工具链不携带本地 official binary/card data/private locator；公开策略边界仍为 `agent(raw_observation) -> list[int]`。
- W2 CABT core selection A1 保持锁定 generation 的 49 Context、17 Option 稀疏 shape 和 lifecycle scoped pass；Search 仍为 `none`，未提升为 A1+Search。
- UCIS Registry generation 1 注册 16 个领域原语、49/49 Context、17/17 Option shape、14/14 lifecycle row 和四类组合边；Python 与 GDScript compiler 对同一 typed `CardEffectSpec` 生成可哈希的 `InteractionProgram`，未知原语、非法组合、旧窗口 continuation 和 custom escape 均 fail closed。
- PtcgDAP 卡牌目录扫描覆盖 797 张卡、730 个 effect：265 个 interactive effect 编译为 UCIS program，464 个为显式 automatic resolution，1 个 `gsm_dynamic_registration` 为解释清楚的 unsupported；729 个声明可用 effect 全部进入统一标准，可用集没有 silent fallback。
- 394/394 个旧 interaction builder callsite 已迁入 UCIS owner；`unregistered=0`、`legacy_author_visible=0`、`legacy_write_entrypoints=0`、`dual_authority=0`、`custom_prompt_builder=0`、`silent_fallback=0`。旧 helper 只保留 sealed engine-private compatibility wrapper，不再是 author wire authority。
- 唯一窗口执行链由 `CardEffectSpec -> UcisInteractionCompiler -> DecisionPort/author owner -> current immutable select.option -> validated list[int] -> engine one-shot commit -> fresh reobserve` 组成。撤退已改为声明后发布 fresh `ATTACHED_CARD` 支付窗口和 fresh `SWITCH` 目标窗口；策略不再绕过标准窗口直接调用 engine retreat。
- Forge vendored SDK 固定 registry/catalog/coverage/legacy/runtime attestation 与资格回执；`doctor` 和 `check` 在执行工作区前校验 generation、registry/catalog hash、16 个原语、unsupported 清单、目录资格回执、性能回执和代表性 operation 回执。任一回执或链接 hash 被修改即 fail closed。

### 13.2 可执行验证与精确证据

目录级资格回执：

```text
PtcgDAP/evidence/ptcgdap/ucis/ucis_catalog_qualification_v1.json
evidence_sha256 = CA6A1FAA4A197FB020F977B627037BDE465E6B5ECE93BE796A399DFA26574785
registry_sha256 = 95472B7D2245A5F26D7911A863DCCA67A9997BB1C6CECB9E3DC086454201C492
catalog_sha256 = 7D463A2E3F49BB37F51C6D9DB0A1E93DF668FB52E7FE1B1C5B9573913D457EBA
```

其 maximum claim 是 `ptcgdap_card_interactions_use_ucis_for_declared_usable_catalog_v1`。explicit unsupported 可以关闭 discovery 分母，但不进入 729 个 usable effect，也不被写成已支持。

性能回执：

```text
PtcgDAP/evidence/ptcgdap/ucis/ucis_performance_qualification_v1.json
evidence_sha256 = D153BDCD5FD205588947243DD8AAB7A68ACD3A458E52EEAD6BB8B99EB3902438
build/load+compile p95 = 2,668,600 ns
precompiled per-window next_step p95 = 4,100 ns
```

该测量只代表当前环境。热路径 10,000 次动态禁止 disk schema/contract read、full catalog scan 和 subprocess/external Forge call，观察次数均为 0；build 成本与 per-window 成本分别报告，没有通过复用旧窗口或回退 classic GDScript 获得速度。

代表性 whole-battle operation input/index 回执：

```text
PtcgDAP/evidence/ptcgdap/a3/corresponding_card_whole_battle_input_index_v1.json
evidence_sha256 = E65C1DCF39FF22F5AF689538788D49E29E9A1BEDF727C028461A458A8EE8EAFC
claim_scope = corresponding_card_whole_battle_input_index_contract
qualification_status = passed
```

九类双引擎 live family 为 `exact_search`、`exact_quantity`、`sequential_source_target`、`ability_activation`、`attack`、`damage_allocation`、`retreat_switch`、`evolution`、`special_condition_attack`。它们均保存合法到达前缀 hash、current-window select header、ordered semantic option hash、两端接受的当前 index，并在多窗口链中 fresh reobserve。公开回执不包含 official 数字映射或 private locator。

### 13.3 已知边界与未提升声明

- 唯一 unsupported effect 是未注册的动态能力入口；在获得 typed capability/owner 前保持 fail closed，不能加入可用卡池。
- W3-10 完整规则结果 A3 仍是独立后续资格：当前未声明提交后 state/log/next checkpoint、damage、KO、RNG、terminal 或五套牌完整规则结果一致。
- Search capability 仍为 `none`；未声明 A1+Search。
- 未声明 Kaggle/Pokémon Company 官方背书、official Card ID equality、全官方卡池规则一致、production 第三方 Python 沙箱、Android/device acceptance 或策略强度非劣。
- timing 是环境测量，不是跨设备 SLA；代表性九类 live operation 证明高风险标准原语可达，不替代 797 张私有目录的规则语义逐项正确性，也不把 explicit unsupported 计入 usable/aligned set。

在上述边界内，可以声明：**PtcgDAP 的每张声明可用卡牌效果通过同一 UCIS generation 描述和标准 current-window index 合同执行；Forge 社区开发者可用固定 SDK 在构建/运行前发现 generation、能力与 unsupported 差异。**

### 13.4 开发者 SDK 与 demo 落地

Forge 已将上述能力变成两层可直接使用的开发入口：

- 仓库级 `UcisDeveloperSdk` 读取 fixed registry/catalog/coverage/qualification，`forge ucis catalog` 显示 generation、hash、16 个原语、729/1 usable/unsupported 分区，`forge ucis inspect` 把公开场景解析为命名化 Context/Option 和公开事实；
- 无依赖 `ucis_runtime.py` 内嵌相同 generation/registry hash，提供 `SelectionWindow.parse`、`choose_exact`、`choose_up_to`、`rebind`、`choose_number`、`choose_boolean`、`first_legal` 与 `PublicBattleFacts`。`competition init` 将其 exact bytes 放入 `src/submission/ucis.py`，作者不需要手写 enum raw 值或稀疏 option shape。

标准 competition 模板已从非标准 `preferred` 测试字段迁移为合法 `CARD / TO_HAND / CARD` 窗口；Marnie demo 的进化场景已从错误的 `YES_NO / IS_FIRST + CARD options` 修正为 `CARD / EVOLVES_TO / CARD`。`forge demo` 除原有 adapter RED→GREEN、10/10 场景、Host 校验与 deterministic build 外，还必须执行 SDK walkthrough，证明：

```text
0..5 精确取 3: [0,2,4]
同一语义在重排新窗口: [4,2,0]
repeated assignment: [1] -> fresh window [0]
公开 active energy debt: 1
公开 two-prize attack clock: 1
unknown option field: ucis_runtime_option_shape_invalid
```

该开发入口没有新增 engine/production/full-rule A3 authority。运行 helper 的 semantic key 只保存公开 option 语义；每个 callback 仍必须重新 `SelectionWindow.parse()`，audit fingerprint 和旧 index 不得跨窗口复用。
