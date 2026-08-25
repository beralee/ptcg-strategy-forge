# 故障排查

| 现象/错误 | 原因与处理 |
|---|---|
| `doctor` 的 Python 失败 | 安装 Python 3.13，并重新运行 `setup.ps1` |
| `sdk_file_hash_mismatch` | SDK 文件被修改；确认来源后重建 manifest，不能手改 hash |
| `sdk_file_unmanifested` | SDK 范围出现额外文件；删除生成垃圾或将受审来源纳入 manifest |
| `package_deck_unmapped` | 缺少精确 source deck/card 数据或 UID 不属于 manifest |
| `simulation_expectation_failed` | 实际裁决与场景期望不同；先检查 matched rules 和 selected source |
| `developer_observation_rejected` | observation 含隐藏/非法字段或不符合官方稀疏形状 |
| `ucis_runtime_select_shape_invalid` | 当前 SelectData 缺少标准字段或混入未知字段；确认 generation 后重建 fixture |
| `ucis_runtime_context_type_mismatch` | Context 与 SelectType 不匹配；运行 `ucis inspect`，不要把 CARD options 塞进 YES/NO header |
| `ucis_runtime_option_shape_invalid` | option 缺字段/多字段；测试代码使用 `option("NAME", ...)` 命名构造器 |
| `ucis_runtime_not_enough_matches` | `choose_exact` 的公开候选不足；修正 predicate/身份或显式走 fallback |
| `ucis_runtime_semantic_rebind_missing` | fresh window 中原语义目标已不存在；重新规划，不复用旧 index |
| `ucis_sdk_walkthrough_failed` | SDK/demo generation 或运行文件漂移；先跑 `doctor`、`ucis catalog` 和 `tests.test_ucis_runtime_sdk` |
| `invalid_local_uid_public_context` | local UID 未在包牌组 manifest 中或使用了 sentinel/错误域 |
| `scenario_suite_invalid` | 套件结构、重复 ID、期望键或路径边界无效 |
| `workspace_check_invalid` | 工作区不是普通目录，或缺少 `package/` / `scenario-suite.json` |
| `workspace_check_output_exists` | `check` 不覆盖已存在的 archive；提升版本或选择新输出名 |
| `workspace_check_paths_conflict` | `--output` 与 `--report` 指向同一路径；为包和 JSON 证据使用不同文件 |
| `demo_output_exists` | demo 不覆盖证据；使用新的版本化输出目录 |
| `platform_endpoint_insecure` | 使用 HTTPS；本地测试需显式 loopback 标志 |
| `platform_write_token_invalid` | 设置 32–256 字符、允许字符范围内的环境凭据 |
| `developer_install_identity_conflict` | 同 package/version 已有不同 archive；提升版本而非覆盖 |

排查时保留失败报告。不要通过放宽 firewall、跳过 Host preflight、关闭 Base veto 或复用旧 index 来“修好”测试。
