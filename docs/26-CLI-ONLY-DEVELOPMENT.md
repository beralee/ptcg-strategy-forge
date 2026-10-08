# 注册后的无网页开发流程

SDK 0.3.1 / 2026-09-16 审查结论：原 0.3.0 CLI 能签名提交，但尚未覆盖完整开发者控制面。
本次补齐自动账号身份、临时认证、远端版本查询/下载/资格等待、暂停/恢复参赛和密钥撤销。
首次注册、丢失所有认证凭据后的账号恢复，以及平台管理员审批属于独立范围。

## 密钥分工

| 持有的材料 | 能做什么 |
|---|---|
| 已验证账号的密码 | 通过邮箱或用户名登录，创建 CLI API Key；不能替代签名私钥 |
| 开发者 API Key | 认证本人账号，登记/撤销公钥，查询/下载本人版本，上传签名包，管理参赛 |
| Ed25519 签名私钥 | 本机签署 `.ptcgai`；不能单独登录账号 |
| 公钥 JSON | 登记和核对签名身份；不能签名，也不能替代 API Key |

## Windows：首次接入

以下 `forge` 表示安装后的命令；仓库中可替换为 `.\forge.ps1`。
私钥放到仓库与工作区之外。已有签名密钥时跳过生成。

先选择一种登录方式，由开发者在本机按助手权限要求确认后执行。密码、API Key 和签名私钥不得发送到聊天或写进命令参数；助手无法展示可交互的隐藏输入时，由开发者在自己的终端完成登录。

**刚注册、没有 API Key：** 完成邮箱验证后使用以下命令，在隐藏提示中输入账号密码，无需先去网页寻找 API Key。用户名账号将 `--email YOUR_EMAIL` 替换为 `--username YOUR_USERNAME`。

```powershell
forge account login --origin https://api.ptcg.skillserver.cn --email YOUR_EMAIL
```

**已有 API Key：** 在隐藏提示中输入 API Key，保留原流程。

```powershell
forge account login --origin https://api.ptcg.skillserver.cn
```

