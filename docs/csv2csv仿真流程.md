## 控制链

`CSV 文件 -> ROS 2 回放节点 -> px4_msgs -> DDS -> Micro XRCE-DDS Agent -> PX4 uxrce_dds_client -> PX4 uORB -> PX4 控制器 -> Gazebo 模型`

PX4 从 v1.14 起通过 uXRCE-DDS 把一部分 uORB 话题直接暴露为 ROS 2 话题；ROS 2 侧发布到 `/fmu/in/...`，PX4 侧订阅后进入控制链。默认桥接话题由 `dds_topics.yaml` 决定。

## 状态回传链

`Gazebo/PX4 状态估计 -> PX4 uORB -> uxrce_dds_client -> DDS -> ROS 2 /fmu/out/... -> 回放节点/QGC/日志系统`

用于你在线监测和离线分析的核心状态源应是 `/fmu/out/vehicle_local_position` 和 ULog。`VehicleLocalPosition` 是 PX4 的本地 NED 融合状态，原点是 EKF2 启动时的机体位置。


## 1.起始点不在原点时，正确的设计

需要保留“相对于世界原点的意图语义”，例如从很远处飞向原点；但 PX4 的本地位置控制和日志并不是世界绝对坐标，而是**以 EKF2 启动点为原点的本地 NED 坐标**。
因此实现是：
1. 从 CSV 读取第一帧绝对起点 `p0=(x0,y0,z0), yaw0`
2. 用 `PX4_GZ_MODEL_POSE` 在 Gazebo 中把机体生成到该轨迹相关的绝对位置
3. 发给 PX4 的轨迹则转换为**相对该起点的本地轨迹**
4. 仿真结束后，再把日志轨迹加回这个偏移，恢复成绝对世界轨迹

也就是：
- 数据语义层保留绝对坐标
- 控制层使用局部 NED
- 输出层再恢复绝对坐标


## 2. 起点在空中的处理策略

很多轨迹第一帧就在空中。这里不用“从原点起飞再飞过去”，也不建议把模型直接瞬间生成在高空后立刻进入正式评估段。

推荐默认策略是：
1. 读取第一帧 `(x0, y0, z0, yaw0)`
2. Gazebo 生成位姿设为**第一帧的绝对 x/y 与期望朝向**
3. z 方向可采用“起始点正下方的安全起飞位”
4. 先做一段**预备段**：起飞、爬升、接近第一帧状态
5. 当机体接近轨迹第一帧后，再把 `time_relative=0` 作为正式评估起点
6. 日志中把预备段和正式段分开保存；评估只统计正式段

Gazebo 提供启动位姿入口，PX4 Offboard 又要求外部控制流先连续建立

## 3. 轨迹预处理必须做什么
为了让 PX4 执行时尽量连续，不出现“每过一个点就减速再加速”，必须在 CSV 回放前做预处理。因为 `TrajectorySetpoint` 要求轨迹本身运动学一致；如果位置和速度不一致、时间轴抖动大、yaw 跳变或折线尖角太多，控制器自然会表现得不连贯。
建议的预处理固定为：
1. **统一时间轴**  
    把输入重采样到固定频率，当前原始csv文件是 10 Hz。
2. **位置-速度一致化**  
    若原始 `vel_*` 与 `pos_*` 导数不一致，优先相信平滑后的 `pos_*`，再由其推导速度；不要直接使用噪声较大的速度列。
3. **yaw unwrap**  
    消除 `-pi / +pi` 跨越导致的突跳。
4. **尖角平滑**  
    对过于尖锐的折线进行样条或分段平滑，避免控制器在转折点急刹。
5. **限幅**  
    对速度、加速度、yaw rate 做物理可实现范围限制，使轨迹与所选模型/参数一致。

结果上，交给 PX4 的不应该是“原始离散点串”，而应该是一条**平滑、固定频率、位置与速度一致的局部 NED 参考轨迹**。这一步是整个系统能否跑得顺的决定性因素。

## 4. ROS 2 回放节点的职责
最终你要写的不是一个“脚本拼接器”，而是一个有状态机的 ROS 2 应用节点。其职责应分成三块。
### A. 轨迹加载与预处理
- 读取 CSV
- 选择 `ref_*` 或回退到基础列
- 重采样、平滑、坐标转换、yaw unwrap、限幅
- 计算本次 run 的起始绝对位姿偏移

### B. Offboard 执行状态机
节点内部建议至少有这几个阶段：
- `LOAD_TRAJECTORY`
- `PREPARE_START`
- `WARMUP`
- `ARM_AND_OFFBOARD`
- `PLAYBACK`
- `HOLD_LAST_SETPOINT`
- `FINISH`

