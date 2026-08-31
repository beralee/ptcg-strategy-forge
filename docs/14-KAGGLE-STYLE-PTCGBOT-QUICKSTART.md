# 旧 `.ptcgbot` 退出与迁移

## 状态

`.ptcgbot` 是历史 Kaggle 风格多文件 Python 策略制品。它曾提供 deterministic bundle、developer-local runner/RPC、公开 trace 与本地预资格，但不能安装到游戏。

项目已实施统一 `.ptcgai` 决策：活动 CLI 只保留 `rules_only` 与 `rules_with_model` 两种 data-only `.ptcgai`；`.ptcgbot` 不再是目标开发路径，也不提供安装或兼容运行期。

当前仓库仍保留历史合同、runner、测试和源码作为不可执行审计记录，但 `forge competition` 已从活动 CLI 移除。这些文件不表示新项目应继续采用该路径；本文不再提供创建、构建、上传或资格命令。

权威目标见[统一 `.ptcgai` 规则与模型策略设计](17-UNIFIED-PTCGAI-RULE-AND-MODEL-DESIGN.md)。

## 不可迁移的权限

以下能力不能从旧 Python 包带入玩家运行时：

- 任意 Python 执行、多文件 import 或持久进程状态；
- 文件系统、subprocess、网络、动态依赖或作者 native module；
- Python callback 对 raw observation 的任意解析；
- 旧 runtime lock、RPC、qualification 或 service credential；
- 旧窗口 index、score、binding、ticket 或 proof。

历史 developer-local qualification 只证明原 scope 的工具链和 current-window 行为，不能自动成为 `.ptcgai`、Godot、macOS、模型或 production 证据。

## 迁移到纯规则 `.ptcgai`

适用于主要由 `if`/规则表/语义 helper 构成的 Python agent：

1. 固定旧策略、牌组和可公开 replay 的 exact hash，作为只读迁移输入。
2. 从 Python 中提取 Match Agenda、当前路线、资源债务、信息检查点和类型化交互；不要翻译文件/网络/状态机副作用。
3. 使用 `forge workspace create` 创建 `.ptcgai` 工作区，重新校验目标 PtcgDAP 私有 UID、精确 60 张与 deck manifest。
4. 将当前 Competitive IR 能表达的公开、当前窗口部分人工写入 adapter；更丰富的条件图保留在 `STRATEGY-BLUEPRINT.md`，不能假装已执行。
5. 为正向、缺少前置、错误目标、option reorder、精确数量、mandatory/terminal、hard tier/veto、未知 UID、隐藏字段和 fallback 建立 RED→GREEN 场景。
6. 运行 `.ptcgai` 的 build/check、Godot 实战、回放和选择审计；旧 `.ptcgbot` receipt 不参与新资格。

不存在把 `main.py` 放入 `.ptcgai`、自动翻译任意 Python 或只改扩展名的受支持路径。

## 迁移 BC/RL 策略

适用于行为克隆、强化学习、BC→RL、self-play 或混合训练策略：

1. 训练仍在外部 Python/Kaggle/集群环境完成；Forge 不提供训练循环。
2. 把最终 Actor 重新导出为首代受审的无状态、CPU-only、固定 shape 单文件 `actor.ort`。
3. 移除 custom op、外部权重、动态维度、远程推理和作者 runtime dependency。
4. 只使用 Competitive Public Frame allow-list，经统一 tensor profile 生成整数特征、presence 和 option mask；未知 UID/shape 必须 fail closed。
5. 同时编写真实 Competitive IR fallback。`model_only` 包无效。
6. 重新校验 card catalog/deck/UID、actor、runtime/operator/tensor/resource profile 的 hash。
7. 通过 `forge workspace model inspect/import/tensorize/conformance`、统一 workspace build/check 和目标平台 Godot 门后，才形成可安装 `.ptcgai`。

上述 model 命令、Windows x86_64 原生 ORT Host、安装和真实 Godot 对局门已经实现；macOS arm64/x86_64 已有同合同构建入口，但尚未获得实机安装、对局和回放证据。因此 Windows 开发包可安装验证，macOS 仍不能声明通过。

## 历史资产处理

| 历史资产 | 处理 |
|---|---|
| `.ptcgbot` archive | 只读归档；不可安装、重签为 `.ptcgai` 或继续晋升 |
| Python source | 作为人工迁移/重新导出输入；不进入玩家包 |
| deck/identity data | 按当前 PtcgDAP catalog 重新校验，不沿用名称猜测 |
| UCIS helper 语义 | 可迁入统一公共张量 SDK，但不携带 Python execution authority |
| trace/replay/evidence | 保留原 generation/scope/non-claim；可用作新场景参考 |
| qualification/service receipt | 不转换为游戏安装、模型或 production 权限 |

## 历史证据仍然说明什么

旧 `.ptcgbot` 实现与 CABT core selection A1 证据仍可证明当时声明的 bundle、公开 current-window、ordered options 与 accepted indexes。UCIS generation、目录 closure 和九类 operation input/index 回执继续由各自 hash/scope 管理。

这些历史证据不证明提交后的 state、damage、KO、RNG、terminal、完整规则 A3、Search、production sandbox、Android/device acceptance 或策略强度，也不构成统一 `.ptcgai v2` 的实现证据；v2 的实现证据必须来自 Forge 和对应 Godot 平台门。
