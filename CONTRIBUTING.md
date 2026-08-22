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
python -m unittest discover -s tests -v
python forge.py demo --output "$env:TEMP\ptcg-strategy-forge-demo"
```

demo 输出目录必须不存在。每个新规则至少增加正向、关键条件缺失、目标错误、option 重排和 Base 阻止场景。

修改 `scripts/ai/ptcgdap`、`contracts/ptcgdap`、`data/ptcgdap`、`data/bundled_user` 或 `tools/ptcgdap` 后，必须说明来源并重新生成 SDK manifest：

```powershell
python tools/build_sdk_snapshot.py
python tools/build_sdk_snapshot.py --check
```

不要手工修改 manifest 里的 hash。
