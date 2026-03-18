## Context

当前生成器把采样、轨迹构造、偏航生成、校验、配额分配和 CSV 导出集中在 `src/intent2trajectory/generator.py` 一个文件里。配置入口也集中在 `configs/dataset_config.json`，其中 `intent_profiles` 直接绑定旧标签体系与 `variant` 参数；站点相对语义指标目前只对 `hover` / `loiter` 局部可见，而 `straight_penetration`、`non_straight_penetration` 与 `retreat` 仍以几何模板和局部规则为主。

3 月 13 日方案要求把系统升级为“相对站点风险行为生成器”。这不是单纯替换几组轨迹模板，而是要求统一以下四件事：语义标签从几何命名切换为风险语义命名、样本生成由阶段指令驱动、机型能力成为主导约束项、输出结果必须携带完整的风险向量和验证证据。因此本次设计必须覆盖领域模型、配置拆分、动力学 rollout、验证流程和导出契约。

另一个约束是仓库里已有 `station-risk-semantics-phase1` 变更，它已经把 `hover/loiter` 的站点语义迁移写成独立提案。本次设计需要吸收这部分结论，但不能再把 `hover/loiter` 作为局部例外保留在新架构之外。

## Goals / Non-Goals

**Goals:**
- 建立统一的内部领域模型，用同一条管线处理 `attack`、`retreat`、`hover`、`loiter` 四类意图。
- 将生成流程重构为“语义目标采样 -> 风格选择 -> 阶段计划 -> 机型约束 rollout -> 语义评分/验证 -> 多样性过滤 -> 导出”。
- 让 `AirframeProfile`、`StageSpec`、`RiskVector`、`IntentScores` 成为一等数据结构，替代当前散落在配置与 metadata 中的隐式约束。
- 将 `generator.py` 的单文件逻辑拆为可测试模块，并为后续 OpenSpec apply 阶段提供清晰的实现边界。
- 定义明确的迁移方式，将旧 `straight_penetration` / `non_straight_penetration` / `variant_name` 体系迁移到新 `primary_intent` / `motion_style` 体系。

**Non-Goals:**
- 本次设计不处理下游识别模型、训练脚本或特征工程的重构。
- 本次设计不承诺一次性完成全量数据集重生成，只定义新生成器落地后的输出契约。
- 本次设计不引入外部物理仿真依赖；动力学仍使用仓库内可控的轻量 rollout 模型。
- 本次设计不试图在 proposal 阶段冻结所有数值阈值，保留一部分校准参数在配置文件中调优。

## Decisions

### 决策：引入规范化的生成域模型，保留 `generator.py` 作为薄编排层
新实现将把当前以 `dict` 为主的隐式数据流拆成显式域对象：`SemanticTarget`、`AirframeProfile`、`StageSpec`、`Trajectory`、`StationMetrics`、`RiskVector`、`IntentScores`、`ValidationResult`。新的 `generator.py` 只负责 orchestration，具体逻辑迁移到 `semantics/`、`airframes/`、`stages/`、`templates/`、`dynamics/`、`validators/`、`exporters/` 子模块。

理由：
- 当前实现把配置读写、轨迹点构造和验证结果耦合在一个字典里，不适合承载多机型、多阶段、多评分输出。
- 显式领域模型可以让测试直接围绕中间结果断言，而不是每次都从最终 CSV 逆推语义。

考虑过的替代方案：
- 在现有 `generator.py` 内继续追加 helper 函数。
- 否决原因：这会继续放大单文件复杂度，并让后续风格扩展、动力学模型切换和 metadata 升级变得不可维护。

### 决策：用站点极坐标速度指令作为阶段计划的统一控制语法
每个 `StageSpec` 统一产出 `v_r_cmd`、`v_theta_cmd`、`v_z_cmd` 与 `yaw_mode`，并带有持续时间范围、终止条件、噪声配置和语义影响。模板模块只负责组合阶段，不再直接产出整段 `x/y/z` 轨迹。

理由：
- 该语法天然对齐 `close_score`、`dwell_score`、`encircle_score`、`point_score`、`uncertain_score`、`disengage_score` 六维风险语义。
- 它允许同一意图在不同机型上保留语义一致性，同时呈现不同形态。

考虑过的替代方案：
- 继续使用几何曲线模板，再从几何轨迹反推语义。
- 否决原因：几何模板无法稳定表达“试探回拉”“监视指向性”“固定翼伪悬停”等关键语义，也会让机型约束成为事后补丁。

### 决策：将机型能力定义为主导约束，并按机型/模式切换动力学模型
`AirframeProfile` 将成为配置中心，至少定义机型家族、速度范围、纵横向加速度、爬升率、偏航率、转弯率、最小转弯半径、控制时间常数、偏好高度、允许风格以及 validator override。rollout 时根据机型家族和飞行模式在 `VelocityTrackingModel` 与 `CourseSpeedModel` 间切换。

理由：
- 文档明确要求“语义相同，不等于形态相同”，固定翼 `hover` 必须通过 `corridor_hold` / `pseudo_hover_racetrack` 这类语义等价风格表达。
- 如果继续按意图绑定统一速度/加速度阈值，就无法同时满足多旋翼、固定翼和 VTOL 的可行性。

考虑过的替代方案：
- 继续保留按 intent 配置的统一约束，只在 validator 阶段做机型差异化例外。
- 否决原因：这样会让不可飞的样本大量生成后才被拒绝，采样效率和语义稳定性都会变差。

