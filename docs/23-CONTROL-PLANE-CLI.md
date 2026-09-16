# 控制面与 Forge CLI（2026-09-16）

本页记录首轮控制面。后续完整 CLI 补全和无需网页的逐步命令见
[CLI 完整性审查](26-CLI-ONLY-DEVELOPMENT.md)，包含远端版本管理、资格等待和参赛操作。

本次补齐账号、登记公钥、身份预检、本机签名、提交、接收对账和资格刷新。
这些功能已连接正式 HTTP 合同并通过本地服务集成；2026-09-16 已部署到
`https://api.ptcg.skillserver.cn`，线上能力发现与权限边界检查通过。
完整原生录像 BC、真实引擎评估仍属于独立未完成项。

## 使用步骤

以下 `ORIGIN` 可替换为 `https://api.ptcg.skillserver.cn`。公网必须使用 HTTPS；HTTP
仅允许 localhost、127.0.0.1 或 ::1。`forge` 表示安装后的入口或仓库的 `forge.ps1`。

```powershell
forge service capabilities --origin ORIGIN
forge account login --origin ORIGIN --email YOUR_EMAIL
# 历史用户名账号改用 --username；已有 API Key 可省略这两个选项并交互输入。
forge account whoami

# 路径选择仓库外的新文件；已有密钥时跳过生成步骤。
forge release-key --private-key PRIVATE_KEY_FILE --public-key PUBLIC_KEY_JSON
forge account register-signing-key --public-key PUBLIC_KEY_JSON --label "My release key"
forge account signing-keys

forge workspace build work\my-strategy
forge workspace release prepare work\my-strategy --public-key PUBLIC_KEY_JSON
forge workspace release submit work\my-strategy --private-key PRIVATE_KEY_FILE
forge workspace release status work\my-strategy --submission SUBMISSION_ID --refresh
forge account logout
```

账号命令支持 `--profile NAME`，默认 `dojo`。密码或 API Key 交互输入不回显；
自动化可用 `--api-key-stdin` 从标准输入读取，避免把凭据写入命令参数或报告。
密码登录复用现有会话接口创建 CLI API Key，并在 finally 尝试注销临时会话。

Windows 凭据保存在当前用户的凭据管理器。配置 JSON 只存服务地址、完整作者 ID
和 profile；凭据内部绑定相同元数据，修改地址或作者后不能带着原凭据发送请求。
`logout` 删除本机 profile 和凭据，不撤销服务端 API Key；`account revoke-api-key` 撤销当前 API Key。
持久凭据实现仅覆盖 Windows；自动化和其他系统可显式传 `--origin` 与
`--api-key-stdin` 或 `--api-key-env NAME`，不调用持久凭据库。

## 提交与恢复

未传 `--author-id` 的 `release prepare` 从已登录账号读取作者身份，并核对服务器
登记的公钥指纹。保留显式 `--author-id` 的离线预检兼容模式，其结果不声明在线登记。

`release submit` 必须具有当前有效工作区验收，完整作者 ID 必须与账号相等，
所用私钥的公钥必须已登记且有效。它从已验收包的原始 payload 在本机签名，
不向服务上传私钥；签名包保存在 `releases/archives/<sha256>.ptcgai`。
准备完成后再次检查验收新鲜度；过期、身份不符、未登记或已撤销的 key 均在 POST 前拒绝。

每次提交先持久化未知状态。首次调用先查询同一归档；服务端已接收时复用原回执，
否则才上传。进程中断或响应丢失后，同一调用默认只 GET 对账。确认服务器支持
`archive_sha256_v1` 后，可显式添加 `--retry-unaccepted`，仅在查询返回 404 时重试
相同字节和相同幂等标识的 POST。服务错误不会触发自动重复上传。

接收结果先落盘，资格刷新随后执行。资格读取失败只把当前资格状态改为 unknown，
保留已接收事实和上次成功观察；资格 failed 也不会变成上传失败。
`status --refresh` 不需要私钥，只读取并更新原提交的回执；账号或服务地址不符时拒绝。

