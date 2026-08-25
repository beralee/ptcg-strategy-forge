# 安全与隐私

## 信任边界

- `.ptcgai` 只含闭合数据，不允许脚本、可执行文件、嵌套 archive 或 symlink；
- policy 只看 allow-list 公共 observation；
- 对手隐藏手牌、牌库顺序、盖放奖赏、私有 RNG 和 `search_begin_input` 不得进入策略输入或报告；
- `ticket`、callback、command、Godot object 和 engine reference 不得进入包；
- Base Graph 和 Host 拥有最终 legal frontier、binding、veto、fallback 与 commit；
- test-fixture 签名不能晋升为 production trust。

## SDK 供应链

`vendor/ptcgdap-sdk-manifest.json` 固定 SDK 快照来源、base commit、文件大小和 SHA-256。`doctor` 会检查：

- manifest 形状和路径规范；
- 大小与 hash；
- 缺失文件；
- case-insensitive 重复路径；
- 路径穿越；
- symlink；
- manifest 未登记的额外 SDK 文件；
- 生成合同是否漂移。

`.ptcgbot` 新工作区还包含 `src/submission/ucis.py`。`competition doctor/check/build/prequalify` 要求它与 Forge generation-locked runtime SDK exact bytes 相同，并把 SHA-256 写入 build/qualification receipt；修改或 symlink 会得到 `competition_ucis_runtime_sdk_mismatch`。该 helper 仍只是作者 current-window view，不是 engine legality 或 production security boundary。

## 凭据

发布凭据只能通过环境变量提供。报告固定声明 `credential_persisted=false`，测试会递归扫描证据，禁止 token/password/secret 等键。不要把 `.env`、shell history 或服务器数据库提交到 Git。

## 网络

创建、构建、校验、模拟和场景测试不需要网络。只有显式发布/服务查询会联网。HTTP 只允许显式 loopback 开发模式；其他端点必须 HTTPS 且禁止 URL userinfo。

## 报告最小化

场景报告保留稳定错误码、公开 matched rule、indexes、裁决来源和无权限 claims，不回显 raw observation 或私有 payload。未知输入 fail closed。
