---
id: support_vertical_reactions
title: 用载荷合力位置检查两岸反力与支承卸载
summary: 在两处接触合力位置和竖直载荷清单已知时计算南北反力，识别偏载或一侧卸载，不将正反力解释为整桥稳定。
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [support]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance]
  stages: [plan, draft, build, refine, assemble]
  triggers: [货物或结构偏心, 南北承载分配不明, 改变模块位置, 检查两岸是否同时受压]
prerequisites:
  - 同一已审核的二维准静态模型内只有两个已知位置的竖直支承合力
  - 列全向下载荷且没有遗漏的外加力矩或水平力矩效应
environment_constraints:
  - 支承只能提供压缩法向力，不能假设桥端被地形拉住
  - 支承合力位置不能直接取间隙边缘或积木中心
  - 不验证侧向、扭转、滑移或构件强度
sources:
  - file: skill/books/statics.pdf
    title: "Engineering Statics: Open and Interactive"
    authors: [Daniel W. Baker, William Haynes]
    edition: "标题页日期 2026-09-12；未标数字版次"
    sha256: be09880aeac98e15ecfc2d1104659321b576e40fc2dfc1854f304d322a343c9b
    chapter: "5.3 Equations of Equilibrium; 5.4 2D Rigid Body Equilibrium; 9.1.3 Normal Forces"
    pdf_pages: [181, 182, 183, 335, 336]
    printed_pages: [169, 170, 171, 323, 324]
    locator: "式 5.3.1–5.3.3；二维平衡方程与选取矩心；接触合力位置"
    license_status: "PDF 前言声明 CC BY-NC-SA 4.0；人工审核待完成"
    supports: [力与力矩同时平衡, 对支点取矩消去未知量, 接触合力位置随载荷变化]
code_evidence:
  - path: levels.yaml
    symbol: support 的三个 task
    supports: 中央逐渐加载，桥端没有固定连接
  - path: spatial/components.py
    symbol: Vector.real
    supports: 南北位置使用 Agent 的 y 分量
  - path: simulation/simulation_support.py
    symbol: main
    supports: 设计坐标需经过仿真放置变换
validation:
  human_review: pending
  logic_tests: passed
  geometry_checks: not_run
  physics_trials: not_run
  evidence: ["2026-09-14: tests/test_skills.py::SkillTests.test_trusted_repository_reference_policies"]
---

# 1. 何时使用与何时不用

用于模型已明确的偏载检查和反力分配。可以在设计阶段作有标记的假设比较，也可在接触位置有观测依据时作条件估算。

多处未知接触、明显变形改变接触点、外加力偶、斜向载荷或三维扭转不属于本函数范围。不能因为两岸反力可解，就认为两处竖直反力约束了所有自由度。

# 2. 原理与来源

教材第 169–171 页给出合力与合矩为零，并建议选择能消去未知反力的矩心。将该方法映射到 Agent 的南北 `y` 轴，对南支点 `a` 取矩：

```text
R_south + R_north = sum(P_i)
R_north * (b - a) = sum(P_i * (y_i - a))
```

因此 `R_north = sum(P_i * (y_i - a)) / (b - a)`，南岸反力由总载荷减去北岸反力得到。这是本技能从原文平衡方程推导的两支承特例，不是教材直接给出的 Besiege 公式。

第 323–324 页说明接触合力不必作用在接触区中心。把地形边缘、整桥几何中心当作实际支点或载荷合力点都需要额外依据。

# 3. 环境映射与限制

`a/b` 为同一放置状态下南北接触法向合力的作用位置，单位为游戏长度单位，满足 `a < b`。`loads` 包括桥自重及货物，在同一单位下表示向下作用量。

尚未校准真实力单位时，可以用明示的归一化载荷作比例分析；不能把质量字段直接命名为牛顿。共同重力因子可用于比例抵消，但结果仍是相同标度下的等效反力，不是实测接触力。

负反力表示这一双接触假设需要地形“拉住”桥梁，与非黏着接触不符。反力接近零表示一侧卸载边界，不是可保留两侧稳定支承的证明。

# 4. Procedure

1. 从整体自由体模型确认二维、准静态、两个接触合力位置及全部载荷。
2. 对南岸取矩，计算两岸反力和载荷合力位置。
3. 有一侧卸载时，检查货物落点、桥端接触和模块偏心；不把负值截断为零后继续使用原模型。
4. 两侧均受压时，继续检查接触范围、侧向稳定及结构内力。相同总载荷下比较候选布置，不能用该函数优化未知强度。

# 5. 输入约定与参考策略

- `south_y/north_y`：有限数值，已转为 Agent 坐标的接触合力位置；来源为标记过的设计假设或接触观测。
- `loads`：非空的 `(y, downward_load)` 列表；位置与支点同坐标系，载荷有限且非负。桥自重不得隐式省略。
- `model_valid`：`True/False/None`，表示上文模型前提已核对、被否定或未知。它是条件分析的审核标记，不是物理通过标记。

