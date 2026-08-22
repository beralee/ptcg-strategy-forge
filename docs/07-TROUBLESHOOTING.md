# 故障排查

| 现象/错误 | 原因与处理 |
|---|---|
| `doctor` 的 Python 失败 | 安装 Python 3.13，并重新运行 `setup.ps1` |
| `sdk_file_hash_mismatch` | SDK 文件被修改；确认来源后重建 manifest，不能手改 hash |
| `sdk_file_unmanifested` | SDK 范围出现额外文件；删除生成垃圾或将受审来源纳入 manifest |
| `package_deck_unmapped` | 缺少精确 source deck/card 数据或 UID 不属于 manifest |
| `simulation_expectation_failed` | 实际裁决与场景期望不同；先检查 matched rules 和 selected source |
| `developer_observation_rejected` | observation 含隐藏/非法字段或不符合官方稀疏形状 |
| `invalid_local_uid_public_context` | local UID 未在包牌组 manifest 中或使用了 sentinel/错误域 |
| `scenario_suite_invalid` | 套件结构、重复 ID、期望键或路径边界无效 |
| `demo_output_exists` | demo 不覆盖证据；使用新的版本化输出目录 |
| `platform_endpoint_insecure` | 使用 HTTPS；本地测试需显式 loopback 标志 |
| `platform_write_token_invalid` | 设置 32–256 字符、允许字符范围内的环境凭据 |
| `developer_install_identity_conflict` | 同 package/version 已有不同 archive；提升版本而非覆盖 |

排查时保留失败报告。不要通过放宽 firewall、跳过 Host preflight、关闭 Base veto 或复用旧 index 来“修好”测试。
