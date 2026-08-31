# Contributing

## 开发原则

1. 先增加会失败的场景或测试，再修改行为。
2. 策略输出只能引用当前 `select.option` 索引。
3. 不持久化旧 option index；观察改变后重新绑定。
4. 不把隐藏手牌、牌库顺序、盖放奖赏、私有 RNG、callback、ticket 或 engine object 放入策略输入和报告。
5. adapter 只提供公开同层偏好，不能绕过 Base Graph。
6. 不把 test-fixture、模拟或本地提交描述成 production 或官方 CABT 权限。

## 提交流程

```powershell
.\setup.ps1
.\forge.ps1 doctor
.\forge.ps1 ucis catalog
.\forge.ps1 ucis walkthrough
python -m unittest discover -s tests -v
python forge.py demo --output "$env:TEMP\ptcg-strategy-forge-demo"
python forge.py workspace check demo\marnie-forge
```

demo 输出目录必须不存在。每个新规则至少增加正向、关键条件缺失、目标错误、option 重排和 Base 阻止场景。

新增场景前用 `forge ucis inspect --scenario <file>` 验证 Context/SelectType/Option shape 组合。统一 `.ptcgai` 作者使用公开 `StrategyWorkspace` / UCIS SDK，不要从历史 `.ptcgbot` 复制 Python runtime、enum raw 值、旧窗口或 private `preferred` 字段。

策略行为变更应同步更新工作区 `STRATEGY-BLUEPRINT.md`。信息动作之后只能保留语义目标/债务，必须重观察并重新绑定当前窗口；关键阈值至少增加一个只改变单一事实的 metamorphic 配对。

修改 `scripts/ai/ptcgdap`、`contracts/ptcgdap`、`data/ptcgdap`、`data/bundled_user` 或 `tools/ptcgdap` 后，必须说明来源并重新生成 SDK manifest：

```powershell
python tools/build_sdk_snapshot.py
python tools/build_sdk_snapshot.py --check
```

不要手工修改 manifest 里的 hash。

准备提交前，先检查 staged 文件名和差异，确认没有 `*.ed25519`、PEM/P12/PFX、`.env*`、token、cookie、验证码、服务器数据库、私有回放或开发者工作区产物。公开签名公钥不是秘密，但私钥和临时写入凭据永远不能进入提交。只有用户明确授权时才推送远端。
