---
id: transport_lateral_rollover
title: 用轮距与装载质心检查准静态侧翻边界
summary: "Transport rollover lateral stability track width loaded center of gravity：比较横向加速度需求与刚性车辆侧翻边界，指导低货台与支承宽度；不把几何阈值当成安全转速。"
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [transport]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance, controller]
  stages: [plan, draft, build, control, refine]
  triggers: [转弯时抬起内侧轮, 货台过高, 加宽底盘, 装载后容易侧翻]
prerequisites:
  - 水平地面、横向居中质心、左右对称接地线，可忽略柔性及快速滚转响应
  - 货物若纳入整体质心，其随车运动的近似已得到支持
environment_constraints:
  - 轮距是接地作用线间距，不是车身最宽外轮廓
  - 刚性模型未覆盖积木连接变形、碰撞绊倒和货物下落冲击
  - 当前分析器的通过与 one_piece 不能证明没有侧翻
sources:
  - file: "skill/books/汽车理论 (余志生) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: 汽车理论
    authors: [余志生主编]
    edition: "第 5 版，机械工业出版社，2009 年 3 月"
    sha256: 671ecf1257274f39a1818b32822cc7d46edc7a648d60b594699e3a5203870420
    chapter: 第五章第八节
    pdf_pages: [210, 211, 212]
    printed_pages: [194, 195, 196]
    locator: "图 5-85，式 (5-44) 至 (5-46)；带悬架与瞬态侧翻的限制"
    license_status: unconfirmed
    supports: [刚性准静态侧翻由内侧轮法向力趋于零定义, 水平地面阈值为轮距除以两倍质心高度, 柔性和快速瞬态会使刚性估计失准]
code_evidence:
  - path: levels.yaml
    symbol: transport.medium / transport.hard
    supports: 货物自由放置，Hard 还要求返回起点
  - path: simulation/simulation_transport.py
    symbol: main
    supports: 货物由适配器放入，构建几何不等于落稳后的装载状态
  - path: analyze/sim_transport.py
    symbol: analyze_simulation_transport / _analyze_wheel_consistency
    supports: 通过条件与轮间距离统计不是侧翻角和轮载的测量
validation:
  human_review: pending
  logic_tests: not_run
  geometry_checks: not_run
  physics_trials: not_run
  evidence: []
---

# 1. 何时使用与何时不用

用于比较同一模型下的货台高度、质心高度与轮距候选，或检查转弯控制的横向需求。偏置货物、悬空轮子、快速交替转向、明显侧倾、碰撞绊倒及不规则支承区域不适用这个居中刚性模型。

# 2. 原理与来源

印刷页 194 区分转向引起的侧翻和碰撞绊倒；本模型只处理前者。页 195 式 (5-46) 在水平地面、内侧轮载荷降为零时给出：

```text
critical_lateral_accel_over_g = track / (2 * cg_height)
demand = abs(lateral_accel_over_g)
```

降低质心、增加有效轮距可提高此模型的边界。教材同时警告刚性准静态估计可能偏高；页 196 说明弹性侧倾、轮胎变形及快速瞬态的影响。这里的边界不是已经包含安全系数的允许值。

# 3. 环境映射与限制

轮距和质心高度均以落稳后支承平面为基准，使用同一游戏长度标度。Agent `[东, 北, 上]` 中的世界高度要扣除地面高度，横向要先投影到车体左右方向。

货物不固定时，先验证其相对底盘的位置与接触；把滑动货物算成固定的整体质心会丢掉关键失效。实际质量未知时不把积木中心平均值代替质心。

规划建议是保持货台低、有效支承宽度明确，并避免未经校准的大幅转向脉冲。这是候选取舍，不保证最优轮距。即使侧翻指标有余量，轮地可能先侧滑，货物也可能先滑出。硬质四轮差动转向更不能直接用无滑移车速公式推算本输入。

# 4. Procedure

1. 核对质心是否横向居中、轮距是否对应有效接地线，以及货物是否落稳。
2. 前提不成立时改用真实支承区域与三维运动证据，不继续套本式。
3. 参数有依据时比较横向需求与边界；参数未知时输出低货台、明确支承宽度及低强度校准要求。
4. 边界内继续检查侧滑与货物保持；边界外修改一个几何或控制变量后再观察，不直接认定游戏必然翻车。
5. 急转中的实际抬轮或明显侧倾一旦出现，停止沿用准静态假设，不用持续加长动作来试探。

# 5. 输入约定与参考策略

`track/cg_height` 为有限正长度；`lateral_accel_over_g` 为有符号横向加速度与同一场景重力加速度之比。三者记录来源及空车/装载状态。未知值用 `None`，不由默认 100 rpm 或地球重力推断。

