# 安装与发布

## 开发目录安装

```powershell
.\forge.ps1 install --package build\my-strategy.ptcgai --report evidence\install.json
```

工具会重新严格校验并原子写入 Godot 固定开发目录。相同 `package_id + version`、相同 archive 字节幂等成功；不同 hash 冲突会被拒绝。安装后需要重启游戏刷新 catalog。

`catalog_discoverable=true` 不等于 `player_start_allowed=true`。普通 test-fixture 包只能显示开发元数据。

## PTCG Dojo 连续联赛作者签名

`build/check` 的公开 test-fixture 密钥不会被开发者上传接口当成账号所有权证明。正式上传由三个独立身份共同约束：

| 身份 | 来源 | 必须满足 |
|---|---|---|
| `developer_id` / 包内 `author_id` | [线上开发者中心](https://ptcg.skillserver.cn/dist/developers.html) | 两者逐字符相等，包括 `developer-` 前缀 |
| `package_id` | 开发者为策略选择 | 简短、稳定、全局唯一；与长 `developer_id` 分开 |
| `signature_key_id` | `release-key` 公钥派生 | 必须对应同一个 `author_id` 账号下仍为“有效”的公钥 |

显示名称、邮箱和密钥标签都不是这些身份，不能替代或修复它们。服务端开发者 ID 通常很长，因此创建正式工作区时要显式指定较短的 `--package-id`：

```powershell
$developerId = "<从开发者后台复制的完整 ID>"

.\forge.ps1 workspace create work\my-strategy `
  --author-id $developerId `
  --package-id dev.myname.my-strategy `
  --author-name "你的显示名称"
```

### 1. 构建前核对作者身份

不要从显示名称猜开发者 ID，也不要只复制前缀后的十六进制部分。构建前可以做一次大小写敏感核对：

```powershell
$manifest = Get-Content work\my-strategy\package\strategy_package.json -Raw | ConvertFrom-Json
if ($manifest.author.author_id -cne $developerId) {
  throw "包内 author_id 与开发者后台 ID 不一致"
}

.\forge.ps1 workspace check work\my-strategy
.\forge.ps1 workspace build work\my-strategy `
  --output work\my-strategy\build\my-strategy-dev.ptcgai `
  --report work\my-strategy\build\workspace-check.json
```

不要直接编辑已经构建的 ZIP。作者身份需要修复时，修改源工作区后重新 `check/build`，再重新签名。

### 2. 在仓库外生成一次发布密钥

私钥路径必须在仓库和工作区之外。密钥标签/文件名不参与作者身份，可以使用容易辨认的本机名称：

```powershell
$keyDir = Join-Path $env:USERPROFILE ".ptcg-strategy-forge\keys"
New-Item -ItemType Directory -Force -Path $keyDir | Out-Null

.\forge.ps1 release-key `
  --private-key "$keyDir\main-release.ed25519" `
  --public-key "$keyDir\main-release.public.json" `
  --report work\my-strategy\build\release-key-report.json
```

命令拒绝覆盖已有密钥。同一把私钥可以继续签署后续版本；公钥仍有效时不需要每次重新生成或登记。

### 3. 只登记公钥

读取公开 JSON：

```powershell
$publicKey = Get-Content "$keyDir\main-release.public.json" -Raw | ConvertFrom-Json
$publicKey.public_key_base64
$publicKey.key_id
$publicKey.fingerprint_sha256
```

登录[开发者中心](https://ptcg.skillserver.cn/dist/developers.html)，只把 `public_key_base64` 的值粘贴到“公钥 Base64”，不要粘贴整份 JSON。登记后核对网页显示的 key ID 和 SHA-256 指纹。密钥标签只是备注；已有同一 key ID 且状态为“有效”时，不要重复登记。状态为“已撤销”的公钥不能用于新上传。

### 4. 在本机签署最终上传包

对刚通过严格验证的开发包只替换签名：

```powershell
.\forge.ps1 release-resign `
  --package work\my-strategy\build\my-strategy-dev.ptcgai `
  --output work\my-strategy\build\my-strategy-upload.ptcgai `
  --private-key "$keyDir\main-release.ed25519" `
  --report work\my-strategy\build\release-signing.json

$signing = Get-Content work\my-strategy\build\release-signing.json -Raw | ConvertFrom-Json
$signing.signature_key_id
$signing.archive_sha256
$signing.payload_preserved
```

`signature_key_id` 必须等于网页上仍然有效的 key ID，`payload_preserved` 必须为 `true`。网页实际选择的是 `my-strategy-upload.ptcgai`，不是 `*-dev.ptcgai`、公开 JSON 或私钥。

### 5. 上传并保存回执

上传前最后确认：

1. 页面开发者 ID 与包内 `author_id` 完全相同，包括前缀；
2. 签名报告的 key ID 在当前账号下为“有效”；
3. 选择文件名明确标为 `*-upload.ptcgai` 的最终包；
4. 保存 `archive_sha256`，不要依靠文件名区分字节；
5. 私钥仍只在仓库外的本机目录。

网页返回“已接收 `<release_id>`，等待资格验证”时，作者身份、公钥登记、签名和包静态合同已经通过上传门。保存 release ID、archive SHA-256 和 key ID；此时不要重复上传，等待资格验证。资格通过、进入比赛、production 批准和官方 CABT 一致性仍是后续独立状态。

### 签名错误的联合排查

`package_signature_untrusted` 不只意味着“公钥没登记”。服务端需要先按包内 `author_id` 找到该账号下的有效公钥，所以即使网页上的 key ID 与本地看起来一致，错误的 `author_id`（尤其漏掉 `developer-` 前缀）也可能得到同一错误。按这个顺序检查：

1. 包源 manifest 的 `author.author_id` 是否逐字符等于页面开发者 ID；
2. 是否误选了旧包、`*-dev.ptcgai` 或修改作者 ID 前构建的包；
3. 签名报告的 `signature_key_id` 是否等于页面“有效”公钥，而不是已撤销公钥；
4. 是否使用生成该公钥的同一私钥重新 `release-resign`；
5. 修正源 manifest 后是否重新 `check/build/resign`，而不是只改文件名。

私钥文件是作者身份凭证：不能粘贴到网页、聊天、工单、截图、ZIP 或 Git。撤销公钥只阻止后续使用该 key ID 的上传，不删除既有审计和评分事实。`developer_registered_release` 也不等于平台产品签名或官方 CABT 批准。

## 策略平台 release 提交

生产端必须使用 HTTPS。只有显式 `--allow-insecure-loopback` 才允许 `127.0.0.1`/`localhost` 的开发验证：

```powershell
$env:PTCGDAP_PLATFORM_WRITE_TOKEN = '<由平台维护者提供的临时写入凭据>'
.\forge.ps1 publish `
  --endpoint https://strategy.example.invalid `
  --strategy-id example.my-strategy `
  --package build\my-strategy.ptcgai `
  --report evidence\publish-receipt.json
Remove-Item Env:\PTCGDAP_PLATFORM_WRITE_TOKEN
```

凭据只从环境变量读取，不写入报告或磁盘。客户端会在上传前严格读取 archive，并校验服务器响应中的 package id、version 和 hash。

成功响应表示 release 已被平台接受，通常处于 `submitted`。它不授予 production 签名、下载、玩家启动、官方统计或引擎权限。

## Demo 发布证据

最终 demo 已向真实本地策略平台 HTTP API 提交，回执位于 [`evidence/demo-publish-receipt.json`](../evidence/demo-publish-receipt.json)。回执确认：

```text
release_state=submitted
archive_sha256=7F53F2DC…D33A
signature_scope=test_fixture_only
execution_trusted=false
authoritative=false
grants=[]
credential_persisted=false
```

公开源码与同一字节的 demo asset 已发布到 [GitHub v0.1.1 Release](https://github.com/beralee/ptcg-strategy-forge/releases/tag/v0.1.1)。公开附件的 SHA-256 为 `7F53F2DC698B0290DFC46C5E439B02439E4849B9522235B547EE5649EDA0D33A`，与本地确定性双构建和干净克隆重建结果一致。

## 旧 competition 服务退出状态

仓库中的 `.ptcgbot` service client、上传资格和 Python runner 属于历史实现，已被统一 `.ptcgai` 取代；活动 CLI 已移除 `forge competition`，它们不再接受新策略资格。历史 evidence 只保留原 scope，不能转换为 `.ptcgai` 安装、模型、macOS 或 production 权限。

规则与模型策略统一沿用本页的 `.ptcgai` build/check/install/publish 流程。v2 ORT Actor 与 Windows Godot development lane 已可执行，安装 resolver 覆盖 Windows/macOS/Linux 的 Godot `user://` 规则；macOS 原生 runtime 仍需实机签发和对局见证。不存在改扩展名或绕过重新校验的迁移。