密码登录会创建 CLI API Key；两种登录方式均将 API Key 保存到 Windows 当前用户凭据管理器，普通配置不保存明文密码或 Token。非 Windows / CI 的临时认证见[下文](#ci-与非-windows不保存凭据)。

登录成功后继续身份核对、工作区创建和公钥登记：

```powershell
forge service capabilities --origin https://api.ptcg.skillserver.cn
forge account whoami
forge workspace create work\my-strategy --account --package-id dev.myname.strategy

$keyDir = Join-Path $env:USERPROFILE '.ptcg-strategy-forge\keys'
New-Item -ItemType Directory -Force $keyDir | Out-Null
forge release-key --private-key "$keyDir\main.ed25519" --public-key "$keyDir\main.public.json"
forge account register-signing-key --public-key "$keyDir\main.public.json" --label 'Development'
forge account signing-keys
```

`--account` 从服务端取得完整 `developer_id` 和显示名称，无需网页复制，也不截断身份。
离线示例保留 `--author-id`，两者互斥。正式包仍需显式指定短而稳定的 `--package-id`。

## 迭代、上传与资格

先完成上面的公钥登记并确认有效，再运行 `prepare` 预检；`submit` 核对该公钥后才在本机签名上传，私钥不离开本机。

```powershell
forge workspace inspect work\my-strategy
forge workspace test work\my-strategy --changed
forge workspace check work\my-strategy
forge workspace build work\my-strategy
forge workspace release prepare work\my-strategy --public-key "$keyDir\main.public.json"
forge workspace release submit work\my-strategy --private-key "$keyDir\main.ed25519"

forge releases list --package-id dev.myname.strategy
forge releases show --release-id RELEASE_ID
forge releases wait --release-id RELEASE_ID --timeout 300 --interval 5
forge releases download --release-id RELEASE_ID --output downloads\strategy.ptcgai
forge releases pause --release-id RELEASE_ID
forge releases resume --release-id RELEASE_ID
```

`RELEASE_ID` 来自提交报告的 `release_id`。本地 `submission_id` 是另外一个身份，
用于 `workspace release status PATH --submission SUBMISSION_ID --refresh` 的断线对账。
重新提交同一归档沿用精确回执；响应丢失时默认只查询，不悄悄重复上传。

分别核对三个结果：

1. **已接收 release**：提交/对账回执有真实 `release_id` 和 `receipt_state=accepted`，只证明该归档已接收。
2. **运行资格 `passed`**：`releases show` 的 `qualification_status=passed`，或 `releases wait` 成功；不代表已经产生计分对局。
3. **实际计分对局**：按同一 `release_id` 核对天梯中的计分记录；参赛 `eligible`、录像下载或资格通过都不能替代计分证据。

网页未显示公钥状态本身不能证明上传失败，应查看本人 release 回执；资格失败也不抹去已接收事实。

`releases wait` 只发 GET；接收、资格和参赛状态独立报告。退出码 0 表示资格通过；
2 表示失败、撤销、超时或 Ctrl+C 取消；1 表示认证、协议或网络错误。
`--timeout 0` 查询一次。资格失败详情保留服务端步骤、错误码和回执摘要；目前服务端只提供
通用 `runtime_qualification_failed`，不能据此臆造具体引擎堆栈。
等待期限控制轮询；正在进行的 HTTP 请求最多额外等待其 45 秒网络超时。

下载绑定本人 release 和完整 SHA-256，限制 16 MiB，拒绝重定向、错误类型和覆盖既有文件，
校验通过才原子创建输出。下载不等于本地安装或平台批准。
恢复参赛仅表达 `eligible`，实际调度仍受资格、账号状态和服务配额约束。

## 录像与训练边界

```powershell
forge workspace matches list work\my-strategy --origin https://api.ptcg.skillserver.cn --release-id RELEASE_ID
forge workspace replays sync work\my-strategy --origin https://api.ptcg.skillserver.cn --release-id RELEASE_ID --concurrency 2 --requests-per-second 2 --max-games 60 --max-bytes 33554432 --resume
forge jobs list
```

最近 60 场发现、系列去重、受控下载、恢复、哈希校验和任务查询均有 CLI。
平台未提供全历史分页或完整决策附件；播放录像不自动满足 BC 标签合同。
原生录像到目标模型的投影及通用引擎评估仍未完成。
本地规则场景、冻结 Actor 导入、夹具 BC 和可选 Godot bench 均可从命令行使用，
但不能把这些不同证据合并宣称为完整原生 BC 闭环。

## CI 与非 Windows：不保存凭据

所有账号查询/公钥操作、`workspace create --account`、在线 release 操作以及 `releases`
支持以下两种临时认证，必须显式指定服务来源：

```text
forge account whoami --origin https://api.ptcg.skillserver.cn --api-key-stdin
forge releases list --origin https://api.ptcg.skillserver.cn --api-key-env FORGE_API_KEY
forge workspace create work/ci-strategy --account --package-id dev.myname.ci --origin https://api.ptcg.skillserver.cn --api-key-env FORGE_API_KEY
```

第一种从标准输入读取一行，由秘密管理工具管道提供；第二种只读取指定的环境变量，
变量由 CI Secret 注入。不要把真实值写进 shell history。无需 `account login` 或 OS 凭据库；
这些操作不会创建账号 profile，也不持久化 token。协议模式不依赖 OS 凭据库，
本轮实机验收仍在 Windows；不代表已验收其他 OS 的 Godot 运行时。

## 密钥生命周期

```powershell
forge account revoke-signing-key --key-id SIGNING_KEY_ID
forge account revoke-api-key
forge account logout
```

前两条是明确的服务端撤销操作：签名公钥撤销阻止后续新签名上传，API Key 撤销只针对当前
请求使用的凭据，不影响其他 API Key。既有 release、评分、录像和审计不会删除。
`logout` 仅删除本机保存。新 API Key 的创建仍要求账号密码认证，可用
`account login --origin ORIGIN --email EMAIL` 隐藏输入密码取得，API Key 不能派生新密钥。

## 验收与尚未关闭的门

新增能力按服务端实时发现结果启用；旧服务不会被当作已具备暂停/撤销接口。
本地验收使用真实 HTTP、Ed25519、独立 CLI 子进程、双构建/Host/场景和临时账号，
覆盖从已有 API Key 创建到签名提交、查询、下载、等待失败、暂停/恢复、公钥撤销及凭据自撤销。
没有借用浏览器会话。源码验收与公网部署、真实开发者生产上传分别记录。

2026-09-16 新接口已上线。Forge 实际请求能力发现，确认三项新增操作可用；公网权限拒绝、
混合认证拒绝、健康和历史录像读取通过。本次没有向生产账号上传测试策略。

仍需单独完成：真实开发者账号生产提交 canary、全历史/决策附件、原生 BC 投影、
通用引擎评估，以及更细的资格失败诊断。已有 API Key 的日常控制面操作不应再依赖网页。
