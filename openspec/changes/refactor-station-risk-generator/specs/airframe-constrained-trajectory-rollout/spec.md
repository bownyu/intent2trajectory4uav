## ADDED Requirements

### Requirement: 机型档案定义生成与校验的主导约束
系统 SHALL 为每个可用机型提供 `AirframeProfile` 配置。每个机型档案 MUST 定义机型家族、悬停能力、速度范围、纵向/横向加速度、爬升与下降率、jerk、偏航率、转弯率、最小转弯半径、控制时间常数、偏好高度、允许风格以及 validator override。系统 MUST 使用这些能力约束风格选择、阶段构建、rollout 与校验流程。

#### Scenario: 风格选择受机型能力约束
- **WHEN** 系统为某个 intent 采样 `airframe_profile`
- **THEN** 系统 MUST 只允许选择该机型 `allowed_styles` 中声明的 `motion_style`
- **AND** 后续 rollout 与 validator MUST 读取同一份机型能力参数

### Requirement: 阶段计划使用相对站点速度指令语法
系统 SHALL 使用 `StageSpec` 作为统一的阶段计划结构。每个阶段 MUST 至少定义 `duration_range`、`terminate_rule`、`v_r_cmd`、`v_theta_cmd`、`v_z_cmd`、`yaw_mode`、`noise_profile` 和 `semantic_effects`。模板模块 MUST 通过组合阶段计划表达行为语义，而不是直接生成完整的几何轨迹点序列。

#### Scenario: 模板产出阶段计划而非几何模板
- **WHEN** 系统根据 `primary_intent` 和 `motion_style` 生成样本计划
- **THEN** 系统 MUST 先输出一个由多个 `StageSpec` 组成的 `stage_plan`
- **AND** 每个阶段 MUST 以径向、切向、垂向速度命令与 `yaw_mode` 定义控制意图

### Requirement: rollout 根据机型家族和飞行模式选择动力学模型
系统 SHALL 至少支持两类 rollout 模型：`VelocityTrackingModel` 与 `CourseSpeedModel`。多旋翼和 VTOL 悬停/低速模式 MUST 使用 `VelocityTrackingModel`；固定翼和 VTOL 巡航模式 MUST 使用 `CourseSpeedModel`。rollout 结果 MUST 满足对应机型的速度、航向与垂向状态更新约束。

#### Scenario: 固定翼使用航向-速度模型
- **WHEN** 系统对固定翼或 VTOL 巡航阶段执行 rollout
- **THEN** 系统 MUST 使用 `CourseSpeedModel` 更新 speed、course 和垂向速度
- **AND** 系统 MUST 强制满足最小速度、转弯率和最小转弯半径约束

#### Scenario: 多旋翼使用速度跟踪模型
- **WHEN** 系统对多旋翼或 VTOL 悬停阶段执行 rollout
- **THEN** 系统 MUST 使用 `VelocityTrackingModel` 跟踪期望速度和偏航
- **AND** 系统 MUST 强制满足加速度、速度和偏航率约束

### Requirement: 系统执行在线约束与离线硬约束双层检查
系统 SHALL 在 rollout 过程中执行在线约束，包括速度 clamp、加速度 clamp、偏航率 clamp、爬升/下降率 clamp，以及固定翼最小速度 clamp。系统 MUST 在 rollout 完成后执行离线硬约束验证，至少覆盖空间边界、最大速度、最小速度、纵向加速度、横向加速度、jerk、爬升率、下降率、最大偏航率、最大转弯率、最小转弯半径以及时间连续性。

#### Scenario: 候选轨迹通过完整硬约束检查
- **WHEN** 系统完成一次候选轨迹 rollout
- **THEN** 系统 MUST 先后执行在线约束与离线硬约束检查
- **AND** 仅当所有必需硬约束通过时，该轨迹才可进入语义评分阶段

### Requirement: 失败样本先尝试轻量修复再重采样
当候选样本因硬约束或语义阈值失败时，系统 SHALL 先尝试一次轻量修复。轻量修复 MUST 仅限于拉长阶段持续时间、降低摆动振幅、对 `v_cmd` 低通平滑或降低末段冲击速度；若修复后仍失败，系统 MUST 放弃该候选并重新采样。

#### Scenario: 候选样本修复失败后重采样
- **WHEN** 一个候选样本首次验证失败
- **THEN** 系统 MUST 先执行一次轻量修复并重新验证
- **AND** 若修复后的样本仍未通过验证，系统 MUST 记录失败并重新采样新的候选样本
