## ADDED Requirements

### Requirement: 站点视角指标定义 hover 与 loiter 的语义
系统 SHALL 在 Phase 1 中通过相对站点的指标来定义 `hover` 与 `loiter` 的语义，而不是通过轨迹几何形态来定义。用于表达语义的指标词汇 SHALL 包含 `range_mean`、`range_std`、`range_slope`、`min_range`、`bearing_cumulative_change`、`radial_speed_mean`、`radial_speed_std`、`tangential_speed_mean`、`tangential_dominance_ratio` 和 `dwell_ratio_in_band`。

#### Scenario: 校验使用站点视角指标
- **WHEN** 系统在 Phase 1 中校验生成的 `hover` 或 `loiter` 样本
- **THEN** 系统基于相对站点的语义指标进行判断，而不是依赖轨道形状或其他几何子型检查

### Requirement: Hover 表示监视型悬停行为
系统 SHALL 将 `hover` 视为相对站点的监视型悬停行为。一个有效的 `hover` 样本 MUST 维持稳定的相对站点距离、较弱的方位演化、较低的平移动作和足够长的局部驻留，同时不得表现出持续逼近、持续撤离或侦察式绕站活动。

#### Scenario: Hover 在站点视角下保持稳定
- **WHEN** 系统评估一个生成的 `hover` 样本
- **THEN** 该样本 MUST 满足 Phase 1 关于低距离漂移、低方位变化和低切向运动的初始阈值集合

#### Scenario: Hover 在表现出 loiter 行为时被拒绝
- **WHEN** 一个 `hover` 样本表现出持续角度扫掠或以切向运动为主的绕站活动
- **THEN** 系统 MUST 拒绝该样本，并判定其不满足 Phase 1 的 `hover` 语义

### Requirement: Loiter 表示站点周边的侦察徘徊
系统 SHALL 将 `loiter` 视为相对站点的侦察徘徊。一个有效的 `loiter` 样本 MUST 在配置的侦察距离带内停留足够长时间以体现持续存在，MUST 累积出明确的方位变化，MUST 呈现切向运动强于径向运动的特征，并且 MUST 避免形成持续突防趋势。

#### Scenario: Loiter 表现出侦察式存在
- **WHEN** 系统评估一个生成的 `loiter` 样本
- **THEN** 该样本 MUST 满足 Phase 1 关于方位变化、切向占优、距离趋势稳定以及在侦察距离带内驻留的初始阈值集合

#### Scenario: Loiter 在表现出 penetration 行为时被拒绝
- **WHEN** 一个 `loiter` 样本对站点呈现持续向内的距离变化趋势
- **THEN** 系统 MUST 拒绝该样本，并判定其不满足 Phase 1 的 `loiter` 语义

### Requirement: Phase 1 区分初始阈值指标与仅方向性指标
系统 SHALL 在 Phase 1 中显式区分两类指标：一类需要给出初始数值阈值，另一类只定义方向约束而不固定数值。

Phase 1 需要给出初始阈值的指标 MUST 包含：
- `hover.abs(range_slope)`
- `hover.range_std`
- `hover.bearing_cumulative_change`
- `hover.tangential_speed_mean`
- `loiter.abs(range_slope)`
- `loiter.bearing_cumulative_change`
- `loiter.tangential_dominance_ratio`
- `loiter.dwell_ratio_in_band`

Phase 1 只定义方向、不固定数值的控制项 MUST 包含：
- `hover` 的精确悬停距离带
- `loiter` 的精确侦察距离带
- `loiter` 的精确向内试探幅度
- 两类意图的高度微变化策略
- 在简化后如仍保留，`loiter` 的内部运动风格定义方式

#### Scenario: 有阈值的指标可直接测试
- **WHEN** Phase 1 测试对 `hover` 或 `loiter` 行为进行断言
- **THEN** 测试 MUST 使用有阈值的指标集合作为通过/失败标准

#### Scenario: 方向性指标保持可配置
- **WHEN** Phase 1 规划中定义了距离带或试探幅度
- **THEN** 系统 MUST 将其视为配置校准输入，而不是 capability 级别的固定常量

### Requirement: Loiter 语义独立于几何子型标签
系统 SHALL NOT 在 Phase 1 中要求 `loiter` 必须通过 circle、ellipse、figure-8、offset-orbit 或任何其他几何优先的子型标签来表达语义。

#### Scenario: 仅有几何形状不能证明 loiter 成立
- **WHEN** 一个样本呈现轨道式形状，但不满足相对站点的侦察徘徊语义
- **THEN** 系统 MUST 拒绝该样本，并判定其不是有效的 `loiter`

#### Scenario: 符合语义的 loiter 不依赖命名轨道子型
- **WHEN** 一个样本满足 Phase 1 的侦察徘徊语义，但不匹配任何旧的几何子型
- **THEN** 系统 MUST 允许该样本被认定为有效的 `loiter`

### Requirement: Phase 1 保持现有顶层标签不变
系统 SHALL 在 Phase 1 中保持 `hover` 和 `loiter` 这两个顶层意图标签不变，从而避免语义迁移立即触发下游标签迁移。

#### Scenario: 标签在 Phase 1 中保持稳定
- **WHEN** Phase 1 文档为 `hover` 和 `loiter` 定义新的语义
- **THEN** 文档 MUST 保留现有顶层标签名称，同时更新其背后的语义契约
