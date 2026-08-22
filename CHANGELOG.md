# Changelog

## 0.1.1 - 2026-08-23

- 修复英文 Windows `cp1252` 控制台无法输出中文 JSON 报告的问题。
- 增加 legacy code-page 回归测试，并在相同严格编码条件下完成完整 demo 验证。

## 0.1.0 - 2026-08-23

- 创建独立的 PTCG Strategy Forge 项目和统一 `forge.py` 命令入口。
- 固定并校验 276 个 PtcgDAP SDK、合同、牌组与工具文件。
- 提供创建、构建、校验、模拟、套件测试、安装和发布工作流。
- 提供完整 Marnie RED→GREEN demo、10 个严格场景和确定性 release 包。
- 完成真实本地 HTTP release 提交验证。
- 增加 Windows 环境脚本、开发者文档、安全测试和 GitHub Actions。
