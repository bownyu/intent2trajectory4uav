## 为什么（Why）

当前的 `hover` 和 `loiter` 意图主要按照轨迹几何形态来定义和校验，这与项目的真实目标不一致。项目真正要解决的是基于专家规则的、相对站点的风险语义意图识别，尤其是在下游模型还会同时使用相对原点距离及其统计量的前提下，几何优先的定义已经偏离核心需求。

现在必须推进这次改动，因为当前 `loiter` 已经明显过度依赖轨道形状，而 `hover` 与 `loiter` 也无法在站点视角下形成清晰边界。如果继续沿着几何变体扩展，只会进一步放大语义漂移，而不会提高训练数据对真实意图的表达质量。

## 变更内容（What Changes）

- 将 `hover` 重定义为相对站点的“监视型悬停”，不再把它视为一种小尺度几何保持动作。
- 将 `loiter` 重定义为相对站点的“侦察徘徊”，不再把它视为一组绕飞形状变体。
- 为 Phase 1 定义一套共享的站点视角指标词汇，包括距离趋势、方位变化、径向运动、切向运动和驻留行为。
- 将 Phase 1 中 `hover` 和 `loiter` 的校验目标从几何形态改为站点视角下的风险语义行为。
- 在 Phase 1 中保持现有顶层意图标签不变，避免同时引入不必要的下游接口变动。
- 移除“`loiter` 必须通过圆形、椭圆、8 字形或偏移圆等几何变体来表达语义”的要求。
- 将 `straight_penetration`、`non_straight_penetration` 和 `retreat` 的语义迁移延后到后续阶段。

## 能力（Capabilities）

### 新增能力（New Capabilities）
- `station-risk-hover-loiter`：定义 Phase 1 中 `hover` 和 `loiter` 的站点相对风险语义，以及相应的配置约束、校验要求、任务拆分、测试项与验收标准。

### 修改能力（Modified Capabilities）

无。

## 影响（Impact）

- 受影响的核心代码主要是 `src/intent2trajectory/generator.py` 中的意图生成与校验流程。
- 受影响的配置主要是 `configs/dataset_config.json`，尤其是 `intent_profiles.hover` 与 `intent_profiles.loiter`。
- 受影响的测试主要是 `tests/test_generator.py`，必要时还需要同步更新导出与配置相关的测试夹具。
- 受影响的文档包括主 README 以及当前的意图规则、配置规则说明文档。
- 一旦 Phase 1 实现完成，现有已生成数据集及其 metadata 在语义上将变得过时，但数据重生成不属于本次 proposal 的范围。
