# Kaggle 风格 `.ptcgbot` v2 快速入门

这条工作流用于多文件纯 Python 策略，与玩家设备上的 data-only `.ptcgai` 分开。`.ptcgbot` 当前只能获得 `developer_local_qualified`：不能直接安装到游戏，不声明 production sandbox、official engine 或完整规则 A3。

## 1. 环境自检

competition runtime 固定为 Windows x86_64、CPython `3.11.13` / `cp311-win_amd64`。Forge 自身使用项目 venv；competition 命令会查找 exact 3.11.13，也可通过 `PTCGBOT_PYTHON` 指向该解释器。

```powershell
.\setup.ps1
.\forge.ps1 competition doctor
.\forge.ps1 ucis catalog
.\forge.ps1 ucis walkthrough
```

`competition doctor` 检查 Python ABI、runtime lock、RPC、A1 scope、Search=none、time profile、SDK snapshot 和 clean-room 分发门。`ucis walkthrough` 先让开发者看懂 current-window 规则，不需要创建工程。

## 2. 创建工作区

```powershell
.\forge.ps1 competition init `
  --output work\my-bot `
  --strategy-id community.example.bot `
  --author-id community.example `
  --display-name "Example Bot"
```

生成内容：

```text
my-bot/
  README.md
  STRATEGY-BLUEPRINT.md
  ptcgbot.toml
  runtime-lock.json
  deck.csv
  src/submission/
    __init__.py
    main.py          # 唯一 agent 入口
    ucis.py          # generation-locked、无依赖 current-window SDK
  scenarios/
    smoke.json       # bootstrap + 正向 + semantic reorder
  tests/README.md
  resources/
```

模板中的 scenario 已使用合法 `CARD / TO_HAND / CARD` 稀疏 wire，不使用测试私有的 `preferred` 字段。`ucis.py` 与 Forge 当前 registry generation/hash 有回归绑定，并作为作者源码进入 deterministic content manifest。

## 3. 读懂生成的 agent

```python
from pathlib import Path

from .ucis import SelectionWindow, semantic_key

_DECK = [int(value) for value in Path("deck.csv").read_text(encoding="ascii").splitlines()]
_SEARCH_TARGET = semantic_key("CARD", area=2, index=20, playerIndex=0)


def agent(raw_observation):
    select = raw_observation.get("select")
    if select is None and raw_observation.get("current") is None:
        return list(_DECK)

    window = SelectionWindow.parse(raw_observation)
    if window.context_name == "TO_HAND":
        return window.rebind([_SEARCH_TARGET])
    return window.first_legal()
```

初始牌组 callback 返回 exact 60 个 official Card ID；之后只能返回当前 `select.option` indexes。每次选择被接受后，旧 `SelectionWindow`、index、score、binding 和 proof 全部失效。

开发者需要记住的循环只有：

```text
parse fresh observation
→ derive public facts / semantic goal
→ choose current indexes
→ return
→ next callback 重新 parse 和 rebind
```

精确数量、NUMBER/YES_NO、重复分配、公开奖赏时钟和能量债务示例见 [UCIS SDK 开发者指南](15-UCIS-SDK-DEVELOPER-GUIDE.md)。

## 4. 第一轮 RED→GREEN

先运行模板：

```powershell
.\forge.ps1 competition test --workspace work\my-bot
```

然后只改一个语义目标或期望，先让场景 RED；再修改 `main.py`/自有模块让它 GREEN。关键动作至少加入：

- 目标存在与缺失；
- min/max 精确数量；
- option reorder；
- 信息动作后 fresh callback；
- one-fact metamorphic flip；
- unknown Context/Option/字段拒绝；
- invalid output、timeout 和 private sentinel containment。

不要把最终 index 写死进跨 callback 状态。若要保存目标，保存 `semantic_key`、official serial 或公开角色债务，再对新窗口 `rebind`。

## 5. 日常命令

```powershell
.\forge.ps1 competition test --workspace work\my-bot
.\forge.ps1 competition check --workspace work\my-bot

.\forge.ps1 competition build `
  --workspace work\my-bot `
  --output work\my-bot\build\my-bot.ptcgbot

.\forge.ps1 competition trace `
  --package work\my-bot\build\my-bot.ptcgbot `
  --suite work\my-bot\scenarios\smoke.json `
  --public

.\forge.ps1 competition prequalify --workspace work\my-bot
```

| 命令 | 通过条件 |
|---|---|
| `test` | scenario transcript 的每个 callback 返回与期望相同 |
| `check` | 两次 canonical build exact bytes 相同、共享 Bundle owner 严格校验、scenario 全绿 |
| `trace --public` | 只输出 ordinal、返回域、option fingerprint、result 和稳定错误，不回显 observation |
| `prequalify` | ABI、deck、determinism、reorder、网络/子进程/私有 sentinel、timeout/output、scratch cleanup 全绿 |

构建输出不覆盖已有文件；建议把版本和 archive hash 一起记录到策略蓝图。

## 6. 多文件和资源

`src/submission/` 可增加纯 Python 模块；`resources/` 只允许 profile 列出的 inert JSON/CSV/TXT/受限 NPY。禁止 wheel、DLL、EXE、pickle、`.pth`、动态安装依赖和作者提供的 `cg` 模块。

`runtime-lock.json` 是平台拥有的 exact copy，不能由作者修改。需要新的 dependency/Search/native capability 时必须提升 runtime generation，不能在策略包里自行扩大权限。

## 7. 当前 authority

当前 `.ptcgbot` 只证明 developer-local tooling、确定性包链和 Godot core selection A1 scoped binding。项目负责人允许 user-private oracle 的本地研究比较，但 official bundle 不复制、不发布、不上传、不进入 SDK。

对应卡九类 operation input/index 是独立 PtcgDAP 证据；它不授予本 runner official Search、official clock、服务端排名、production 多租户隔离、玩家安装，或提交后的 state/damage/KO/RNG/terminal 一致性。
