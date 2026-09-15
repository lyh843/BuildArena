---
id: transport_axle_load_transfer
title: 根据质心与纵向加减速检查前后轴卸载
summary: "Transport axle load transfer center of gravity wheelbase：以轴距和装载质心估算前后轴法向载荷比例，识别加速抬头、制动后轴卸载；不平均分配未知轮载。"
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [transport]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance, controller]
  stages: [plan, draft, build, control, refine]
  triggers: [起步翘头, 制动翘尾, 装载后质心变化, 前后轮牵引不均]
prerequisites:
  - 水平地面上可采用刚体两轴的纵向准静态模型
  - 质心和加速度比有依据，货物与底盘没有影响本模型的相对运动
environment_constraints:
  - 几何中心不是质量中心，空车质心不能直接代替装载质心
  - Medium 和 Hard 的自由货物由仿真适配器添加，不由 Builder 固定连接
  - 任务质量与实际配重配置需要核对，不能以配置成本推算轮载
sources:
  - file: "skill/books/汽车理论 (余志生) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: 汽车理论
    authors: [余志生主编]
    edition: "第 5 版，机械工业出版社，2009 年 3 月"
    sha256: 671ecf1257274f39a1818b32822cc7d46edc7a648d60b594699e3a5203870420
    chapter: 第一章第四节
    pdf_pages: [39, 40, 41]
    printed_pages: [23, 24, 25]
    locator: "图 1-29，式 (1-13)、(1-14)，静载与纵向加速分量"
    license_status: unconfirmed
    supports: [前后轴法向反力取决于质心和轴距, 加速将法向载荷向后转移, 简化模型需要忽略项依据]
code_evidence:
  - path: simulation/simulation_transport.py
    symbol: main
    supports: 以积木中心坐标组织水平平移与货物添加，不计算质量中心
  - path: levels.yaml
    symbol: transport.medium / transport.hard
    supports: 货物自由放置，任务指定载荷但不允许将其作为构建部件
  - path: blocks/configs/ballast_.yaml
    symbol: data / weight / geo
    supports: 配重配置需要与实际导出及游戏状态核对
validation:
  human_review: pending
  logic_tests: not_run
  geometry_checks: not_run
  physics_trials: not_run
  evidence: []
---

# 1. 何时使用与何时不用

用于选择轴距、货台高度和纵向载荷位置，或解释起步、制动时某一轴卸载。货物尚在下落、车身弹跳、明显俯仰振动、坡地、多轴分配未知或结构柔性显著时，不进行本模型的数值判断。

# 2. 原理与来源

印刷页 23 的图 1-29 与式 (1-13) 包含坡度、质心、加速度、轮系惯性及空气力等项；页 24–25 说明简化。仅在水平、无显著空气力并可忽略相关惯性力偶的条件下，将式 (1-14) 除以总重，得到：

```text
front_fraction = (cg_from_rear - cg_height * accel_over_g) / wheelbase
rear_fraction = 1 - front_fraction
```

纵向正方向为车头方向，`accel_over_g > 0` 表示向前加速；向前行驶时制动为负。两个比例均严格为正才有两轴同时保持受压接触的模型余量。负反力不是地面能拉住轮子。

# 3. 环境映射与限制

轴距是落稳后前后接地轴线沿车身纵向的距离，不是车身外框长度。`cg_from_rear` 从后轴接地线向前量；`cg_height` 从支承平面向上量。先由 Agent `[东, 北, 上]` 转到所声明的车体方向，倒车不重新交换前后轴名字。

适配器的积木中心平均值用于水平对齐，不是质心。任务的 Medium/Hard 货物质量写为 50，但适配器没有直接赋值 50；不得用这段任务文字声称已经测得游戏载荷。即使本式消去了总质量，装载质心仍需要可靠质量与位置依据。

货物未固定。只有落稳且在该工况中随车运动的近似得到支持，才能使用整体质心；否则分别分析载荷接触，不能焊接配重来满足假设。

# 4. Procedure

1. 定义车头、两轴接地线和载荷边界，区分空车与装载状态。
2. 质心未知时提出低货台、载荷投影落在支承区域内的布置候选，不声称轴载均分。
3. 已有质心与加速度比时，分别检查起步和制动工况；任何一侧比例非正都要重新审视两轴接触假设。
4. 可比较降低质心、改变纵向载荷位置或轴距的候选，但不得用“更长必然更好”替代转向与积木成本检查。
5. 修改后仅提交一个有依据的布置或控制调整，等待实际状态与轨迹反馈。

# 5. 输入约定与参考策略

四个数值均为有限实数，不接受布尔值。`wheelbase > 0`、`cg_height >= 0`；三种长度使用同一游戏尺度。`cg_from_rear` 可超出轴间区间，以便检查偏载。`accel_over_g` 是同一场景的纵向加速度除以重力加速度，来源必须记录，不默认游戏重力为 9.81。

