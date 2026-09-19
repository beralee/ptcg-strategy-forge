# 能力核对与代码定位

这是在 `D:/ai/code/ptcg-strategy-forge` 核对的 **2026-09-18 快照**。路径以下均相对实际 Forge 根目录；根目录可由当前工作区或 `git rev-parse --show-toplevel` 确认。数字和状态不是永久约束，改变时以受审代码及回执为准。

## 已有能力与关键缺口

| 核对入口 | 当时可证明的能力 | 研发时的处理 |
|---|---|---|
| `scripts/ai/ptcgdap/ptcgai_model_actor.py` | `competitive_public_actor_i32_v1`；frame 24 维、option 16 维、最多 1024 项，含 presence/mask 和当前索引重绑定 | 特征主要是计数、标志和稀疏动作字段；未表达充分的场面/卡牌语义。UID 的有符号哈希不是连续数值语义 |
| `scripts/ai/ptcgdap/ptcgai_model_package.py`、`src/ptcg_strategy_forge/ptcgai_ort.py` | 无状态、CPU、定长整数 I/O，Actor 8 MiB、25 ms；仅批准有限算子 | Tensor profile generation 与 `.ptcgai` package generation 是不同概念。新增输入/算子需版本化和双端支持；不能直接导入比赛 Transformer/RNN |
| `src/ptcg_strategy_forge/training.py` | 确定性整数线性 BC；评分仅使用 option 特征；数量必须等于 `min_count` | 它证明训练/导出链路，不是新方案的小型场面网络；审查实际 `_features`、`predict` 和导出等价 |
| `src/ptcg_strategy_forge/datasets.py` | `forge_decision_trace_v1` 显式夹具数据通道 | 拒绝自称 engine 的输入；真实 trace 适配没有完成时不能改字段冒充 |
| `src/ptcg_strategy_forge/native_trace.py` | 原生 trace 完整性、观察和窗口指纹、单决策引擎提交见证 | 当时 `native_eligibility` 没有返回合格 BC 的路径；分别返回 `target_model_frontier_unavailable` / `target_projection_not_verified`，需先实现目标投影与资格链 |
| `src/ptcg_strategy_forge/online_decision_traces.py`、`docs/27-ONLINE-DECISION-TRACES.md` | 本人版本/座位的完整 trace 下载、校验和导入已有线上回执 | 下载认证、录像完整性、引擎见证与 BC 资格分别核对；旧摘要不可恢复完整输入。线上正文保留期限有限 |
| `examples/minimal-bc-rl-marnie/README.md` | 小场景 BC + 离线 contextual-bandit Actor，在 Windows Godot 被调用 | 不是 full-game RL，也无模型胜率提升证明 |
| `tools/local_engine_bench.py`、`docs/24-LOCAL-ENGINE-BENCH.md` | 隔离冻结 Godot 副本中的规则包串行整局对照 | 模型 bench 要额外验证 native ORT、模型调用/改选和 fallback；通用 `evaluate --mode engine` 当时仍未接通 |
| `vendor/ptcgdap-sdk-manifest.json` | vendored SDK 的来源及 exact-byte 锁 | 修改 SDK 需受审源和机械刷新，不能手改哈希或单改 Forge 快照制造双端一致假象 |

## 读取顺序

### 2026-09-19 增量（原表保留历史起点）

已经实现公开语义 128/32 profile、Base 同层候选域、单决策单提交真实教师资格、同窗规则查询独立通道、96/48 BC Actor 和 Windows native ORT。`neural_dataset.py` 按教师座位/精确牌表提取，并为可互换手牌副本产生多正例；`neural_actor.py` / `neural_relations.py` 实现等价目标及现有输入关系。`tools/neural_strategy_research.py` 为实际提取/训练入口，`tools/local_engine_bench.py` 验证冻结包真实调用与整局。两类重型运行均由 `run_safety.py` 独立监督和机器锁保护。

`heavy_job(wait_ms=...)` 和 `local_engine_bench.run(..., wait_ms=...)` 可有限等待锁，每次不超过 60 秒，获得锁后重新检查资源。外围队列须设总截止时间；只有明确的其他重型任务占用可排队，RAM/commit/磁盘故障不循环重试。待机协调器不应启动工作池。

详见 `docs/28-LEARNED-SEMANTIC-ACTOR.md`、`docs/30-TRAINING-MACHINE-STABILITY.md` 及具体工作区的计划/回执。主行动外的学习、全局搜索、整局 PPO 和跨平台模型验收仍不可由这些接口推定完成。

项目 `AGENTS.md` 的必读顺序优先。之后按当前阶段选择：

- 模型集成：`docs/17-UNIFIED-PTCGAI-RULE-AND-MODEL-DESIGN.md`，上述 actor/package/ORT 源码及 `tests/test_ptcgai_model_actor.py`。
- 数据/训练：`docs/21-ITERATION-CLI-IMPLEMENTATION.md`、`docs/27-ONLINE-DECISION-TRACES.md`，dataset/native trace/training 源码及对应测试。
- 评估：`docs/24-LOCAL-ENGINE-BENCH.md`、`docs/25-COMPLEX-DECISION-BENCH.md`、`docs/LIMITATIONS.md`，精确基线工作区的回执。
- 规则裁决与多步计划：`docs/09-STRATEGY-THINKING.md`，相关 Host/Base 实现。不要用策略分数掩盖身份、输入或 interaction 错误。

## 可复用命令

在实际 Forge 根目录执行。先核对本地 `--help`，示例中的工作区/文件名需替换为已经确认的对象；不重新初始化已有目录。

```powershell
.\forge.ps1 doctor
.\forge.ps1 workspace status work\my-strategy
.\forge.ps1 workspace inspect work\my-strategy
.\forge.ps1 workspace model inspect work\my-strategy --artifact exports\actor.onnx
.\forge.ps1 workspace model import work\my-strategy --source exports\actor.onnx --training-method bc --source-run-id experiment-id
.\forge.ps1 workspace model conformance work\my-strategy
.\forge.ps1 workspace check work\my-strategy
.\forge.ps1 workspace build work\my-strategy
```

`workspace create --mode model` 可建立模型工作区，但 scaffold 的 Actor 和规则模板不继承成熟基线强度。用明确的本地开发身份或已授权账号；创建离线研究工作区不要求登录服务。移植现有规则时保留合法的 v2 包结构并重新验收。

原生 trace 导入/检查、本人线上 trace 拉取、fixture dataset/train 命令已有入口；**本 skill 不虚构 `train ppo`、`dataset build --native` 或尚不存在的完整 pipeline 命令**。缺失功能应先实现并验证，随后记录实际接口和回执。

常用轻量核对：`rg --files`、`rg -n`、相应 unittest 模块、受影响工作区 `check`、`git diff --check`。新增模型与数据功能用行为和隐私测试验证；不为文档措辞编写实现镜像测试。
