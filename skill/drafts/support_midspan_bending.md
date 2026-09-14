---
id: support_midspan_bending
title: 用中央载荷的截面弯矩识别跨中检查重点
summary: 在已声明的两支点等效梁模型下计算中央点载与均布自重的弯矩需求，用于比较跨度和安排接缝检查，不预测积木强度或挠度。
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [support]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance]
  stages: [plan, draft, build, assemble]
  triggers: [跨度增大, 中央承载方案比较, 跨中模块接缝, 仅凭平衡宣称不会弯折]
prerequisites:
  - 等效跨内只有两端竖直反力，没有端部力偶或其他中间支承
  - 非负中央集中载荷和非负均布载荷是完整且明确的近似
  - 接触位置固定于本次分析，准静态模型适用
environment_constraints:
  - L 是两处支承合力之间的距离，不自动等于地形间隙
  - 实际货物有接触面积，点载近似只用于全局需求比较
  - 不具有已校准的积木弹性模量、截面刚度或连接强度
sources:
  - file: skill/books/statics.pdf
    title: "Engineering Statics: Open and Interactive"
    authors: [Daniel W. Baker, William Haynes]
    edition: "标题页日期 2026-09-12；未标数字版次"
    sha256: be09880aeac98e15ecfc2d1104659321b576e40fc2dfc1854f304d322a343c9b
    chapter: "8.1–8.6 Internal Forces"
    pdf_pages: [291, 292, 293, 294, 295, 296, 297, 298, 299, 300, 301, 302, 303, 304, 305, 306, 307]
    printed_pages: [279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295]
    locator: "8.1 截面内力；例 8.3.3 均布载荷跨中弯矩；8.4–8.6 弯矩图与截面法"
    license_status: "PDF 前言声明 CC BY-NC-SA 4.0；人工审核待完成"
    supports: [先求外部反力再截面分析, 内力需求不等于强度或变形, 均布载荷项 qL²/8, 通过平衡推导截面弯矩函数]
code_evidence:
  - path: levels.yaml
    symbol: support 的三个 task
    supports: 跨度和中央货物条件
  - path: simulation/simulation_support.py
    symbol: main
    supports: 配重与放置变化，未暴露梁刚度参数
  - path: analyze/sim_support.py
    symbol: analyze_simulation_support / _calculate_ballast_metrics
    supports: 现有指标基于货物高度和载荷，不是截面弯矩测量
  - path: blocks/configs/small_wooden_block.yaml
    symbol: weight / shape / faces
    supports: 离散积木自重和连接，不能直接认定为均匀连续梁
validation:
  human_review: pending
  logic_tests: passed
  geometry_checks: not_run
  physics_trials: not_run
  evidence: ["2026-09-14: tests/test_skills.py::SkillTests.test_trusted_repository_reference_policies"]
---

# 1. 何时使用与何时不用

用于中央承载桥的初步需求比较和模块接缝审核。关注的问题是“哪里需要承担较大的截面弯矩”，而不是“最大能承受多少货物”。

仅适用于两支承之间的等效跨内，没有悬臂自重、额外支承、端部力矩或其他偏心载荷。实际机器不满足时应重新建立截面平衡，不强行套公式。中间有不能传递所需内力的接缝时，计算给出的是必须承担的需求，不证明该接缝可以承担。

# 2. 原理与来源

教材第 279–284 页强调，切开构件后需补上相反成对的轴力、剪力和弯矩。例 8.3.3 在第 287 页得到均布载荷下的跨中弯矩 `qL²/8`。第 290、294–295 页说明通过截面法得到沿跨长的需求分布。

本技能从相同平衡方法推导中央点载特例，再叠加均布载荷；这里不是材料变形叠加：

```text
R = (P + qL) / 2
M(s) = R*s - q*s²/2 - P*max(0, s - L/2), 0 <= s <= L
M_mid = P*L/4 + q*L²/8
```

`P >= 0, q >= 0` 且至少一项非零时，需求最大值出现在跨中。`P*L/4` 是本技能推导项；`qL²/8` 有教材例题直接依据。

它说明增加跨度可能增加需求，不能推出“增加高度必然增加承载”，更不能用未知的 `E`、`I` 计算游戏挠度。

# 3. 环境映射与限制

沿 Agent `y` 轴建立局部坐标 `s=y-y_south`。`L` 使用两支承合力间距；任务间隙 5/10/20 不自动给出 `L`。有限桥端接触区中的压力合力会移动。

真实货物是有限面积接触，集中在跨中的 `P` 只是全局近似。离散积木的自重不天然均布；`q=0` 也需要明确说明忽略了什么。未说明或未知的自重不能默认取零。

整个截面的总弯矩不能当成某个 Brace 的轴力或某根木块的实际弯矩。多个平行承载路径如何分担仍需要独立分析。

# 4. Procedure

1. 核对支承位置、中央点载和自重近似，不满足时返回模型不适用。
2. 计算两端反力和跨中弯矩，同时列出沿跨的几个需求点。
3. 优先检查跨中附近的模块接缝、桥面载荷进入处和持续传力路径；不要把大弯矩位置直接设计成没有依据的自由铰。
4. 改变设计后重新计算需求，并单独验证承载能力和成本。需求下降不自动等于实际性能提升。

