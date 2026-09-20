# 架构与 SDK 来源

## 独立项目边界

PTCG Strategy Forge 位于独立目录和独立 Git 仓库。运行时所有必需 Python、合同、模板包、牌组源数据和发布客户端都在本仓库，不依赖相邻 PtcgDAP 或 `ptcgabc` 路径。

```text
forge.py
  └─ src/ptcg_strategy_forge/
       ├─ sdk.py          公开 StrategyWorkspace/WorkspaceModel 开发门面
       ├─ cli.py          SDK 的命令行适配、底层兼容命令和验收编排
       ├─ scenarios.py    严格套件与隐私扫描
       ├─ ucis_runtime.py generation-locked、无依赖的 current-window helper（目标迁入统一张量 SDK）
       └─ provenance.py   SDK byte closure
            │
            ├─ tools/ptcgdap/       受审开发/构建/发布工具
            ├─ scripts/ai/ptcgdap/  公共边界、Host、Base Graph
            ├─ contracts/ptcgdap/   闭合合同与 conformance vectors
            └─ data/                固定模板、卡牌和牌组源
```

开发者交付面分为三层：`workspace` CLI 和 `StrategyWorkspace` 是稳定主入口；`SelectionWindow/PublicBattleFacts` 是 current-window SDK；`tools/`、`scripts/` 与低层 `build/model/ucis` 命令用于合同维护和诊断。主入口共享实现和 JSON 报告，不建立第二套 package 或策略解释器。

## SDK 来源

快照取自 `https://github.com/beralee/PtcgDeckAgent` 的 PtcgDAP 受审工作树，记录的 base commit 为 `3534d22b28d2895d5de5bf12cd35836d686714aa`，捕获日期 2026-08-23。由于源工作树当时含受审但未提交的 PtcgDAP 增量，不能只用 commit 表示内容；因此 manifest 固定每个实际分发文件的 exact bytes/hash。

## 报告与 authority

所有 Forge 报告都是开发证据，不拥有 engine、current window、production、CABT official 或玩家 runtime authority。真正游戏执行仍由 PtcgDAP Host 重新观察、重建窗口、绑定 ticket 并 commit；工具包模拟不会执行引擎方法。

## Unified Card Interaction Standard

卡牌身份继续使用 PtcgDAP 私有 UID；卡牌交互则统一由 UCIS generation 1 描述。`CardEffectSpec` 只能组合 registry 中的 typed primitive，compiler 将它映射为固定 Context/Option/数量编码的 `InteractionProgram`。Host 是唯一窗口与提交 owner；effect 和作者策略都不能自建 prompt、持有旧 index 或直接调用 engine command。Forge vendored SDK 只投影当前 immutable `select.option`，并把语义 fingerprint 在 fresh observation 上重新绑定为当前 index。

current-window 实现分两层且共用同一 registry hash：

- `scripts/ai/ptcgdap/ucis_sdk.py` 加载 vendored registry/catalog/coverage，供 `doctor`、`check`、`ucis catalog` 和 `ucis inspect` 做仓库级资格与场景检查；
- `src/ptcg_strategy_forge/ucis_runtime.py` 是无磁盘合同依赖的 current-window helper。历史 competition 工具曾把 exact bytes 复制进 Python submission；下一代不再复制 agent SDK，而是把可复用的解析、presence、semantic key 和 public facts 收敛到 `.ptcgai` 模型张量 SDK。

面向应用的 `src/ptcg_strategy_forge/sdk.py` 再把工作区 create/open/status/inspect/check/build/install 和模型 inspect/import/tensorize/conformance 组合成稳定对象；它不拥有 Host authority，也不改变 UCIS generation。

运行 helper 内嵌 `UCIS_GENERATION / CONTRACT_GENERATION / REGISTRY_SHA256`，回归测试要求它与 vendored registry 完全相等。它只保存当前窗口不可变 view；`SemanticOptionKey` 可表达跨 callback 的公开目标，但每次必须在 fresh `SelectionWindow.parse()` 结果上 `rebind()`。`audit_fingerprint` 只用于本窗口审计，不能成为跨窗口 authority。

目录资格将 1,011 张卡/888 个 effect 完整分区为 compiled、automatic 或 explicit unsupported，并要求未登记、silent fallback、author-visible legacy 和 dual authority 全为零。Forge 同时固定 catalog、runtime attestation、coverage/legacy ledger、性能回执和代表性 whole-battle operation input/index 回执；任一 hash 漂移会让 `doctor`/`check` 在策略执行前失败。

