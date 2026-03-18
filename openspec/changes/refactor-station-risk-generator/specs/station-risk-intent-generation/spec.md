## ADDED Requirements

### Requirement: 系统使用统一的风险语义意图分类
系统 SHALL 使用 `attack`、`retreat`、`hover`、`loiter` 作为唯一的顶层 `primary_intent` 分类，并 SHALL 使用 `motion_style` 表达同一意图下的二级行为风格。每个被接受的样本 MUST 至少携带 `primary_intent`、`motion_style`、`airframe_profile`、`risk_vector` 和 `stage_plan` 五层语义描述。

#### Scenario: 生成样本暴露规范化标签
- **WHEN** 系统生成并接受一个样本
- **THEN** 该样本 MUST 使用四类顶层 intent 之一作为 `primary_intent`
- **AND** 该样本 MUST 包含对应的 `motion_style`、`airframe_profile`、`risk_vector` 和 `stage_plan`

### Requirement: 所有候选样本都映射到六维风险语义向量
系统 SHALL 对每个候选样本计算相对站点的站点指标与六维 `risk_vector`，其维度 MUST 包含 `close_score`、`dwell_score`、`encircle_score`、`point_score`、`uncertain_score` 和 `disengage_score`，并且每个维度 MUST 归一化到 `[0, 1]`。`point_score` MUST 同时考虑速度方向相对站点的对齐度与机体朝向相对站点的对齐度。

#### Scenario: 候选样本生成完整风险向量
- **WHEN** 系统完成一个候选轨迹的 rollout
- **THEN** 系统 MUST 计算六个风险维度的数值
- **AND** 每个维度 MUST 在 `[0, 1]` 范围内
- **AND** `point_score` MUST 由 course 对齐度与 yaw 对齐度共同决定

### Requirement: 生成流程先采样语义目标区域再选择风格
系统 SHALL 在轨迹生成前先按目标意图采样 `semantic_target`，该目标 MUST 来自可配置的 intent 区域定义；系统 MUST 先根据 `semantic_target` 与 `airframe_profile` 选择允许的 `motion_style`，再构建 `stage_plan`，而不是先固定几何模板再事后校验。

#### Scenario: 语义目标驱动风格选择
- **WHEN** 系统开始生成一个目标 intent 的样本
- **THEN** 系统 MUST 先采样该 intent 的语义目标区域
- **AND** 系统 MUST 仅从该 `airframe_profile` 允许的 `motion_style` 集合中选择风格
- **AND** 系统 MUST 使用该语义目标和风格生成 `stage_plan`

### Requirement: 意图接受判定采用连续评分与模糊性排斥
系统 SHALL 为每个候选样本同时计算 `I_attack`、`I_retreat`、`I_hover` 与 `I_loiter` 四个连续评分。系统 MUST 仅在目标意图评分达到配置阈值且与第二高分的差值达到最小 margin 时接受样本；否则 MUST 拒绝该样本为语义模糊样本。

#### Scenario: 目标意图分数足够高时接受样本
- **WHEN** 一个候选样本的目标 intent 评分达到该 intent 的 `score_min`
- **AND** 该评分与第二高 intent 评分的差值达到 `margin_min`
- **THEN** 系统 MUST 接受该样本的 intent 判定

#### Scenario: 模糊样本被拒绝
- **WHEN** 一个候选样本的目标 intent 评分未达到阈值
- **OR** 该评分与第二高 intent 评分的差值低于最小 margin
- **THEN** 系统 MUST 拒绝该样本并记录其为语义模糊或目标未命中

### Requirement: 四类意图以可配置风险区域定义语义边界
系统 SHALL 为 `attack`、`retreat`、`hover`、`loiter` 分别维护可配置的六维语义区域定义，并 MUST 用这些区域同时约束语义目标采样与 validator 接受边界。`attack` MUST 表现为高接近性与高指向性、低脱离性；`retreat` MUST 表现为高脱离性与低接近性；`hover` MUST 表现为高滞留性、低环绕性与低净接近/脱离；`loiter` MUST 表现为高滞留性、高环绕性和切向主导但不得持续转化为 `attack` 或 `retreat`。

#### Scenario: Hover 与 loiter 由语义边界区分
- **WHEN** 系统分别验证 `hover` 与 `loiter` 候选样本
- **THEN** `hover` 样本 MUST 满足高滞留、低环绕、低净接近/脱离的边界
- **AND** `loiter` 样本 MUST 满足高滞留、高环绕和切向主导的边界
- **AND** 两者的接受条件 MUST 不依赖旧几何子型名称
