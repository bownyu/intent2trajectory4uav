## 1. 配置与领域模型

- [x] 1.1 新增 `AirframeProfile`、`SemanticTarget`、`StageSpec`、`Trajectory`、`StationMetrics`、`RiskVector`、`IntentScores`、`ValidationResult` 等核心数据结构
- [x] 1.2 将 `configs/dataset_config.json` 重构为入口配置，并新增 `airframes.json`、`intent_regions.json`、`style_library.json` 等能力配置文件
- [x] 1.3 实现新配置加载与校验逻辑，支持读取机型、语义区域、风格模板和导出配置
- [x] 1.4 建立旧 `straight_penetration` / `non_straight_penetration` / `variant` 到新 `attack` / `motion_style` 体系的迁移映射与错误提示

## 2. 站点语义与意图评分

- [x] 2.1 提取 `semantics/station_metrics.py`，统一计算相对站点距离、方位、径向/切向速度、对齐度等基础指标
- [x] 2.2 实现 `semantics/risk_vector.py`，按配置计算六维 `risk_vector`
- [x] 2.3 实现 `semantics/intent_scoring.py`，输出四类 intent 连续评分、阈值判定和 ambiguity margin
- [x] 2.4 为 `attack`、`retreat`、`hover`、`loiter` 建立可配置的语义区域采样逻辑，并增加对应单元测试

## 3. 机型与阶段模板

- [x] 3.1 提取 `airframes/profiles.py` 与 `airframes/capability_matrix.py`，实现机型采样与 `allowed_styles` 约束
- [x] 3.2 提取 `stages/primitives.py`、`stages/envelopes.py`、`stages/yaw_modes.py`，实现统一的阶段命令构件
- [x] 3.3 为 `attack` 风格实现阶段模板，覆盖 `direct_commit`、`weave_commit`、`climb_dive_commit`、`turn_dive_commit`、`zigzag_commit`、`probe_recommit`
- [x] 3.4 为 `retreat`、`hover`、`loiter` 风格实现阶段模板，并覆盖固定翼 `corridor_hold`、`pseudo_hover_racetrack`、`racetrack_loiter` 等机型相关风格

## 4. 动力学 rollout 与验证

- [x] 4.1 实现 `dynamics/velocity_tracking.py` 与 `dynamics/course_speed.py` 两类动力学模型
- [x] 4.2 实现 `dynamics/rollout.py`，根据机型家族和飞行模式选择 rollout 模型并执行在线约束 clamp
- [x] 4.3 实现 `validators/hard_constraints.py`，覆盖速度、加速度、jerk、偏航率、转弯率、最小转弯半径、空间边界和时间连续性检查
- [x] 4.4 实现 `validators/semantic_validator.py`，串联硬约束、风险向量、intent 评分、阈值判定与模糊性排斥
- [x] 4.5 实现一次轻量修复流程，并在修复失败后执行重采样

## 5. 生成编排、导出与多样性

- [x] 5.1 重写 `src/intent2trajectory/generator.py` 为编排层，串联语义目标采样、机型选择、风格选择、阶段计划、rollout、验证与重采样
- [x] 5.2 实现 `validators/diversity_filter.py`，包含语义覆盖分桶和同桶最近邻去重
- [x] 5.3 实现 `exporters/origin_csv.py`、`exporters/metadata_csv.py`、`exporters/meta_json.py`、`exporters/threat_csv.py`，导出新 metadata 契约与样本级富信息文件
- [x] 5.4 更新失败日志与运行摘要，区分硬约束失败、语义失败和多样性重复失败

## 6. 测试、迁移与文档

- [x] 6.1 重构 `tests/test_generator.py`，将旧 intent/variant 断言迁移为 `primary_intent`、`motion_style`、`risk_vector`、`intent_scores` 与 `stage_plan` 断言
- [x] 6.2 为固定翼、多旋翼和 VTOL 分别增加 rollout/validator 回归测试，验证机型约束与允许风格生效
- [x] 6.3 为 metadata/export 和 diversity filter 增加回归测试，验证 `sample_meta`、失败日志和最近邻去重逻辑
- [x] 6.4 更新 README、配置说明和迁移文档，明确新标签体系、配置结构、导出字段和与旧实现的差异

