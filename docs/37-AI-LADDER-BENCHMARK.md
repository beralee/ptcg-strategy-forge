# AI 天梯 benchmark

## 数据与复核

- 页面：[公开 AI 天梯](https://ptcg.skillserver.cn/dist/competition.html)。
- 页面所用数据：[公开 snapshot API](https://api.ptcg.skillserver.cn/v1/ladder/snapshot?match_limit=1)，无需账号或密钥。
- 本次冻结：[2026-09-27 公开字段摘录](benchmarks/ai-ladder-20260927.json)，北京时间 22:20:08。
- 图表：[同一快照的榜单图](assets/ai-ladder-20260927.png)，由公开字段绘制，不是网页截图。

摘录保存服务的 snapshot ID/hash、原始响应 SHA-256、公开引擎声明、赛季、计分配置与全部 52 行榜单。它不包含私钥、账号凭据、策略包、规则源码、模型或决策轨迹。动态 API 之后返回的结果可能已经不同；摘录的原始响应摘要是溯源标识，不声称仅靠删减后的 JSON 就能重建原始响应。

## 读懂指标

| 指标 | 解释 |
|---|---|
| 参赛版本 | 52 个版本，27 开发者版本与 25 平台 NPC；不是 52 个独立作者或牌组 |
| 版本身份 | 每行以 release ID、package ID 和 package version 定位；不同版本分别计分 |
| 排名 | `score_gap_pair_v2`，按 `mu_desc` 排序；μ 为平台积分，不直接解释为胜率或标准 Elo |
| 组 / 局 | `rated_series_count` 与 `actual_game_count`；双座位系列对应两局，不能把两个相关座位当成独立实验 |
| 近期胜率 | `recent_60_games.wins / games`；README 同时给出分母与胜负，不冒充累计胜率 |
| 资格 | `passed`、`eligible` 是平台运行/参赛状态，独立于策略强度与官方规则一致性 |

| 排名 | 策略 / 版本 | 平台积分 μ | 已计分组 / 实际局 | 最近 60 局 |
|---:|---|---:|---:|---:|
| 1 | [余烬霜幕 · 攻击接力与奖赏竞速](https://ptcg.skillserver.cn/dist/strategy.html?release_id=release-b721ed7f55b4c2d4b1b93eb5659d770035d033b0) · 0.4.0 | 987.69 | 207 / 414 | 39 胜 21 负 · 65.0% |
| 2 | [幽影接力 · 18.5 多龙黑夜魔灵](https://ptcg.skillserver.cn/dist/strategy.html?release_id=release-cf196388c350c2d1d81de05682f03a09f60d5cb8) · 0.9.1 | 935.93 | 200 / 400 | 37 胜 23 负 · 61.7% |
| 3 | [余烬霜幕 · 支援者统筹与孤场抢救](https://ptcg.skillserver.cn/dist/strategy.html?release_id=release-9027dadefc5dfa2b534c7b16b0244bccf59d774e) · 0.6.1 | 927.06 | 207 / 414 | 27 胜 33 负 · 45.0% |
| 4 | [厄诡椪／岩殿居蟹 R4](https://ptcg.skillserver.cn/dist/strategy.html?release_id=release-e3794d686875434b30c51f45730b885c9e38808c) · 1.4.0 | 872.55 | 204 / 408 | 30 胜 30 负 · 50.0% |
| 5 | [苍刃咒线 · 赫普的苍响](https://ptcg.skillserver.cn/dist/strategy.html?release_id=release-8dda7b942cf9c5e6300273bad82dd85bb7c3b10e) · 0.2.0 | 847.75 | 202 / 404 | 32 胜 28 负 · 53.3% |

同一快照中排名第 3 的 0.6.1 近期为 27/60，第 1 的 0.4.0 为 39/60。积分累计和近期对手不同，不能把这两个数字当作受控的新旧版因果比较，也不能用版本号推定晋级。

## 能证明与不能证明的范围

公开天梯提供持续、多对手、精确版本下的实战反馈。当前 profile 为 `godot_v18_ladder_v1`，引擎 Godot 4.6.1，服务返回证据状态 `windows_local_stopped_snapshot`，官方 CABT 与 production 声明均为 false；本文保留这些原始限定，不将一个公开网页推导为更高等级引擎认证。

排名会受对手池、调度、样本量、牌组相性与赛季变化影响。这份快照不证明对人类水平、全卡池规则、训练算法优越性或个人策略的源码开放状态；不能把局部场景通过、教师一致率或本地 bench 结果混入线上战绩。

要验证策略改进，应冻结引擎和双方包，预先约定对手、种子与双座位，先过合法性/回放/错误审计，再按相关种子分组进行配对比较。开发集用于诊断，独立确认集只评估冻结候选；失败和退步均应保留。SDK 的可选工具见 [本地引擎 bench](24-LOCAL-ENGINE-BENCH.md) 与 [公开语义模型工具](28-LEARNED-SEMANTIC-ACTOR.md)。
