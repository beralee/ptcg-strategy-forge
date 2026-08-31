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

历史 `.ptcgbot` 工作区曾复制 generation-locked `ucis.py`；该 Python agent 分发路径已被统一 `.ptcgai` 决策取代，不再作为下一代供应链。可复用的 current-window 解析只迁入由平台/Forge 固定 hash 的统一张量 SDK，不把 Python 执行权限带入玩家运行时。

`.ptcgai v2` 模型仍是 data-only：只允许 hash-pinned 单文件 `model/actor.ort`，禁止 custom op、作者 native library、外部数据、动态下载、网络和远程推理。Forge 与 Windows Godot 原生扩展已锁定 CPU-only、单线程、固定整数张量、25ms 可取消 deadline 和算子 allow-list；未知 UID/shape、损坏 artifact、超时或输出异常 fail closed 并回退到 Competitive IR/Base。macOS 使用相同合同与 `@loader_path` 构建入口，但尚未实机签发。详见[统一 `.ptcgai` 规则与模型策略设计](17-UNIFIED-PTCGAI-RULE-AND-MODEL-DESIGN.md)。

`StrategyWorkspace.model.tensorize` 接受工作区场景时，不直接从 JSON 挑字段：它先经过 CABT envelope parser 与 public observation firewall，再投影固定 Actor 张量，并以工作区 deck manifest 审核 UID。`workspace model import` 先在同目录临时区检查/转换/conformance，通过后才替换 Actor 与 manifest；失败保留原模型。

## 凭据

发布凭据只能通过环境变量提供。报告固定声明 `credential_persisted=false`，测试会递归扫描证据，禁止 token/password/secret 等键。不要把 `.env`、shell history 或服务器数据库提交到 Git。

开发者发布私钥（例如 `*.ed25519`、PEM/P12/PFX 或其他私钥导出）必须位于仓库与策略工作区之外。Forge 的 `release-key` 拒绝覆盖已有文件，公开 JSON 只包含可登记的公钥、key ID 和指纹；它不是私钥，但也不需要随策略源码提交。仓库 `.gitignore` 防御性忽略常见私钥扩展、`.env*`、`work/`、构建包和本地 artifacts；提交前仍要人工检查 `git status` 与 staged 文件，因为 ignore 规则不能保护已经被 Git 跟踪的秘密。

私钥泄漏时应立即在开发者后台撤销对应公钥，并生成、登记新密钥；仅修改密钥标签或文件名不会换钥。显示名称拼写错误不要求轮换密钥，作者身份以完整 `developer_id` 和包内 `author_id` 为准。

## 网络

创建、构建、校验、模拟和场景测试不需要网络。只有显式发布/服务查询会联网。HTTP 只允许显式 loopback 开发模式；其他端点必须 HTTPS 且禁止 URL userinfo。

## 报告最小化

场景报告保留稳定错误码、公开 matched rule、indexes、裁决来源和无权限 claims，不回显 raw observation 或私有 payload。未知输入 fail closed。