`check` 只编排已有权威入口：构建仍由固定 package builder 拥有，严格校验仍走 `PtcgDAPAuthorMatchHost.create`，场景仍走公开 firewall/current-window/Base Graph 链路。Forge 不实现第二套策略解释器。

## Competitive v2 热路径

完整 schema/hash/UID closure 在 package 加载期编译为按 policy hash 封存的 execution plan。运行窗口只接受该 sealed hash，缓存 frame facts，先过滤 frame-only 条件，再按 option kind 评估候选规则。公开 policy 副本后续被修改不会别名到 sealed plan；未知 hash 直接拒绝。

这只是同一策略解释器的预编译执行路径，不改变 `agent(raw_observation) -> list[int]`、current-window 失效规则或 Base authority。固定重放的 21.6× 加速及强度未达门说明见 `docs/12-ARCHITECTURE-UPGRADE-DESIGN-AND-PLAN.md`。

## 整回合路线裁决

Competitive v2 的 `route_candidates` 在局部分数之前比较有限条整回合语义路线。候选包含公开 guard、typed resource budget、有序 current-window steps，以及攻击窗口、奖赏推进、续航、资源成本、对手响应风险和不确定性的安全整数值。

Base 只授权获选路线当前合法的第一步；terminal、mandatory、hard tier、veto、cardinality 和 fallback 仍在其后拥有最终裁决权。提交后不保存旧 index/score/proof，而是重新观察、重新计算候选并重新绑定当前 option。

Python 与 Godot 使用同一 CABT tree hash 固定 policy/audit；conformance vector 同时锁定动作和审计哈希。旧包没有 `route_candidates` 时保持原执行路径。

## 更新流程

升级 SDK 时必须：

1. 从受审来源机械同步最小文件集；
2. 更新来源说明和 capture date；
3. 重新生成 manifest；
4. 运行 doctor、unittest、完整 demo 和干净克隆；
5. 比较 demo archive/行为变化并在 CHANGELOG 说明；
6. 不在一次 SDK 更新中顺手扩大策略权限。

## 统一 `.ptcgai` 模型运行时与历史 A1 证据

当前 v2 架构只有一个作者包 owner：`.ptcgai` package validator/loader。`rules_only` 沿 Competitive IR 执行；`rules_with_model` 在相同包内增加冻结 ORT Actor，但 legality、mandatory/terminal、规则路线、hard tier、veto、fallback 和 commit 仍由 Host/Base 独占。平台原生扩展和 ONNX Runtime 是平台 runtime，不是作者包成员。

历史 `.ptcgbot` canonical bundle、RPC/runner、runtime lock 和 qualification 只作为已发生的实现/证据保留；活动 CLI 已无 competition 入口。已有 CABT core selection A1、UCIS 与 A3 non-claim 不因退出而失效，也不自动晋升为模型、macOS、production 或完整规则一致性。

包、张量、裁决、平台 runtime 与迁移合同见[统一 `.ptcgai` 规则与模型策略设计](17-UNIFIED-PTCGAI-RULE-AND-MODEL-DESIGN.md)。Windows Host 已通过原生 ORT 真实对局；macOS 两架构仍是未见证平台。

## 下一阶段：完整研发迭代

[下一阶段架构升级提案](20-DEVELOPER-ITERATION-ARCHITECTURE-AND-PLAN.md) 将 CLI/SDK 应用服务、产物记录、资源调度、服务适配、录像/BC 数据、可选本地训练、评估与发布反馈纳入同一工作区。首批纵向目标是从真实对局目录受控采集录像，并产出具备完整决策前输入与 accepted choice 的可重复 BC 数据集。

该提案已部分实施，不改变 `.ptcgai`/Base/Host 权威边界；外部服务、页面和引擎导出能力有独立 owner 与集成门。具体迁移、并发准入、标签映射、防泄漏分区、阶段计划和回滚口径由该提案统一记录，实际完成范围见实施说明和 [CLI 完整性审查](26-CLI-ONLY-DEVELOPMENT.md)。

### v0.3 已落地的应用层分离

`cli.py` 保留参数解析、JSON 输出和兼容入口，原工作区业务服务迁入 `application.py`；SDK 不再反向导入 CLI。`resources.py` 统一源码/wheel 的资源根，安装包保留 manifest 审查过的 vendor 布局。`lineage.py` 绑定验收输入与产物；`replays.py`、`jobs.py` 和 `datasets.py` 承担采集、任务历史与受限数据合同。

当前边界与尚未实现的完整迭代流程见 [实施说明](21-ITERATION-CLI-IMPLEMENTATION.md)。公共策略调用与 Base authority 未改变。
