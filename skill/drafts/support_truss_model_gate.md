---
id: support_truss_model_gate
title: 先核对桁架假设，再选择节点法、截面法或一般结构分析
summary: 面对三角形或 Brace 方案时检查两力杆、节点加载、连接转动与空间约束，避免按外观套用理想桁架公式或删除零力杆。
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [support]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance]
  stages: [plan, draft, build, refine, assemble]
  triggers: [选择三角支撑方案, 声称杆件只有轴力, 使用零力杆规则, 选择结构求解方法]
prerequisites:
  - 已列出构件、节点、外载荷与实际支承条件
  - 模型假设有设计说明或独立证据，不能仅由积木名称判断
environment_constraints:
  - Brace 可连接两个已有积木的面，但其配置不证明理想无摩擦铰
  - 积木和连接件有自重，货物也不一定恰好加载在理想节点
  - 单个平面上的三角形不证明三维稳定
sources:
  - file: skill/books/statics.pdf
    title: "Engineering Statics: Open and Interactive"
    authors: [Daniel W. Baker, William Haynes]
    edition: "标题页日期 2026-09-12；未标数字版次"
    sha256: be09880aeac98e15ecfc2d1104659321b576e40fc2dfc1854f304d322a343c9b
    chapter: "5.6 Stability and Determinacy; 6.1–6.4"
    pdf_pages: [193, 194, 195, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211]
    printed_pages: [181, 182, 183, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199]
    locator: "6.3.2 简单桁架假设；6.3.3 方法选择；6.3.5 零力杆的用途；6.4 节点平衡"
    license_status: "PDF 前言声明 CC BY-NC-SA 4.0；人工审核待完成"
    supports: [简单桁架的两力杆和铰节点前提, 整体到局部的分析顺序, 零力杆与实际冗余, 节点法和截面法的选择]
code_evidence:
  - path: blocks/configs/brace.yaml
    symbol: description / type / weight / faces
    supports: 双端连接件，有自重且自身不提供附着面；未给出理想铰的物理参数
  - path: blocks/configs/small_wooden_block.yaml
    symbol: faces / weight
    supports: 真实连接面与积木自重
  - path: spatial/build.py
    symbol: Machine.connect_blocks / Machine.get_block_details
    supports: 按真实积木 ID 和连接面进行连接，反馈为文本
  - path: spatial/agent.py
    symbol: MultiAgents.build
    supports: build 和 assemble 的 builder 可获得连接工具，refine 不获得 build 分组
  - path: levels.yaml
    symbol: support 的三个 task
    supports: 接触支承和子结构数量限制，不能虚构固定支座
validation:
  human_review: pending
  logic_tests: passed
  geometry_checks: not_run
  physics_trials: not_run
  evidence: ["2026-09-14: tests/test_skills.py::SkillTests.test_trusted_repository_reference_policies"]
---

# 1. 何时使用与何时不用

在提出桁架方案、用轴力计算证明结构可行、选择分析方法或准备删除“零力杆”时使用。本技能选择分析路线，不求解完整结构，也不保证某种三角形布局比其他方案更强。

连接刚度未知不意味着桁架布局无用；它意味着数值上的理想铰、纯轴力结论尚不能用于真实机器。

# 2. 原理与来源

- 第 187–190 页区分桁架与含多力构件的框架，要求先求整体外部平衡，再分析相互作用；分开构件时的作用反作用力必须成对。
- 第 192 页的简单桁架模型要求两力杆、无摩擦铰节点、外力与反力在节点处作用，并作刚体近似。
- 第 194 页建议：需要全部杆力时通常选节点法，只关心少数杆时可选截面法。第 199 页说明平面节点提供两个独立力平衡方程。
- 第 193、197 页提示失去单根杆件可能失去载荷路径；特定工况下的零力杆仍可能参与抗屈曲、自重或其他工况，不应直接从实物删除。

模型计数 `m + r = 2j` 不是游戏稳定性证书。第 182–183 页还讨论反力方向和作用线的约束问题。本技能因此不通过数量相等自动批准结构。

# 3. 环境映射与限制

Brace 是已有双端连接件，可以用于三角布局，但“有 Brace”不证明节点没有力矩，也不证明杆件只受轴力。货物压在两节点之间的桥面上时，那段桥面可能承受弯曲。

先安排货物落点、桥面到主结构的传力和两岸接触，再选择连接位置。构建阶段由 Builder 核对实际连接面；Planner、Drafter 和 Guidance 不直接调用构建工具。Refine 阶段也不能为了加撑而调用未绑定的 `connect_blocks`。

三维约束需另审；跨中加载改变、积木自重和连接形变都可能破坏原模型。不能照搬教材中“常见三个支座反力”到没有固定连接的两岸接触。

# 4. Procedure

1. 标记实际构件和节点，列出桥面接收货物的位置、模块连接和支承接触。
2. 为下表各前提给出有来源的布尔判断。未知先保留，不能从结构外形推断。
3. 有明确不满足项时切换到相应的三维或一般结构分析，并调整加载与连接设计。
4. 只有前提被明确接受时才选择节点法或截面法；仍保留“条件近似”的标签。
5. 零力杆只可从当前数学分析中暂时消去，不能自动生成删除积木操作。

# 5. 输入约定与参考策略

