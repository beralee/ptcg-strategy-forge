# 统一 `.ptcgai` 规则与模型策略设计

## 0. 文档控制

| 字段 | 值 |
|---|---|
| 文档状态 | **规范已实施（Windows development）；三平台完整门待完成** |
| 决策日期 | 2026-08-30 |
| 目标版本 | 下一代 `.ptcgai v2` |
| 当前实现 | v1 exact 兼容；v2 `rules_only`/`rules_with_model`、Forge 模型命令与 Windows x86_64 原生 ORT/Godot 实战已实现 |
| 取代范围 | `.ptcgbot`/双制品开发路径及其下一代目标；不抹除 UCIS、A1/A3 历史证据 |
| 公共策略边界 | `agent(raw_observation) -> list[int]` |

本文既是统一规则与模型策略的规范，也是当前实现状态的控制文档。Windows development 能力已有独立合同、可执行测试、Godot 实战和平台回执；macOS、Android 与 production 没有对应实机/签发证据，仍只能表述为未完成范围。

## 1. 最终决策

下一代只保留一种作者制品：`.ptcgai`。它同时承载纯规则策略和“规则 + 冻结模型”策略，并继续保持 data-only、无作者脚本、Host/Base 最终裁决。

`.ptcgai v2` 只有两种 policy mode：

| `policy_mode` | 内容 | 运行行为 |
|---|---|---|
| `rules_only` | Competitive IR 规则 | 沿现有规则/Base 链执行 |
| `rules_with_model` | Competitive IR 规则 + 受审 ORT Actor | 规则先形成合法且受保护的候选域，模型只在获准范围内评分；任何模型故障都回退规则/Base |

`model_only` 永久禁止。BC、RL 或混合训练得到的模型包必须携带可独立运行、覆盖必要选择窗口的 Competitive IR fallback。规则不是占位文件：模型被禁用、超时、损坏、超限或输出异常时，同一窗口必须能够继续安全裁决。

现有 `.ptcgai v1` 保持原样兼容：

- 不重建、不改 archive bytes/hash；
- 不静默升级 manifest 或 policy；
- 不改变既有规则裁决语义；
- v1 loader 与 v2 loader 显式按 schema generation 分派；
- v2 实现失败时可以关闭 v2 capability，而不是破坏 v1。

`.ptcgbot` 不再是下一代开发路径。切换到统一 v2 的实现版本中，`forge competition`、Python agent runner/RPC 和 `.ptcgbot` 安装/执行兼容层直接移除，不设置 deprecated runtime、不自动改扩展名，也不允许新包继续取得资格。历史源码、合同和 evidence 可保留为不可执行记录，以便审计旧结论。

## 2. 不变量与非目标

无论策略来自人工规则、BC、RL 还是混合训练，以下不变量不变：

1. 当前 immutable `select.option` 是唯一合法动作前沿；返回值仍是当前窗口 index。
2. 每次 accepted selection 后旧窗口、index、score、tier、proof 和 model output 全部失效；下一步必须重观察、重投影、重绑定。
3. Base Graph 拥有 legality、mandatory/terminal、hard tier、veto、cardinality、deterministic fallback 和 final commit authority。
4. 作者规则和模型只能提出公开语义目标、路线偏好、同层评分或精确数量建议，不能执行 engine command。
5. 输入由 Competitive Public Frame allow-list 正向构造；隐藏手牌、牌序、盖奖、私有 RNG、ticket、callback、credential、Godot object 和 engine reference 不得进入张量、报告或 replay。
6. 未知 UID、字段、enum、option shape、tensor shape 或 runtime generation 必须 fail closed。
7. 训练方法不创造运行时权限。`bc`、`rl`、`bc_then_rl` 等只属于非权威 provenance。

首代 v2 的非目标包括：

- 不在 Forge 内实现训练循环、环境并行器、经验回放或超参数平台；
- 不执行 Python、GDScript、pickle、TorchScript、动态库或作者 custom op；
- 不做远程推理、运行时下载或联网取权重；
- 不支持 GPU、CoreML、NNAPI、自定义 execution provider 或状态型/循环型 Actor；
- 不因模型评分跨越 hard tier、解除 veto 或绕过 mandatory/terminal；
- 不声明 production、Android、A5、完整规则 A3 或策略强度。

