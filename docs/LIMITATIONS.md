# 明确限制

以下是当前产品/权限边界，不是可以在独立工具包中伪造关闭的工程 TODO：

- 支持平台为 Windows x86_64 / Godot 4.6.1；Android 尚未进入作者策略自助路径。
- scaffold 只基于已审核的 Marnie 18.0 本地 UID 牌组；任意新牌组需先完成精确卡牌身份、卡源、卡效和规则审查。
- `.ptcgai` 使用 `godot_local_card_uid_v1`，`cabt_exportable=false`；它不是 Kaggle/CABT `.tar.gz` 或竞争服务 `.ptcgbot`。
- 开发构建使用公开 test-fixture Ed25519 材料，`execution_trusted=false`、`production_ready=false`。
- 平台 production 签名、release approval、玩家启动、device canary、A5 和信任根由产品维护者控制。
- `publish` 只提交 release，不自动批准或晋升。
- 模拟验证接口/策略行为，不证明全部卡牌引擎一致性或官方 CABT engine parity。
- Python 是开发工具依赖，不是 PtcgDAP 玩家设备运行时依赖。
- OS 级断网证据不由本项目声明；本地开发流程本身除发布外不发起网络请求。