`assumptions` 是角色整理的审核记录，每项为 `True/False/None`：

| 字段 | 判断含义 |
| --- | --- |
| `planar` | 当前受力与构件可以在同一平面内近似 |
| `two_force_members` | 杆件仅有两端作用，未遗漏杆中外载或力偶 |
| `pin_joints` | 连接可合理近似为不传递力矩的铰 |
| `nodal_loads` | 载荷和支反力进入已定义的节点 |
| `weight_treatment` | 自重已处理，忽略或等效至节点有明确依据 |
| `rigid_approximation` | 当前阶段采用刚体近似有依据 |
| `stable_geometry` | 独立检查未发现平面机构或外部支承失约束；不是计数相等 |

`target` 为 `all_members` 或 `selected_members`。为真可以是明确标记的初步设计近似，但不得被改写成已经过游戏校准；证据记录仍须保留。

```python
def choose_truss_analysis(assumptions, target="all_members"):
    remedies = {
        "planar": "use_three_dimensional_equilibrium",
        "two_force_members": "include_shear_and_bending_in_member_models",
        "pin_joints": "include_joint_moments_or_measure_connection_behavior",
        "nodal_loads": "provide_a_load_transfer_node_or_analyze_loaded_spans",
        "weight_treatment": "include_member_weight_before_axial_only_analysis",
        "rigid_approximation": "obtain_deformation_or_physics_evidence",
        "stable_geometry": "revise_constraints_and_load_paths",
    }
    result = {
        "status": "insufficient_evidence", "reason": "",
        "checks": [], "next_steps": [],
    }
    if not isinstance(assumptions, dict) or target not in (
        "all_members", "selected_members",
    ):
        result["reason"] = "invalid_input"
        return result
    for key in remedies:
        value = assumptions.get(key)
        if value is not None and type(value) is not bool:
            result["reason"] = "flags_must_be_boolean_or_none"
            return result
        result["checks"].append({
            "name": key, "result": value, "basis": "caller_reviewed_model",
        })
    failed = [c["name"] for c in result["checks"] if c["result"] is False]
    missing = [c["name"] for c in result["checks"] if c["result"] is None]
    if failed:
        result.update(status="not_applicable", reason="simple_truss_model_rejected")
        result["next_steps"] = [
            {"kind": "revise_analysis", "action": remedies[key]} for key in failed
        ]
    elif missing:
        result["reason"] = "simple_truss_assumptions_missing"
        result["next_steps"] = [{"kind": "obtain_evidence", "fields": missing}]
    else:
        result.update(status="candidate", reason="conditional_analysis_route")
        method = "method_of_joints" if target == "all_members" else "method_of_sections"
        result["next_steps"] = [
            {"kind": "analysis", "action": "solve_global_reactions_first"},
            {"kind": "analysis", "action": method},
            {"kind": "review", "action": "check_other_load_cases_and_lateral_stability"},
        ]
    result["do_not_infer"] = [
        "physical_strength_verified", "zero_force_member_is_removable",
    ]
    return result
```

这是确定分析路线的完整函数，不是假装已经实现节点法求解器。需要定量杆力时，由原角色按方程展开，不能调用不存在的求解 API。

# 6. 最小自测

合成审核记录，未执行；与上方函数放在同一命名空间：

```python
assumptions = dict.fromkeys((
    "planar", "two_force_members", "pin_joints", "nodal_loads",
    "weight_treatment", "rigid_approximation", "stable_geometry",
), True)
all_members = choose_truss_analysis(assumptions)
assert all_members["status"] == "candidate"
assert all_members["next_steps"][1]["action"] == "method_of_joints"
assert choose_truss_analysis(
    assumptions, "selected_members",
)["next_steps"][1]["action"] == "method_of_sections"
assert choose_truss_analysis({
    **assumptions, "pin_joints": False,
})["status"] == "not_applicable"
assert choose_truss_analysis({
    **assumptions, "pin_joints": None,
})["status"] == "insufficient_evidence"
assert choose_truss_analysis({
    **assumptions, "stable_geometry": False,
})["status"] == "not_applicable"
assert choose_truss_analysis({
    **assumptions, "planar": "yes",
})["status"] == "insufficient_evidence"
```

# 7. Checklist

- 载荷是否进入真实节点，构件中部是否还受货物或自重作用？
- Brace 与木块的实际连接没有被无条件认定为铰；面编号来自当前状态。
- 三角布置只作为设计候选，外部接触和侧向约束另有说明。
- 零力杆没有转化为删除操作；子结构拼接处没有遗漏传力路径。

# 8. 验证方案与证据

逻辑：检查各前提缺失、被否定以及不同分析目标的分支。几何：逐一核对节点、构件方向、可连接面及三维连接，不仅检查杆数。

开发仿真：在相同任务和加载条件下比较有无指定撑杆的设计，记录形变、失效模式、承载及新增成本；这些都是待验证假设，不能预设有撑必然更优。原始运行记录和失败样本均保留。

未执行几何与物理验证，也未用游戏数据校准理想铰模型。

# 9. 交给下一角色的结论

传递分析类型、载荷进入节点的位置、自重处理及未核实的连接假设。子结构的接口节点和职责写入各自的 `design_requirements`；不要仅给下游一句“使用桁架”。
