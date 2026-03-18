# intent2trajectory

一个面向站点相对风险语义的无人机意图轨迹生成器。当前生成器不再围绕几何模板命名，而是围绕 `attack`、`retreat`、`hover`、`loiter` 四类风险语义意图生成、验证和导出样本。

## 当前能力

- 统一的四类顶层意图：`attack`、`retreat`、`hover`、`loiter`
- 同一意图下的 `motion_style` 风格采样
- `AirframeProfile` 约束下的阶段计划与 rollout
- 站点相对指标、六维 `risk_vector` 和 intent 连续评分
- 硬约束检查、轻量修复、重采样
- 多样性过滤和失败原因分类
- `origin` / `threat` / `meta` 三类导出

## 配置结构

入口配置：`configs/dataset_config.json`

外部能力配置：
- `configs/airframes.json`：机型档案、能力边界、允许风格
- `configs/intent_regions.json`：风险带、语义区域、评分阈值
- `configs/style_library.json`：各意图的风格模板与阶段定义

## 主要输出

- `output_root/origin/<intent>/*.csv`：逐时刻轨迹明细
- `output_root/threat/<intent>/*.csv`：1 Hz 威胁导出
- `output_root/meta/<intent>/*.json`：样本级富语义 metadata
- `output_root/metadata.csv`：数据集级摘要
- `output_root/failures.csv`：失败样本摘要（若存在）

样本 metadata 重点字段：
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

## 运行方式

生成数据集：
```powershell
python scripts/export_dual_format.py --config configs/dataset_config.json --formats origin threat --output-root dataset_workspace
```

直接调用核心模块：
```powershell
python -c "import sys; sys.path.insert(0, 'src'); from intent2trajectory.generator import generate_dataset; print(generate_dataset('configs/dataset_config.json'))"
```

运行核心测试：
```powershell
pytest tests/test_generator.py tests/test_export_dual_format_script.py -q --basetemp=tests/.tmp_pytest
```

## Python 接口

- `load_config(config_path)`：读取入口配置并展开外部能力配置
- `generate_sample(intent, seed, profile, variant_name=None, airframe_name=None)`：生成单个样本；`variant_name` 兼容旧接口，但内部会映射到新 `motion_style`
- `validate_sample(sample, profile)`：执行硬约束、风险向量和 intent 判定
- `generate_dataset(config_path)`：按配额批量生成数据集

## 旧标签迁移

旧标签已迁移到新体系：
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

更完整的迁移说明见 `docs/trajectory-generator-migration.md`。
