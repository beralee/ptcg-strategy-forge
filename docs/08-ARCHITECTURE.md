# 架构与 SDK 来源

## 独立项目边界

PTCG Strategy Forge 位于独立目录和独立 Git 仓库。运行时所有必需 Python、合同、模板包、牌组源数据和发布客户端都在本仓库，不依赖相邻 PtcgDAP 或 `ptcgabc` 路径。

```text
forge.py
  └─ src/ptcg_strategy_forge/
       ├─ cli.py          统一工作流、工作区蓝图、一键验收和报告
       ├─ scenarios.py    严格套件与隐私扫描
       ├─ ucis_runtime.py generation-locked、无依赖的 current-window helper
       └─ provenance.py   SDK byte closure
            │
            ├─ tools/ptcgdap/       受审开发/构建/发布工具
            ├─ scripts/ai/ptcgdap/  公共边界、Host、Base Graph
            ├─ contracts/ptcgdap/   闭合合同与 conformance vectors
            └─ data/                固定模板、卡牌和牌组源
```

## SDK 来源

快照取自 `https://github.com/beralee/PtcgDeckAgent` 的 PtcgDAP 受审工作树，记录的 base commit 为 `3534d22b28d2895d5de5bf12cd35836d686714aa`，捕获日期 2026-08-23。由于源工作树当时含受审但未提交的 PtcgDAP 增量，不能只用 commit 表示内容；因此 manifest 固定每个实际分发文件的 exact bytes/hash。

## 报告与 authority

所有 Forge 报告都是开发证据，不拥有 engine、current window、production、CABT official 或玩家 runtime authority。真正游戏执行仍由 PtcgDAP Host 重新观察、重建窗口、绑定 ticket 并 commit；工具包模拟不会执行引擎方法。

## Unified Card Interaction Standard

卡牌身份继续使用 PtcgDAP 私有 UID；卡牌交互则统一由 UCIS generation 1 描述。`CardEffectSpec` 只能组合 registry 中的 typed primitive，compiler 将它映射为固定 Context/Option/数量编码的 `InteractionProgram`。Host 是唯一窗口与提交 owner；effect 和作者策略都不能自建 prompt、持有旧 index 或直接调用 engine command。Forge vendored SDK 只投影当前 immutable `select.option`，并把语义 fingerprint 在 fresh observation 上重新绑定为当前 index。

开发者入口分两层且共用同一 registry hash：

- `scripts/ai/ptcgdap/ucis_sdk.py` 加载 vendored registry/catalog/coverage，供 `doctor`、`check`、`ucis catalog` 和 `ucis inspect` 做仓库级资格与场景检查；
- `src/ptcg_strategy_forge/ucis_runtime.py` 是无磁盘合同依赖的 current-window helper，`competition init` 将 exact bytes 复制为工作区 `src/submission/ucis.py`，供 callback 热路径解析和选择。

运行 helper 内嵌 `UCIS_GENERATION / CONTRACT_GENERATION / REGISTRY_SHA256`，回归测试要求它与 vendored registry 完全相等。它只保存当前窗口不可变 view；`SemanticOptionKey` 可表达跨 callback 的公开目标，但每次必须在 fresh `SelectionWindow.parse()` 结果上 `rebind()`。`audit_fingerprint` 只用于本窗口审计，不能成为跨窗口 authority。

目录资格将 797 张卡/730 个 effect 完整分区为 compiled、automatic 或 explicit unsupported，并要求未登记、silent fallback、author-visible legacy 和 dual authority 全为零。Forge 同时固定 catalog、runtime attestation、coverage/legacy ledger、性能回执和代表性 whole-battle operation input/index 回执；任一 hash 漂移会让 `doctor`/`check` 在策略执行前失败。

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

## Competition v2 与 A1 发布绑定

`.ptcgbot` v2 的 canonical archive、目录闭包、runtime lock 和 v1/v2 dispatch 只有 vendored `CompetitionBundleOwner` 一个实现。Builder、Forge、API validator、Worker 和 Runner 都复用该 owner；schema 与 conformance vectors 用于外部合同说明和漂移检查，不能成为第二套解释器。

runtime lock 同时固定 official SDK contract、RPC、A1 scope、Godot development time profile 和 `Search=none`。Forge 会从 vendored census 重新生成 A1 scope，并要求与报告和 runtime lock exact 相等；build/prequalify receipt 记录这些 hash。W3 A3 scope 只在真的 promotion 时加入 release；当前 blocked scope 不进入任何 official parity claim。
