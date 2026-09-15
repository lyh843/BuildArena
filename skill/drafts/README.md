# Statics 首批 Support 技能草案

本页保留 Support 首批提炼记录。2026-09-15 新增的汽车理论技能见 [Transport 批次说明](TRANSPORT_README.md)，其参考代码尚未执行。

提炼日期：2026-09-14。范围：按 `skill/EXTRACT_PROMPT.md` 从本地教材选章提炼五条知识技能，未新增 Agent 工具、检索系统或自动执行宏。

这些文件可以作为角色按需阅读的知识草案；它们不是已经完成物理验证的技能版本。后续同日已接入可关闭的 Planner 检索，并实际通过逻辑自测；人工审核、技能独立几何检查和仿真仍待完成。下文提炼记录保留当时的检查范围。

## 技能目录

| 技能 | 解决的问题 | 优先接入位置 |
| --- | --- | --- |
| [接触自由体模型](support_contact_fbd.md) | 支承、载荷和坐标是否明确，是否虚构固定端 | Planner、Drafter、Guidance |
| [两岸反力分配](support_vertical_reactions.md) | 偏载是否使一侧支承卸载 | Planner、Drafter、Reviewer |
| [桁架模型适用性](support_truss_model_gate.md) | 是否可以使用理想桁架分析，如何选择方法 | Planner、Drafter、Reviewer |
| [跨中弯矩需求](support_midspan_bending.md) | 中央加载下哪里需要重点检查连接 | Planner、Drafter、Guidance |
| [接触摩擦检查](support_contact_friction.md) | 已知接触条件下的摩擦需求和未知参数 | Planner、Reviewer、Guidance |

上表的 Reviewer 指现有 `draft_reviewer`。各文件分别声明完整的阶段与角色范围。唯一具体工具提案是接触自由体技能中由 Builder 调用已有 `get_machine_summary` 辅助清点，不能据此读取物理接触力。

每条技能有独立 YAML 元数据、来源、模型前提、Procedure、纯函数参考策略、合成自测、Checklist、验证方案和阶段交接内容。`candidate` 只表示条件分析的候选结论，不是任务成功或物理验证通过。

## 原书核验

| 项目 | 本地核验结果 |
| --- | --- |
| 文件 | `skill/books/statics.pdf` |
| 标题 | Engineering Statics: Open and Interactive |
| 作者 | Daniel W. Baker、William Haynes |
| 版本定位 | PDF 第 3 页标题页日期为 2026-09-12，未标数字版次 |
| PDF 页数 | 435 |
| 文件大小 | 25,295,000 字节 |
| SHA-256 | `be09880aeac98e15ecfc2d1104659321b576e40fc2dfc1854f304d322a343c9b` |
| 文件内许可声明 | PDF 第 5–6 页、印刷页 iv–v 声明正文 CC BY-NC-SA 4.0；GeoGebra 内容另有声明 |
| 审核状态 | 记录了许可声明；书目选择、提炼内容及公开分发方式仍待人工审核 |

版本日期来自标题页，不将 PDF 创建时间或本地修改时间当作下载日期。没有联网下载或核对另一份版本，没有更改 `book_candidates.md` 的人工审核勾选项。

这些草案以中文释义和自行编写的参考代码表达教材知识，保留作者、版本、页码与改写性质；没有复制书中的照片、互动程序或大段原文。文件内许可声明不等于本批次已完成发布审核。

## 实际阅读范围

PDF 页码均从 1 起算。所选正文满足“PDF 页码 = 印刷页码 + 12”；前言使用罗马页码，不能沿用此换算。

| PDF 页码 | 印刷页码 | 实际读取内容 |
| --- | --- | --- |
| 1–14 | 前置页、iv–xi、1–2 | 标题、日期、许可、目录和导论 |
| 174–187 | 162–175 | 自由体图、支反力、平衡方程、二维平衡示例 |
| 193–195 | 181–183 | 稳定性、静定性及支承约束方向 |
| 199–211 | 187–199 | 多体结构、载荷路径、简单桁架、零力杆、节点法入口 |
| 291–307 | 279–295 | 截面内力、均布载荷例题、弯矩图与截面法 |
| 331–339 | 319–327 | 静摩擦、临界运动、滑移与倾覆；最后一页仅使用 9.2 的结束部分 |

另外查看了 PDF 第 177、204、299、338 页的渲染图，核对支座表、桁架前提、均布载荷跨中公式和滑移/倾覆图。未读取全书，不声称覆盖其他章节。

## 候选取舍

- 采用：上述五个决策问题，覆盖建模、条件计算、分析路线和失效边界。
- 暂缓独立技能：一般载荷路径图算法。本批次将载荷路径作为受力与桁架检查的一部分，未为此虚构可直接读取的连接图 API。
- 暂缓独立技能：挠度、屈曲和最大承载预测。当前没有可靠的游戏材料、连接和截面刚度参数；也未阅读足够的后续材料力学资料。
- 未生成自动加撑或删杆宏；未把零力杆识别转换为删除积木的权限。
- 未输出完整机器、BSG 或对正式评测场景调优的设计。

