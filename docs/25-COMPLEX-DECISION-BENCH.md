# 复杂决策链 bench

`tools/complex_decision_bench.py` 检查同一行动方在多个公开选择窗口中的完整决策序列。它使用严格包加载器、锁定 SDK 的 CompetitivePolicyV2Runtime 和逐链语义事务日志，不依赖游戏仓库。

```powershell
.\.venv\Scripts\python.exe tools/complex_decision_bench.py --package work/my-strategy/build/my-strategy.ptcgai --suite demo/ember-frost-complex-bench/suite.json --report work/my-strategy/build/complex-report.json
```

报告路径必须不存在，防止覆盖反例和历史结果。规则包仍须通过标准 `forge check`。

## 怎样定义复杂场景

套件文件包含 `document_type: forge_complex_decision_bench_v1`、`schema_version: 1` 和 `cases`。每个 case 有唯一 `id`、分类 `family`，以及顺序 `steps`。每步指定普通 competitive scenario 文件的相对 `path` 和 `expect_error`（正常步骤为空字符串）。最后一步可以是预期的隐私/合同拒绝，拒绝之后不得继续后缀。

场景文件保持现有 `ptcg_strategy_forge_competitive_scenario_v2` 合同，包含 frame、Base authority 和 expected indexes。使用 `ptcg_strategy_forge.decision_bench.bind_frame` 在编写夹具时生成规范观察/窗口哈希；运行期不会自动修复输入漂移。

每条链自动执行原顺序和逆序两遍。逆序只重新分配当前索引，卡牌 serial、目标 entity 和 Base 的必选/终局/tier/veto 同步重绑定。每个后续窗口必须有新的哈希、递增 sequence，且行动方一致。前缀选错后立即停止该条链，不能把假定前缀成功的后续答案计为通过。

## 评估维度

- 支付与资源冲突：手贴、撤退已用完，已有能量，保留稀缺能量与换位牌。
- 多步执行：支付→撤退→选择攻击手→攻击；打出多步卡牌后的双方目标选择。
- 信息变化：检索结果和当前可见候选变化后重新判断，不保留旧索引或旧证明。
- 权限与隐私：mandatory、terminal、hard tier、veto、未知身份和对手隐藏字段拒绝。

报告分别列出类别与完整链通过数。大量简单权限用例通过，不能掩盖关键攻击链失败。

## 余烬霜幕示例套件

`demo/ember-frost-complex-bench` 包含 52 个场景、12 个类别，每个都运行原序与重排，共 104 个变体。其中 7 条多窗口链对应 14 个链变体，覆盖两种撤退支付、顶尖双方目标选择、目标离场/失去能量，以及检索结果有/无进化桥两种后缀。

实际反例是顶尖两次选择都进入 `effect_target`，己方选择也被旧的低 HP 抓人规则评分。示例要求按己方实体身份绑定就绪火暴兽；对手同名火暴兽不能命中该偏好。原始窗口中的 acting player 不是目标所属玩家，不能以它替代身份检查。

运行报告记录包、套件、每步场景及窗口哈希，并用 `fixture_manifest_sha256` 绑定所有场景文件，包括前缀失败后没有执行的后缀。对比应同时核对套件与完整夹具清单；新增场景后必须重跑基线，不能把旧套件分母直接用于新套件提升率。

## 证据边界

后续 frame 是人工编写的公开夹具，不由游戏引擎自动执行前一个动作生成。因此通过只证明给定窗口序列下的策略行为，不证明这些局面真实可达、不证明卡效结果正确，也不证明胜率。真实多窗口执行、合法整局和强度提升必须由 [本地 Godot bench](24-LOCAL-ENGINE-BENCH.md) 另外见证。

不得将缺失的抓人伤害、未来抽牌或对手隐藏牌填成确定事实。受限 IR 不能表达的精确斩杀路线应列为明确缺口，不能用人工期望伪装运行能力。
