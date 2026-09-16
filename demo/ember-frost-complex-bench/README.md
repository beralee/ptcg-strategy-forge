# 余烬霜幕：复杂决策题库

52 个场景，12 类问题；每个场景运行原序及选项重排，共 104 个变体。其中 7 个场景包含连续窗口，共 14 个链变体。

| 题目类别 | 要验证的决策 |
|---|---|
| 支付撤退 | 当前手贴/撤退仍可用，后排攻击手已就绪，支付对象是己方前场 |
| 资源取舍 | 有火能时保留暗能；可正常撤退时保留顶尖 |
| 连续攻击链 | 支付→撤退→换上攻击手→攻击，任意一步错误就停止 |
| 顶尖入口 | 前场阻塞、后排就绪、对手有可选择后排时才触发 |
| 双方目标绑定 | 对方目标和己方目标同为 effect_target；己方只按实体身份绑定 |
| 信息变化 | 目标离场、失去能量或检索未得到进化桥后重新判断 |
| Base 权限 | mandatory、terminal、hard tier 和 veto 不被策略偏好覆盖 |
| 身份和隐私 | 对手同名卡、未知 UID、对手隐藏字段不能获得己方目标偏好 |

## 运行

在仓库根目录执行，替换包路径和未使用的报告路径：

```powershell
.\.venv\Scripts\python.exe tools/complex_decision_bench.py --package work/my-strategy/build/my-strategy.ptcgai --suite demo/ember-frost-complex-bench/suite.json --report work/my-strategy/build/complex-report.json
```

应查看完整链通过数、首个失败步骤和每类结果。比较两个版本时，同时核对包 SHA、suite SHA 和 fixture manifest SHA，不能只比较一个总通过率。

## 这些题目证明什么

题目是人工构造的公开窗口。真实对局发现了缺暗能支付、顶尖无法主动使用、顶尖选错己方目标三个问题，但这里没有将后续题目伪装为引擎自动生成的状态转移。整局录像及强度评估使用独立的本地 Godot bench。

完整格式和边界见 [复杂决策 bench 文档](../../docs/25-COMPLEX-DECISION-BENCH.md)。