## 3. `.ptcgai v2` 包合同

### 3.1 规范拓扑

`rules_only` 源目录保持规则文件并省略整个 `model/` 目录；构建后的 canonical archive 增加生成的 `files.sha256.json` 与 `signature.json`：

```text
strategy_package.json
deck/deck.csv
deck/deck_manifest.json
policy/adapter.json
policy/config.json
policy/policy_ir.json
files.sha256.json
signature.json
```

`rules_with_model` 在同一闭合包中增加：

```text
model/model_manifest.json
model/actor.ort
```

`model/actor.ort` 是唯一模型 artifact。v2 不复用或重新解释旧的可选 `weights.bin`；旧成员只按其原 package generation 处理。禁止外部数据文件、分片权重、嵌套 archive、软链接、绝对路径和动态下载。

包仍使用 canonical ZIP、闭合成员清单、逐文件 SHA-256 和 archive 签名。首代沿用当前资源上限：

| 项目 | 上限 |
|---|---:|
| `.ptcgai` archive | 12 MiB |
| `model/actor.ort` 单文件 | 8 MiB |
| 解压后总量 | 16 MiB |

如果真实 BC/RL Actor 无法满足这些上限，必须新建、评审并晋升资源 profile；不得在构建现场改常量或借用 `weights.bin` 规避门。

### 3.2 v2 manifest 绑定

顶层 `strategy_package.json` 必须显式固定：

```json
{
  "document_type": "strategy_package_v2",
  "schema_version": 2,
  "policy": {
    "policy_mode": "rules_with_model",
    "entry_kind": "restricted_policy_ir_v1",
    "model_manifest_path": "model/model_manifest.json",
    "model_artifact_path": "model/actor.ort",
    "weights_path": null
  },
  "compatibility": {
    "minimum_game_api": "ptcgdap-author-host-v2",
    "required_capabilities": ["learned_policy_head_v1"]
  }
}
```

以上字段已经由 v2 validator、构建器和测试固定。`rules_only` 的 model 路径与 `weights_path` 必须为 null，且不得携带 `model/` 成员；`rules_with_model` 缺失规则 fallback、manifest 或 actor 时构建即失败。

`model/model_manifest.json` 至少固定以下闭包：

| 字段族 | 必须绑定的内容 |
|---|---|
| artifact | 路径、字节数、SHA-256、ORT format generation |
| runtime | ONNX Runtime C API/ORT model compatibility generation、CPU execution provider、线程/内存/时间 profile |
| operators | 受审 operator-set profile ID/hash、opset、禁止 custom domain/custom op |
| tensors | public tensor profile ID/hash、每个 input/output 的名称、dtype、固定 shape 与语义版本 |
| public data | Competitive Public Frame schema/hash、UCIS generation/hash、option semantic canonicalizer/hash |
| identity | card catalog/deck manifest/UID domain hash |
| resources | package/model/tensor/workspace memory 与 decision budget profile/hash |
| provenance | 可选训练方法、训练代码/数据/seed/eval hash；仅审计，不参与运行裁决 |

任何绑定 hash 漂移都产生新 package/model generation。Host 不接受“兼容大概相同”的模型。

### 3.3 训练 provenance

BC、RL、BC→RL、self-play 或人工规则蒸馏不形成不同运行时类型。运行时只识别 `ptcgai_ort_actor_v1`。建议 provenance 记录：

```text
training_method = bc | rl | bc_then_rl | hybrid | unspecified
training_code_sha256
dataset_or_environment_manifest_sha256
seed_manifest_sha256
exporter_version
evaluation_receipt_sha256
```

这些字段不能影响 legality、优先级、运行预算或平台信任。缺少 provenance 可以阻止发布资格，但不能让 Host 采用另一套推理语义。

## 4. 首代 ORT Actor 合同

### 4.1 运行限制