# 5. 输入约定与参考策略

`length`：有限正值，游戏长度单位。`point_load`：中央向下载荷。`uniform_load`：同一载荷标度除以游戏长度，显式给定且非负。两者来自声明的设计载荷模型，而非构建工具的应力传感器。

`model_valid=True` 表示本文件全部模型前提已核对；`False` 表示明确不符；`None` 表示未知。输出反力与弯矩分别使用输入载荷标度及“载荷标度乘长度”，不得标注为已校准 SI 单位。

```python
from math import isfinite


def estimate_midspan_demand(length, point_load, uniform_load, model_valid=None):
    result = {
        "status": "insufficient_evidence", "reason": "",
        "checks": [], "next_steps": [],
    }
    if type(model_valid) is not bool:
        result["reason"] = "model_assumptions_unconfirmed"
        return result
    if not model_valid:
        result.update(status="not_applicable", reason="outside_central_load_model")
        return result
    try:
        values = (length, point_load, uniform_load)
        if any(type(v) not in (int, float) or not isfinite(v) for v in values):
            raise ValueError
        if length <= 0 or point_load < 0 or uniform_load < 0:
            raise ValueError
        total_load = point_load + uniform_load * length
        if not isfinite(total_load) or total_load <= 0:
            raise ValueError
        reaction = total_load / 2
        midpoint = length / 2
        peak = point_load * length / 4 + uniform_load * length * length / 8
        samples = []
        for fraction in (0, 0.25, 0.5, 0.75, 1):
            s = fraction * length
            moment = (
                reaction * s - uniform_load * s * s / 2
                - point_load * max(0, s - midpoint)
            )
            if not isfinite(moment):
                raise ValueError
            samples.append({"s": s, "moment": moment})
        if not isfinite(peak):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        result["reason"] = "missing_or_invalid_numeric_inputs"
        return result
    result.update(status="candidate", reason="section_demand_not_capacity")
    result["checks"] = [
        {"name": "declared_load_model", "result": True, "basis": "model_valid"},
        {"name": "connection_capacity", "result": None, "basis": "not_measured"},
        {"name": "deflection", "result": None, "basis": "stiffness_unknown"},
    ]
    result["estimates"] = {
        "reaction_each": reaction, "midspan_moment": peak,
        "critical_s": midpoint, "moment_samples": samples,
        "moment_units": "input_load_scale_times_game_length",
    }
    result["next_steps"] = [
        {"kind": "review", "target": "midspan_connections_and_load_transfer"},
        {"kind": "validation_plan", "target": "geometry_then_local_physics"},
    ]
    return result
```

该函数只返回条件需求和检查位置，不调用构建工具，不创建新材料模型。

# 6. 最小自测

合成输入，未执行；先加载函数：

```python
point = estimate_midspan_demand(10, 8, 0, True)
assert point["status"] == "candidate"
assert point["estimates"]["midspan_moment"] == 20
assert point["estimates"]["reaction_each"] == 4
combined = estimate_midspan_demand(10, 8, 2, True)
assert combined["estimates"]["midspan_moment"] == 45
assert combined["estimates"]["reaction_each"] == 14
assert combined["estimates"]["moment_samples"][0]["moment"] == 0
assert combined["estimates"]["moment_samples"][-1]["moment"] == 0
assert estimate_midspan_demand(5, 8, 0, True)["estimates"]["midspan_moment"] == 10
assert estimate_midspan_demand(0, 8, 0, True)["status"] == "insufficient_evidence"
assert estimate_midspan_demand(10, 8, None, True)["status"] == "insufficient_evidence"
assert estimate_midspan_demand(10, 8, float("inf"), True)["status"] == "insufficient_evidence"
assert estimate_midspan_demand(10, 8, 0, False)["status"] == "not_applicable"
assert estimate_midspan_demand(10, 8, 0)["status"] == "insufficient_evidence"
```

# 7. Checklist

- `L` 是支承间距，`P/q` 是完整且自洽的模型，不遗漏悬臂和偏载。
- 中央点载近似的适用范围已说明；有限接触区域附近的局部响应未被冒充为已求解。
- 保持连续传力路径，跨中接缝的需求与能力分开记录。
- 没有使用真实木材材料常数预测游戏位移或最大承载。

# 8. 验证方案与证据

逻辑：核对点载项、均布项、支点边界、跨度变化与非法输入。几何：核对候选设计中跨中及其邻近位置的连接和接缝。

开发仿真：固定场景、载荷、总预算和放置条件，比较不同模块接缝安排，记录失效位置、货物轨迹、承载和积木成本。仅能检验设计假设及趋势；现有遥测没有截面弯矩，不能声称直接测得公式数值。

未执行自测、几何检查或仿真。

# 9. 交给下一角色的结论

传递支点位置、`L/P/q` 及其来源、跨中位置、需求标度和需要检查的接缝。相关子结构中写明“此处必须维持载荷路径，能力待验证”，不能写成“该截面已通过强度校验”。
