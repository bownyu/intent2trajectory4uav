# 轨迹生成器迁移说明

## 新标签体系

顶层标签统一为：
- `attack`
- `retreat`
- `hover`
- `loiter`

旧 `variant_name` 已被 `motion_style` 取代，用来表达同一意图下的行为风格。

## 配置迁移

旧实现把大部分规则都放在 `configs/dataset_config.json` 的 `intent_profiles` 中。

新实现拆成四部分：
- `configs/dataset_config.json`：入口、配额、输出、全局约束
- `configs/airframes.json`：机型能力
- `configs/intent_regions.json`：风险语义与阈值
- `configs/style_library.json`：阶段模板与风格库

## 核心流程迁移

旧流程：
`intent -> geometric template -> csv`

新流程：
`intent -> semantic target -> airframe -> motion_style -> stage_plan -> rollout -> validate -> diversity filter -> export`

## 旧标签映射

- `straight_penetration` -> `attack.direct_commit`
- `non_straight_penetration.weave_approach` -> `attack.weave_commit`
- `non_straight_penetration.climb_then_dive` -> `attack.climb_dive_commit`
- `non_straight_penetration.turn_then_dive` -> `attack.turn_dive_commit`
- `non_straight_penetration.zigzag_dive` -> `attack.zigzag_commit`
- `hover.standoff_hover` -> `hover.drift_hold`
- `loiter.surveillance_loiter` -> `loiter.circle_loiter`
- `retreat.direct_escape` -> `retreat.direct_breakaway`
- `retreat.arc_escape` -> `retreat.arc_breakaway`
- `retreat.zigzag_escape` -> `retreat.zigzag_breakaway`
- `retreat.climb_escape` -> `retreat.climb_breakaway`

## 输出迁移

旧 metadata 关注 `intent` 与 `variant_name`。

新 metadata 重点关注：
- `primary_intent`
- `motion_style`
- `airframe_name`
- `airframe_family`
- `flight_mode_sequence`
- `semantic_target`
- `risk_vector`
- `intent_scores`
- `stage_plan`
- `hard_constraint_report`
- `repair_count`
- `ambiguity_margin`

## 兼容说明

`generate_sample(intent, seed, profile, variant_name=...)` 仍保留旧调用入口，但会把旧 `intent` / `variant_name` 映射到新标签体系。新的调用应优先使用四类顶层意图和新的 `motion_style` 名称。