```python
from math import fsum, isfinite


def estimate_vertical_reactions(south_y, north_y, loads, model_valid=None):
    result = {
        "status": "insufficient_evidence", "reason": "",
        "checks": [], "next_steps": [],
    }
    if type(model_valid) is not bool:
        result["reason"] = "model_assumptions_unconfirmed"
        return result
    if not model_valid:
        result.update(status="not_applicable", reason="outside_two_support_model")
        return result
    try:
        if not isinstance(loads, (list, tuple)) or not loads:
            raise ValueError
        if any(not isinstance(row, (list, tuple)) or len(row) != 2 for row in loads):
            raise ValueError
        values = [south_y, north_y] + [v for row in loads for v in row]
        if any(type(v) not in (int, float) or not isfinite(v) for v in values):
            raise ValueError
        length = north_y - south_y
        if not isfinite(length) or length <= 0 or any(p < 0 for _, p in loads):
            raise ValueError
        total = fsum(p for _, p in loads)
        if not isfinite(total) or total <= 0:
            raise ValueError
        north = fsum(p * ((y - south_y) / length) for y, p in loads)
        south = total - north
        center_y = south_y + (north / total) * length
        if not all(isfinite(v) for v in (north, south, center_y)):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        result["reason"] = "missing_or_invalid_numeric_inputs"
        return result
    tolerance = 1e-9 * total
    engaged = min(south, north) > tolerance
    result["checks"] = [{
        "name": "both_supports_compressed", "result": engaged,
        "basis": "force_and_moment_balance_in_reviewed_model",
    }, {
        "name": "three_dimensional_stability", "result": None,
        "basis": "not_computed",
    }]
    result["estimates"] = {
        "south_reaction": south, "north_reaction": north,
        "load_resultant_y": center_y,
        "units": "same_load_scale_as_inputs",
    }
    result["status"] = "candidate" if engaged else "not_applicable"
    result["reason"] = (
        "conditional_reactions_only" if engaged else "support_unloading_or_uplift"
    )
    result["next_steps"] = [{
        "kind": "review",
        "target": "contact_and_lateral_stability" if engaged else "load_and_support_layout",
    }]
    return result
```

`1e-9` 仅是相对于总载荷的浮点分类容差，不是物理安全余量。所有输出保持输入载荷标度；接触点变化后需要重新计算。

# 6. 最小自测

合成输入，未执行；在上方函数之后运行：

```python
symmetric = estimate_vertical_reactions(-3, 3, [(0, 10)], True)
assert symmetric["status"] == "candidate"
assert symmetric["estimates"]["south_reaction"] == 5
assert symmetric["estimates"]["north_reaction"] == 5
shifted = estimate_vertical_reactions(-3, 3, [(1.5, 8)], True)
assert shifted["estimates"]["south_reaction"] == 2
assert shifted["estimates"]["north_reaction"] == 6
assert estimate_vertical_reactions(-3, 3, [(3, 10)], True)["status"] == "not_applicable"
assert estimate_vertical_reactions(-3, 3, [(6, 10)], True)["status"] == "not_applicable"
assert estimate_vertical_reactions(-3, -3, [(0, 10)], True)["status"] == "insufficient_evidence"
assert estimate_vertical_reactions(-3, 3, [(0, float("nan"))], True)["status"] == "insufficient_evidence"
assert estimate_vertical_reactions(-3, 3, [], True)["status"] == "insufficient_evidence"
assert estimate_vertical_reactions(-3, 3, [(0, 10)])["status"] == "insufficient_evidence"
assert estimate_vertical_reactions(-3, 3, [(0, 10)], False)["status"] == "not_applicable"
```

# 7. Checklist

- 支点不是随意指定的地形边缘；载荷使用同一坐标、同一标度且包含自重。
- 未遗漏外加力偶或水平力的力矩；反力没有被人为截断。
- 正反力只作为后续检查的条件结果，三维稳定和连接强度仍未知。

# 8. 验证方案与证据

逻辑：对称、偏载、卸载、越界合力、非法输入的合成检查。几何：独立核对接触合力位置的可行区域。开发仿真：保持桥型和加载相同，观察不同偏心设计的接触丢失趋势；现有遥测不提供两岸反力，不能声称直接验证了反力数值。

全部动态与几何验证未运行。已有分析器分数不能验证这些条件估算。

# 9. 交给下一角色的结论

传递 `(south_y, north_y)` 的来源、全部载荷、合力位置、两岸反力标度以及卸载风险。若调整某个模块，更新该模块的 `design_requirements` 和全桥平衡清单，不能只修改整体描述。
