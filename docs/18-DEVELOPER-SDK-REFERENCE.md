# Python 开发者 SDK 参考

`ptcg_strategy_forge` 的公开 SDK 分两层：

- `StrategyWorkspace` 管理完整开发生命周期；
- `SelectionWindow`、`PublicBattleFacts` 等 UCIS 类型处理一个 current-window。

应用代码不应从 `cli.py`、`tools/` 或 `scripts/` 导入。那些模块可以变化，包根目录导出的类型才是开发者合同。

## 导入

在仓库环境或安装后的包中：

```python
from ptcg_strategy_forge import (
    PublicBattleFacts,
    SelectionWindow,
    StrategyWorkspace,
    WorkspaceError,
    option,
    semantic_key,
)
```

## 创建和打开工作区

```python
workspace = StrategyWorkspace.create(
    "work/my-strategy",
    author_id="<后台完整 developer_id>",
    author_name="Example Author",       # 展示名称，不是作者身份
    package_id="dev.example.strategy",  # 正式工作区建议显式指定
    package_version="0.1.0",
    strategy_name="My Strategy",        # 可省略，按目录生成
    summary="Public-window strategy.",
    mode="rules",                        # rules | model
    deck_id=None,                         # 或已审核的精确 deck id
)

same_workspace = StrategyWorkspace.open("work/my-strategy")
```

创建是非覆盖操作。线上账号的 `author_id` 必须逐字符复制完整 `developer_id`，包括 `developer-` 前缀。缺省 `package_id` 是 `dev.<author_id>.<workspace-slug>`；服务端 ID 通常会让组合超过当前 48 字符身份上限，此时 SDK 返回 `workspace_package_id_required`。正式工作区应直接显式提供较短、稳定且全局唯一的 `package_id`，不要截断 `author_id` 来迁就包名。

`open` 会拒绝 symlink 工作区、非目录、缺失/非法 manifest 和未知 policy mode。它只做结构边界检查；行为验收由 `check` 完成。

## 属性

| 属性 | 类型 | 含义 |
|---|---|---|
| `root` | `Path` | 已解析的绝对工作区目录 |
| `manifest` | `dict` | 每次读取当前 package manifest |
| `package_id` | `str` | 稳定包身份 |
| `package_version` | `str` | 当前版本 |
| `strategy_name` | `str` | 展示名 |
| `policy_mode` | `str` | `rules_only` 或 `rules_with_model` |
| `default_artifact` | `Path` | `build/<package>-<version>.ptcgai` |
| `default_report` | `Path` | `build/workspace-check.json` |
| `model` | `WorkspaceModel` | 仅模型模式可用，否则 fail closed |

## 日常方法

### `status()`

不修改文件，返回开发者就绪报告。主要字段是：

- `status=ready|needs_attention`；
- `package`：身份、版本、显示名和模式；
- `scenarios.count`；
- `edit`：蓝图、规则、场景和可选模型入口；
- `outputs`：默认归档和报告；
- `issues`：稳定问题码；
- `next_actions`：等价 CLI。

`ready` 不是完整验收通过，也不声明引擎或 production 权限。

### `inspect(scenario=None)`

通过 UCIS 开发者视图检查一个场景。省略参数时使用 suite 第一项；相对路径以工作区为根，工作区外路径会被拒绝。

```python
inspection = workspace.inspect("scenarios/04-reordered.json")
```

报告显示命名化 context/options 和公开事实，不回显 raw observation。

### `check()`

运行确定性双构建、Host 同路径严格校验、完整场景、UCIS 资格和可选模型 conformance。它不保留临时 `.ptcgai`：

```python
report = workspace.check()
assert report["status"] == "passed"
```

### `build(output=None, report=None)`

运行与 `check` 相同的门，并且只有全部通过才写归档。省略参数时使用工作区默认路径：

```python
report = workspace.build()
print(workspace.default_artifact)
print(workspace.default_report)
```

输出不覆盖。版本/文件已经存在时，应提升版本或显式选择新路径，不要删除证据后伪装为同一 artifact。

### `install(artifact=None)`

安装指定开发归档；省略时使用默认归档。如果默认归档不存在，SDK 先执行 `build`。安装仍会走严格 package validation，只进入平台 resolver 决定的 Godot 用户数据目录。

## 模型子门面

只有 `rules_with_model` 工作区可以访问 `workspace.model`。

### 检查和一致性

