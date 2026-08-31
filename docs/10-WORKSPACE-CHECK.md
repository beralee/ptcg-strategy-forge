# 工作区一键验收

`check` 是作者提交评审前的默认入口。它把容易遗漏的四步合并为一个不可覆盖、可审计的工作流：

```text
源码 A 构建 + 源码 B 构建
→ exact bytes/hash 比较
→ Host 同路径严格校验
→ 完整 scenario-suite
→ 全部通过后才写出最终包
```

## 日常入口

开发者工作区优先使用短命令：

```powershell
.\forge.ps1 workspace check work\my-strategy
.\forge.ps1 workspace build work\my-strategy
```

`workspace check` 只返回验收报告，不保留临时归档；`workspace build` 在相同门通过后，按 package identity 写入默认 `.ptcgai` 和 `build/workspace-check.json`。默认路径可通过 `workspace status` 查看。

## 底层兼容入口

已有 CI 仍可显式控制路径：

```powershell
.\forge.ps1 check `
  --workspace work\my-strategy `
  --output work\my-strategy\build\my-strategy-0.1.0.ptcgai `
  --report work\my-strategy\build\check-report.json
```

工作区必须含 `package/` 和 `scenario-suite.json`。底层 `check --output` 可省略，此时只生成控制台或 `--report` 证据，不保留临时包。它与 `workspace check/build` 共享同一个验收实现。

为了保护证据：

- 已存在的输出不会被覆盖；
- `--output` 与 `--report` 不能是同一路径；
- 场景失败时不会写出最终包；
- 所有临时构建在退出时清理；
- 报告继续接受 public-only 禁止字段扫描。

## 通过报告

重点字段：

| 字段 | 含义 |
|---|---|
| `build.deterministic` | 两次 archive exact bytes 是否相同 |
| `build.archive_sha256` | 可提交开发包的固定身份 |
| `validation.status` | 正式 loader、deck、UID、IR 和 Host 编译是否通过 |
| `scenarios.passed_count/case_count` | 场景套件是否全部 GREEN |
| `ucis.accepted` | registry、目录 closure、性能与 operation 资格是否在执行前通过 |
| `ucis.ucis_generation/registry_sha256` | 工作区实际绑定的标准交互 generation |
| `ucis.unsupported_capabilities` | 当前明确不能进入可用集的效果/能力 |
| `artifact.written` | 最终包是否已原子写出 |
| `claims.*` | 明确没有 engine、CABT parity 或 production 权限 |

退出码：通过为 0，场景/确定性失败为 2，输入、合同或 I/O 错误为 1。

`check` 不替代新牌组卡效审核、Godot 真实引擎见证、官方 CABT 差分、设备 canary 或生产审批；这些仍是独立验收门。

若 `ucis.accepted=false`，先运行 `forge ucis catalog`；若场景窗口不合法，优先运行 `forge workspace inspect <workspace> --scenario <relative-file>`。不要为了通过 `check` 修改或删除 vendored contract、qualification receipt 或 unsupported 清单。
