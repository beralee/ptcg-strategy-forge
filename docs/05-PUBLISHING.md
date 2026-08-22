# 安装与发布

## 开发目录安装

```powershell
.\forge.ps1 install --package build\my-strategy.ptcgai --report evidence\install.json
```

工具会重新严格校验并原子写入 Godot 固定开发目录。相同 `package_id + version`、相同 archive 字节幂等成功；不同 hash 冲突会被拒绝。安装后需要重启游戏刷新 catalog。

`catalog_discoverable=true` 不等于 `player_start_allowed=true`。普通 test-fixture 包只能显示开发元数据。

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

## 竞争服务客户端

仓库还包含 `tools/ptcgdap/competition_service_client.py`，用于开发者申请、一次性凭据领取、已构建 `.ptcgbot` 上传、榜单/对局查询与公开录像下载。`.ptcgbot` 是 CABT Python competition agent，和本工具包主流程的纯数据 `.ptcgai` 不是同一种包；不要互换扩展名、合同或权限声明。