Python 使用相同实现：

```python
from ptcg_strategy_forge import AccountStore, StrategyWorkspace
workspace = StrategyWorkspace.open("work/my-strategy")
client = AccountStore().client("dojo")
receipt = workspace.submit_release(client, "PATH_OUTSIDE_REPOSITORY/private.key")
```

## 公开 HTTP 合同

| 接口 | 认证与语义 |
|---|---|
| `GET /v1/developer/capabilities` | 无需登录；返回实际装配的认证、幂等、对账、上传预算和录像能力 |
| `GET /v1/developer/me` | Cookie 或 API Key；只返回本人公开账号字段 |
| `GET/POST /v1/developer/signing-keys` | 本人公钥列表/登记；Cookie 写入仍需 CSRF |
| `POST /v1/developer/releases` | Cookie + CSRF 或 API Key；原始 `.ptcgai`，类型 `application/vnd.ptcgdap.ptcgai` |
| `GET /v1/developer/releases`、`/{release_id}`、`/{release_id}/package` | Cookie 或 API Key；保持本人范围 |
| `GET /v1/developer/releases/by-archive/{sha256}` | 精确完整哈希、账号与服务绑定的接收回执；未知和他人归档均为 404 |

API Key 不获准创建更多 API Key、修改密码、访问管理员接口或绕过浏览器 Cookie
的 CSRF 校验。Cookie 与 Bearer 同时出现返回 `developer_auth_ambiguous`。
HTTP 客户端拒绝重定向，并共用有界并发和速率预算。

上传可携带 `Idempotency-Key: sha256:<64 位小写归档 SHA-256>`；与请求体不符
返回 409 `release_idempotency_conflict`。旧客户端不带该头仍兼容。同账号、同字节
重复提交返回原 release，不增加资格排队项或上传事件，也不再次消费待资格配额。

回执类型 `developer_release_receipt_v1` 包含 `release_id`、`developer_id`、
`archive_sha256`、`receipt_state=accepted` 和独立 `qualification_state`，后者为
pending/passed/failed/unknown。回执不授予生产执行权。

## 本次验证与限制

Forge 最终全量 **155/155**，耗时 **556.934 秒**；工作区双构建、Host/场景校验
与源码目录外 wheel 安装通过，412 个 vendored SDK 文件校验通过。公开客户端的
[机器回执](../evidence/control-cli-20260915.json) 固定源码、测试日志、wheel 和真实录像摘要；
后端实现和后端验收记录保留在私有仓库。

- 本地真实 HTTP、真实签名包、独立 CLI 进程与 Windows 凭据管理器验收通过。
  同包并发仅产生一个 release/上传事件；断线恢复不重复 POST；资格失败保留接收回执。
- 2026-09-09 失败的两个公网录像任务于 2026-09-15 按原任务恢复成功，并发 2、
  每秒 2 请求、2 系列上限、32 MiB 总预算，共下载 220,170 字节。
  两份都是 `godot_v18_public_series_replay_v1`；下载成功不代表具有 BC 所需决策标签。
- 2026-09-16 新接口已部署；Forge CLI 实测返回认证、公钥、归档幂等和精确对账能力。
  公网健康、权限拒绝、无效幂等标识拒绝、榜单与真实录像读取通过；
  [公开接口验收记录](../evidence/control-api-live-20260916.json) 只记录客户端观察。
  真实开发者账号的生产签名上传尚未执行，本次未提交新的生产策略。
- 完整原生录像到 BC、引擎评估、网页 Blob 下载落盘验收继续保留独立缺口。

回滚可恢复本次修改前的源码及旧 wheel；新增本地回执和签名包保留原字节。
后端为兼容性的加法接口，不要求数据库迁移；回滚后新客户端明确报告接口不可用，
不会静默切换成无对账的上传流程。
