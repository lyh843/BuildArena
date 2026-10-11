---
id: lift_thrust_alignment
title: 同时核对合推力方向与相对质心的三维力矩
summary: "Lift thrust alignment resultant torque nozzle direction 推力偏心：区分喷流与反冲，计算多水炮合力和质心力矩；合力向上仍可能产生俯仰、横滚或偏航，不能只凭对称外形结束审核。"
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [lift]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance]
  stages: [plan, draft, build, assemble]
  triggers: [水炮朝向核对, 反冲抵消, 升空时翻转, 推力轴偏离质心]
prerequisites:
  - 使用同一瞬时工况、同一世界坐标的作用线和推力向量
  - 整机质心或显式代理以及刚性整体模型已经核对
environment_constraints:
  - 水炮描述器给的是喷流方向，反冲取相反方向
  - 不假设万向喷管、尾翼或主动姿态控制已被暴露
  - 纯水炮与火把结构不会仅因是Lift任务而自动进入Refine
sources:
  - file: "skill/books/理论力学（第9版）（I） (哈尔滨工业大学理论力学教研室) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: 理论力学
    edition: "第9版 I，高等教育出版社；出版年未核实"
    chapter: "3-2 力对点的矩；3-4 空间任意力系的简化"
    pdf_pages: [112, 113, 118, 119]
    printed_pages: [81, 82, 87, 88]
    locator: "式3-7、3-8、3-18、3-19"
    license_status: unconfirmed
    supports: [力矩为位置叉乘力, 合力和主矩需分别计算]
  - file: "skill/books/Rocket Propulsion Elements (George P. Sutton, Oscar Biblarz) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: Rocket Propulsion Elements
    edition: "Ninth Edition, Wiley, 2017"
    chapter: "2.2 Thrust; 3.6 Nozzle Alignment"
    pdf_pages: [55, 56, 115, 116]
    printed_pages: [31, 32, 91, 92]
    locator: "reaction force; thrust axis misalignment"
    license_status: unconfirmed
    supports: [反作用推进原理, 固定推力线偏离质心会产生转动]
code_evidence:
  - path: blocks/descriptors/water_cannon.py
    symbol: descriptor
    supports: 给出入口、出口和喷流朝向
  - path: spatial/construction.py
    symbol: BUILD_OPERATIONS / Blueprint
    supports: 结构化蓝图可声明twist_block并通过现有几何预检
  - path: scheduler/runner.py
    symbol: run_build
    supports: 单独Refine由has_spinful触发；水炮和火把的spin均为false
validation:
  human_review: pending
  logic_tests: not_run
  geometry_checks: not_run
  physics_trials: not_run
  evidence: []
---

# 1. 何时使用与何时不用

在设计、朝向微调和最终装配后核对每个水炮的反冲贡献。若机器正在明显变形、已断开或推力状态未知，应先补证据；不能用一个恒定力系预测整个飞行过程。

# 2. 原理与来源

《理论力学》页82、88给出 `F=sum(F_i)` 和 `M_C=sum((r_i-r_C) x F_i)`。合力平行竖直轴不代表主矩为零；不同位置的横向力还可能形成纯力偶。Rocket 页91说明固定推进轴偏离质心可导致翻转，页92指出启动瞬态和结构变形也会造成失配。

相同推力在水平面对称分布且同向时可抵消相应力矩，这是条件结论。降低静态主矩是布局目标，不是恢复力矩或抗扰稳定性证明；不搬用教材真实火箭的毫米或角度公差。

# 3. 环境映射与限制

Agent `[东,北,上]` 为右手坐标。本函数在这个坐标中叉乘；不要先在内部交换轴的坐标中叉乘，再仅交换结果。水炮 `sprays towards` 是喷流方向：向下喷射才产生向上的反冲。

喷口轴上一点可作力作用线代表点；几何中心不在已核定作用线上时不能任意代用。没有真实推力时可用同一等效质量标度代理，但输出力矩也只是“等效质量乘游戏长度”。所有力和容差使用同一标度。

纯水炮结构的方向必须在 Draft/Build 就核对，不依赖后续一定存在 Refine。旋转以实际工具和结构化蓝图操作为准，不把技能注册为新的工具。

# 4. Procedure

1. 从实际描述器整理入口、出口和世界喷流向量，反向得到反冲方向。
2. 结合当前工况的推力和整机质心计算合力与三轴主矩。
3. 合力非向上或横向分量超出设计容差时修正朝向；主矩超限时重排作用线或质量，不能只增加同侧水炮。
4. 每次修改交由原有预检及真实构建核对，随后重新计算，并检查冷热不一致情景。

# 5. 输入约定与参考策略

`thrusters` 每项为 `{id: 非空字符串, point: 三维作用线点, force: 三维反冲向量}`；清单须完整，ID唯一。`center` 为同坐标质心或注明来源的代理。`lateral_limit`、`moment_limit` 是有限非负设计容差，分别为力标度和力乘长度标度，不是物理通过阈值。`rigid_model` 三态记录适用性。

