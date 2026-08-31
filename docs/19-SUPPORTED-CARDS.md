# 游戏支持卡牌清单

Forge 在开发者交付中固定一份机器可读清单：

- 仓库：[`data/developer/supported-cards-v1.json`](../data/developer/supported-cards-v1.json)；
- 新建工作区：`SUPPORTED-CARDS.json`，与仓库文件 exact bytes 相同；
- 静态开发者页面：提供同一快照的下载入口。

该文件由 `contracts/ptcgdap/ucis_card_catalog_v1.json` 和已通过的 `ucis_catalog_qualification_v1.json` 机械生成。当前有 797 个 `godot_local_card_uid_v1` 条目：796 个 `usable=true`，1 个明确 `unsupported`。运行以下命令可验证文件没有落后于锁定合同：

```powershell
.\.venv\Scripts\python.exe tools\build_developer_supported_cards.py --check
.\forge.ps1 doctor
```

## 查询一张卡

PowerShell：

```powershell
$catalog = Get-Content .\work\my-strategy\SUPPORTED-CARDS.json -Raw | ConvertFrom-Json
$catalog.cards | Where-Object card_uid -eq "CSV10C_146"
```

Python：

```python
import json
from pathlib import Path

catalog = json.loads(Path("work/my-strategy/SUPPORTED-CARDS.json").read_text(encoding="utf-8"))
card = next(row for row in catalog["cards"] if row["card_uid"] == "CSV10C_146")
print(card["usable"], card["interaction_status"], card["capability_ids"])
```

每一项包含：

| 字段 | 含义 |
|---|---|
| `card_uid` | 当前 Godot 本地卡牌身份；不是官方 CABT Card ID 或卡名 |
| `usable` | 声明的交互路径是否可进入当前资格范围 |
| `interaction_status` | `automatic`、`compiled` 或 `unsupported` |
| `effect_id` | 锁定 effect 身份，用于审计，不是作者自由调用接口 |
| `capability_ids` | 已登记能力标签；空数组是合法值 |
| `source_path/source_sha256` | 生成目录所依据的受审来源与 hash |

## 三种状态

- `automatic`：该效果不需要作者可见的选择程序；不是“没有效果”。
- `compiled`：效果交互已编译到已资格化的 UCIS current-window 合同。
- `unsupported`：明确不可用，必须 fail closed，不能静默降级或伪造选择。

## 不能从清单推出什么

`usable=true` 只说明这张本地 UID 的声明交互路径属于当前 UCIS 可用范围。它不自动证明：

- 官方完整卡池、官方 Card ID 或翻译名一致；
- 选择提交后的伤害、KO、RNG、终局和完整规则 A3 parity；
- Forge 已提供该牌的策略规则、场景、牌组模板或模型训练数据；
- macOS、Android、production 或比赛资格已经通过；
- 同名、异画或复刻 printing 可以互换。

因此开发新牌组时要依次确认：清单中的本地 UID 可用、精确 60 张与 printing 来源正确、目标策略能在当前 IR 表达、场景通过，最后再走 Godot 与发布资格门。

## 更新规则

清单不能手工编辑。卡表/UCIS 合同升级后运行：

```powershell
.\.venv\Scripts\python.exe tools\build_developer_supported_cards.py
.\.venv\Scripts\python.exe tools\build_developer_supported_cards.py --check
```

生成器固定源文件 raw SHA-256、资格 evidence、条目顺序和状态计数；`doctor` 会在创建工作区前拒绝缺失或过期的交付文件。
