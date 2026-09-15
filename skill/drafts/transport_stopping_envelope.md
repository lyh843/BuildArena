---
id: transport_stopping_envelope
title: 为目标点停车和返程预留制动距离与时间
summary: "Transport braking stopping distance deceleration return route：使用同载荷下的车速上界、减速度下界和动作延迟上界检查停车预算，避免越过目标后才反向；不把反转按键当作瞬间制动。"
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [transport]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, controller]
  stages: [plan, draft, control, refine]
  triggers: [冲过目标点, 松键后仍在移动, Hard 需要返程, 控制窗口不足以停车]
prerequisites:
  - 同一机器载荷和地面的直线减速模型已核对，延迟期间速度不超过给定上界
  - 减速度下界在响应延迟结束后直至停止均成立，不是单帧峰值
environment_constraints:
  - 控制是预先生成的按键时间序列，不是新增的实时闭环控制器
  - 自动制动配置不等于已知减速度，反转动作也不等于瞬间停止
  - 30 秒仿真窗口需要同时容纳出发、转向、到达以及 Hard 的返程
sources:
  - file: "skill/books/汽车理论 (余志生) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: 汽车理论
    authors: [余志生主编]
    edition: "第 5 版，机械工业出版社，2009 年 3 月"
    sha256: 671ecf1257274f39a1818b32822cc7d46edc7a648d60b594699e3a5203870420
    chapter: 第四章第三节
    pdf_pages: [113, 114, 115]
    printed_pages: [97, 98, 99]
    locator: "制动距离与制动减速度；图 4-14；式 (4-6) 前的持续制动积分"
    license_status: unconfirmed
    supports: [制动距离取决于初速度与减速度, 制动建立需要时间, 停车计算应区分响应阶段和持续减速阶段]
code_evidence:
  - path: blocks/configs/powered_wheel.yaml
    symbol: data.bmt-auto-brake / locomotion
    supports: 有自动制动配置和反向转动动作，但没有实测制动能力
  - path: prompt.yaml
    symbol: agents.controller.system_message
    supports: Controller 输出定时按键 JSON 与有限控制窗口
  - path: script/run_simulation.py
    symbol: init_simulation_db
    supports: 初次控制任务接收原任务以及总计划的功能和运动控制说明
  - path: simulation/simulation_transport.py
    symbol: main
    supports: 仿真调用的 duration 为 30
  - path: levels.yaml
    symbol: transport
    supports: 目标为东北目标点，Hard 还需返回起点
  - path: analyze/sim_transport.py
    symbol: analyze_simulation_transport
    supports: 距起点的最大位移通过条件不能代替到达与返程验证
validation:
  human_review: pending
  logic_tests: not_run
  geometry_checks: not_run
  physics_trials: not_run
  evidence: []
---

# 1. 何时使用与何时不用

用于 Planner 为路线划分加速、减速和转向阶段，以及 Controller 在有校准依据时检查停车预算。强烈转弯、货物滑移、车身碰撞、坡度或持续加速导致速度越过输入上界时，不用本直线包络。

# 2. 原理与来源

印刷页 97–99 将制动建立阶段与持续减速阶段分开，给出恒定减速度下的平方速度项。本技能没有照搬真实驾驶员反应时间或书中的公里每小时换算常数，而是自行整理为游戏统一单位下的条件上界：

```text
stop_distance_upper = speed_upper * delay_upper + speed_upper**2 / (2 * decel_lower)
stop_time_upper = delay_upper + speed_upper / decel_lower
```

成立前提：延迟段速度不超过 `speed_upper`，之后到停止前的减速度不小于 `decel_lower > 0`，且无反复驱动。它是带假设的包络，不是单次轨迹拟合就能保证的安全距离。

# 3. 环境映射与限制

全部距离为游戏长度、时间为秒，速度为游戏长度/秒；不是米、公里每小时混算。`delay_upper` 是本次制动动作的响应与建立上界，不是 LLM 生成整份控制序列的墙钟耗时。

当前 Controller 一次输出时间序列，不能“运行时发现到点再调工具”。应先利用允许的试验反馈形成保守候选时序，再独立验证。自动制动开关、倒转按键均需在相同载荷下校准。

目标仍是地面 `(东 10, 北 10)`；Hard 还要返程。分析器的最大离起点距离大于 10 不能代替这两个要求。`distance_available` 必须是当前停车段的可用路程，不可直接用距起点的位移或固定目标坐标充当。

# 4. Procedure

1. 区分首次到达、转向前停车与返程结束停车，确定对应路线段和剩余窗口。
2. 没有同载荷减速证据时，仅安排一次低速制动校准候选，不编造停车时长。
3. 用速度上界、延迟上界和持续减速度下界计算包络，另外声明人为选择的距离余量。
4. 距离或时间不足则降低计划速度、提前制动或调整路线；不能通过删去 Hard 返程让预算看起来足够。
5. 下一次动作以反馈为依据，保持任务原有最多三次控制尝试，不在技能里启动额外循环。

# 5. 输入约定与参考策略

所有数值必须有限且非布尔。`speed_upper >= 0`、`decel_lower > 0`、`delay_upper >= 0`。`distance_available`、`buffer_distance`、`time_available` 均非负；后者是当前停车段真正剩余时间，不自动等于 30。

