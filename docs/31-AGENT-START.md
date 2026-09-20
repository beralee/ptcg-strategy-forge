# PTCG Dojo：交给 Agent 的开发与提交任务书

适用于能读写本地文件、运行命令的 Codex、WorkBuddy 等编程助手。用户可以直接说：

> 请按这份任务书，帮我做出第一份 PTCG 策略并提交到我的 Dojo 开发者账号，持续处理失败直到取得资格结果。我会提供牌组或策略想法；如果暂时没有，请从工具自带的规则模板开始。环境检查、开发、测试、签名和提交都由你推进，需要我操作时只告诉我当前必须做的一步。

## 给 Agent 的目标与工作方式

你的目标是让用户得到一份真实可复现的 `.ptcgai` 策略、服务端接收回执和明确的运行资格结果。不要止于给命令、写计划、生成文件或“建议用户自行上传”。用户已要求提交时，完成本地验收后按其授权提交；用户明确要求仅本地开发时则保留这个边界。不要保证胜率、排名或完成时间。

自动检查已有环境和进度，再执行下一步；不要覆盖已有工作区、密钥或提交记录。每个阶段用一句话说明已经完成什么和下一步是什么。遇到错误先读取本地结构化报告和本机帮助，修复后复验；不能把身份、签名、测试或资格失败当作成功。记录进度到工作区的 `AGENT-PROGRESS.md`，只保留命令、阶段、产物路径、公开 ID 和错误码，不记录任何秘密。

用户只需提供策略意图、完成账号邮箱验证，并在本机安全输入凭据。先问清是否已有牌组/策略；没有时使用自带规则模板完成第一轮，不把训练模型、修改游戏引擎、下载整个游戏源码或大规模对战作为首次提交前置条件。自定义牌组应逐张核对工具提供的卡牌目录，不能按同名卡猜测 UID 或偷偷替换卡牌。

## 可信入口

- 开发者注册与网页备用上传：https://ptcg.skillserver.cn/dist/developers.html
- 人类可读指南：https://ptcg.skillserver.cn/dist/developer-guide.html
- 开源工具：https://github.com/beralee/ptcg-strategy-forge
- 正式控制面：https://api.ptcg.skillserver.cn
- 本文只描述公开工具、公开接口和本人账号操作；不需要管理员权限或私有仓库。

## 1. 检查电脑，准备工具

先识别操作系统、当前目录、Git、Python 版本、已有 Forge 和已登录账号。以下命令以 **Windows 的已验证路径** 为例。Forge 要求 Python 3.13；现有 Windows PowerShell 可以运行启动脚本，不需要用户先手工安装 PowerShell 7。缺失依赖时由你完成普通用户范围的安装或提供唯一必要的安装操作，不让用户理解环境配置细节。遵守本机权限要求，不静默提升权限，不永久放宽系统执行策略。

在用户选择的空目录中克隆；已有仓库先看 `git status`，保留改动，不执行破坏性的 reset/clean。Git 不可用时可以使用该官方仓库提供的源码 ZIP，再进入解压目录。

```powershell
git clone https://github.com/beralee/ptcg-strategy-forge.git
cd ptcg-strategy-forge
.\setup.ps1
.\forge.ps1 doctor
.\forge.ps1 --help
```