```python
workspace.model.inspect()  # 默认 package/model/actor.ort
workspace.model.inspect("exports/actor.onnx")
workspace.model.conformance()
```

`inspect` 检查格式、固定输入输出、shape、dtype、opset 和算子集；`conformance` 实际创建 CPU session 并验证确定性输出。

### 从场景生成训练张量

```python
report = workspace.model.tensorize("scenarios/01-positive.json")
```

默认写 `build/01-positive-tensors.json`。SDK 先让 CABT parser 和 public observation firewall 审核场景，再只投影公开时钟、turn flags、当前窗口、presence/mask 和审核 UID。隐藏对手手牌、私有字段、未知 UID/shape 会 fail closed。

也可以传入已经符合 `competitive_public_actor_i32_v1` 的 public context JSON。输出始终是固定 `[1,24]` frame、`[1,1024,16]` options、presence/mask 和当前窗口重绑定表。

### 导入训练结果

```python
report = workspace.model.import_actor(
    "exports/actor.onnx",
    training_method="bc_rl",  # bc | rl | bc_rl | hybrid | other
    source_run_id="run-2026-08-30",
)
```

该方法解决工作区模板已经存在 `actor.ort` 的替换问题：它先在模型目录的临时位置检查、导入和 conformance，再更新 Actor 与 manifest；失败时保留原模型。`training_method` 和 `source_run_id` 只是非权威 provenance，不扩大运行权限。

## UCIS current-window 类型

```python
window = SelectionWindow.parse(raw_observation)

indexes = window.choose_exact(
    2,
    lambda candidate: candidate.option_type_name == "CARD",
)

target = semantic_key("CARD", area=2, index=20, playerIndex=0)
fresh_indexes = SelectionWindow.parse(next_observation).rebind([target])
```

不要缓存 `SelectionWindow`、索引、tier、veto 或 proof。每个已接受选择都使旧窗口失效；跨窗口只能保存公开语义目标、稳定身份或资源债务。完整 API 和错误码见 [UCIS SDK 指南](15-UCIS-SDK-DEVELOPER-GUIDE.md)。

## 稳定异常

工作区 API 抛出 `WorkspaceError`，其 `code` 是机器可读稳定值：

```python
try:
    StrategyWorkspace.open("missing")
except WorkspaceError as error:
    print(error.code)
```

常见代码：

| code | 含义 |
|---|---|
| `workspace_missing` | 路径不存在 |
| `workspace_path_invalid` | symlink 或非普通目录 |
| `workspace_manifest_missing` | 缺少 package manifest |
| `workspace_manifest_invalid` | manifest 结构/身份无效 |
| `workspace_package_version_invalid` | 版本不能形成安全稳定的 artifact identity |
| `workspace_policy_mode_invalid` | 未知模式或 `model_only` |
| `workspace_model_not_enabled` | 在规则工作区调用模型 API |
| `workspace_scenario_invalid` | 场景不存在、越出工作区或形状错误 |
| `workspace_scenario_suite_invalid` | suite 不能提供合法场景入口 |
| `model_output_exists` | tensor/底层产物拒绝覆盖 |
| `model_hidden_field` | 场景未通过公开输入 firewall |

底层 package/ORT/UCIS 错误会保留其原稳定 code，并包装成 `WorkspaceError`。CLI 将同一 code 写入 `ptcg_strategy_forge_error_v1` JSON。

## CLI 对照

| Python | CLI |
|---|---|
| `StrategyWorkspace.create(...)` | `workspace create` |
| `open(...).status()` | `workspace status` |
| `workspace.inspect()` | `workspace inspect` |
| `workspace.check()` | `workspace check` |
| `workspace.build()` | `workspace build` |
| `workspace.install()` | `workspace install` |
| `workspace.model.import_actor()` | `workspace model import` |
| `workspace.model.tensorize()` | `workspace model tensorize` |
| `workspace.model.conformance()` | `workspace model conformance` |

SDK 与 CLI 共享实现和报告，不需要维护两套工作流。

## 兼容与版本

旧 `.ptcgai v1` 的运行字节兼容不因 SDK 门面改变。旧的 Forge CLI 低层命令继续保留；新 SDK 不导入或运行历史 `.ptcgbot`。当前 API 版本随 `ptcg_strategy_forge.__version__` 发布，新增字段可以向后兼容地出现在 JSON 报告中，调用方应读取需要的字段而不是断言完整键集合。