首代 Actor 必须满足：

- 无状态：一次调用只依赖本次公开 frame 和当前 options；
- CPU-only：只允许平台维护的 CPU execution provider；
- 固定 shape：禁止动态维度、可变 batch 和未绑定 symbolic dimension；
- 单 batch：`batch = 1`；
- 无 custom op、custom domain、外部数据或作者动态库；
- 无网络、文件系统、时钟、熵源或进程权限；
- session 在包加载期创建，决策热路径不得解析 schema、扫描卡表或下载内容；
- runtime、operator set 和线程配置由平台 manifest 管理，包不能覆盖。

Godot 通过平台维护的原生扩展调用 ONNX Runtime C API。作者包只提供受审 `actor.ort` 数据，不提供原生扩展。实现应以 [ONNX Runtime C/C++ 官方合同](https://onnxruntime.ai/docs/get-started/with-cpp.html) 为运行接口依据。

### 4.2 公开张量 profile

首代 profile 使用整数特征和显式 presence/mask。固定输入名如下，具体 `FRAME_WIDTH` 与 `OPTION_WIDTH` 由 profile generation 锁定，不能由作者选择：

| 输入 | dtype | 固定 shape | 语义 |
|---|---|---|---|
| `frame_i32` | `int32` | `[1, FRAME_WIDTH]` | allow-list 当前公开事实 |
| `frame_presence_i32` | `int32` | `[1, FRAME_WIDTH]` | 字段存在性；只允许 0/1 |
| `option_i32` | `int32` | `[1, 1024, OPTION_WIDTH]` | 语义稳定排序后的当前候选特征 |
| `option_presence_i32` | `int32` | `[1, 1024, OPTION_WIDTH]` | 稀疏 option 字段存在性；只允许 0/1 |
| `option_mask_i32` | `int32` | `[1, 1024]` | 真实候选为 1，padding 为 0 |

所有数值必须来自 Competitive Public Frame allow-list 或当前 option 的公开稀疏字段。缺失值由 presence 表达，不能用某个合法 UID/enum 冒充。未知 UID、超范围整数、未知 shape 或无法规范化的 option 使模型分支 fail closed；不得 hash 未知身份后继续推理。

当前窗口最多接收 1024 个 options。Host 对候选建立 canonical semantic key，按 canonical bytes 稳定排序；语义完全相同的重复项保留引擎原相对顺序并分配 occurrence ordinal。排序表只在当前窗口有效，同时保存“tensor row → current option index”映射。剩余行零填充且 mask 为 0。

option reorder 测试必须证明：同一语义候选集合经过不同原始排列后，Actor 看到的有效语义行一致；最终输出再映射到各自当前窗口 index，而不是复用旧 index。

### 4.3 固定输出

Actor 只能产生：

| 输出 | dtype | 固定 shape | 语义 |
|---|---|---|---|
| `option_scores` | `int32` | `[1, 1024]` | 对当前 canonical rows 的同层偏好分；padding 行必须被 Host 忽略 |
| `desired_count` | `int32` | `[1]` | 本窗口建议的精确选择数量 |

输出必须逐项验证 dtype、shape、张量大小和范围。`desired_count` 必须落在当前 `minCount..maxCount`，且不得大于通过 legality、route、tier 和 veto 的候选数。Host 按 `option_scores` 降序、canonical semantic key、occurrence ordinal组成确定性排序键；模型分数相同不得依赖平台浮点差异。

Host 从获准候选中取 `desired_count` 个 row，映射回当前 option indexes，再按当前窗口要求的确定性输出顺序交给 sanitizer。Actor 不能直接输出 option index、ticket、command、semantic key 或跨窗口状态。

## 5. 裁决与降级顺序

每次选择严格执行：

```text
公开投影
→ legality
→ mandatory / terminal
→ Competitive IR 规则路线
→ hard tier / veto
→ 可选模型评分
→ output / desired_count 验证
→ Competitive IR 规则 fallback
→ Base deterministic fallback
→ commit
→ invalidate / reobserve
```

模型只接收规则路线、hard tier 与 veto 后仍有资格的当前候选，并只能做同一授权层内的评分/数量建议。以下情况禁止调用模型：

- mandatory/terminal 已唯一决定动作；
- 当前 route 或 hard tier 已要求不可比较的唯一动作；
- `learned_policy_head_v1` unavailable/unsupported；
- 剩余 decision budget 不足；
- package/model/session 未通过加载期资格；
- 公开投影或 identity 无法完整张量化。

模型失败只影响本窗口。Host 立即丢弃该窗口的 model session output，先执行包内 Competitive IR fallback，再执行 Base deterministic fallback；不得在下一窗口沿用 failure 前的 score、count 或 tensor row。

预算沿用 `public_policy_budget` 的可选 capability `learned_policy_head_v1` 和既有 decision/time-bank 机制。模型无权声明更高预算；平台 profile 决定是否调用、超时阈值、线程数和内存上限。推理耗时计入同一决策预算。

## 6. 稳定错误与公开审计

实现提供以下稳定错误族；Python/reference 与 Godot/native 层使用无前缀的 `model_*` 代码：

| 错误码 | 含义 | 当前窗口处理 |
|---|---|---|
| `model_unavailable` | 平台没有可用模型 capability | 规则/Base fallback |
| `model_manifest_invalid` | manifest 形状或绑定不合法 | 包加载拒绝 |
| `model_artifact_hash_mismatch` | actor bytes 与声明不符 | 包加载拒绝 |
| `model_runtime_profile_invalid` | ORT/runtime generation 不支持 | 包加载拒绝或 capability unavailable |
| `model_operator_forbidden` | 使用未批准算子/domain/opset | 包加载拒绝 |
| `model_external_data_forbidden` | 引用了外部数据 | 包加载拒绝 |
| `model_tensor_profile_invalid` | tensor 名称、dtype 或 shape 不符 | 包加载拒绝 |
| `model_contract_hash_mismatch` | catalog/CABT/tensor hash 漂移 | 包加载拒绝 |
| `model_public_frame_invalid` / `model_unknown_uid` / `model_unknown_option_shape` | 当前公开 frame 无法安全张量化 | 规则/Base fallback |
| `model_output_shape_invalid` | score dtype/shape/range 异常 | 规则/Base fallback |
| `model_desired_count_invalid` | 精确数量不满足当前窗口 | 规则/Base fallback |
| `model_timeout` | 推理超时或剩余预算耗尽 | 规则/Base fallback |
| `model_resource_limit_exceeded` | 内存、线程或 artifact 超限 | 拒绝加载或规则/Base fallback |
| `model_inference_failed` | ORT session/inference 失败 | 规则/Base fallback |

公开审计只记录：package/model/profile hash、当前 public input hash、semantic option-set hash、是否调用模型、稳定 outcome/error、fallback owner、最终 indexes 和最终 decision audit hash。不得记录隐藏输入、原始 observation、未筛选 logits、内存地址或 Host-private binding。

## 7. Forge 开发入口

当前面向开发者的主 CLI 已收敛为工作区生命周期：

```text
forge workspace create <path> --mode rules|model
forge workspace status|inspect|check|build|install <path>
forge workspace model inspect|import|tensorize|conformance <path>
```

公开 Python SDK 提供等价的 `StrategyWorkspace`/`WorkspaceModel`；旧 `new/build/check/install` 和顶层 `model` 命令继续作为自动化兼容与底层诊断入口。职责是：

| 命令 | 唯一职责 |
|---|---|
| `workspace create --mode rules` | 以约定默认身份创建 `rules_only` 工作区 |
| `workspace create --mode model` | 创建带真实 Competitive IR fallback 的 `rules_with_model` 工作区 |
| `workspace status/inspect` | 显示编辑入口/缺口，并通过公开 SDK 检查场景 |
| `workspace model inspect` | 离线检查 ORT graph、opset、operator、external data、I/O 和资源估算 |
| `workspace model import` | 临时验证后替换工作区 Actor，生成 hash-pinned manifest；不转换训练代码 |
| `workspace model tensorize` | 场景先过 CABT/public firewall，再转成固定张量和可复核 hash |
| `workspace model conformance` | 在 reference CPU ORT 上验证固定 I/O、provider、输出和 Actor 合同；平台选择/审计一致性由 Godot 门另行证明 |
| `workspace check/build/install` | 对两种 mode 共用同一闭合包、签名、场景和平台门 |

Forge 只提供公开张量 SDK、ORT 导入/检查、确定性构建和一致性验证，不负责 BC/RL 训练循环。训练可以在外部 Python/Kaggle/集群完成，但交付物必须重新导出为受审 `actor.ort` 并通过 Forge 门。

`ucis_runtime.py` 中可复用的 current-window 解析、presence、semantic key 和 public facts 能力迁入统一 `.ptcgai` 模型张量 SDK。SDK 由同一 UCIS/tensor profile hash 生成，不再复制进作者 Python agent 包。

## 8. Godot、ORT 与安装解析

运行结构固定为：

```text
.ptcgai data package
  → PtcgDAP package validator
  → Competitive Public Frame / UCIS tensorizer
  → platform-owned Godot native extension
  → platform-owned ONNX Runtime CPU
  → validated scores/count
  → Base adjudication and one-shot commit
```

平台维护的 native extension 固定 Godot/ONNX Runtime、CPU provider、operator/tensor profile 和资源限制；它不进入作者包，因此 Windows x86_64、macOS arm64 和 macOS x86_64 必须运行同一份 `.ptcgai` exact bytes。Windows x86_64 绑定已实测；macOS 两架构的 CMake、GDExtension 路径、`@loader_path` 与构建脚本已配置但未签发实机回执。

安装目录由 Godot `user://` 与平台 resolver 决定，不能在包、Forge 或 Host 中硬编码 Windows `APPDATA`。实现以 [Godot user data 官方合同](https://docs.godotengine.org/en/stable/tutorials/scripting/filesystem.html) 为路径依据。resolver 必须提供规范化绝对路径、目录穿越拒绝、原子安装、同 identity/hash 幂等和冲突拒绝。

## 9. `.ptcgbot` 退出与迁移

### 9.1 下一代删除范围

统一 v2 已从活动产品表面移除：

- `forge competition` 命令与模板；
- competition rights、qualification、service client、专用发布合同和活动测试；
- 把 `ucis.py` 复制到 Python submission 的生成路径。

历史 `.ptcgbot` schema/profile/builder、Python runner/RPC 和相关测试源仍可留在仓库作为不可执行审计材料，但活动 CLI、安装、资格、发布和游戏运行期不得引用它们。

保留且继续演进：

- UCIS registry/compiler/current-window 合同；
- Competitive Public Frame、公开张量 SDK 与 Base/Host；
- 策略平台、通用 evaluator、回放和公开审计；
- 历史 `.ptcgbot` evidence、A1 scope 与 A3 non-claim，作为不可执行审计记录。

### 9.2 迁移规则

| 旧资产 | 迁移到 `.ptcgai` 的方式 |
|---|---|
| 纯规则 Python agent | 人工提取公开语义、路线和交互策略，编写 Competitive IR adapter 与场景；不能机械翻译任意 Python |
| BC/RL Python 策略 | 在外部训练环境重新导出冻结 ORT Actor，同时编写规则 fallback，运行 tensor/model/platform conformance |
| `deck.csv`/身份映射 | 重新校验目标 PtcgDAP card catalog、私有 UID、精确 60 张和 deck manifest hash |
| Python helper | 只把可证明的公开解析/张量语义迁入平台 SDK；不迁移执行权限、文件访问或状态机 |
| 历史 qualification/evidence | 只保留原 scope；不能自动晋升为 `.ptcgai`、Godot、macOS 或 production 证据 |

不存在 `.ptcgbot` → `.ptcgai` 自动改扩展名、包内原样搬运 `main.py`、无审计模型转换或沿用旧资格 hash 的路径。

## 10. RED→GREEN 实施门

### 10.1 包与兼容门

| 场景 | RED 要证明 | GREEN 条件 |
|---|---|---|
| v1 字节兼容 | v2 改动使既有 v1 bytes/hash/行为变化 | 原 v1 fixture exact bytes、hash、选择和审计不变 |
| rules-only | v2 错误要求模型成员或调用 ORT | 无 `model/` 仍可完整 build/check/live run |
| 有效模型 | Actor 未被加载或结果未进入受控同层裁决 | 受审模型在 reference/Godot 得到相同选择与审计 |
| option reorder | 缓存旧 index 或 tensor row 跟随原顺序 | canonical rows 语义一致，最终 indexes 正确重绑定 |
| 精确数量 | `desired_count` 被忽略或越过 min/max | 合法精确数量通过，非法数量稳定 fallback |
| mandatory/terminal | 模型覆盖强制或终局动作 | Actor 不被调用，Base 结果不变 |
| hard tier/veto | 高分越层或恢复 veto 候选 | 模型只见获准候选，最终不越权 |
| 未知 UID/shape | 未知值被 hash/截断后继续推理 | 模型分支 fail closed，规则/Base 可用 |
| 隐藏字段 | hidden sentinel 进入 tensor/log | tensor与公开证据均无泄漏，构建/运行门拒绝污染 |
| 损坏模型 | hash/graph 损坏在运行中静默失效 | 加载期拒绝并给出稳定错误 |
| 非法算子/外部数据 | custom op 或 sidecar 被加载 | inspect/build/Host 三层一致拒绝 |
| 资源超限 | 大模型、tensor 或 session 越界 | 构建/加载失败，无现场放宽 |
| 超时 | 卡死或侵占 Base 预算 | 截止时间内中止模型分支并确定性 fallback |
| 规则 fallback | 模型失败导致无动作/随机动作 | 同一窗口进入 Competitive IR，再进入 Base fallback |

每个模型 macro/特征还必须覆盖正向、缺少前置、错误目标、semantic reorder、mandatory/terminal、hard-tier/veto、unknown UID、隐藏字段和 one-fact metamorphic flip。模型通过胜率门不能豁免任何安全或确定性门。

### 10.2 张量与推理一致性门

必须用固定公开 vectors 证明：

1. Python/reference tensorizer 与三个桌面 Host 得到 exact input tensors/hash；
2. 同一 `actor.ort`、runtime/operator profile 产生 exact `int32 option_scores` 和 `desired_count`；
3. 各平台得到相同 semantic choices、current indexes 和 public decision audit hash；
4. 两次 Forge 构建得到 exact archive bytes/hash；
5. 任何未知字段、mask、padding、dtype、shape 或输出长度漂移都在 commit 前 fail closed。

## 11. 首个完整平台交付门

首个完整开发交付必须同时覆盖：

| 平台 | 架构 | 必需证据 |
|---|---|---|
| Windows | x86_64 | exact package install、ORT load、真实 Godot 对局、回放、逐选择审计 |
| macOS | arm64 | 同上 |
| macOS | x86_64 | 同上 |

三个目标必须使用同一 `.ptcgai` bytes；各自的平台 runtime manifest 独立签名和锁定。验收要求：

- 双构建 exact bytes；
- 相同 conformance vectors 的 semantic choice 与 audit hash 一致；
- 每个平台完成 Godot 真实对局和可复核 replay；
- 零非法动作、零 stale-window authority、零隐藏信息泄漏、零远程推理；
- 模型故障注入全部回退到规则/Base；
- 报告明确标记 `development_only=true`、`production_ready=false`。

Android、GPU/CoreML、状态型模型和 production 是独立晋升，不因桌面三架构通过而自动获得资格。

### 11.1 当前 Windows development witness

最小参考实现位于 `examples/minimal-bc-rl-marnie/`：它以两条公开 current-window 样本完成 BC warm start，再进行 64 次确定性离线 contextual-bandit 更新，最后导出无状态整数线性 Actor。训练方法只写入非权威 provenance；该样例不声明完整对局训练、强度或 production 资格。

| 项目 | Windows x86_64 结果 |
|---|---|
| Actor | 4,328 bytes；SHA-256 `0BAF0E2C1E3F92CE65794928419AF321CD75A3BB8400FED11BB99E9C09DCF136` |
| `.ptcgai` | 27,415 bytes；SHA-256 `D4A7BAD9A6C7ECD6837026E090F2FF7CC592D90F1E0DB578968311BAA27BCBA0`；双构建 exact bytes |
| Forge | 10/10 strict 场景；模型 inspect/conformance 与安装通过 |
| Godot 对局 | 111 steps 正常终局；55/55 policy success；42 engine commits |
| 原生模型 | 38 次 `CPUExecutionProvider` 推理成功；30 次最终选择被模型改变；remote inference=false |
| 安全结果 | policy error、非法输出、engine rejection、model fallback 均为 0 |
| 确定性 | 两次对局 semantic audit SHA-256 均为 `C381EC50FA1F4BD9E54D7B823973079808DA19FFEDBA530D15C5B128E9F22CF1`；public replay snapshot SHA-256 均为 `EE2B5E6C389003C9948544B795591577999FA4C1F752BF9D84A6EC58C4E5684E` |

权威 Windows 回执位于 PtcgDAP 的 `evidence/ptcgdap/minimal_bc_rl_model_battle_windows_20260830.json` 与 repeat 文件。回执中规则座位获胜；这不影响“模型确实加载、推理并改变选择”的功能结论，也不能被表述为模型强度胜利。

## 12. 实施顺序与完成定义

owning layer 的实施状态为：

1. **已完成**：v2 package/model/tensor/operator/runtime validator、profile、稳定错误与 v1 兼容回归。
2. **已完成**：Forge `--policy-mode`、`model inspect/import/tensorize/conformance`、rules/model 双构建与模型 check。
3. **已完成**：唯一 public tensor SDK、allow-list、presence/mask、semantic reorder 与 unknown/hidden fail-closed 测试。
4. **已完成**：Host/Base `learned_policy_head_v1` 裁决、预算、故障、fallback 和逐窗口 authority 失效。
5. **部分完成**：Windows x86_64 原生 ORT CPU 已实测；macOS arm64/x86_64 已有构建入口，待实机签发。
6. **部分完成**：Windows 已完成真实对局、replay、选择/audit hash；三平台同包一致性待 macOS 设备证据。
7. **已完成活动面退出**：`forge competition`、资格、安装和运行期不可达；历史源码/合同/测试保留为只读审计材料，未做破坏性删除。

完成必须同时具备：实现代码、生成合同、RED→GREEN 测试、确定性构建、三平台 Godot witness、公开证据、known gaps 和 rollback identity。只有修改文档、存在 ORT 文件或在 Python reference 中得到相同分数，都不算模型能力完成。

## 13. 当前状态快照

截至 2026-08-30 当前工作树：

| 能力 | 状态 |
|---|---|
| `.ptcgai v1` 规则包 | 当前已实现 |
| Competitive IR / UCIS / Base current-window 裁决 | 当前已实现，scope 以既有合同和证据为准 |
| `learned_policy_head_v1` 名称与预算槽位 | Windows 原生 Actor 后端已实现，25ms 可取消 deadline |
| `.ptcgai v2 rules_only` | 已实现并纳入 scaffold/build/check |
| `.ptcgai v2 rules_with_model` | 已实现；Windows Godot development witness 通过 |
| ORT tensorizer/import/conformance | 已实现；CPU reference 与 Windows native inference 通过 |
| macOS 开发安装与真实对局门 | arm64/x86_64 构建入口已实现；实机证据待完成 |
| `.ptcgbot` 下一代退出 | 活动 CLI、安装、资格和运行期已移除；历史源码/合同/测试只读保留 |
| Android/GPU/CoreML/有状态模型/production | 未晋升，独立后续范围 |

统一 v2 的 Windows development 实现已经完成；只有取得 macOS 两架构的同字节安装、真实对局、回放和审计回执后，才能把三平台完整交付门标为完成。
