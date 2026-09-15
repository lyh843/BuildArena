---
id: transport_differential_yaw
title: 用左右轮组的独立动作形成可校准的差动转向
summary: "Transport differential steering skid steer yaw moment wheel control：常规前轮转向不可用时规划左右轮组分控，检查纵向力差的横摆作用；不由按键时长直接承诺转角。"
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [transport]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance, controller]
  stages: [plan, draft, build, control, refine]
  triggers: [只有前进没有转向, 全部轮子绑定相同动作, 左右轮动作相互抵消, Hard 返程需要改变航向]
prerequisites:
  - 真实轮组、动作方向和分控能力已经核对
  - 定量力矩只针对已明确的轮地纵向合力，不等价于整车净横摆力矩
environment_constraints:
  - 当前没有常规汽车转向机构、差速器或连续扭矩分配工具
  - Controller 输出原有控制 JSON，不直接调用构建或改键工具
  - 四轮刚性差动转向涉及轮胎侧向滑移，不能直接套理想两轮差速运动学
sources:
  - file: "skill/books/汽车理论 (余志生) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: 汽车理论
    authors: [余志生主编]
    edition: "第 5 版，机械工业出版社，2009 年 3 月"
    sha256: 671ecf1257274f39a1818b32822cc7d46edc7a648d60b594699e3a5203870420
    chapter: 第五章第六节
    pdf_pages: [199, 200, 201]
    printed_pages: [183, 184, 185]
    locator: "地面切向反作用力控制转向特性；内、外侧车轮间切向力分配的控制"
    license_status: unconfirmed
    supports: [纵向驱动与制动力会影响转向, 左右纵向力分配可以产生横摆力偶矩, 驱动与侧向能力相互影响]
code_evidence:
  - path: levels.yaml
    symbol: transport
    supports: 不提供常规前轮转向，要求替代转向机制
  - path: blocks/configs/powered_wheel.yaml
    symbol: locomotion / spin / data
    supports: 轮子有前后转动动作，实际世界方向取决于装配与翻转状态
  - path: prompt.yaml
    symbol: agents.controller.system_message
    supports: 控制输出为 control_config 和 control_sequence，使用真实 block_id 与动作
  - path: spatial/agent.py
    symbol: MultiAgents.control
    supports: Controller 接收机器摘要和动作配置后生成 JSON，没有直接绑定控制工具
  - path: script/run_simulation.py
    symbol: init_simulation_db
    supports: 控制任务的计划文本来自 overall_structure 的 functionality 和 motion_control
validation:
  human_review: pending
  logic_tests: not_run
  geometry_checks: not_run
  physics_trials: not_run
  evidence: []
---

# 1. 何时使用与何时不用

用于 Planner 和 Drafter 提前预留左右驱动组，以及 Controller 根据反馈制定转向脉冲。它不设计缺失的转向铰链，也不提供保证成功的原地转向宏。轮子离地、车身卡地或货物正在撞击时，先处理状态问题。

# 2. 原理与来源

印刷页 183–185 讨论纵向地面力与操纵稳定性的耦合；页 185 明确左右驱动力分配的改变可形成横摆力偶矩。

本技能自行将该力矩原理整理为对称轮组的平面计算。取车体 `x` 向前、`y` 向左、`z` 向上，左右纵向力合力作用线位于 `y = +/- track/2`，则：

```text
longitudinal_force = left_force + right_force
drive_yaw_moment = (right_force - left_force) * track / 2
```

正力矩指向左转方向，但只是纵向力对横摆的贡献。教材没有证明本仓库四轮机器是无滑移差速机器人；侧向轮地力矩可能抵消它，因此不能直接预测转角或转弯半径。

# 3. 环境映射与限制

“左右轮分控”是本项目的设计建议，不是增加新工具。镜像安装时，相同 `spinning_forward` 名字不必然使左右轮都推动整车向前，必须结合实际轴线、翻转与后续运动反馈确认。

Controller 仍输出 `control_config` 中的真实 `key/action/block_id` 和 `control_sequence` 中的 `motion_action/time/key/hold_for`。它没有直接调用 `change_control_key` 的工具权限。不能塞入 `steering_angle`、`torque` 或 `target_yaw_rate` 等未支持字段。

先保留至少两组可独立触发的轮子动作，不把所有前后动作绑在同一键。单侧放键可能触发自动制动，不能当作自由滑行。加宽轮距既改变力矩臂，也影响摩擦与结构成本，并非必然更容易转向。

# 4. Procedure

1. 从实际机器摘要和动作配置清点左右轮组；缺真实 ID 或方向依据时只提出补充核对。
2. 规划中分别写出直行动作与转向动作的轮组意图，不提前猜按键持续时间。
3. 没有力数据时保留定性力矩方向；有力数据且模型成立时，检查左右差值是否真的产生横摆贡献。
4. 开发验证先做一个短差动动作，读取转向符号、位移与货物状态，再决定下一次调整。最多使用任务原有三次控制反馈，不编写无限调参循环。
5. 出现方向相反、几乎不转或货物滑移时，分别检查映射、轮地约束与加速度，不只加长脉冲。

# 5. 输入约定与参考策略

