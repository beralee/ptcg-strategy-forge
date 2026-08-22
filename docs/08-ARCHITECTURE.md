# 架构与 SDK 来源

## 独立项目边界

PTCG Strategy Forge 位于独立目录和独立 Git 仓库。运行时所有必需 Python、合同、模板包、牌组源数据和发布客户端都在本仓库，不依赖相邻 PtcgDAP 或 `ptcgabc` 路径。

```text
forge.py
  └─ src/ptcg_strategy_forge/
       ├─ cli.py          统一工作流和报告
       ├─ scenarios.py    严格套件与隐私扫描
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

## 更新流程

升级 SDK 时必须：

1. 从受审来源机械同步最小文件集；
2. 更新来源说明和 capture date；
3. 重新生成 manifest；
4. 运行 doctor、unittest、完整 demo 和干净克隆；
5. 比较 demo archive/行为变化并在 CHANGELOG 说明；
6. 不在一次 SDK 更新中顺手扩大策略权限。
