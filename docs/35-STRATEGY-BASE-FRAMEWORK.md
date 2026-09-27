# Base 策略构筑与复盘框架

`StrategyBase` 是 AI 训练家的通用作者工具：把比赛议程、资源与角色、按公开局面重规划的路线、当前交互和录像反思编译为现有 SDK 支持的 data-only Competitive IR。运行时仍由 Base/Host 裁决。

入口流程见 [`ptcg-strategy-base`](../skills/ptcg-strategy-base/SKILL.md)，学习模型流程见 [`ptcg-learned-strategy-pipeline`](../skills/ptcg-learned-strategy-pipeline/SKILL.md)。本次公共 SDK 不分发个人参赛策略、实验工作区或训练权重。

## 已实现

- 草稿、审计与编译：16 项设计考虑，未决项阻止编译；实现引用必须解析到规则、目标或路线，明确缺口保持可见。
- `ResourceBudget`、`RouteValue`、`route_step` 和 `route_candidate`：声明资源预算、路线价值和每步 fresh checkpoint。
- 分阶段编译：每次观察从公开条件重新选择阶段、剩余预算与当前合法第一步，不保存旧索引或假定前缀已经执行。
- 冻结 adapter、牌表与 SDK 来源锁；检测漂移，沿用 compiler 的 UID、资源、数量与路线数限制。
- 原生/bench 录像复盘：校验完整性与接受记录，只分析指定座位，生成带窗口定位的优化假设及待验证实验。

16 项考虑覆盖赢法、奖赏时钟、角色、进化、抽检、费用、资源竞争、换位抓取、后继、信息检查点、交互、伤害、反制、备战负担、耗尽回收和 fallback。设计审核本身不是正确性证明。

## 使用

```powershell
.\.venv\Scripts\python.exe tools/strategy_base.py init --workspace work/my-strategy
.\.venv\Scripts\python.exe tools/strategy_base.py audit --workspace work/my-strategy --report work/my-strategy/base/audit-r1.json
.\.venv\Scripts\python.exe tools/strategy_base.py compile --workspace work/my-strategy --output work/my-strategy/base/candidate-r1
```

输入须是已审核的 Competitive IR v2 工作区。编译结果应用到候选副本后，仍需运行完整 `workspace check`；工具不会自动上传。schema、资源语义和测试入口见 [框架使用](../skills/ptcg-strategy-base/references/framework.md)。

```powershell
.\.venv\Scripts\python.exe tools/strategy_base.py reflect-native --trace <directory> --seat 0 --report <new-report.json>
.\.venv\Scripts\python.exe tools/strategy_base.py reflect-bench --bench-report <report.json> --candidate-sha256 <sha256> --report <new-report.json>
```

Bench 每次最多 32 局，可重复 `--game-index` 限定。原生提交见证与 bench 整局审计分开报告；完整性不等于来源认证。未执行的替代动作只是待验证假设。

## 能力边界

这是有限候选路线、公开谓词和逐步重规划。人工路线整数不是胜率预测。支援者、手贴、撤退和备战位有当前可用性门；能力次数、弃牌、检索仍需公开前置条件与具体卡效验证。没有通用特殊能量求解器、完整对手响应树或全局指示物优化。

通用测试见 `tests/test_strategy_base.py`、`tests/test_strategy_base_cli.py` 和 `tests/test_strategy_reflection.py`，覆盖 fresh rebind、选项重排、Base 保护、未知事实和资源门。这些是公开窗口证据；整局强度必须另外验收。