这里 `WARMUP` 是必需的。PX4 要求外部控制器持续发送 `OffboardControlMode` 作为“proof of life”，频率不能低于约 2 Hz，而且必须先持续约 1 秒，PX4 才允许进入 Offboard 或在 Offboard 中解锁。官方 Offboard 示例也是先发 setpoint，再切 Offboard 和 Arm。
### C. 监测与结果收集
- 订阅 `/fmu/out/vehicle_status`
- 订阅 `/fmu/out/vehicle_local_position`
- 在结束后等待日志落盘
- 触发结果后处理

## 5. 坐标系规则
这是实现时必须硬编码清楚的一条规则：
- PX4 `TrajectorySetpoint` 使用 **NED**
- ROS 世界系常见是 **ENU**
- ROS 与 PX4 之间**没有隐式坐标转换**
因此，如果你的 CSV 不是 NED，而是 ENU，就必须在 ROS 节点里自己转换，再发布到 `/fmu/in/trajectory_setpoint`。PX4 官方 ROS 2 用户指南专门提醒了这一点。

## 6. 启动顺序与“等待条件”

推荐的运行顺序固定为：
1. 启动 QGroundControl
2. 启动 `MicroXRCEAgent`
3. 启动 `make px4_sitl gz_x500` 或你的目标模型
4. 等 ROS 2 能看到 `/fmu/out/vehicle_status`
5. 再启动的 CSV 回放节点

PX4 的 ROS 2 架构要求 Agent 和话题桥已建立之后，ROS 2 应用再上层运行；Offboard 本身又要求先收到一段稳定的心跳流。

## 7. 日志获取与输出结果

你的主结果日志应以 **PX4 ULog** 为准。PX4 默认支持 ULog 记录，可在 SITL 的虚拟 `microsd/log` 目录中获得；这才是生成 `act_pos_* / act_vel_* / act_yaw` 最稳的来源。
Gazebo 也可以记录世界状态日志，但它更适合做世界回放、实体状态审计，而不是作为你的主评估源。Gazebo 支持 `--record` 和 `--record-path` 记录状态日志。
推荐输出分三类：

1. **原始输入 CSV**
2. **本次运行实际使用的预处理后局部轨迹 CSV**
3. **ULog 解析后的执行结果 CSV**

执行结果 CSV 建议至少包含：
- `time_relative`
- `act_pos_x, act_pos_y, act_pos_z`
- `act_vel_x, act_vel_y, act_vel_z`
- `act_yaw`

然后再基于起始偏移恢复成绝对坐标版结果，以便和你的 `intent` 语义一致。

## 8. 环境、风场、世界与模型管理

Gazebo 侧的环境应按“world + model”两层管理。
### world
用于定义：
- 是否空世界
- 风场
- 地面/边界/障碍物
- 其他环境插件

可以选择是否建立在环境中启动风场，且风速及其方向可调
PX4 官方支持通过 world 启动不同环境，模型和世界都来自 `PX4-gazebo-models` 仓库。你当前的主需求是空世界 + 可调风，所以默认基线可以是 `default` 或 `windy`。

### model
用于定义：
- 机体几何与质量
- 电机/桨叶相关物理
- 传感器
- 与 PX4 的仿真接口

当前基线建议保持 `gz_x500`，后续再派生出：
- “家用机”基线模型
- “穿越机”基线模型

Gazebo 支持通过 `PX4_GZ_MODEL_POSE` 设置生成位置，也支持通过 `PX4_SIM_MODEL` / `PX4_GZ_MODEL_NAME` 指定模型。

## 9. 批量仿真与加速策略

最终轨迹量级是 500 到 2000 条，所以必须按“批处理系统”设计，而不是手工单次飞行思维。
推荐策略是：
### 单条 run
- 读取一条轨迹
- 预处理
- 生成本次模型起始位姿
- 启动仿真
- 执行预备段 + 正式回放
- 回收 ULog
- 解析并导出结果
- 退出实例

### 批处理管理器
- 顺序或小并发调度多个 run
- 为每条 run 建独立目录
- 保存配置、输入、输出、日志、统计结果
Gazebo 支持通过 `PX4_SIM_SPEED_FACTOR` 改变仿真速度；PX4 官方明确支持在 Gazebo 下快于或慢于实时运行。

但这里有一条必须坚持的规则：

**如果要做 5x 仿真，回放节点必须按“仿真时间”解释 `time_relative`，不能按墙钟时间解释。**  
否则 10 Hz 的 CSV 在 5x 下会变成错误的物理时间语义。PX4/Gazebo 的 lockstep 和速度因子正是为这种场景设计的。

所以在实现方案中，时间系统应分成两层：
- 实时模式：可用系统时钟
- 加速模式：必须使用仿真时钟

# px4中的可用uav模型
```bash
make px4_sitl gz_x500  
make px4_sitl gz_standard_vtol  
make px4_sitl gz_rc_cessna  
make px4_sitl gz_quadtailsitter  
make px4_sitl gz_tiltrotor
```