三个运动界限来自同机器、轮子动作、地面与载荷的校准记录；不足以建立界限时填 `None`。`buffer_distance` 为显式设计余量，须记录选择依据，不声称来自教材或游戏默认值。`braking_model_valid` 为三态前提确认。

```python
from math import isfinite


def check_stopping_envelope(speed_upper, decel_lower, delay_upper,
                             distance_available, buffer_distance, time_available,
                             braking_model_valid=None):
    result = {
        "status": "insufficient_evidence", "reason": "braking_bounds_unconfirmed",
        "checks": [],
        "next_steps": [{"kind": "validation_plan",
                        "target": "same_load_straight_braking_and_response_bounds"}],
    }
    if braking_model_valid is False:
        result.update(status="not_applicable", reason="outside_straight_braking_envelope")
        return result
    if braking_model_valid is not True:
        return result
    try:
        values = (speed_upper, decel_lower, delay_upper, distance_available,
                  buffer_distance, time_available)
        if any(type(v) not in (int, float) or not isfinite(v) for v in values):
            raise ValueError
        if any(v < 0 for v in values) or decel_lower == 0:
            raise ValueError
        stop_time = delay_upper + speed_upper / decel_lower if speed_upper else 0
        stop_distance = speed_upper * delay_upper + (speed_upper / decel_lower) * speed_upper / 2
        distance_margin = distance_available - stop_distance - buffer_distance
        time_margin = time_available - stop_time
        if not all(isfinite(v) for v in (stop_time, stop_distance, distance_margin, time_margin)):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        result["reason"] = "missing_or_invalid_numeric_inputs"
        return result
    distance_ok = distance_margin > 1e-9 * max(distance_available, stop_distance, buffer_distance)
    time_ok = time_margin > 1e-9 * max(time_available, stop_time)
    result["estimates"] = {"stop_distance_upper": stop_distance, "stop_time_upper": stop_time,
                           "distance_margin": distance_margin, "time_margin": time_margin}
    result["checks"] = [
        {"name": "distance_reserve", "result": distance_ok, "basis": "reviewed_motion_bounds"},
        {"name": "time_reserve", "result": time_ok, "basis": "remaining_segment_budget"},
    ]
    reserve = distance_ok and time_ok
    result.update(status="candidate" if reserve else "not_applicable",
                  reason="conditional_stopping_budget" if reserve else "stopping_budget_exhausted")
    result["next_steps"] = [{"kind": "review",
                              "target": "cargo_retention_and_complete_route" if reserve
                              else "lower_speed_or_begin_braking_earlier"}]
    return result
```

达到边界表示没有额外正余量，不等于已经冲过目标。浮点阈值不是另一个隐藏安全系数。

# 6. 最小自测

合成数据，未执行：

```python
ok = check_stopping_envelope(4, 2, 0.5, 8, 1, 4, True)
assert ok["status"] == "candidate"
assert ok["estimates"]["stop_distance_upper"] == 6
assert ok["estimates"]["stop_time_upper"] == 2.5
assert check_stopping_envelope(4, 2, 0.5, 7, 1, 4, True)["status"] == "not_applicable"
assert check_stopping_envelope(4, 2, 0.5, 8, 1, 2.5, True)["status"] == "not_applicable"
assert check_stopping_envelope(0, 2, 0.5, 2, 1, 1, True)["estimates"]["stop_time_upper"] == 0
assert check_stopping_envelope(4, 0, 0.5, 8, 1, 4, True)["status"] == "insufficient_evidence"
assert check_stopping_envelope(4, None, 0.5, 8, 1, 4, True)["status"] == "insufficient_evidence"
assert check_stopping_envelope(4, 2, True, 8, 1, 4, True)["status"] == "insufficient_evidence"
assert check_stopping_envelope(4, 2, -1, 8, 1, 4, True)["status"] == "insufficient_evidence"
assert check_stopping_envelope(float("inf"), 2, 0.5, 8, 1, 4, True)["status"] == "insufficient_evidence"
assert check_stopping_envelope(4, 2, 0.5, 8, 1, 4, False)["status"] == "not_applicable"
assert check_stopping_envelope(4, 2, 0.5, 8, 1, 4)["status"] == "insufficient_evidence"
```

# 7. Checklist

- 使用前：检查界限来源、单位、载荷一致性及剩余路程的定义。
- 使用后：控制序列无相反动作冲突，停车之外仍有转向或返程时间。
- 物理另查货物保持、实际停止和目标位置；最大运输距离不是停车准确性。

# 8. 验证方案与证据

在开发场景固定机器与货物，记录短直线运行后的松键或已核定制动动作，估计全过程速度与响应范围。单帧峰值减速度不得作持续下界；轨迹采样和测量误差需保留。失效包括越过停车区、窗口内未停、制动时货物滑出。没有实测记录，未运行参考策略。

# 9. 交给下一角色的结论

Planner 在 `design_requirements` 保留 `transport_stopping_envelope@0.1.0`、停车阶段与控制可用性要求。Controller 保留经过核对的运动界限、路线段、显式余量和未验证项，继续输出原有 JSON，不输出新协议。

Planner 同时在 `overall_structure.motion_control` 写下停车与返程预算的短结论，才能进入现有控制任务输入；只写在子结构或蓝图里不保证 Controller 能看到。
