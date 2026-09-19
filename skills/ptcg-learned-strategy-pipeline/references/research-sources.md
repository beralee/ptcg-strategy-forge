# 方法来源与适配取舍

核对日期：2026-09-19。以下是方法来源，不是当前项目运行能力或复现回执；训练量、名次与性能均以作者公开资料的原始范围理解。再次取代码时固定 commit/实际 bytes、许可证和依赖，不运行未审查的下载内容。

| 原始资料 | 本 pipeline 采用的思想 | 适配边界 |
|---|---|---|
| [第 24 名技术报告](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/writeups/24th-solution-a-population-based-rl-ecosystem)、[开源 sample](https://github.com/ymgaq/ptcg-population-rl) | 规则/GBDT 教师、蒸馏、小模型、群体 PPO、对局矩阵与专家复盘 | 仓库为 sample，约 1M Transformer；当时不含权重、教师录像、matchup experts、自动群体选择和完整规模系统。示例代码 Apache-2.0；官方引擎另取。不能把报告吞吐当我们机器实测，也不直接搬 C++ 推理进 `.ptcgai` |
| [第 183 名 CatBoost＋规则](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/writeups/catboost-rules-hybrid-agent) | 每个合法候选一行、明确 context 分流、规则 fallback、低成本特征诊断 | 约 22 分钟是作者最终模型训练时间，不含整个数据/调参流程。CatBoost 原生导出不保证被当前 ORT allow-list 接受 |
| [第 15 名循环 Actor–Critic](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/writeups/15th-place-solution) | 冻结历史对手、专项模型、终局奖励、输入/动作编码的重要性 | 7.5M 循环网络与当前无状态 Actor 不同；不照搬隐藏记忆或假设大训练量消除战术错误 |
| [第 27 名三级课程](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/738158) | 多牌组 → 体系 → 精确牌表的逐级专门化 | 我们先固定单牌表验证闭环，后续按预算扩展；概述不等于已有完整可复现训练包 |
| [第 20 名动作结果预训练](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/writeups/20th-place-learning-to-play-pokmon-tcg) | 动作效果表征、分开评估策略与改牌、通用到专项 | 25M Transformer 和大规模训练超出首版目标；引擎克隆与分支模拟不在当前作者包权限内 |
| [第 191 名 Deck 312 模仿学习](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/writeups/imitation-learning-for-deck-312) | 玛俐长毛巨魔/雪妖女/愿增猿的公开资源、出牌顺序、伤害分配与合法候选建模 | Kaggle deck hash 不是本地 deck id；需要重新核对精确 printing、卡效和观察合同 |

共同取舍：先建立可观察、可监督、可部署、可评估的闭环；采用模型真正能利用的公开特征。首版用小型前馈 Actor 和现成规则底线，Transformer、循环模型、搜索、专家路由及自动改牌均为后续有证据支持的扩展。
