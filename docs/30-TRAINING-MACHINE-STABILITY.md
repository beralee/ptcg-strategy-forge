# 本机训练与对局的稳定性

共享机器排队可通过 Python 入口的 `heavy_job(wait_ms=...)` 或 `local_engine_bench.run(..., wait_ms=...)` 有限等待现有锁；每次最多 60 秒，默认仍为立即检查。获得锁后才重新检查 RAM、commit、其他重型进程和磁盘，超时不创建实验目录、不释放别人持有的锁。外围队列必须有总截止时间，内存/磁盘压力失败不自动循环重试。

进程扫描若遇到不可读或空命令行，最多再做一次完整扫描，包含期间新出现的重型进程。再次不可读时，只有 Windows 明确证明该 PID 不存在或进程句柄已退出才可排除；权限不足、仍存活或等待错误继续以 `resource_probe_unavailable` 拒绝，错误原因附 PID。RAM/commit 在进程扫描之后重新采样。此有限探针复核不等于自动重启失败实验，也不放宽任何阈值；失败、修复前后摘要和恢复结果应保留在各自的本地研究目录。


学习流水线启动和恢复时阅读 [电脑稳定性保护](../skills/ptcg-learned-strategy-pipeline/references/computer-stability.md)。这是本机保护，不能保证避免全部硬件、驱动或其他程序故障。

| 条件 | 启动 | 运行中停止 |
|---|---|---|
| 系统内存 | 可用 RAM ≥12 GiB，commit <70% | RAM <12 GiB 或 commit ≥70% |
| 输出盘 / 实际分页盘 | 空闲 ≥20 GiB | 空闲 <10 GiB |
| 系统盘 / 临时盘 | 空闲 ≥5 GiB | 空闲 <3 GiB |
| 本任务私有内存 | 单重型任务、最多 4 workers | 单进程 >8 GiB 或进程树 >12 GiB |
| 每次输出 | 最多 2 GiB，预先固定更小预算 | 超过预算 |
| 每次时长 | 最多 90 分钟，BC 30 分钟 | 超过预算 |

`resources_gate.py` 持有机器级互斥并执行启动检查；`run_safety.py` 监督计算子进程，约每 2 秒落盘记录 RAM、commit、磁盘、进程树和输出大小。数学库线程设为 1，计算子进程使用较低优先级。监控、日志、资源或时长失败只结束本次拥有的子树，留下失败回执；用户正在使用的游戏/编辑器不会被按名称清除。

`neural_strategy_research.py train` 使用监督器启动 BC worker，训练/导出/验证都在监督范围。`local_engine_bench.py run` 监督 Godot，随后逐局记录轨迹验收的资源快照。实际记录见输出目录的 `resource-admission.json`、`resource-telemetry.jsonl`；失败时另有 `resource-failure.json` 或 `failed-run.json`。这些是本机诊断资料，不作为 Actor 输入。

Python 汇总先写临时文件、flush/fsync、读回核对，再原子替换。Godot `research_io.gd` 检查每次 trace 追加，汇总也经过 flush 和字节读回再替换；不能用引擎退出码 0 豁免空轨迹或坏 JSON。模型输出以原子写入的完整报告为完成标记，失败目录不可用于恢复/训练/晋级。

资源门测试使用模拟阈值，不制造真实满盘或内存耗尽；真实 Windows 子进程测试只启动短暂休眠程序并验证目标终止。Godot I/O 探针验证坏目标不能覆盖先前完整结果。恢复后先做短试运行，并复用冻结数据/候选，避免从已看过的确认结果反向调参。

原始失败确认目录保留。升级了 bench I/O 后运行时摘要改变，最终基线与候选在同一新运行时重新配对；不会拿新旧运行时混算。当前是 CPU 路径，没有宣称具备 GPU 温度/VRAM 或系统级故障恢复能力。