`model_valid` 为 `True/False/None`，确认上述全部简化条件，而非“看起来像汽车”。没有真实参数时可用明确标记的设计假设做条件比较，不能改写为实测值。

```python
from math import isfinite


def check_axle_load_transfer(wheelbase, cg_from_rear, cg_height,
                             accel_over_g, model_valid=None):
    result = {
        "status": "insufficient_evidence", "reason": "two_axle_model_unconfirmed",
        "checks": [],
        "next_steps": [{"kind": "review", "target": "settled_loaded_cg_and_contact_basis"}],
    }
    if model_valid is False:
        result.update(status="not_applicable", reason="outside_two_axle_model")
        return result
    if model_valid is not True:
        return result
    try:
        values = (wheelbase, cg_from_rear, cg_height, accel_over_g)
        if any(type(v) not in (int, float) or not isfinite(v) for v in values):
            raise ValueError
        if wheelbase <= 0 or cg_height < 0:
            raise ValueError
        front = (cg_from_rear - cg_height * accel_over_g) / wheelbase
        rear = 1 - front
        if not all(isfinite(v) for v in (front, rear)):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        result["reason"] = "missing_or_invalid_numeric_inputs"
        return result
    front_loaded, rear_loaded = front > 1e-9, rear > 1e-9
    result["estimates"] = {"front_fraction": front, "rear_fraction": rear}
    result["checks"] = [
        {"name": "front_compression", "result": front_loaded, "basis": "two_axle_balance"},
        {"name": "rear_compression", "result": rear_loaded, "basis": "two_axle_balance"},
    ]
    reserve = front_loaded and rear_loaded
    result.update(status="candidate" if reserve else "not_applicable",
                  reason="conditional_two_axle_contact" if reserve
                  else "axle_unloading_boundary_or_beyond")
    result["next_steps"] = [{"kind": "review",
                              "target": "per_wheel_traction_and_lateral_stability" if reserve
                              else "lower_cg_rebalance_load_or_reduce_acceleration"}]
    return result
```

数值阈值仅处理浮点边界，不是物理安全余量。该结果不能作为 Guidance 拒绝构建的实际失败证据。

# 6. 最小自测

合成输入，未执行：

```python
static = check_axle_load_transfer(4, 2, 1, 0, True)
assert static["status"] == "candidate"
assert static["estimates"]["front_fraction"] == 0.5
assert check_axle_load_transfer(4, 2, 1, 1, True)["estimates"]["front_fraction"] == 0.25
assert check_axle_load_transfer(4, 2, 1, -1, True)["estimates"]["rear_fraction"] == 0.25
assert check_axle_load_transfer(4, 2, 1, 2, True)["status"] == "not_applicable"
assert check_axle_load_transfer(4, 2, 1, -2, True)["status"] == "not_applicable"
assert check_axle_load_transfer(4, 5, 1, 0, True)["status"] == "not_applicable"
assert check_axle_load_transfer(0, 2, 1, 0, True)["status"] == "insufficient_evidence"
assert check_axle_load_transfer(4, None, 1, 0, True)["status"] == "insufficient_evidence"
assert check_axle_load_transfer(4, 2, True, 0, True)["status"] == "insufficient_evidence"
assert check_axle_load_transfer(4, 2, 1, float("inf"), True)["status"] == "insufficient_evidence"
assert check_axle_load_transfer(4, 2, 1, 0, False)["status"] == "not_applicable"
assert check_axle_load_transfer(4, 2, 1, 0)["status"] == "insufficient_evidence"
```

# 7. Checklist

- 使用前：核对轴距、车体方向、质心来源及货物是否落稳。
- 使用后：逻辑检查起步与制动两种符号；几何检查轮子与货台布置。
- 仿真另查实际抬轮、货物相对运动及柔性变形，不能由正比例证明全部轮子接地。

# 8. 验证方案与证据

开发场景保持轮组与质量配置相同，改变一个货台高度或纵向位置变量，使用相同低强度控制动作。观察车身俯仰、前后轮离地和货物相对位移；没有这些观测时不能以平面位移曲线验证轴载公式。本轮未执行代码、几何检查或仿真。

# 9. 交给下一角色的结论

在 `design_requirements` 传递 `transport_axle_load_transfer@0.1.0`、车体方向、载荷区域与高度要求、哪些质心量只是设计假设，以及起步和制动中应关注的卸载侧。不要传递“每轮承担四分之一重量”的未经核对结论。

起步与制动限制还需简短写入 `overall_structure.motion_control`；当前 `script/run_simulation.py::init_simulation_db` 不自动把子结构的设计要求传给 Controller。
