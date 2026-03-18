## ADDED Requirements

### Requirement: 导出元数据必须携带完整语义与校验证据
系统 SHALL 为每个被接受的样本导出结构化 metadata。该 metadata MUST 至少包含 `primary_intent`、`motion_style`、`airframe_name`、`airframe_family`、`flight_mode_sequence`、`active_band_name`、`risk_bands_json`、`semantic_target_json`、`risk_vector_json`、`intent_scores_json`、`stage_plan_json`、`repair_count`、`ambiguity_margin` 和 `hard_constraint_report`。系统 MUST 以样本级独立文件或等价的稳定载体承载富语义信息，并且上述字段 MUST 可被稳定读取。

#### Scenario: 样本导出包含完整语义元数据
- **WHEN** 系统保存一个通过验证的样本
- **THEN** 系统 MUST 同时保存该样本的语义 metadata
- **AND** metadata MUST 包含意图、风格、机型、风险向量、评分、阶段计划和硬约束报告字段

### Requirement: 样本级富信息导出必须可独立审计
系统 SHALL 为每个被接受的样本提供样本级富信息导出，至少包含 `sample_id`、`primary_intent`、`motion_style`、`airframe`、`risk_vector`、`intent_scores` 和 `stage_plan`。该导出 MUST 支持独立于轨迹点 CSV 进行审计与抽样检查。

#### Scenario: 审计者无需解析整段轨迹即可查看样本语义
- **WHEN** 审计流程读取单个样本的富信息导出
- **THEN** 审计者 MUST 能直接看到该样本的意图、风格、机型、风险向量、intent 评分和阶段计划
- **AND** 审计流程 MUST 不依赖重新扫描全量轨迹点来恢复这些语义字段

### Requirement: 多样性控制必须基于语义覆盖分桶
系统 SHALL 为每个候选样本计算覆盖特征向量，并 MUST 至少包含 `duration_norm`、`start_r_norm`、`min_r_norm`、`mean_speed_norm`、`max_speed_norm`、`altitude_excursion_norm`、`path_ratio`、`encircle_cycles_norm`、六维 `risk_vector`、`abort_count_norm`、`airframe_id` 和 `style_id`。系统 MUST 至少按 `min_range`、`mean_speed_norm`、`uncertain_score`、`duration` 和 `encircle_cycles` 做配额分桶，以避免样本集中在少数参数区间。

#### Scenario: 候选样本进入语义覆盖控制
- **WHEN** 一个候选样本通过 intent 验证
- **THEN** 系统 MUST 计算该样本的覆盖特征向量
- **AND** 系统 MUST 使用预定义的语义覆盖分桶判断该样本是否填补目标配额

### Requirement: 重复过滤必须在同语义桶内使用最近邻距离
系统 SHALL 在相同 `primary_intent + airframe + motion_style` 桶内执行最近邻距离过滤。若新样本与已有样本在覆盖特征向量空间中的距离低于配置阈值，系统 MUST 拒绝该样本为重复样本；若距离满足阈值且其他验证步骤通过，系统 MUST 允许该样本进入数据集。

#### Scenario: 近重复样本被拒绝
- **WHEN** 一个候选样本与同 intent、同机型、同风格桶内的已有样本距离低于最近邻阈值
- **THEN** 系统 MUST 拒绝该候选样本并记录为多样性重复

### Requirement: 失败日志必须区分语义失败与多样性失败
系统 SHALL 在失败记录中区分至少三类失败原因：硬约束失败、语义判定失败和多样性重复失败。若记录候选样本 metadata，系统 MUST 保留导致失败的主要评分、margin 或硬约束摘要，以支持后续调参。

#### Scenario: 失败日志保留可追踪原因
- **WHEN** 一个候选样本在验证或多样性过滤阶段失败
- **THEN** 系统 MUST 记录其失败类别和核心原因
- **AND** 若该样本已经计算出风险向量或 intent 评分，失败日志 MUST 保留相应摘要以支持排查

