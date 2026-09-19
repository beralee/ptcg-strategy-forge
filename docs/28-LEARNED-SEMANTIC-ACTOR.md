# 本地公开语义神经网络策略

2026-09-19。使用 `ptcg-learned-strategy-pipeline` 研发；策略包仍是数据，神经网络只排序 Base 允许的当前单选候选。

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

## 验收和复现

### 多对手与等价标签迭代

提取器按精确教师包和牌表绑定座位：异构对局仅收教师座位，双方相同包时才允许双方入集；去重键包含对手 SHA，跨对手仍按相关 seed 整组切分。研究运行器在隔离 runtime 中登记双方 v2 测试签名包的精确摘要，原产品 gate 不变；旧 v1 帧不能伪装成当前 v2 轨迹。

`train --variant exact|equivalent|relations` 提供固定对照。`exact` 保留原单标签目标；`equivalent` 使用经公开手牌/同 UID/同目标实体/相同交互字段证明的多个正例，优化正例集合的概率和，不能仅因张量相同就合并。所有候选另报统一的多正例验证 NLL，以及精确和等价一致率、分动作统计。样本量与独立 seed 组数分开报告。

`relations` 在原 128/32 张量内部计算八项带 presence 的关系：伤害余量、附能数量与最低费用的差、手填可用性与能量缺口/攻击就绪的关系、目标奖赏与剩余奖赏之差、同卡手牌余量、就绪攻击手余量、双方奖赏进度差。附能数量差不证明属性费用已付清，任何特征都不能覆盖 Base 规则。没有新增 Host 字段或跨窗口记忆；NumPy 与部署 ORT 的阈值、未知值、重排、padding 均需一致。

关系消融保留相同 seed 的基础网络权重与 RNG 序列，新增关系列以零初始化且保留梯度，初始输出与无关系版相同。对照只代表记录的初始化和数据条件，不能用单次结果断言某类特征普遍更优。

持续改进方法和研究来源维护于新 skill 的 `references/continuous-improvement.md`。历史改选保留完整己方回合轨迹，分别记录等价、有益、有害、未知；没有反事实或规则证明时，失败局和首次分歧不能自动成为负标签。实际强度结论必须由各工作区的独立确认报告证明。

模型工作区 `check` 验证精确双构建、包/ORT 合同与规则场景。Python 场景的通过不能冒称神经网络在 Godot 的行为证据。`tools/semantic_model_probe.gd` 比对真实公开帧投影及 Base gate；`tools/semantic_actor_probe.gd` 比对实际 native ORT 的选择、选项重排和保护分流。

`tools/local_engine_bench.py` 冻结 native loader/DLL、双方包和引擎输入，并检查模型调用、改选、正常分流、异常回退与真实提交。要求模型运行至少一次；只靠规则跑完不能通过模型调用门。相同引擎、对手、seed、座位才允许配对比较，按 seed 聚类统计。完整日志保留失败，不能删除失败局后报胜率。

研究运行时的 native 文件采用冻结复制，排除 build/cache；不再经目录联接跟随源仓库修改。运行前后摘要变化使整片失效，须修复隔离并在新目录重跑，原失效对局不进入训练或统计。