### 决策：采用“双层判定”作为统一验证契约
样本验证统一分为四步：硬约束检查、站点指标计算、`risk_vector` 计算、四类 intent 连续评分与目标意图接受判定。接受判定必须同时满足目标意图评分阈值和与第二名的最小分差；若硬约束失败，则允许进行一次轻量修复后重试。

理由：
- 连续评分可以表达接近语义目标区域的程度，硬阈值与 margin 则能避免模糊样本混入数据集。
- 先做硬约束再做语义评分，可以避免无物理意义的轨迹污染统计特征。

考虑过的替代方案：
- 仅依赖风格模板命中结果判断 intent。
- 否决原因：模板命中并不能保证风险语义成立，也无法防止 `probe_loiter` 演化成 `attack` 或 `retreat`。

### 决策：配置拆为“入口配置 + 外部能力配置”，不在一个 JSON 里塞满全部语义与机型参数
保留 `configs/dataset_config.json` 作为配额、随机种子、输出路径和总入口，但让它引用 `airframes.json`、`intent_regions.json`、`style_library.json` 等能力配置。旧 `intent_profiles` 会拆分：与配额相关的采样控制保留在入口配置，语义阈值、风格模板和机型能力迁入独立配置文件。

理由：
- 当前 `dataset_config.json` 已经同时承担配额、模板参数、约束、导出配置和语义阈值，扩展到新方案后会失去可维护性。
- 分文件后可以单独测试语义区域、机型矩阵和风格模板，而不必加载整份数据集配置。

考虑过的替代方案：
- 继续保留单文件 JSON，通过更深层嵌套承载新配置。
- 否决原因：这会使修改和 code review 变得困难，也会加剧不同关注点之间的耦合。

### 决策：显式接受一次 schema 变更，不在核心流水线内维持长期旧字段兼容
新生成器以 `primary_intent`、`motion_style`、`airframe_name`、`airframe_family`、`flight_mode_sequence`、`semantic_target_json`、`risk_vector_json`、`intent_scores_json`、`stage_plan_json`、`hard_constraint_report` 为主输出字段。对旧标签和旧 metadata 的兼容只通过迁移映射、测试夹具和文档说明处理，不在核心域模型里保留双写字段。

理由：
- 长期双写会让领域模型持续背负旧 taxonomy，削弱这次重构的收益。
- 用户已经明确要求先重构逻辑与流程，说明当前优先级是语义正确性，而不是维持旧字段零变更。

考虑过的替代方案：
- 在所有导出中同时保留新旧字段，并把新标签映射回旧标签。
- 否决原因：旧 `straight_penetration` / `non_straight_penetration` 与新 `attack` 的关系不是一一对应，强行映射会制造误导。

## Risks / Trade-offs

- [风险] 模块拆分过大，首轮实现容易出现接口震荡 -> 缓解：先冻结领域对象与模块边界，再按 capability 分批实现和测试。
- [风险] 风险向量阈值初始值不稳，导致样本通过率偏低或语义混叠 -> 缓解：将阈值放入独立配置，并在任务中加入统计校准与样本审查。
- [风险] 固定翼和 VTOL 风格模板如果不足，会导致 intent 匹配偏向多旋翼 -> 缓解：将 `allowed_styles` 与 `validator_overrides` 作为机型配置的一部分，并将各机型最小样本覆盖写入测试与验收任务。
- [风险] schema 变更会打破现有测试和下游脚本 -> 缓解：提供显式迁移表、更新测试夹具，并让旧入口在短期内只做参数解析与错误提示，不再生成旧 schema 样本。
- [风险] 新 metadata 和去重特征会增加导出体积和实现复杂度 -> 缓解：将富 metadata 收敛到 `sample_meta.json` 与 metadata CSV 摘要，避免在每一行轨迹点中重复展开全部字段。

## Migration Plan

1. 冻结 capability 与领域对象命名，明确 `attack/retreat/hover/loiter`、`motion_style`、`AirframeProfile`、`StageSpec`、`RiskVector` 等核心数据结构。
2. 新增配置文件与解析层，让 `dataset_config.json` 只承担入口作用，并为旧配置提供迁移映射或明确报错。
3. 实现 `semantics/`、`airframes/`、`stages/`、`templates/`、`dynamics/`、`validators/`、`exporters/` 模块，同时让 `generator.py` 改为编排层。
4. 按 capability 分批迁移测试：先语义指标与评分，再 rollout/约束，再导出与多样性控制。
5. 在新管线可通过测试后，移除或瘦身旧几何模板实现，仅保留必要的迁移辅助函数与文档映射。
6. 如需回退，保留当前 `generator.py` 的历史版本和旧配置样例，回退时以 git 级别回退整个 change，而不是在新代码里维持长期双栈逻辑。

## Open Questions

- 第一版 `airframes.json` 是否只覆盖最小可用机型集合，还是需要一次性补齐训练集计划中的全部机型档案？
- `sample_meta.json` 是否作为每个样本的必选输出，还是只在 `metadata.csv` 之外作为可选富信息导出？
- `hover` / `loiter` 的 Phase 1 既有阈值是否直接迁入新 `intent_regions`，还是先保留为 validator 基线并在第二轮标定后合并？
- 入口 CSV 是否还需要保留旧列名 `intent` / `variant_name` 作为过渡提示字段，还是在实现阶段一次性切换为新列名？
