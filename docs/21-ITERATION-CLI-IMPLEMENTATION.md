# v0.3 开发迭代基础设施：当前实现与验收边界

本页描述当前可执行功能。[完整架构升级方案](20-DEVELOPER-ITERATION-ARCHITECTURE-AND-PLAN.md) 中的 M0–M5 仍是分阶段目标，不能把本次实现视为整个升级已经完成。

## 安装与 SDK

Python 3.13+，在 Forge 源码目录执行：

```powershell
python -m pip install .
forge doctor
forge workspace create work\my-deck --author-id local.dev
```

需要模型导入、ORT 推理时，使用 `python -m pip install ".[model]"`。原有 `setup.ps1` 保留完整依赖安装路径。`local.dev` 仅用于本地开发；上传必须使用已注册账号的完整开发者 ID 和显式短 package ID。

wheel 内携带 manifest 锁定的 SDK、合同和牌组资源；不依赖相邻游戏仓库。源码导入也支持在仓库外设置 `PYTHONPATH`。CLI 参数解析与 SDK 应用服务分离；既有 CLI JSON 输出与底层命令保留。

```python
from ptcg_strategy_forge import StrategyWorkspace

workspace = StrategyWorkspace.open("work/my-deck")
workspace.status()
workspace.replays    # 录像集合服务
workspace.dataset    # BC 数据服务
workspace.bump_version(part="patch")
workspace.upgrade(dry_run=True)
```

## 构建、版本与新鲜度

构建先在临时目录执行原有双构建、Host 校验和完整场景套件，比较验收前后的输入摘要。源码变化返回 `workspace_source_changed_during_build`，不发布产物。报告不得覆盖 package、scenarios、suite 或输出包。

成功构建新增 `build/records/<sha256>.json` 不可覆盖回执。记录绑定包字节、package 文件、场景、suite、SDK 快照和 Forge 应用源码。`build/workspace-check.json` 是最近报告；旧回执保留。`workspace status` 返回 `acceptance.status = unchecked/current/stale`，默认安装拒绝 stale 或没有有效回执的现存包。

```powershell
forge workspace version bump work\my-deck --part patch
forge workspace build work\my-deck
forge workspace upgrade work\my-deck --dry-run
forge workspace upgrade work\my-deck
```

版本变更先保存原 manifest 到 `.forge/backups/`；现存包仍不覆盖。迁移当前仅增加 v1 Forge 工作区元数据，不修改包或重签；未知元数据拒绝迁移。模型 `status` 只读与 Actor、manifest、验证器字节绑定的 conformance 缓存，不启动推理；真实验收仍重跑 conformance。

## 服务与录像

```powershell
forge service capabilities --profile dojo
forge workspace matches list work\my-deck --origin https://YOUR-API-ORIGIN --release-id RELEASE_ID
forge workspace replays sync work\my-deck --origin https://YOUR-API-ORIGIN --release-id RELEASE_ID --concurrency 4 --requests-per-second 2
```

Dojo 适配器使用已核对页面源码中的 profile 和单场 replay 路由。目录查询明确标记 `recent_60_only`，不宣称支持全部历史、游标分页或决策附件。`service capabilities` 是已审查客户端合同的说明，不代表实时服务探测成功。本机页面配置的 `http://127.0.0.1:8765` 在本次运行中无法连接，真实集成尚未验收。

也可以提供明确的冻结下载目录，JSON 是以下对象组成的数组：

```json
[
  {
    "id": "series-001",
    "url": "https://YOUR-API-ORIGIN/v1/ladder/matches/series-001/replay",
    "sha256": "从可信目录获取的64位十六进制摘要；没有则省略此字段"
  }
]
```

```powershell
forge workspace replays sync work\my-deck --manifest replay-manifest.json --concurrency 2 --requests-per-second 2 --max-games 1000 --max-bytes 1073741824
forge workspace replays sync work\my-deck --manifest replay-manifest.json --concurrency 2 --requests-per-second 2 --max-games 1000 --max-bytes 1073741824 --resume
forge workspace replays verify work\my-deck --collection COLLECTION_ID
forge workspace replays inspect work\my-deck --collection COLLECTION_ID
```

输入目录、查询和预算共同决定 collection ID。恢复必须使用相同输入；成功对象先复核缓存摘要，然后跳过下载。写入按对象 staging→校验→提交进行；有服务摘要时核对，没有时只声明记录了本地字节摘要。无法把下载完整性推导为来源可信、对局干净或 BC 资格。