如果系统阻止 `.ps1`，优先直接用已有 Python 创建环境并执行入口，而不是要求用户修改全局策略：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe forge.py doctor
```

后文所有 `.\forge.ps1` 均可替换为 `.\.venv\Scripts\python.exe forge.py`。先读仓库 `AGENTS.md`、`README.md`、`docs/01-QUICKSTART.md`、`docs/23-CONTROL-PLANE-CLI.md` 和 `docs/26-CLI-ONLY-DEVELOPMENT.md`，并遵守仓库规定的相关阅读要求。命令选项以这份安装的 `--help` 为准；接口变化时不要凭空拼接口。

macOS/Linux 的临时 API Key 模式与 Windows 持久登录不同，游戏预览版也不等于完整开发工具验收。先检查本机工具支持情况；未通过环境检查时说明具体缺口，不声称所有操作系统都已验证，也不让用户盲目执行 Windows 命令。

## 2. 完成账号接入，由工具读取完整身份

已有账号跳过注册。没有账号时打开开发者中心，让用户完成邮箱注册和验证码；密码至少 12 位，验证码有效期 10 分钟。不要索取验证码、密码或 API Key 到聊天记录，不读取浏览器 Cookie，也不替用户猜测凭据。

让用户在自己的可交互终端中执行下面的登录命令，并在隐藏提示中输入密码；你可以预填命令和非秘密邮箱，不能把密码拼进命令参数。如果你的运行环境不能展示隐藏输入，就打开用户可操作的本机终端，让他只做这一步。不要在后台启动一个无人能输入的密码提示后反复等待。

```powershell
.\forge.ps1 service capabilities --origin https://api.ptcg.skillserver.cn
.\forge.ps1 account login --origin https://api.ptcg.skillserver.cn --email 用户注册邮箱
.\forge.ps1 account whoami
```

用户名账号使用 `--username`。已有 API Key 可在 `account login --origin ...` 的隐藏提示中输入。API Key、账号密码、签名私钥是不同的东西，不要混用。Windows 登录信息保存在当前用户凭据管理器，普通配置不保存明文密码或 Token。

非 Windows 或 CI 如使用临时认证，按 `docs/26-CLI-ONLY-DEVELOPMENT.md` 的 `--api-key-stdin` / `--api-key-env` 读取用户在本机配置的秘密；不能通过聊天或明文文件传递。不能通过公共网页给别人代建 API Key。

## 3. 做出最小可用策略

先用规则模式走完整流程，之后再提高强度。选择一个简短、稳定的包身份，例如 `dev.myname.first-strategy`；每个策略独立，不使用超长开发者 ID 作为包名。

```powershell
.\forge.ps1 workspace create work\first-strategy --account --package-id dev.myname.first-strategy --strategy-name "我的第一份策略" --mode rules
.\forge.ps1 workspace status work\first-strategy
.\forge.ps1 workspace inspect work\first-strategy
```

`--account` 自动从本人账号取得完整作者 ID，无需用户复制或理解 `author_id`。不能把显示名称、邮箱、开发者 ID 的后半段当成作者身份。不要创建已存在的工作区；续做时从 status 和进度文档恢复。

把用户意图写入 `STRATEGY-BLUEPRINT.md`，检查 `SUPPORTED-CARDS.json`，在 `package/policy/adapter.json` 及相关场景中实现工具当前支持的规则。先以自带模板和示例为可执行依据，不凭文案发明指令字段。向用户解释策略的实际行为，不要求用户先学 JSON、签名或 SDK。

自定义牌组先阅读 Forge 的 `docs/19-SUPPORTED-CARDS.md`。卡源已随工具提供；在自己的工作区生成精确牌表和清单、同步策略配置，再运行验收。不要把自定义牌组写入 SDK 的内置牌组目录，也不要修改 SDK 来源锁。如果旧版工具因缺少同名内置牌组而报 `package_deck_unmapped`，先保留工作区并更新官方工具，再检查具体 UID、数量和摘要；不要关闭校验。

游戏客户端收录了新卡，不代表当前开发工具和服务器已同步支持。逐张核对当前工具目录；缺失或标为不支持时，说明具体卡牌并让用户决定是否换用已支持牌组。不要绕过目录、手改 SDK 身份或擅自替换同名版本；目录检查通过后仍须取得服务端运行资格结果。

策略只使用公开观察，选择当前选项窗口的索引；每次行动后重新观察。包是数据，不是任意 Python/GDScript 程序。未知能力、卡牌或规则要明确说明，并保持已有合法性和兜底机制。没有真实证据时不能宣称“完整卡效正确”“官方比赛一致”或“强于其他策略”。

## 4. 验证并构建，由你修复错误

```powershell
.\forge.ps1 workspace test work\first-strategy --changed
.\forge.ps1 workspace check work\first-strategy
.\forge.ps1 workspace build work\first-strategy
```

以结构化报告和退出码为准。默认验收包含构建一致性、Host 路径及场景；新增策略行为应有正向与相应负向场景。失败就定位最早报错环节，修复后重跑相关验证。不要跳过检查、删掉失败用例、修改固定 SDK 哈希或放宽上传合同。

环境/安装失败不等于策略失败。首次提交不需要训练进程池或大规模 benchmark。需要额外真实对战评估时另行检查资源和工具支持，并如实区分本地检查与真实对战证据。

## 5. 自动处理签名和公钥登记

先查已有公钥和本机密钥。已有可用匹配密钥时复用；不要覆盖或撤销旧密钥。如果私钥丢失，生成新文件并登记新公钥，不把撤销旧公钥作为默认清理动作——旧策略执行可能依赖它。

首次生成示例：

```powershell
$keyDir = Join-Path $env:USERPROFILE '.ptcg-strategy-forge\keys'
New-Item -ItemType Directory -Force -Path $keyDir | Out-Null
.\forge.ps1 release-key --private-key "$keyDir\main.ed25519" --public-key "$keyDir\main.public.json"
.\forge.ps1 account register-signing-key --public-key "$keyDir\main.public.json" --label '主发布密钥'
.\forge.ps1 account signing-keys
.\forge.ps1 workspace release prepare work\first-strategy --public-key "$keyDir\main.public.json"
```

密钥必须保存在仓库和工作区之外。私钥只供本机签名程序读取，绝不输出、截图、提交 Git 或发送到网页/聊天。网页只登记公钥。核对当前账号、包作者和有效公钥三者一致；Agent 应通过工具完成核对，不让用户手工复制编码字符串。

## 6. 提交，保存回执，等到明确的资格结果

```powershell
.\forge.ps1 workspace release submit work\first-strategy --private-key "$keyDir\main.ed25519"
.\forge.ps1 releases show --release-id 实际回执中的release_id
.\forge.ps1 releases wait --release-id 实际回执中的release_id --timeout 300 --interval 5
```

`release_id` 和本地 `submission_id` 必须取自工具的真实输出，不能自行拼造。`submit` 会对已验收归档进行本机签名并提交，不需要用户再手工执行重签或网页上传。保存归档 SHA-256、版本、release ID、接收状态和资格状态。

“已接收”与“资格通过”是两件事。`releases wait` 超时只说明这次等待结束，先查询进度并继续合理间隔等待，不能把超时当作被拒绝。发生网络断开或接收状态未知时，先按原回执只读对账：

```powershell
.\forge.ps1 workspace release status work\first-strategy --submission 实际submission_id --refresh
```

不要反复创建新版本或重复 POST。仅在服务支持精确归档对账、明确未接收且用户任务仍授权提交时，才按工具帮助使用 `--retry-unaccepted` 重试相同归档。

## 7. 按错误继续推进

| 当前问题 | Agent 的下一步 |
|---|---|
| 登录失效或密码错误 | 保留工作和报告，让用户在本机重新登录一次；不索取聊天密码。 |
| 作者不一致 | 对照 `account whoami` 和工作区身份，使用正确账号/工作区重新构建，不仅篡改归档字段。 |
| 公钥未登记、签名不可信 | 核对账号、完整作者 ID、公钥指纹和私钥对应关系；不要把开发签名包直接上传。 |
| `package_policy_unsupported` 或包合同错误 | 保留错误码，核对本机 SDK、实际策略字段和服务器支持范围；修复、增加版本后重新验收。不要盲目重试。 |
| 资格未通过 | 读取本人 release 详情和可用错误信息；有具体策略问题就修复，有基础设施问题就保留回执并说明阻塞；不能绕过资格门。 |
| 429 / 上传额度限制 | 遵循 Retry-After 或接口提示等待，不换账号绕过限制。 |
| 已接收但响应丢失 | 使用原 submission ID / 归档 SHA-256 查询精确回执，不重复上传。 |
| 只有泛化错误，信息不足 | 给出时间、release ID、请求 ID（若有）和错误码；不猜测根因，不上传凭据或私有日志。 |

网页是备用路径：如果 CLI 不可用，按人类指南在本机生成已签名包，在开发者中心登记公钥并上传；仍由 Agent 准备正确产物和核对结果。不得把“请自行研究网页教程”作为交付。

## 完成条件和交付

交付时以真实证据列出：工作区路径、实际实现的策略、验收结果、包版本和 SHA-256、release ID、服务端接收状态、运行资格状态，以及下一条最有价值的改进。资格通过可给出 `https://ptcg.skillserver.cn/dist/strategy.html?release_id=实际release_id`；不把资格通过等同于已经有排名或保证胜率。

若外部服务、权限、未知合同或用户必需输入造成阻塞，保留可恢复进度，清楚说明已完成到哪一步和唯一的下一动作。不要虚报已发布，也不要悄悄改用其他账号、服务地址或上传不属于用户的策略。
