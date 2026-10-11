---
id: lift_startup_asymmetry
title: 检查启动热失配产生的角冲量
summary: "Lift startup transient asymmetry angular impulse 启动不同步：一侧先产生蒸汽推力时，最终对称也无法消除已经积累的转动；用短时力差与力臂评估条件风险，保持原有固定点火时序。"
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [lift]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance]
  stages: [plan, draft, build, assemble]
  triggers: [左右加热时间不一致, 最终推力相等但仍旋转, 扩大水炮离轴距离, 点火后短时翻转]
prerequisites:
  - 只分析关于一个轴的短时定力矩近似，不能把它扩展为完整三维飞行求解
  - 力差持续时间和力臂有测量依据或被明确标为情景假设
environment_constraints:
  - Lift不经过Transport的Controller调参回路
  - 所有水炮在仿真时被映射到同一Alpha1并从2秒开始持续触发
  - 没有自动等待全炮受热、单炮节流或姿态闭环
sources:
  - file: "skill/books/理论力学（第9版）（I） (哈尔滨工业大学理论力学教研室) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: 理论力学
    edition: "第9版 I，高等教育出版社；出版年未核实"
    chapter: "11-5 质点系相对于质心的动量矩定理"
    pdf_pages: [316, 317, 318]
    printed_pages: [286, 287, 288]
    locator: "式11-23"
    license_status: unconfirmed
    supports: [外力对质心的主矩决定动量矩变化, 后续主矩为零并不使既有动量矩消失]
  - file: "skill/books/Rocket Propulsion Elements (George P. Sutton, Oscar Biblarz) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: Rocket Propulsion Elements
    edition: "Ninth Edition, Wiley, 2017"
    chapter: "2.1 Definitions; 3.6 Nozzle Alignment; 4.9 Flight Stability"
    pdf_pages: [50, 116, 172]
    printed_pages: [26, 92, 148]
    locator: "时变推力积分；启动瞬态；稳定力矩"
    license_status: unconfirmed
    supports: [不能无条件忽略启动过程, 平衡布局和抗扰稳定需分别判断]
code_evidence:
  - path: simulation/simulation_lift.py
    symbol: main
    supports: 2秒开始触发同一按键，Soft仿真10秒，其余30秒
  - path: spatial/build.py
    symbol: Machine.to_xml
    supports: 输出被跟踪水炮burning状态，未输出转动惯量或全机角动量
  - path: scheduler/runner.py
    symbol: run_control / run_simulation
    supports: Lift使用自身适配器而非Transport控制优化
validation:
  human_review: pending
  logic_tests: not_run
  geometry_checks: not_run
  physics_trials: not_run
  evidence: []
---

# 1. 何时使用与何时不用

含多个水炮的发动机或总装火箭，在比较同步供热与不同步供热情景时使用。已在地面发生倾覆、支撑碰撞或进入大角度转动时，下面的自由飞行短时模型不适用，应单独分析接触和姿态。

# 2. 原理与来源

《理论力学》页288的 `dL_C/dt = sum(M_C)` 表明力矩会积累角动量。对关于某轴近似恒定的短时不平衡，积分得 `delta_L = lever * thrust_difference * duration`。这是教材方程在本技能假设下的推导。

当对称两侧均已进入相同推力状态，新的力矩可降为零，但之前积累的角动量不会因此归零。Rocket 页148指出稳定依赖恢复或控制力矩；本项目没有已验证的自动纠偏，因此优先缩小启动失配和无必要的离轴距离，而非依赖事后自动恢复。

# 3. 环境映射与限制

水炮点火按键同步不等于热状态同步。当前适配器从2秒触发，Soft写入持续10秒、实际观测10秒；Medium/Hard写入持续30秒、实际观测30秒。按脚本时间窗口，记录中可见的喷射段约为8/28秒，不能假设记录包含完整的10/30秒喷射或停止后的恢复。

力使用一致的游戏力标度；若采用1.6与13.76的等效质量差，结果只是归一化角冲量代理，不能直接解释为真实角动量或角速度。没有转动惯量和姿态数据，不输出翻转角度或时间。只随机跟踪部分块时，未见某水炮变热属于数据缺失。

# 4. Procedure

1. 为每对离轴水炮写启动情景：相同供热、单侧提前受热、供热中断。
2. 有适用的短时输入时计算角冲量；未知失配时长保持未知，不能按0秒处理。
3. 角冲量超过预先声明的开发比较限值时，优先改善配对供热、缩短力臂或减小瞬态力差。
4. 保持正式点火协议；提交一个布局改动并观察，不自动修改控制器或追加仿真轮数。

