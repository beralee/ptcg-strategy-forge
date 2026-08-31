# Marnie Forge Demo 策略蓝图

> 状态：可执行教学基线。它只演示 current-window RED→GREEN，不代表完整牌组强度。

## Match Agenda

本 demo 的唯一受审目标是在 `EVOLVES_TO` 窗口中，当公开手牌存在 Morgrem 进化来源且当前 option 对应审核 UID `CSV10C_146` 时，优先提出该语义目标。其他路线交给 Base 确定性 fallback。

## Current-window 边界

- 只返回当前 `select.option` index；
- option 重排后重新按公开 UID 绑定，不保存旧 index；
- mandatory、terminal、hard tier 和 veto 始终优先；
- 未知 UID 或隐藏字段不得通过 adapter 获得选择权。

## RED→GREEN 证据

`scenarios/` 的 10 项覆盖正向、前置缺失、错误目标、重排、mandatory、terminal、hard tier、veto、未知 UID 和隐藏字段。`optimization/baseline_adapter.json` 保留错误身份形成的 RED；`package/policy/adapter.json` 是 GREEN。

## 非声明范围

这里没有完整 Match Agenda、攻击路线、Godot 对局强度、CABT full-rule parity 或 production 权限。需要真实牌组策略时，从 `forge workspace create` 生成的新蓝图开始，并补齐资源账本、攻击窗口和信息检查点。
