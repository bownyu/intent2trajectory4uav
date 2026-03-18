## Why

当前生成器仍然以单文件几何模板为中心：`straight_penetration`、`non_straight_penetration`、`hover`、`loiter`、`retreat` 的生成、校验和导出逻辑紧耦合在 `generator.py` 中，语义标签、运动学约束和导出 metadata 也主要围绕“轨迹形状”组织。这与 2026 年 3 月 13 日方案要求的“相对站点风险行为生成器”不一致，已经无法支撑统一的风险语义向量、机型约束和可控多样性。

现在需要推进这次重构，因为已有 Phase 1 只覆盖了 `hover/loiter` 的局部语义迁移，而新方案要求对四类意图、生成流程、动力学展开、校验流程和元数据结构进行统一升级。如果继续在现有模板上叠加变体，只会进一步放大配置复杂度和语义漂移。

## What Changes

- 将顶层意图体系从 `straight_penetration + non_straight_penetration + hover + loiter + retreat` 重构为 `attack + retreat + hover + loiter`，并将旧 `variant` 语义迁移为同一意图下的 `motion_style`。
- **BREAKING**：将生成器主流程从“按意图直接画几何轨迹”改为“采样语义目标 -> 选择机型 -> 选择风格 -> 构建阶段计划 -> 机型约束 rollout -> 风险评分/判定 -> 多样性过滤 -> 导出”。
- 引入统一的 6 维 `risk_vector`、四类 intent 连续评分、硬阈值判定和模糊性排斥规则，使所有样本都映射到可计算的风险语义空间。
- 引入 `AirframeProfile`、按机型分层的动力学模型、在线约束和离线硬约束校验，并增加一次轻量修复后再重采样的流程。
- **BREAKING**：将导出 metadata 从当前以 `variant_name` 为主的结构升级为 `primary_intent`、`motion_style`、`airframe_profile`、`risk_vector`、`intent_scores`、`stage_plan`、`hard_constraint_report` 等结构化语义数据。
- 引入语义覆盖分桶与最近邻去重，替代当前仅按配额和随机采样扩展样本的方式。
- 将现有 `hover/loiter` 的站点风险语义要求并入统一生成器能力，作为全量重构的一部分落地，而不是继续作为独立的局部例外。

## Capabilities

### New Capabilities
- `station-risk-intent-generation`: 定义四类顶层意图、二级行为风格、六维风险语义向量、意图评分与接受判定，以及基于语义区域采样的生成流程。
- `airframe-constrained-trajectory-rollout`: 定义机型档案、阶段指令语法、按机型切换的动力学 rollout、在线约束、离线硬约束校验和失败修复策略。
- `trajectory-semantic-metadata-and-diversity`: 定义新 metadata/export 契约、样本级语义说明、覆盖控制与重复过滤要求。

### Modified Capabilities

无。当前 `openspec/specs/` 下没有已生效 capability，本次以新增 capability 的方式落地完整重构契约。

## Impact

- 核心实现将从 `src/intent2trajectory/generator.py` 拆分为生成、语义、机型、阶段、动力学、校验、导出等模块。
- 受影响配置包括 `configs/dataset_config.json` 以及新增的 `airframes`、`intent_regions`、`style_library` 等配置文件。
- 受影响测试包括 `tests/test_generator.py` 和导出相关测试；现有围绕旧 intent/variant 名称的夹具需要同步迁移。
- 这是一次 schema 级变更：生成样本标签、metadata 字段、配置结构和内部模块边界都会调整，旧数据集和依赖旧标签的下游流程需要评估迁移。