## 环境依据与复现

提炼时仓库 HEAD：`a43ecb47c1fe53e7357f27f8d8ae99de5e87b701`。提炼前已有未跟踪文件 `skill/EXTRACT_PROMPT.md`，本批次未修改它。运行模块与配置均未修改。

| 文件 | SHA-256 |
| --- | --- |
| `skill/EXTRACT_PROMPT.md` | `144044d131ea5cabf22c3218461bc284174744f51ce09b8b2489624bf1f72e4f` |
| `levels.yaml` | `97f0c81fde7766ef42e01d9b8ecb9c3553d93a104c411a7b65b6e46fc6a22812` |
| `prompt.yaml` | `f97c9dbabe7ca6688987b1d892a2e252ef7207331c659bc830d5b97a4e7b97f5` |
| `spatial/agent.py` | `d43020a59279134eeea780f7193d61fd30db08ecb5bf6913be4a5c65dff5782e` |
| `spatial/build.py` | `57c48dacabc8ab2a42f8bfe778b4de4a0023cbc8fcb15dce812913c1dcfa3831` |
| `spatial/components.py` | `0fd47f8b4a324895dde80df3172eb2f1d49cc2e3f084bb82d9801f2688eb73a5` |
| `spatial/utils.py` | `ab5d04120f92356fa327390a08a1036252a155a98e6129a68a3ef07fb46dc681` |
| `scheduler/runner.py` | `fe49a3a945dc0834ac5de264a451848d35a99a458efcd36bf67c27a48ff867bc` |
| `simulation/simulation_support.py` | `aa8c5d6efd2aee06548d1e4312e222b2530ee3ad0ef227cc3e013bbe4e515365` |
| `analyze/sim_support.py` | `9bdadbfd6ce68f45b36a379347cb46716c61ae9e9742f4107d193879b98f6bc8` |
| `blocks/configs/brace.yaml` | `5e42c0586d42c9f6dedc0b3268a2b0b9614c5634b5fadb2d4fa10b198a7a169e` |
| `blocks/configs/small_wooden_block.yaml` | `0f1e88b4e86f4c180aa428ab8cffd61d7989b0ab39ada217f8aa0dc00067936f` |
| `blocks/configs/starting_block.yaml` | `d651bd704ba95f82a1ae5decdf9caca9bfdea14b44e7a44dc133b56a51961f4a` |

需要持续保留的边界：

1. 任务中没有地形固定端；游戏放置和接触合力位置必须独立核对。
2. 构建摘要不返回实测接触力、摩擦系数或材料刚度。技能的输入约定不是已实现的环境接口。
3. 理想两支点、中央点载、均布自重和桁架铰接均需显式前提，不能由“看起来像桥”推出。
4. 当前 Support 分析器用货物高度阈值和累计保持时间判断通过，默认阈值为高度 4、保持时间 2 秒，并排除初始高度超过 20 的情况。这与“全程稳定承载”不同；其分数也不是应力、反力或摩擦的测量。

## 检查记录

2026-09-14 已完成：五条技能的 YAML 解析、必需字段与 ID 检查、引用文件存在性、所选页码对应关系、九个正文章节、Python AST 解析与静态编译、导入与危险调用名称检查、工作流保留标记扫描。

| 范围 | 结果 |
| --- | --- |
| 技能元数据 | 5 条可解析，ID 唯一 |
| Python 语法 | 5 个参考函数、5 个自测代码块可解析和静态编译 |
| 自测断言 | 51 个；2026-09-14 后续接口接入时实际执行通过 |
| 策略运行 | 仅离线测试执行纯函数与断言；检索接口从不执行正文代码 |
| 人工审核 | pending |
| 几何检查、物理仿真 | not_run |
| 性能收益、成功率变化 | 未测量 |

最初静态编译没有执行策略函数或断言。用户随后要求接入与对照测试，已在 `tests/test_skills.py::SkillTests.test_trusted_repository_reference_policies` 执行这五份本地可信测试，`logic_tests` 据实更新为 `passed`；几何与物理验证仍分别记录。版本仍为 0.1.0（策略逻辑未变），本次验证元数据变化由新内容 SHA-256 区分。

## 候选关系

[relations.json](relations.json) 保留本批次五条有条件的 `requires` / `uses` 关系；后续 Transport 的四条候选边也存放于此。所有边都是 `pending`，没有未经验证的修复效果或自动图扩展行为；技能本身保留必要前提，不依赖检索到另一篇才知道关键限制。

提炼阶段没有修改冻结技能库、原始提示词、评价标准、运行路径或模型设置。后续 Planner 接入可在显式 `--allow-draft-skills` 下将草案冻结为探索性实验快照，但不代表人工审核或正式评测验收通过。
