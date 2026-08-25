# 场景测试

## 场景合同

每个场景包含 `raw_observation`、prompt authority、公开 local UID bindings 和测试期望。它不是完整游戏快照，也不能提供对手隐藏信息。

`scenario-suite.json` 为每个用例声明：

```json
{
  "id": "positive",
  "path": "scenarios/01-positive.json",
  "expect": {
    "status": "passed",
    "selected_indexes": [1],
    "matched_rule_id": "forge.morgrem.evolve",
    "selected_source": "adapter_proposal"
  }
}
```

路径必须是套件目录下的普通文件；绝对路径、`..`、反斜杠、symlink 和重复 ID 会被拒绝。

## 最低覆盖

每个 macro 至少应包含：

1. 正向命中；
2. 关键手牌/active 条件不存在；
3. 目标 UID 不同；
4. option 顺序重排；
5. mandatory/terminal 阻止；
6. hard tier/veto 阻止；
7. 未知 UID fail closed；
8. 隐藏信息污染被 firewall 拒绝。

场景的 `select.type/context/option` 必须本身是 UCIS 合法组合。例如进化目标使用 `CARD / EVOLVES_TO / CARD`，不能把 CARD options 塞进 `YES_NO / IS_FIRST` header。先运行：

```powershell
.\forge.ps1 ucis inspect --scenario scenarios\01-positive.json
```

对精确数量或多窗口能力还要补：

- `0..N` 中准确选择 0、边界值和策略需要值；
- source→target 每一步使用新的 observation/window；
- 新窗口 option 重排后相同 semantic key 得到新 index；
- 目标消失时 `semantic_rebind_missing`，不能复用旧 index；
- NUMBER、YES/NO、ENERGY units 不混用 list-length 编码。

运行：

```powershell
.\forge.ps1 test `
  --package build\my-strategy.ptcgai `
  --suite scenario-suite.json `
  --report evidence\scenario-report.json
```

通过条件不仅是期望 index 相等，还包括匹配规则、选择来源和权限 claims。报告会扫描禁止的私有字段。

## 不能用胜率替代的测试

无论胜率如何，以下失败都会阻止发布：非法 index、stale window、隐藏信息、dirty game、包 hash/signature、未知 UID、错误选项稀疏形状和生产权限冒充。