# 5. 输入约定与参考策略

`lever` 为关于所选轴的有效非负力臂，单位游戏长度；对称两侧各距轴r时用r，不用两炮总间距2r。`thrust_difference` 为带符号的恒定力差，`duration` 为有限非负持续秒数。`impulse_limit` 为同标度角冲量的显式非负比较限值，须有开发方案依据，并非通用稳定阈值。`free_flight_model` 三态说明力矩主导的短时近似是否可用。

```python
from math import isfinite


def check_startup_asymmetry(lever, thrust_difference, duration, impulse_limit,
                            free_flight_model=None):
    out = {"status": "insufficient_evidence", "reason": "short_interval_model_unconfirmed",
           "checks": [{"name": "angular_impulse_limit", "result": None,
                       "basis": "known_or_declared_startup_scenario_required"}],
           "next_steps": [{"kind": "review", "target": "heat_timing_contact_and_force_basis"}]}
    if free_flight_model is False:
        out.update(status="not_applicable", reason="contact_or_large_rotation_requires_other_model")
        return out
    if free_flight_model is not True:
        return out
    try:
        values = (lever, thrust_difference, duration, impulse_limit)
        if any(type(v) not in (int, float) or not isfinite(v) for v in values):
            raise ValueError
        if min(lever, duration, impulse_limit) < 0:
            raise ValueError
        torque = lever * thrust_difference
        impulse = torque * duration
        if not isfinite(torque) or not isfinite(impulse):
            raise ValueError
    except (ValueError, OverflowError):
        out["reason"] = "missing_invalid_or_nonfinite_inputs_and_estimate"
        return out
    within = abs(impulse) <= impulse_limit
    out.update(status="candidate" if within else "not_applicable",
               reason="conditional_impulse_limit" if within else "startup_impulse_requires_redesign")
    out["estimates"] = {"torque": torque, "angular_impulse": impulse}
    out["checks"] = [{"name": "angular_impulse_limit", "result": within,
                      "basis": "declared_constant_torque_scenario_and_limit"},
                     {"name": "flight_stability", "result": None,
                      "basis": "inertia_attitude_and_restoring_response_not_measured"}]
    out["next_steps"] = [{"kind": "review" if within else "redesign",
                          "target": "startup_observation" if within else "matched_heating_or_smaller_lever"}]
    return out
```

# 6. 最小自测

合成情景，未执行：

```python
assert check_startup_asymmetry(2, 3, 0.5, 3, True)["estimates"]["angular_impulse"] == 3
assert check_startup_asymmetry(2, 3, 0.5, 3, True)["status"] == "candidate"
assert check_startup_asymmetry(2, 3, 0.5, 2, True)["status"] == "not_applicable"
assert check_startup_asymmetry(2, -3, 0.5, 3, True)["estimates"]["angular_impulse"] == -3
assert check_startup_asymmetry(2, 3, 0, 0, True)["status"] == "candidate"
assert check_startup_asymmetry(2, 3, None, 3, True)["status"] == "insufficient_evidence"
assert check_startup_asymmetry(2, 3, -1, 3, True)["status"] == "insufficient_evidence"
assert check_startup_asymmetry(2, float("nan"), 1, 3, True)["status"] == "insufficient_evidence"
assert check_startup_asymmetry(2, 3, 1, 3, False)["status"] == "not_applicable"
assert check_startup_asymmetry(2, 3, 1, 3)["status"] == "insufficient_evidence"
```

# 7. Checklist

- 逻辑：力臂不是两炮间距，时长不是总仿真时长，0失配只能来自明确情景或观测。
- 工具：逐炮加热布局、最终离轴距离和点火协议与输入对应。
- 物理：检查启动期间的支撑接触、热失配和转动；最终零力矩不代表已经停止转动。

# 8. 验证方案与证据

开发对照只改变配对加热布局，保持炮数、总质量、点火时序和场景一致。记录热状态首次出现时刻与持续性、初始偏转、离地和漂移。若数据缺少其中一炮或缺少姿态，不反推出确定角冲量；独立诊断才增加观测，不静默改变正式协议。本轮没有执行逻辑、几何或物理验证。

# 9. 交给下一角色的结论

`design_requirements` 写 `lift_startup_asymmetry@0.1.0`、同供热要求、力臂约束和待测时长；`overall_structure.motion_control` 只说明原有同步持续触发，不要求不存在的自动姿态闭环。
