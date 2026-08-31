# Minimal BC RL Marnie 策略思考蓝图

> 牌组：18.0 玛俐的长毛巨魔
> 状态：DRAFT。先用公开事实和场景证据填完蓝图，再调整规则 priority。

## 1. 不可变决策边界

```text
agent(raw_observation) -> list[int]
```

- 每次只从当前 `select.option` 窗口选择索引；旧索引、旧分数和旧证明不跨窗口复用。
- 任何已接受选择或信息变化后都重观察、重建公开事实并重新绑定语义目标。
- Base Graph 拥有合法性、mandatory/terminal、hard tier、veto、fallback 和最终裁决。
- 作者 adapter 只表达公开目标、macro 和同层 tie-break；不执行引擎动作，也不读取隐藏信息。

## 2. Match Agenda

- 主要获胜路线：TODO
- 备用获胜路线：TODO
- 最快奖赏日程（按攻击窗口，不按自然回合）：TODO
- 稳健奖赏日程：TODO
- 当前应保护的引擎、攻击手和一奖桥：TODO
- 何时从铺场切换到终结：TODO

## 3. 公开事实与身份

- 只使用本包 `deck_manifest.json` 中审核过的本地 UID。
- 对手隐藏手牌、牌序、盖放奖赏、私有 RNG 和搜索 capability 不进入策略输入或报告。
- 决策所需公开事实：TODO
- 关键身份/角色映射（攻击手、引擎、检索、加速、回收、换位）：TODO

## 4. Resource Ledger

| 资源或额度 | 当前用途 | 必须保留给 | 可消费条件 | 过度投入风险 |
|---|---|---|---|---|
| 支援者额度 | TODO | TODO | TODO | TODO |
| 手贴/能量 | TODO | TODO | TODO | TODO |
| 备战位 | TODO | TODO | TODO | TODO |
| 关键检索/回收 | TODO | TODO | TODO | TODO |

## 5. 候选路线与攻击窗口

| Route | 当前收益 | 对手可信回应 | 下一攻击手连续性 | 最小资源支付 | 切换条件 |
|---|---|---|---|---|---|
| Rule floor | TODO | TODO | TODO | TODO | TODO |
| Route A | TODO | TODO | TODO | TODO | TODO |
| Route B | TODO | TODO | TODO | TODO | TODO |

只在公共证明或已验证场景支持时离开 Rule floor。不要把“退到备战区”自动视为保奖成功；同时评估对手抓取与自己的攻击窗口是否变慢。

## 6. 信息动作与重规划检查点

抽牌、检索、揭示、奖赏变化、随机结果和新交互窗口都可能改变最优路线：

| 信息动作 | 新增公开信息 | 必须失效的旧假设 | 重观察后的条件后缀 |
|---|---|---|---|
| TODO | TODO | TODO | TODO |

条件后缀只保存语义债务和目标，不保存未来索引或预造动作。每次仍只执行一个当前窗口动作。

## 7. 类型化交互

- 检索目标策略：TODO
- 弃牌/能量支付策略：TODO
- 换位与出战目标策略：TODO
- 伤害/指示物分配策略：TODO
- 明确允许 whiff/空选择的窗口：TODO

## 8. Hard Guards 与回滚

- 当前可直接获胜时禁止的无关动作：TODO
- 会丢失当前攻击窗口的资源消费：TODO
- 无精确可支付击倒时禁止的抓取/换位：TODO
- 信息不足、未知枚举或策略失败时的确定性 fallback：Base Graph
- 回滚单位：上一份 exact `package_id + package_version + archive_sha256`

## 9. Adapter 规则映射

| rule_id | goal_stage | 公开前置条件 | 目标 option 语义 | Base 可阻止原因 |
|---|---|---|---|---|
| TODO | acquire/deploy/fund/ready/execute/maintain/recover | TODO | TODO | TODO |

## 10. RED→GREEN 场景矩阵

每个 macro 至少覆盖：正向、关键条件缺失、错误目标、option 重排、mandatory/terminal、hard tier/veto、未知 UID 和隐藏信息污染。

再为关键判断增加 metamorphic 配对：每次只改变一个事实（例如目标 HP、剩余奖赏、能量数量、抓取能力或攻击窗口），期望决策随阈值正确翻转。

## 11. 完成门

- [ ] 蓝图中的所有 TODO 已被规则、场景或明确非目标关闭。
- [ ] `check` 双构建字节一致、严格校验通过、场景全部 GREEN。
- [ ] 报告中无隐藏信息、raw authority、ticket、command 或凭据。
- [ ] 已区分开发模拟、Godot 引擎见证、CABT 对齐与 production 权限。
- [ ] 失败按 observation / identity / policy / Base adjudication / interaction / engine 分层归因。
