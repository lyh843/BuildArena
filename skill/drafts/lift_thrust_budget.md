---
id: lift_thrust_budget
title: 用竖直推力区间核算整机起飞预算
summary: "Lift rocket thrust weight budget 起飞推重比：把水炮反冲投影到竖直方向，计入火把、底盘和 Brace 的全部质量；区分冷态、蒸汽态与未知加热，给出减重或补足推力的条件决策。"
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [lift]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance]
  stages: [plan, draft, build, assemble]
  triggers: [选择水炮数量, 发动机能推但整机不起飞, 加固导致质量增加, 蒸汽状态未知]
prerequisites:
  - 全部最终积木质量和各水炮反冲方向已纳入同一工况
  - 推力除以同一参考重力后的等效质量标度与整机质量可比较
environment_constraints:
  - 不把水炮 bmt-strength 当作可任意调节的实测推力
  - 火把质量与积木成本不同；不能用块数或 cost 代替质量
  - 没有燃料消耗证据，不使用变质量火箭速度公式
sources:
  - file: "skill/books/Rocket Propulsion Elements (George P. Sutton, Oscar Biblarz) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: Rocket Propulsion Elements
    edition: "Ninth Edition, Wiley, 2017"
    chapter: "2.1, 2.5, 4.3"
    pdf_pages: [53, 62, 130, 131]
    printed_pages: [29, 38, 106, 107]
    locator: "thrust-to-weight ratio; Eq. 2-23; Eq. 4-13"
    license_status: unconfirmed
    supports: [推力质量比必须明确系统边界, 同时同向推力相加, 重力和推力方向影响加速]
  - file: "skill/books/理论力学（第9版）（I） (哈尔滨工业大学理论力学教研室) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: 理论力学
    edition: "第9版 I，高等教育出版社；出版年未核实"
    chapter: "10-3 质心运动定理"
    pdf_pages: [295]
    printed_pages: [265]
    locator: "式 10-14"
    license_status: unconfirmed
    supports: [质量不变系统的质心加速度由外力合力决定]
code_evidence:
  - path: blocks/configs/water_cannon.yaml
    symbol: weight / description / data
    supports: 配置质量1.5，普通反冲标称1.6等效质量，蒸汽倍数8.6，强度配置4
  - path: analyze/sim_lift.py
    symbol: _calculate_propulsion_forces / analyze_simulation_lift
    supports: 分析器按13.76和1.6计数估算，Soft阈值为effective大于1
  - path: analyze/sim_common.py
    symbol: calculate_total_mass
    supports: 指标质量来自配置weight的求和，不是游戏中的力传感器
validation:
  human_review: pending
  logic_tests: not_run
  geometry_checks: not_run
  physics_trials: not_run
  evidence: []
---

# 1. 何时使用与何时不用

Planner 为发动机和最终整机分配质量，Drafter 增加火把、木块、Brace 后重新预算。仅判断同一姿态和工况的竖直推力余量；不能由此预测最高高度、热稳定性或连接强度。

# 2. 原理与来源

Rocket 印刷页29要求明确推重比对应发动机还是整机；页38的标量相加以同时同向为前提。页107与《理论力学》页265支持 `m*a_z = sum(T_z) - m*g` 的受限竖直模型。本技能将其改写为参考重力下的等效质量比较，不引入地球重力数值。

仓库标称冷态1.6、蒸汽态13.76仅作为配置代理。已核定冷态可用区间 `[1.6,1.6]`；假设蒸汽态用 `[13.76,13.76]` 并标注未验证；加热未知可比较 `[1.6,13.76]`。这个区间还要求水炮确实持续喷射且未失效，否则下界不能乐观设为1.6。

# 3. 环境映射与限制

Agent 坐标 `[东,北,上]`，水炮喷流方向与反冲相反；`up_cos` 是**反冲**单位向量的第三分量。内部 `Vector.virtual` 需先交换第二、第三分量，不能直接取其第三分量。

总质量包括起始块、所有水炮、火把、底盘、连接件及 Hard 复制实例。成本独立记录；火把配置 `weight=1, cost=13`。分析器并不做此方向投影，且其 `active` 依据被跟踪水炮出现过 `burning=true`，不等于全程持续高推力。不要照着宽松指标制造朝向错误的机器。

# 4. Procedure

1. 在最终装配边界列质量清单；缺件、未知方向或缺少喷射状态依据时保留缺口。
2. 先算全冷、预期蒸汽与加热不确定三种情景，再对每个反冲做竖直投影。
3. 即使上界也不够时，重新分配非推进质量或推进单元；区间跨过要求时优先核对加热，不宣称起飞。
4. 下界有余量后继续检查偏心力矩和连接。每次方案修改重新计算一次，停止于下一项真实观察，不自动加块。

# 5. 输入约定与参考策略

