# 本地 Godot 策略评估

`tools/local_engine_bench.py` 为规则 `.ptcgai` 提供串行整局评估。Forge 的构建、校验和场景工具继续独立运行；只有这个可选研究工具需要本机 Godot 与 PtcgDAP 设计源。

## 使用

先完成策略工作区 `check`，再准备一个不存在的新运行目录：

```powershell
.\.venv\Scripts\python.exe tools/local_engine_bench.py prepare --game D:/ai/code/PtcgDAP --runtime work/experiment/runtime
.\.venv\Scripts\python.exe tools/local_engine_bench.py run --runtime work/experiment/runtime --godot D:/ai/godot/Godot_v4.6.1-stable_win64_console.exe --plan work/experiment/plan.json --output work/experiment/baseline
.\.venv\Scripts\python.exe tools/local_engine_bench.py compare --baseline work/experiment/baseline/report.json --candidate work/experiment/candidate/report.json
```

计划文件包含 `candidate`（包的绝对路径）、可选 `candidate_sha256`、`seeds` 和 `opponents`。包对手形如 `{"path":"D:/.../opponent.ptcgai","sha256":"完整大写SHA256"}`；每个种子自动跑双方座位。内置 NPC 入口接受 `{"npc":"已支持的牌组ID"}`，其准入与干净整局证据必须另行验证。输出目录必须不存在，失败运行保留原始诊断，不能拼接成成功报告。

## 执行与证据边界

- 复制引擎脚本、合同与 data，按运行目录建立唯一用户数据目录并预置原始卡牌/牌组；独立保存开发准入项。共享美术只用于读取，启动游戏场景，不运行 editor/import，不改写产品工程。
- 官方分发包通过原有 control-distributed 检验；本机测试签名包仅在副本中按 ID、版本、完整归档哈希精确准入。保留签名、schema、牌表和 Host 检验。这不构成生产准入。
- 双方均通过现有 BattleDecisionOwnerFactory、Host 与 HeadlessMatchBridge 执行。策略输入只来自当前决策者的 allow-list 公开窗口。
- 每局保存双方包哈希、种子、座位、终局、所有错误/回退计数，以及带哈希链的决策诊断。记录内每份 frame 都属于当时决策者的视角，不得将另一座位的手牌回填为策略特征。
- 校验 frame、观察哈希、窗口哈希、每项 fingerprint、接受索引、双方调用数和轨迹链。诊断字段由同一份隔离引擎快照的公开 frame 校验器验证；不会删除新字段来绕过旧解析器。Forge 的锁定 NativeTraceStore 不因此扩大支持范围。
- 平台 NPC 的匿名奖赏 CARD 诊断使用独立窄校验：仅 `take_prize`、Context 7、身份全部为空、数量与剩余奖赏一致时，在验证副本中转换为等价序号形状；原始帧、哈希、选择指纹保持不变。带卡牌身份或其他额外信息的 NPC 奖赏窗口拒绝；作者包仍使用原来的严格合同。
- 配对比较要求完全相同的运行时、对手包、种子、座位集合；拒绝重复配对、混用候选字节和不干净的报告。
- `resources_gate.heavy_job(workers=1)` 串行锁、启动前资源检查、运行中压力检查和时间/步骤上限保护本机。不要并行启动训练或其他重型评估。
- Windows 控制台启动器与实际游戏程序均记录哈希；异常中断只停止本次启动的进程树，包含其实际游戏子进程。

新准备的运行目录含 `sealed-inputs.json`；运行时指纹锁定脚本、合同、完整 data、native 文件、Godot、启动配置，以及实际用户目录中的卡牌/牌组 JSON。旧研究目录不含此标记时只有旧指纹范围，应仅作探索记录。首次启动若引擎迁移用户数据而导致指纹变化，该次运行拒绝计入结果；在状态稳定后建立新的基线和候选对照。修改运行时后必须重建对照证据，不能混算胜率。

## 解读结果

保留每轮反例 RED、完整场景 GREEN、同种子胜负变化和拒绝实验。先用小样本发现问题，再冻结最终包，在未参与调参的种子上对比。对手版本相近、同种子双座位并非独立样本；Wilson 区间和配对检验只作描述，不单独证明稳定优势。

比较同时提供按种子分组的符号置换检验 `seed_cluster_sign_flip_p`，将同种子的全部对手和座位保持在一起；`paired_exact_p` 则明确标记依赖逐局独立假设。种子组很少时两者都不能证明稳定天梯优势。

这里的最高声明是指定本机 Godot 快照上的干净整局行为。线上天梯名次、官方 CABT parity、设备 UI 验收及生产批准均需独立证据。`forge evaluate` 的完整通用服务集成仍未由这个研究入口关闭。
