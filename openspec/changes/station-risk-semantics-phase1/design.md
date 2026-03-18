## 背景（Context）

项目的目标是在专家规则定义下，识别相对站点的风险语义意图。进入 Phase 1 后，最明显的语义错位集中在 `hover` 和 `loiter`：它们目前仍然主要通过几何运动模式生成和校验，而下游学习任务真正关心的是相对站点的距离、距离变化、方位变化以及相关统计量。

因此，`hover` 和 `loiter` 必须改由站点视角行为来定义。`hover` 应表示稳定的远距监视，具有较弱的平移动作；`loiter` 应表示带有明显方位演化和切向运动占优的侦察性徘徊，但不应呈现持续逼近站点的趋势。

这次改动属于跨模块变更，因为它同时影响配置语义、生成器行为、校验规则、测试和当前有效文档。为了控制第一次落地范围，Phase 1 明确不包含 penetration 和 retreat 的实现迁移。

## 目标 / 非目标（Goals / Non-Goals）

**目标：**
- 将 Phase 1 中的 `hover` 和 `loiter` 明确定义为相对站点的风险语义，而不是几何形态。
- 引入一套共享的站点视角指标词汇，并让生成、校验、测试和文档使用同一套语义坐标系。
- 移除“`loiter` 必须通过圆形、椭圆、8 字形或偏移圆等几何变体表达”的要求。
- 在 Phase 1 中保持现有顶层标签和导出接口稳定。
- 将实现任务、验收标准和测试项分开组织，降低后续编码阶段的歧义。

**非目标：**
- 本阶段不重写 `straight_penetration`、`non_straight_penetration` 或 `retreat`。
- 本阶段不改造生成器之外的下游模型结构或特征工程。
- 本阶段不试图一次性给所有指标都定出最终生产阈值；只对必须可测试的指标给出初始阈值。
- 在 proposal 阶段不处理现有全量数据集的重生成或重新标定。

## 设计决策（Decisions）

### 决策：使用共享的站点视角指标作为语义契约
Phase 1 将通过相对站点原点推导出的指标来定义 `hover` 和 `loiter`，而不是使用轨迹形状描述符。

选定指标：
- `range_mean`
- `range_std`
- `range_slope`
- `min_range`
- `bearing_cumulative_change`
- `radial_speed_mean`
- `radial_speed_std`
- `tangential_speed_mean`
- `tangential_dominance_ratio`
- `dwell_ratio_in_band`

理由：
- 这些指标与专家对站点相对威胁态势的理解更一致。
- 这套词汇后续可以直接复用到 penetration 和 retreat，而不需要再次定义新的语义坐标系。

考虑过的替代方案：
- 保留现有几何优先的校验方式，只在 metadata 中追加风险特征。
- 否决原因：这会保留当前语义错位，让生成逻辑继续朝着“形状好看”而不是“语义正确”的方向偏移。

### 决策：将 `hover` 重定义为监视型悬停
`hover` 在 Phase 1 中表示持续时间足够、平移动作较弱、方位变化较弱的相对站点保持行为。

Phase 1 初始阈值候选：
- `abs(range_slope) <= 0.5 m/s`
- `range_std <= 40 m`
- `bearing_cumulative_change <= 0.35 rad`
- `tangential_speed_mean <= 2.0 m/s`

Phase 1 中仅定义方向、不固定数值的内容：
- 期望的悬停距离带
- 高度微变化策略
- 不同场景下的观测持续时间调优

理由：
- `hover` 必须能通过弱平移、弱角度扫掠与 `loiter` 明确区分。

考虑过的替代方案：
- 保留微轨道式 `hover` 子型。
- 否决原因：在 Phase 1 中，这会削弱 `hover` 与 `loiter` 之间本应明确的语义边界。

### 决策：将 `loiter` 重定义为侦察徘徊
`loiter` 在 Phase 1 中表示处于侦察距离带内的持续存在，具有显著方位变化、切向运动占优，但不表现为持续突防。

Phase 1 初始阈值候选：
- `abs(range_slope) <= 1.0 m/s`
- `bearing_cumulative_change >= 4.0 rad`
- `tangential_dominance_ratio >= 1.5`
- `dwell_ratio_in_band >= 0.7`
- `min_range` 不得体现持续 penetration 轨迹特征

Phase 1 中仅定义方向、不固定数值的内容：
- 侦察距离带的具体半径范围
- 短时试探性靠近的允许幅度
- 简化后若仍保留内部运动风格，其模板定义方式

理由：
- `loiter` 应表达的是站点周边的侦察压力，而不是某一种绕飞几何族。

考虑过的替代方案：
- 保留 circle / ellipse / figure-8 作为 `loiter` 的一等子型。
- 否决原因：这些只是实现手段，不是目标语义标签本身。

### 决策：在 Phase 1 中保持对外标签稳定
Phase 1 保持 `hover` 和 `loiter` 作为顶层对外标签。

理由：
- 这样可以把变更重点集中在语义契约和校验逻辑上，避免同时引入下游 schema 迁移。

考虑过的替代方案：
- 立即重命名为 `standoff_hover` 和 `surveillance_loiter`。
- 否决原因：在语义与阈值仍处于首次校准阶段时，这会带来不必要的接口抖动。

### 决策：明确分离任务、验收标准与测试项
本次规划文档将显式拆分：
- 实现任务
- 验收标准
- 测试项

理由：
- 这是用户的明确要求，也能减少 Phase 1 进入实现阶段时的执行歧义。

## 风险 / 取舍（Risks / Trade-offs）

- [风险] 初始阈值可能过紧或过松 -> 缓解：将一部分指标标记为“仅定义方向”，并把数值视为首轮校准点而非最终事实。
- [风险] 如果只改 `hover` 不改 `loiter`，两者边界仍会不稳定 -> 缓解：Phase 1 将两者作为耦合对一起处理。
- [风险] 现有测试偏向几何结构 -> 缓解：在实现完成前，将形状断言替换为站点视角语义断言。
- [风险] 现有数据集在语义上变旧 -> 缓解：把数据重生成放到实现和阈值校准之后。

## 迁移计划（Migration Plan）

1. 在 proposal、design 和 specs 中冻结 Phase 1 的语义契约。
2. 实现共享的站点视角指标提取，以及 `hover` / `loiter` 的语义校验。
3. 更新 `hover` / `loiter` 的生成配置语义与测试。
4. 审查生成样本的统计分布，再决定是否需要进一步调阈值。
5. 在 Phase 2 中复用同一套指标词汇继续推进 penetration 的语义迁移。

## 开放问题（Open Questions）

- 如果位置保持稳定，`hover` 是否允许有意识的扫描式偏航行为？
- `loiter` 在 Phase 1 中是否允许短时向内试探作为一等行为，还是应等到基础侦察徘徊稳定后再引入？
- `dwell_ratio_in_band` 应该基于单一配置距离带，还是基于一组嵌套风险距离带来计算？