网络线程最多 4 个；同用户 Forge 进程按 origin 共享 SQLite 租约、并发和速率预算，活跃客户端采用更严格限制。429/502/503/504 有限重试并共享 Retry-After；较长服务等待返回可恢复错误。普通 HTTP 仅允许 loopback，拒绝跳转及携带凭据/查询参数的对象 URL。当前是任务级恢复，未实现 HTTP Range 续传。

```powershell
forge jobs list
forge jobs status JOB_ID
forge jobs cancel JOB_ID
forge jobs resume JOB_ID
forge jobs retry JOB_ID
```

任务同步执行，状态保存在本机用户目录 `PTCGStrategyForge`。取消是协作式的，网络读受超时约束；状态查询不重新运行任务。恢复和重试开始新的 attempt，保留历史失败；恢复支持录像和 BC 训练。attempt token 阻止过期进程修改接替者的状态。尚未提供后台常驻调度器。

## BC 数据合同与当前限制

当前实现 `forge_decision_trace_v1` **测试夹具通道**，必须显式 `--allow-fixture`。它用于证明特征、标签、候选域和切分语义；不接受把 `evidence_kind` 改成 engine 来伪造引擎资格。Godot `developer_decisions.jsonl` 和天梯录像需要各自经过审查的适配器，当前缺少这一接入。因此，真实录像→合格 BC 数据的 M2 验收尚未完成。

```powershell
forge workspace dataset build work\my-deck --source decision-trace.json --allow-fixture
forge workspace dataset build work\my-deck --collection COLLECTION_ID --allow-fixture
forge workspace dataset audit work\my-deck --dataset DATASET_ID
forge workspace dataset stats work\my-deck --dataset DATASET_ID
forge workspace dataset split work\my-deck --dataset DATASET_ID --ratios 80,10,10 --seed 20260908
forge workspace dataset export work\my-deck --dataset DATASET_ID --output work\exported-dataset
```

普通播放录像传给 dataset build 会返回 `dataset_decision_trace_unavailable`，不会从胜负推造动作标签。夹具结构的可执行参考在 [BC 数据测试](../tests/test_bc_dataset.py)。真实训练不得把该通道的产物升级为 engine witnessed 证据。

实现的约束包括：

- 决策前输入严格解析并通过 public firewall，拒绝未知字段；座位必须匹配。
- 只接受 Host accepted 的合法当前索引；bool、越界、重复标签失败。
- mandatory/terminal 窗口排除；模型标签必须在 Rule 所属 hard tier 且未被 veto 的范围。
- 使用原 SDK 张量器的 `current_index_to_row` 映射标签，语义重排保持相同特征与标签。
- 分开存储存在掩码、模型候选域掩码、多选集合和 desired_count。
- 数据集内容寻址、输入摘要追溯、重复窗口冲突拒绝、相关比赛整体分组切分。
- dataset ID 不依赖 split；切分 ID 单独固定 seed、比例与分组。

数据构建使用临时 SQLite 排序/去重，确定性 JSONL 分片默认每片 4096 行，选项行去除 padding；审计逐片核对摘要、行数和每行身份。输入 JSON 文件仍逐文件解析，并受总字节预算限制。源数据不含合格决策附件时，命令停止，不构建空的“成功数据集”。

## TDD 验收与后续缺口

新增测试覆盖 foundation、HTTP 下载、跨客户端限额、jobs attempt 历史、BC 重排/负例/多选、CLI 端到端。首次失败已确认，再实现功能并回归。最终全量 121/121 测试通过，受影响工作区通过双构建、Host 与 10/10 场景；独立 wheel 和纯核心依赖干净虚拟环境验证通过。结果记录在 [验收回执](../evidence/iteration-cli-v0.3.json) 中；回执明确标记 `partial_delivery_verified`，不声明整个架构计划完成。

上面的 121 项回执属于首批实现。2026-09-09 的扩展功能与剩余验收门如下，不能沿用旧回执宣布新增功能全部通过。

## 2026-09-09 扩展

