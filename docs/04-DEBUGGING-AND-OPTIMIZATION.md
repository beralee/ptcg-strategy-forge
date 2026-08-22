# 调试与优化

## 从最早 owning layer 排查

按以下顺序定位：

1. `doctor`：SDK/合同/模板是否完整；
2. `build`：文件集、hash、签名和牌组是否闭合；
3. `validate`：Host 编译、UID 和 IR 是否有效；
4. `simulate` 的 `frontier`：当前窗口是否允许 policy；
5. `adapter.matched_rules`：规则是否命中预期 option；
6. `adjudication.candidates`：是否被 forced/tier/veto/cardinality 淘汰；
7. `selected_source`：adapter、mandatory、terminal 或 fallback 谁最终拥有决策。

不要先通过改 priority 掩盖 UID、公开上下文或窗口绑定错误。

## RED→GREEN demo

[`optimization/baseline_adapter.json`](../demo/marnie-forge/optimization/baseline_adapter.json) 故意要求错误的手牌 UID `CSV10C_216`。合法窗口不命中规则，Base 选择 `[0]`，而场景期望 `[1]`，所以得到 `simulation_expectation_failed`。

最终 adapter 改为真实关键 UID `CSV10C_147`，主场景命中规则并选择 `[1]`。重排场景把相同语义目标移到 index 0，策略重新绑定后选择 `[0]`，证明没有持久化旧 index。

完整复现：

```powershell
.\forge.ps1 demo `
  --output evidence\my-demo-run `
  --report evidence\my-demo-report.json
```

输出目录必须不存在。通过报告同时证明：baseline RED、10/10 GREEN、严格校验和两次 archive exact-byte 一致。

## 优化准则

- 每次只改变一个可解释规则；
- 保存失败场景作为永久回归；
- 对相同语义始终增加 option 重排用例；
- 比较 `matched_rules` 与候选淘汰原因，不只比较最终动作；
- 完成合同/隐私回归后再做多局胜率评估；
- 单局录像只能形成假设，不能直接晋升 release。
