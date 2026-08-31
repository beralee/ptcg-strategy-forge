# Minimal BC→RL `.ptcgai` 端到端样例

这是最小的可执行模型接入样例，不是强度样例。`train_minimal_actor.py` 只读取两条公开 current-window 场景：先做行为克隆 warm start，再做 64 次确定性离线 contextual-bandit 更新，导出固定 shape、无状态、CPU-only 的整数 ORT Actor。包内 Competitive IR 始终是可独立运行的 fallback。

从 Forge 仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe examples\minimal-bc-rl-marnie\train_minimal_actor.py
.\forge.ps1 workspace model inspect examples\minimal-bc-rl-marnie
.\forge.ps1 workspace model conformance examples\minimal-bc-rl-marnie
.\forge.ps1 workspace build examples\minimal-bc-rl-marnie --output examples\minimal-bc-rl-marnie\build\minimal-bc-rl-marnie.ptcgai
```

当前冻结 Actor 为 4,328 bytes，SHA-256 `0BAF0E2C1E3F92CE65794928419AF321CD75A3BB8400FED11BB99E9C09DCF136`。冻结包为 27,415 bytes，SHA-256 `D4A7BAD9A6C7ECD6837026E090F2FF7CC592D90F1E0DB578968311BAA27BCBA0`，10/10 场景与双构建通过。

Windows x86_64 的真实 Godot 对局回执位于 PtcgDAP `evidence/ptcgdap/minimal_bc_rl_model_battle_windows_20260830.json`：55/55 策略调用成功、38 次原生 ORT 推理、30 次模型改选、0 fallback/非法输出/引擎拒绝。对局由规则座位获胜，所以该证据只证明接入和裁决链跑通，不证明模型强度；`full_game_rl=false`、`production_ready=false`。macOS 两架构仍需实机回执。
