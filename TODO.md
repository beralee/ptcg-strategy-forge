# PTCG Strategy Forge TODO 闭环

本文只记录工具包建设过程中发现、且属于本项目可解决范围的缺口。产品方 production 私钥、审核批准、A5、Android 和任意新牌组规则一致性是明确的平台权限/产品范围，记录在 `docs/LIMITATIONS.md`，不伪装成本项目可自行关闭的 TODO。

| ID | 发现的缺口 | 处理结果 | 状态 | 证据 |
|---|---|---|---|---|
| T01 | 工具散落，开发者必须了解主工程目录 | 建立统一 `forge.py`，覆盖创建、构建、校验、模拟、测试、安装、提交和 demo | DONE | `python forge.py --help` |
| T02 | 独立校验缺少模板牌组的精确源 deck/card 数据 | 随 SDK 固定 800018501 及其 28 个 printing 源文件 | DONE | `forge.py doctor` |
| T03 | 原 scaffold 只有一个正向场景 | 增加 10 场景 strict suite | DONE | `evidence/demo-workflow-green.json` |
| T04 | 场景生成不可重复且负例假设不准确 | 场景生成器改为幂等，并使用真实 allow-list/UID 负例 | DONE | `regenerate-demo-scenarios` 连续运行测试 |
| T05 | 没有可证明的优化过程 | 增加错误基线 RED、修正后 GREEN 和选项重排证据 | DONE | `demo/marnie-forge/optimization` |
| T06 | 没有确定性双构建收据 | `demo` 比较两份 archive 的 exact bytes/hash | DONE | SHA-256 `7F53F2DC…D33A` |
| T07 | 发布工具与开发流程分离 | 统一 `publish` 并完成真实 loopback HTTP 提交 | DONE | `evidence/demo-publish-receipt.json` |
| T08 | SDK 来源只能靠目录约定 | 增加 byte-level manifest，拒绝篡改、额外文件和 symlink | DONE | `vendor/ptcgdap-sdk-manifest.json` |
| T09 | 缺少一套从零可执行的开发者文档 | 增加 Quickstart、策略、测试、优化、发布、安全、排障和架构文档 | DONE | `docs/` |
| T10 | 缺少自动化回归入口 | 增加 unittest、PowerShell setup/runner 和 GitHub Actions | DONE | `tests/`、`.github/workflows/ci.yml` |
| T11 | 尚未证明离开当前工作目录仍可运行 | 从 GitHub 全新克隆，空环境安装后 doctor、11 项测试和完整 demo 全部通过 | DONE | `evidence/clean-clone-acceptance.json` |
| T12 | 新项目和 demo 尚未上传用户 GitHub 空间 | 已创建公共仓库、推送源码并发布带 SHA-256 的 demo asset | DONE | `evidence/github-publication.json` |

完成规则：只有证据文件和外部状态都可复核时才能把 `PENDING` 改为 `DONE`；不能仅因代码已写就关闭。
