# 公开语义神经网络 SDK

面向 AI 训练家的公开特征、数据资格、BC 与冻结 Actor 工具。运行的个人策略、数据和权重由作者在自己的工作区维护。

## 公开场面 v2

2026-09-20 新增 `ptcgdap_local_semantic_actor_i32_v2`（416/48）。保留 v1 的前 128/32 列，加入双方前场与最多八个后场位置的公开 HP、能量、登场时机、进化层数、道具、卡牌类别和当前合法动作关系；候选同时绑定当前目标/来源位置。实体 serial 仅用于当前窗口绑定，不作为网络的数值输入。没有把当前可进化清单当作未来可进化证明，也没有把能量总数当作完整属性费用证明。

v1 合同与默认行为保留；v2 超容量、未知己方卡牌、隐藏字段、歧义实体绑定均拒绝。跨语言类别标识哈希使用精确 UTF-8 字节和 NUL 分隔，不能经 Godot String 构造 NUL。公开 printing 和能量多重集只作类别，训练输入之外的类别编码为未命中；旧 profile 的 unknown UID 规则不放宽。代码在 `semantic_model_profile_v2.py`，新合同在 `semantic_model_tensor_profile_v2.json`。


`neural_features.py` 固定版本化编码；类别只来自训练输入。`train --initial-checkpoint PATH` 按编码语义映射父模型权重，新通道零初始化并检查初始输出。历史 v1 轨迹不能仅改 capture 头冒充 v2，重投影与原生运行需独立核验。

新版需要支持 416/48 的 Host、包验证和原生 runtime；本 SDK 的 Python 通过不能代替对应平台验收。

## 输入和运行边界

新增 `ptcgdap_local_semantic_actor_i32_v1`，固定 frame 128、option 32、最大 1024 个选项。合同在 `contracts/ptcgdap/semantic_model_tensor_profile_v1.json`，Python 投影在 `scripts/ai/ptcgdap/semantic_model_profile.py`。原 24/16 profile 保持独立；不将旧模型解释为新输入。

模型读取本座位可见手牌、场面、弃牌、双方公开 HP/能量/奖赏数，以及当前候选的卡牌与目标语义。自己的卡牌按封存牌表 UID 字典序分类编码，最多 32 种 printing；未知己方 UID/交互形状走明确规则分流。缺失值使用 presence，卡牌身份不作为连续数值。没有对手手牌、牌序、盖奖、seed、教师分数或引擎对象输入。

Base 在裁决结果中增加观察/窗口绑定的 `model_frontier`，不改变原规则选择与 audit hash。只有相同最优 hard tier 且未 veto 的候选能够改选；强制、终局、配额、多选、已绑定路线/事务、规则 fallback、单候选保留规则路径。每次接受动作后重新投影，不保存旧索引。Godot Windows Host 和 native v4 支持新 profile；旧 profile、旧原生 v3 保留。新模型尚无 Android、macOS、官方 CABT 或生产验收。

## 数据与训练

开发环境需要本仓库 `model` 可选依赖（NumPy、ONNX、ONNX Runtime）；使用现有 `.venv`。训练工具只属于 Forge，不进入 `.ptcgai` 或玩家端。

首个学习 gate 仅允许主行动窗口，候选类型限定为 attach_energy、play_basic_to_bench、play_stadium、end_turn、use_stadium_effect、retreat、play_trainer、attack、attach_tool、evolve、granted_attack。效果选目标等未训练交互明确走 `unsupported_learning_context` 规则分流；不会因为上层 prompt 被标为 main 而误入模型。

`qualify_teacher_query_record` 单独验收模型访问状态中的同窗规则建议：要求原规则输出、Base 选择与 Host 记录的 fallback 一致，绑定精确模型、窗口和观察；原始模型动作不改写。调用方另外核对完整规则文档与冻结教师的等价关系。这些标签标记 `godot_same_window_rule_query_v1` 和 `teacher_was_executed=false`，与教师真实提交标签分开统计。

`tools/neural_strategy_research.py dataset` 检查完整干净对局、精确教师包、原生日志哈希链、公开帧和选项绑定、Host 接受与单决策单提交见证，再核对 Godot/Python 投影。只有 Base 授权且教师标签位于其中的窗口进入 BC；排除原因全部保留。同一 seed 的双方和镜像对局属于同组，重复窗口去重，再按预先确定的 seed 边界分训练/验证。模型自己访问的局面必须使用单独的教师查询证据，不能伪装为教师执行标签。

`train` 使用 NumPy 前馈候选排序网络、masked listwise CE、Adam 和验证损失选 checkpoint。部署是纯 ORT 数据：categorical 比较、presence、两个隐藏层和单一分数头；无网络请求、Python 运行依赖、在线学习或隐藏记忆。整数输出在转换前饱和，所有 padding 被 mask。模型最大 8 MiB、单次 CPU 推理 25 ms，不能通过提高预算掩盖超时。

```powershell
.\.venv\Scripts\python.exe tools/neural_strategy_research.py dataset --run RUN --runtime RUNTIME --workspace BASELINE --validation-seed FIRST_VALIDATION_SEED --output DATASET.json
.\.venv\Scripts\python.exe tools/neural_strategy_research.py train --dataset DATASET.json --output NEW_RUN_DIRECTORY --epochs 100 --seed 260919
```

路径和整数占位符需替换为实验的冻结身份。训练与整局评估使用机器级资源锁，串行执行。SDK `workspace.model.tensorize` 对显式 `ptcgdap-competitive-public-frame-v2` 文档采用新投影；旧 CABT/developer scenario 输入路径不变。

训练和对局现在由独立监督器执行，检查真实分页/输出盘余量、持续资源采样、进程树私有内存、输出量和时长；失败只终止本任务子树。恢复前按 [电脑稳定性保护](30-TRAINING-MACHINE-STABILITY.md) 通过短试运行，不能直接重启损坏的旧确认目录。


## 验收与边界

`train --variant exact|equivalent|relations` 支持精确教师标签、公开语义证明的等价标签，以及当前张量内的公开资源关系。相同张量不能自动证明动作等价；能量数量也不能证明属性费用已付清。

`tools/semantic_model_probe.gd` 与 `tools/semantic_actor_probe.gd` 用于独立引擎中的投影、原生 Actor 和 Base 分流核对。`tools/local_engine_bench.py` 对精确引擎、双方包、种子与座位做串行评估；异常、非法选择、回退及失败轨迹不能被胜率掩盖。

训练/验证/确认须按相关种子分组，确认结果被查看后不能再作为独立留出。教师一致率、窗口选择、引擎运行、天梯排名和强度提升分别报告。通用 PPO、模型续行干预、其他设备、官方 CABT 与生产门未由本次 SDK 发布关闭。

受控单动作收益工具见 [受控收益训练](31-CONTROLLED-OUTCOME-TRAINING.md)，当前线上指标见 [AI 天梯 benchmark](37-AI-LADDER-BENCHMARK.md)。