`track` 为有限正值，两个纵向合力作用线的横向间距，使用游戏长度标度。`left_force/right_force` 是同一时段的有符号地面纵向合力，向前为正；不是转速、按键编号或未经校准的电机参数。

`independent_groups` 与 `force_model_valid` 均为 `True/False/None`。后者确认坐标、作用线、力来源与对称几何适用性；前者确认轮组可分别控制。模型力矩非零仍不证明具有实际转向能力。

```python
from math import isfinite


def check_differential_yaw(track, left_force, right_force,
                           independent_groups=None, force_model_valid=None):
    result = {
        "status": "insufficient_evidence", "reason": "wheel_group_mapping_unconfirmed",
        "checks": [],
        "next_steps": [{"kind": "design_requirement",
                        "target": "independent_left_right_actions_with_verified_signs"}],
    }
    if independent_groups is False:
        result.update(status="not_applicable", reason="no_independent_wheel_groups")
        return result
    if independent_groups is not True:
        return result
    if force_model_valid is False:
        result.update(status="not_applicable", reason="outside_two_force_line_model")
        return result
    if force_model_valid is not True:
        result["reason"] = "force_model_unconfirmed_use_pulse_calibration"
        return result
    try:
        if any(type(v) not in (int, float) or not isfinite(v)
               for v in (track, left_force, right_force)):
            raise ValueError
        if track <= 0:
            raise ValueError
        delta = right_force - left_force
        moment = delta * track / 2
        force = left_force + right_force
        if not all(isfinite(v) for v in (delta, moment, force)):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        result["reason"] = "missing_or_invalid_numeric_inputs"
        return result
    nonzero = abs(delta) > 1e-9 * max(abs(left_force), abs(right_force))
    result["estimates"] = {"drive_yaw_moment": moment, "longitudinal_force": force,
                           "drive_yaw_direction": "left" if nonzero and moment > 0
                           else "right" if nonzero else "none"}
    result["checks"] = [
        {"name": "drive_yaw_contribution", "result": nonzero, "basis": "force_times_arm"},
        {"name": "actual_turning_response", "result": None, "basis": "not_measured"},
    ]
    result.update(status="candidate" if nonzero else "not_applicable",
                  reason="yaw_contribution_requires_calibration" if nonzero
                  else "equal_forces_provide_no_differential_yaw")
    result["next_steps"] = [{"kind": "validation_plan" if nonzero else "design_requirement",
                              "target": "one_short_pulse_then_observe" if nonzero
                              else "differentiate_left_right_actions"}]
    return result
```

浮点阈值不是转向死区的实测值。输出是轮组意图或验证建议，不是可直接执行的控制序列。

# 6. 最小自测

合成输入，未执行：

```python
left = check_differential_yaw(4, 1, 3, True, True)
assert left["status"] == "candidate"
assert left["estimates"]["drive_yaw_moment"] == 4
assert left["estimates"]["drive_yaw_direction"] == "left"
assert left["checks"][1]["result"] is None
assert check_differential_yaw(4, 3, 1, True, True)["estimates"]["drive_yaw_direction"] == "right"
assert check_differential_yaw(4, -2, 2, True, True)["estimates"]["longitudinal_force"] == 0
assert check_differential_yaw(4, 2, 2, True, True)["status"] == "not_applicable"
assert check_differential_yaw(4, 1, 3, False, True)["status"] == "not_applicable"
assert check_differential_yaw(4, 1, 3, True, False)["status"] == "not_applicable"
assert check_differential_yaw(0, 1, 3, True, True)["status"] == "insufficient_evidence"
assert check_differential_yaw(4, None, 3, True, True)["status"] == "insufficient_evidence"
assert check_differential_yaw(4, True, 3, True, True)["status"] == "insufficient_evidence"
assert check_differential_yaw(4, 1, float("inf"), True, True)["status"] == "insufficient_evidence"
assert check_differential_yaw(4, 1, 3)["status"] == "insufficient_evidence"
```

# 7. Checklist

- 使用前：几何核对左右、轴线与真实 ID；协议核对动作名与独立按键。
- 使用后：逻辑保留力矩符号，物理另测实际航向；不能用 `candidate` 宣称机器已经会转向。
- 同一轮子的相反动作不能在同一时段冲突；按键序列保持原有格式和 30 秒窗口。

# 8. 验证方案与证据

固定机器、地面与载荷，比较直行动作和单个差动脉冲。记录航向符号、横向位移、是否抬轮及货物相对运动；若只有单点轨迹，不能把路径切线当作低速时准确车身航向。力矩正负预测与实测方向不符时先排查动作映射和轮地约束。本轮未执行自测或仿真。

# 9. 交给下一角色的结论

`design_requirements` 保留 `transport_differential_yaw@0.1.0`、左右轮组分控要求及坐标定义。Drafter 落实轮组布置，构建后以实际 ID 交接 Controller。控制阶段只保留有效动作映射、最新校准证据和待解决问题，不重复传递整段讨论。

轮组意图与校准要求还须简短写入 `overall_structure.motion_control`。现有控制入口读取这里而非子结构设计要求，实际 ID 则由机器摘要确认；不能假设 Controller 主动检索了本技能。
