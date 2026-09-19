# 天梯决策录像：下载、校验与复盘

服务端需要在 `/v1/developer/capabilities` 声明 `decision_trace: true`。
使用已登录的账号，只能下载本人版本所在座位的决策视角；其中包含自己的手牌、
双方公开场面、当次合法选项、策略选择与 Host 接受结果，不包含对手隐藏手牌。

```powershell
.\forge.ps1 workspace decision-traces pull work\my-strategy --release-id release-实际版本ID --max-games 20 --profile dojo
```

该命令先校验版本归属，再从最近对局逐场下载。结果写入工作区的
`data/online-decision-traces/latest-pull.json`，通过校验的原生录像保存于
`data/native-traces/<trace_id>/`。重复下载不会覆盖既有录像。

每份录像校验原生哈希链、公开观察哈希、窗口哈希、选项指纹、接受索引和步骤见证。
`decision_count` 是可复盘窗口数；`engine_commit_witness_count` 只计算能证明
一次决策对应一次引擎提交的窗口，二者可能不同。记录器新增的公开布尔字段
`appeared_this_turn` 可被读取，原始字段仍参与完整性校验；这不扩展策略执行 SDK 的输入能力。

## 保留期限和缺失

- 录像正文最长保留 24 小时；空间紧张、实例替换或故障可能使其提前不可用。
- 404/410 会明确记录为 `unavailable`，不会导入空录像或编造完整决策。
- 老版本只记录摘要的对局不能恢复为完整决策录像。
- 默认最多下载 20 局、总计 256 MiB；可用 `--max-games`（1–60）和 `--max-bytes` 调整。
- 重要失败案例应及时拉取到本地，再固化为当前窗口及选项重排的回归场景。

这条链路提供复盘证据，不能直接证明策略更强，也不自动授予 BC 训练资格。
仍需独立完成场景测试、双座位引擎对照和生产资格验证。

## 证据边界

`native-traces inspect` 单独读取本地文件，不推断网络来源，所以其
`source_authenticated` 仍为 false；认证下载关系记录在对应的在线下载回执中。
`production_ready` 和 `bc_eligible` 均不会因为这次下载自动变成 true。