```python
from math import hypot, isfinite


def check_thrust_alignment(thrusters, center, lateral_limit, moment_limit, rigid_model=None):
    out = {"status": "insufficient_evidence", "reason": "rigid_model_unconfirmed",
           "checks": [{"name": "alignment", "result": None, "basis": "current_force_system"}],
           "next_steps": [{"kind": "review", "target": "actual_axes_mass_center_and_thrust"}]}
    if rigid_model is False:
        out.update(status="not_applicable", reason="outside_rigid_force_system")
        return out
    if rigid_model is not True:
        return out
    def vector(v):
        return (isinstance(v, (list, tuple)) and len(v) == 3
                and all(type(x) in (int, float) and isfinite(x) for x in v))
    try:
        if not vector(center) or not isinstance(thrusters, (list, tuple)) or not thrusters:
            raise ValueError
        if any(type(v) not in (int, float) or not isfinite(v) or v < 0
               for v in (lateral_limit, moment_limit)):
            raise ValueError
        force, moment, ids = [0.0] * 3, [0.0] * 3, set()
        for item in thrusters:
            ident, point, f = item["id"], item["point"], item["force"]
            if not isinstance(ident, str) or not ident or ident in ids or not vector(point) or not vector(f):
                raise ValueError
            ids.add(ident)
            r = [point[i] - center[i] for i in range(3)]
            cross = [r[1]*f[2] - r[2]*f[1], r[2]*f[0] - r[0]*f[2], r[0]*f[1] - r[1]*f[0]]
            force = [force[i] + f[i] for i in range(3)]
            moment = [moment[i] + cross[i] for i in range(3)]
        lateral, magnitude = hypot(*force[:2]), hypot(*moment)
        if not all(isfinite(v) for v in [*force, *moment, lateral, magnitude]):
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError):
        out["reason"] = "missing_or_invalid_force_system"
        return out
    out["estimates"] = {"force": force, "moment_about_center": moment}
    out["checks"] = [{"name": name, "result": verdict, "basis": "declared_instantaneous_model"}
                     for name, verdict in [("upward", force[2] > 0),
                                           ("lateral_limit", lateral <= lateral_limit),
                                           ("moment_limit", magnitude <= moment_limit)]]
    ok = all(check["result"] for check in out["checks"])
    out.update(status="candidate" if ok else "not_applicable",
               reason="conditional_alignment" if ok else "force_or_moment_requires_redesign")
    out["next_steps"] = [{"kind": "review" if ok else "redesign",
                          "target": "thrust_budget_and_startup" if ok else "axes_positions_or_mass_balance"}]
    return out
```

# 6. 最小自测

合成数据，未执行：

```python
pair = [{"id": "l", "point": [-1, 0, 0], "force": [0, 0, 2]},
        {"id": "r", "point": [1, 0, 0], "force": [0, 0, 2]}]
assert check_thrust_alignment(pair, [0, 0, 0], 0, 0, True)["status"] == "candidate"
assert check_thrust_alignment(pair[:1], [0, 0, 0], 0, 0, True)["estimates"]["moment_about_center"] == [0, 2, 0]
assert check_thrust_alignment(pair[:1], [0, 0, 0], 0, 0, True)["status"] == "not_applicable"
assert check_thrust_alignment(pair[:1], [0, 0, 0], 0, 2, True)["status"] == "candidate"
assert check_thrust_alignment([{"id": "a", "point": [0, 0, 0], "force": [0, 0, -1]}], [0, 0, 0], 0, 0, True)["status"] == "not_applicable"
assert check_thrust_alignment(pair + pair, [0, 0, 0], 0, 0, True)["status"] == "insufficient_evidence"
assert check_thrust_alignment(pair, None, 0, 0, True)["status"] == "insufficient_evidence"
assert check_thrust_alignment(pair, [0, 0, 0], -1, 0, True)["status"] == "insufficient_evidence"
assert check_thrust_alignment(pair, [0, 0, 0], 0, 0, False)["status"] == "not_applicable"
assert check_thrust_alignment(pair, [0, 0, 0], 0, 0)["status"] == "insufficient_evidence"
```

# 7. Checklist

- 逻辑：同坐标、同瞬时状态、完整推力清单，合力与主矩分别审查。
- 工具：真实喷流朝向和变换后作用线对应当前版本，几何修改经过预检。
- 物理：零静态主矩不等于具有恢复力矩；实际热失配、漂移、翻转和连接仍待测。

# 8. 验证方案与证据

开发场景固定质量和加热方案，只比较一种轴线对准修改；记录离地、横向漂移及姿态。若没有姿态日志，只能根据可观察证据标记偏转，不能编造三轴角速度。未执行逻辑、几何或物理验证。

# 9. 交给下一角色的结论

`design_requirements` 写 `lift_thrust_alignment@0.1.0`、喷流/反冲方向、质心依据、作用线布置和冷热情景。每个 Hard 实例需要在总装坐标重新核对，不能只复用独立模块的“向上”文字。
