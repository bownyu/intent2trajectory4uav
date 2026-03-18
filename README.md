# intent2trajectory

一个面向站点相对风险语义的无人机意图轨迹生成器。当前生成器围绕 `attack`、`retreat`、`hover`、`loiter` 四类风险语义意图工作，并在 `attack` 内部进一步引入 `start_context`、`pressure_profile`、`maneuver_profile` 三层语义，以避免样本继续塌缩到单一的“先逼近再终端冲刺”模式。

## 当前能力

- 统一的四类顶层意图：`attack`、`retreat`、`hover`、`loiter`
- `attack` 的三层内部结构：`start_context`、`pressure_profile`、`maneuver_profile`
- `motion_style` 仍保留为导出字段，但 `attack` 的 stage plan 已由 profile 组合驱动，而不是单一 style 直接驱动
- `AirframeProfile` 约束下的阶段计划、hybrid dynamics 和 yaw 语义
- 站点相对指标、六维 `risk_vector`、intent 连续评分与 attack 后验分型
- 硬约束检查、轻量修复、重采样、分布控制与去重
- `origin` / `threat` / `meta` 三类导出

## 配置结构

入口配置：`configs/dataset_config.json`

外部能力配置：
- `configs/airframes.json`：机型档案、显式启用开关、能力边界、允许风格，以及 `attack_capability`
- `configs/intent_regions.json`：风险带、语义区域、评分阈值
- `configs/style_library.json`：各意图的风格模板与阶段定义；`attack` 额外包含 profile 组合定义和 legacy style 映射

`attack_capability` 当前至少定义：
- `allowed_start_contexts`
- `allowed_pressure_profiles`
- `allowed_maneuvers`
- `attack_dynamics_policy`

`attack_diversity` 当前至少定义：
- `profile_quota`
- `profile_compatibility`
- `distribution`：`early_commit_ratio_max`、`low_terminal_spike_max`、`high_terminal_spike_min` 等边界
- `posterior_metrics`：`commit_window_sec`、`immediate_duration_max`、`staged_duration_min` 等分型参数

机型配置职责：`enabled` 控制是否参与生成，`selection_weight` 控制启用候选中的采样概率，`allowed_styles` 控制各 intent 下允许的输出 `motion_style`。`enabled: false` 会让该机型既不会被随机采样，也不能被显式 `airframe_name` 选中。

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
- `start_context`
- `pressure_profile_target`
- `pressure_profile_realized`
- `maneuver_profile`
- `dynamics_model`
- `yaw_mode_sequence`
- `commit_onset_ratio`
- `terminal_spike_ratio`
- `pressure_persistence`
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

生成小样本 attack 分布报告：
```powershell
python scripts/report_attack_distribution.py --config configs/dataset_config.json --airframe quad_small --count 20
```

## Python 接口

- `load_config(config_path)`：读取入口配置并展开外部能力配置
- `generate_sample(intent, seed, profile, variant_name=None, airframe_name=None)`：生成单个样本；`variant_name` 兼容旧接口，但对 `attack` 会先映射到目标 profile 再生成
- `validate_sample(sample, profile)`：执行硬约束、风险向量、intent 判定与 attack realized-profile 判定
- `generate_dataset(config_path)`：按配额批量生成数据集

## 旧标签迁移

旧标签已迁移到新体系：
- `straight_penetration` -> `attack.staged_commit_direct`
- `non_straight_penetration.weave_approach` -> `attack.staged_commit_weave`
- `non_straight_penetration.climb_then_dive` -> `attack.staged_commit_climb_dive`
- `non_straight_penetration.turn_then_dive` -> `attack.staged_commit_dogleg`
- `non_straight_penetration.zigzag_dive` -> `attack.staged_commit_zigzag`
- `hover.standoff_hover` -> `hover.drift_hold`
- `loiter.surveillance_loiter` -> `loiter.circle_loiter`
- `retreat.direct_escape` -> `retreat.direct_breakaway`
- `retreat.arc_escape` -> `retreat.arc_breakaway`
- `retreat.zigzag_escape` -> `retreat.zigzag_breakaway`
- `retreat.climb_escape` -> `retreat.climb_breakaway`

更完整的迁移说明见 `docs/trajectory-generator-migration.md`。