```powershell
forge resources status
forge workspace native-traces import work\my-deck --source PATH_TO_NATIVE_MATCH_DIRECTORY
forge workspace native-traces inspect work\my-deck --trace TRACE_ID
forge workspace explain work\my-deck --scenario scenarios/01-positive.json
forge workspace explain work\my-deck --scenario scenarios/01-positive.json --baseline BASELINE_PTCGAI
forge workspace test work\my-deck --case positive --changed
forge workspace test work\my-deck --watch
forge workspace scenario generate work\my-deck --scenario scenarios/01-positive.json --permutation 1,0
forge workspace scenario from-replay work\my-deck --trace TRACE_ID --decision DECISION_ID --base-authority authority.json
forge workspace train bc work\my-deck --dataset DATASET_ID --split SPLIT_ID --epochs 8 --allow-fixture
forge workspace evaluate work\my-deck --mode offline --run RUN_ID
forge workspace compare work\my-deck --candidate RUN_ID --baseline BASELINE_RUN_ID
forge workspace release prepare work\my-deck --author-id COMPLETE_DEVELOPER_ID --public-key PUBLIC_KEY_JSON
forge authoring metadata
forge workspace rules lint work\my-deck
forge workspace rules compile work\my-deck --source NAMED_RULES_JSON --output COMPILED_ADAPTER_JSON
forge cards search 玛俐的长毛巨魔
```

原生录像导入只复制 manifest 与 developer_decisions.jsonl，验证完整性、诊断域哈希链、公开 frame、窗口与选项指纹以及 Host 标签绑定。单个 owner step 明确提交单个决策时才记录逐决策引擎见证。旧录像没有模型 frontier 时返回 `target_model_frontier_unavailable`；不将 ranked indexes 伪装为可学习域。转换为开发场景时必须提供明确的模拟 Base authority，报告保留教师选择和 trace/decision 定位，不把该人工 authority 当成引擎证据。

`inspect`/`explain` 分派 raw 与 Competitive v2 场景。explain 使用既有模拟 owner，绑定精确包摘要并定位包内规则 JSON Pointer；通过 Python 3.13 的局部 monitoring 观察已执行谓词调用，报告实际值、未满足前提及命中结果，不替换裁决函数。`--baseline` 在同一窗口比较精确包。重排重建当前索引绑定和窗口摘要，保留 raw option.index 的卡牌位置语义。`scenario counterfactual --scenario PATH --field JSON_POINTER --value JSON_SCALAR --expected JSON_INDEX_ARRAY` 修改一个公开事实并保留教师期望与人工期望的区分；生成文件尚不自动加入 suite。

`test --case` 经现有 suite owner 运行指定场景；`--changed` 按包、单场景和 SDK 源码摘要复用成功结果。`--watch` 仅观察作者输入、合并连续修改并串行运行，Ctrl+C 停止。快速检查不出具完整验收回执，也不替代双构建和全部场景。

BC 是可选模型依赖下的确定性整数线性基线，仅支持 `desired_count == min_count`；其他数量头显式报错。使用独立 train/validation/test 分组，验证集选 checkpoint，最后测试；checkpoint 固定输入/代码/Python/配置身份，恢复不读取可执行 pickle。导出 ONNX/ORT 后在留出行逐项比较精确 int32 分数和数量。训练接入 jobs 取消/恢复，每 128 行检查资源压力；Windows 全局互斥和启动前进程/RAM/commit 探测限制单重型任务，workers 上限 4、RAM 下限 12 GiB、commit 上限 70%。未启动真实多进程训练池。

成功构建另存 `build/archives/<sha>.ptcgai`，相同输入、包与归档摘要全部有效时复用最近回执。命名化 `authoring.macro_rule/compile_rules/compile_named_rules` 编译到现有 v1 restricted adapter，metadata 同时提供命名枚举与编辑器 JSON Schema；lint 使用原 v1/v2 编译器，不创建新的运行时。名称检索只使用包内有摘要验证的卡牌源，缺少源文件的 printing 仍可按 UID 查询。

发布 prepare 支持显式 author ID 的离线模式和已登录账号的在线公钥登记核对模式。2026-09-15 已补齐正式 HTTP 账号登录、公钥登记、本机签名提交与精确归档对账，复用 `ReleaseLedger` 的接收/资格分离；使用步骤、权限和部署边界见 [控制面 CLI](23-CONTROL-PLANE-CLI.md)。

2026-09-16 控制接口已部署，Forge 公网能力发现与接口检查通过。仍需关闭的完整架构验收门：真实录像到目标模型张量/候选域的等价转换、跨源合同兼容及泄漏验收；真实引擎配对评估；复杂路由/模型的完整因果明细、通用负例矩阵自动生成与性能基线；真实开发者账号生产提交联调。`--mode engine` 当前明确返回 `evaluation_engine_unavailable`。这些不是已交付行为。

2026-09-09 阶段未修改 vendored SDK 字节或外部仓库；后续外部仓库修改另见跨仓库进展和控制面文档。未安装生产策略、提交 Git 或发布 release。回退可使用原源码版本和已有 `.ptcgai`；升级元数据与本地数据目录不会赋予策略执行权限。