`rigid_model_valid` 为 `True/False/None`，确认水平、居中、刚性、准静态以及货物运动前提。代码不查询引擎状态，不预测翻转时间或角度。

```python
from math import isfinite


def check_lateral_rollover(track, cg_height, lateral_accel_over_g,
                            rigid_model_valid=None):
    result = {
        "status": "insufficient_evidence", "reason": "rigid_roll_model_unconfirmed",
        "checks": [],
        "next_steps": [{"kind": "review", "target": "loaded_cg_contacts_and_slow_turn_basis"}],
    }
    if rigid_model_valid is False:
        result.update(status="not_applicable", reason="outside_centered_rigid_roll_model")
        return result
    if rigid_model_valid is not True:
        return result
    try:
        values = (track, cg_height, lateral_accel_over_g)
        if any(type(v) not in (int, float) or not isfinite(v) for v in values):
            raise ValueError
        if track <= 0 or cg_height <= 0:
            raise ValueError
        limit = track / cg_height / 2
        demand = abs(lateral_accel_over_g)
        margin = limit - demand
        if not all(isfinite(v) for v in (limit, margin)) or limit <= 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        result["reason"] = "missing_or_invalid_numeric_inputs"
        return result
    reserve = margin > 1e-9 * max(limit, demand)
    result["estimates"] = {"rigid_roll_limit_over_g": limit, "margin_over_g": margin}
    result["checks"] = [
        {"name": "rigid_roll_reserve", "result": reserve, "basis": "centered_quasistatic_model"},
        {"name": "lateral_slip_and_cargo_retention", "result": None, "basis": "not_computed"},
    ]
    result.update(status="candidate" if reserve else "not_applicable",
                  reason="conditional_roll_reserve_only" if reserve
                  else "at_or_beyond_rigid_roll_boundary")
    result["next_steps"] = [{"kind": "review",
                              "target": "sliding_cargo_and_transient_response" if reserve
                              else "lower_loaded_cg_or_reduce_lateral_demand"}]
    return result
```

浮点容差仅用于数值分类，未引入游戏实测安全裕度。

# 6. 最小自测

合成输入，未执行：

```python
ok = check_lateral_rollover(4, 2, 0.5, True)
assert ok["status"] == "candidate"
assert ok["estimates"]["rigid_roll_limit_over_g"] == 1
assert ok["checks"][1]["result"] is None
assert check_lateral_rollover(4, 2, -0.5, True)["status"] == "candidate"
assert check_lateral_rollover(4, 2, 1, True)["status"] == "not_applicable"
assert check_lateral_rollover(4, 2, 2, True)["status"] == "not_applicable"
assert check_lateral_rollover(4, 0, 0.5, True)["status"] == "insufficient_evidence"
assert check_lateral_rollover(-4, 2, 0.5, True)["status"] == "insufficient_evidence"
assert check_lateral_rollover(4, None, 0.5, True)["status"] == "insufficient_evidence"
assert check_lateral_rollover(4, 2, True, True)["status"] == "insufficient_evidence"
assert check_lateral_rollover(4, 2, float("nan"), True)["status"] == "insufficient_evidence"
assert check_lateral_rollover(4, 2, 0.5, False)["status"] == "not_applicable"
assert check_lateral_rollover(4, 2, 0.5)["status"] == "insufficient_evidence"
```

# 7. Checklist

- 使用前：逻辑核对模型前提；几何核对有效轮距与实际支承平面。
- 使用后：区分整体侧翻、轮地侧滑、货物相对滑移与连接失效。
- 仿真观察内侧轮离地、车身倾斜和货物位置，不将分析器 `pass` 或 `one_piece` 当作替代证据。

# 8. 验证方案与证据

开发场景中固定载荷和轮组动作，每次只比较一个质心高度或轮距变化。观测侧倾、接地状态和货物保持；快速动态失效不能用于拟合本准静态模型的“精确阈值”。如缺姿态与接地观测，只能记录预测未验证。本轮未执行代码、几何检查或物理仿真。

# 9. 交给下一角色的结论

在 `design_requirements` 保留 `transport_lateral_rollover@0.1.0`、低货台与支承宽度的实际要求、质心假设和待查侧滑。Controller 接收条件需求或校准限制，不接收“按某键若干秒必然安全”的承诺。

控制限制须另写一份短结论到 `overall_structure.motion_control`，以适配 `script/run_simulation.py::init_simulation_db` 的现有交接，不依赖 Controller 读取子结构全文或主动检索。