- `mass`：有限正数，最终配置质量或同标度实测质量，来源必须写入计划。
- `cannons`：非空清单，每项 `strength=[下界,上界]` 为有限非负等效质量，`up_cos` 在 `[-1,1]`；这是整理后的输入，非工具返回结构。
- `reserve_fraction`：显式有限非负设计余量；0表示只看严格起飞边界，不是推荐安全系数。
- `model_valid`：`True/False/None`，分别表示当前受限模型已核对、明确不成立、未知。已核对代理模型也仍非物理证据。

```python
from math import isfinite


def check_lift_budget(mass, cannons, reserve_fraction, model_valid=None):
    out = {"status": "insufficient_evidence", "reason": "model_unconfirmed",
           "checks": [{"name": "vertical_reserve", "result": None,
                       "basis": "complete_mass_and_thrust_intervals_required"}],
           "next_steps": [{"kind": "review", "target": "mass_direction_firing_and_heat"}]}
    if model_valid is False:
        out.update(status="not_applicable", reason="outside_fixed_pose_model")
        return out
    if model_valid is not True:
        return out
    def number(v):
        return type(v) in (int, float) and isfinite(v)
    try:
        if not number(mass) or mass <= 0 or not number(reserve_fraction) or reserve_fraction < 0:
            raise ValueError
        if not isinstance(cannons, (list, tuple)) or not cannons:
            raise ValueError
        lower = upper = 0.0
        for cannon in cannons:
            lo, hi = cannon["strength"]
            cosine = cannon["up_cos"]
            if not all(number(v) for v in (lo, hi, cosine)):
                raise ValueError
            if not 0 <= lo <= hi or not -1 <= cosine <= 1:
                raise ValueError
            lower += min(lo * cosine, hi * cosine)
            upper += max(lo * cosine, hi * cosine)
        required = mass * (1 + reserve_fraction)
        if not all(isfinite(v) for v in (lower, upper, required, lower / mass, upper / mass)):
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError):
        out["reason"] = "missing_or_invalid_inputs"
        return out
    out["estimates"] = {"vertical_equivalent_mass": [lower, upper],
                        "ratio": [lower / mass, upper / mass], "required": required}
    verdict = True if lower > required else False if upper <= required else None
    out["checks"] = [{"name": "vertical_reserve", "result": verdict,
                      "basis": "declared_fixed_pose_interval_model"}]
    if verdict is True:
        out.update(status="candidate", reason="conditional_reserve")
        out["next_steps"] = [{"kind": "review", "target": "moments_and_startup"}]
    elif verdict is False:
        out.update(status="not_applicable", reason="declared_reserve_unmet_even_at_upper_bound")
        out["next_steps"] = [{"kind": "redesign", "target": "mass_or_propulsion_allocation"}]
    else:
        out["reason"] = "heat_or_thrust_uncertainty_changes_decision"
    return out
```

# 6. 最小自测

合成输入，未执行；13.76是代码标称值，不是本次测量：

```python
hot = [{"strength": [13.76, 13.76], "up_cos": 1}]
assert check_lift_budget(5, hot, 0, True)["status"] == "candidate"
assert check_lift_budget(13.76, hot, 0, True)["status"] == "not_applicable"
assert check_lift_budget(5, [{"strength": [1.6, 13.76], "up_cos": 1}], 0, True)["status"] == "insufficient_evidence"
assert check_lift_budget(5, [{"strength": [1, 2], "up_cos": -1}], 0, True)["estimates"]["vertical_equivalent_mass"] == [-2, -1]
assert check_lift_budget(5, [], 0, True)["status"] == "insufficient_evidence"
assert check_lift_budget(None, hot, 0, True)["status"] == "insufficient_evidence"
assert check_lift_budget(True, hot, 0, True)["status"] == "insufficient_evidence"
assert check_lift_budget(5, hot, float("nan"), True)["status"] == "insufficient_evidence"
assert check_lift_budget(5, hot, 0, False)["status"] == "not_applicable"
assert check_lift_budget(5, hot, 0)["status"] == "insufficient_evidence"
```

# 7. Checklist

- 逻辑：总质量边界完整、方向符号正确、加热假设显式、区间不冒充校准。
- 工具：实际块数、喷口朝向和装配后的姿态对应预算版本。
- 物理：持续喷射、实际离地、整体连接与竖直轨迹均待验证。

# 8. 验证方案与证据

开发试验固定布局和原有点火时序，比较一种质量修改或一种加热布局修改；记录逐水炮热状态、离地时刻和完整轨迹。不能用分析器 `effective>1` 单独确认真实升空。没有执行逻辑函数、几何重放或仿真。

# 9. 交给下一角色的结论

各相关 `sub_structure.design_requirements` 写入 `lift_thrust_budget@0.1.0`、分配质量、反冲朝向、冷/热预算和加热缺口。Hard 另在总装说明写最终实例数及总质量；不只汇报独立发动机的推重比，不传完整代码。
