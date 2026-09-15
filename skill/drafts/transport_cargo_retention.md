---
id: transport_cargo_retention
title: 对自由货物分别检查滑移需求与接触倾覆边界
summary: "Transport payload cargo retention sliding tipping acceleration braking：Medium/Hard 自由载荷不可固定连接，以实际货台接触区域检查加减速和转弯需求；车辆没翻不代表货物仍在车上。"
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [transport]
  levels: [medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance, controller]
  stages: [plan, draft, build, control, refine]
  triggers: [起步货物向后滑, 刹车货物前冲, 转向时货物掉落, 货物长轴与支承区域不匹配]
prerequisites:
  - 货物已落稳，水平底面与居中的矩形有效支承区域接触，无侧壁力参与
  - 接触可采用准静态刚体和各向同性静摩擦近似，底面加速度可近似均匀
environment_constraints:
  - Builder 不添加或固定连接任务货物，适配器在仿真阶段自行添加
  - 任务名义尺寸、配重缩放、实际接触区域是不同信息
  - 货物撞击护栏或存在快速旋转时，简单摩擦与倾覆模型不再充分
sources:
  - file: "skill/books/汽车理论 (余志生) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: 汽车理论
    authors: [余志生主编]
    edition: "第 5 版，机械工业出版社，2009 年 3 月"
    sha256: 671ecf1257274f39a1818b32822cc7d46edc7a648d60b594699e3a5203870420
    chapter: 第一章第四节；第五章第八节
    pdf_pages: [38, 210, 211]
    printed_pages: [22, 194, 195]
    locator: "纵向接触力的附着上界；图 5-85 和水平地面侧翻力矩平衡"
    license_status: unconfirmed
    supports:
      - 接触切向能力受到法向载荷限制，不能无条件提供驱动力
      - 倾覆边界由重力与惯性作用对接触边缘的力矩决定
      - 本技能的自由货物二维扩展为提炼者迁移推导，非原书货物模型或游戏实测
code_evidence:
  - path: levels.yaml
    symbol: transport.medium / transport.hard
    supports: 货物不参与构建且无固定连接，Hard 长轴初始沿南北
  - path: simulation/simulation_transport.py
    symbol: main
    supports: 导出前新增 Ballast，货物高度依据现有积木中心最高值
  - path: blocks/configs/ballast_.yaml
    symbol: geo / data / disable
    supports: 配重尺寸与质量相关配置需与实际游戏对象核对
  - path: analyze/sim_transport.py
    symbol: _determine_tracking_target / analyze_simulation_transport
    supports: 跟踪配重位移不能证明配重始终由车辆承载
validation:
  human_review: pending
  logic_tests: not_run
  geometry_checks: not_run
  physics_trials: not_run
  evidence: []
---

# 1. 何时使用与何时不用

用于 Medium/Hard 的货台布置以及起步、制动和缓慢转向的货物保持检查。Soft 没有本任务货物，不适用。货物下落、跳动、已经滑移、撞击护栏或承载面破损时，停止使用该静止接触近似。

# 2. 原理与来源

教材页 22 的附着关系和页 194–195 的力矩平衡提供迁移出发点；原书讨论轮地接触及汽车侧翻，**没有直接给出本项目自由货物策略**。

以下为提炼者的条件推导：货物随水平货台平移、无显著垂直或角加速度时，`N = m*g`、所需底面切向力为 `m*(ax, ay)`。进一步假定各向同性 Coulomb 静摩擦，则：

```text
required_mu = hypot(ax_over_g, ay_over_g)
pressure_center_x = -cg_height * ax_over_g
pressure_center_y = -cg_height * ay_over_g
abs(pressure_center_x) < half_length
abs(pressure_center_y) < half_width
```

矩形支承范围内的压力中心是无倾覆余量的必要检查；摩擦另需 `required_mu < mu_static`。质量在这个简化比值中消去，不代表真实质量对车辆、接触冲击或变形无关。该二维货物迁移及摩擦模型均待人工审核和游戏验证。

# 3. 环境映射与限制

货物局部 `x/y` 沿所选矩形有效支承区域两条水平边，`z` 向上。它不必与车头方向一致：Hard 货物初始长轴沿世界南北，不能无条件令长边等于车辆轴距方向。

`half_length/half_width` 描述实际有效支承矩形，不是整块货物标称尺寸或货台外框尺寸。存在孔洞、离散支点、偏心或不共面接触时必须重新核对模型。`cg_height` 从接触平面量起，不是整车高度。

任务 Medium 名义货物为 `2.5 x 2.5 x 1.5`，Hard 为 `4 x 8 x 1.5`；适配器额外缩放和旋转配重，需检查导出与落稳后的朝向、接触及质量，不能仅凭这些文字填满函数参数。

可以提出低货台、承托面和不阻碍下落的挡边候选，但不创建配重、不固定货物、不声称护栏绝对不会让货物弹出。挡边一旦实际受力，本函数的“仅底面接触”假设就需重新评估。

# 4. Procedure

1. 先为适配器的下落与落稳预留空间，核对真实支承面；不能把配重当作蓝图中已固定的积木。
2. 选定货物局部轴，记录加速度需求来源。快速差动转向使长货物各点加速度显著不同，不能用车体单点加速度代替。
3. 检查倾覆几何余量，再独立检查滑移需求。摩擦未知时只报告 `required_mu` 与待校准，不默认通过。
4. 越界时优先减小对应方向的加速度、重选承托区域或重新审视质心；已经撞击挡边时另建接触模型。
5. 每次只提交一个调整与下一观察点，物理验证计入原有三次控制机会。

# 5. 输入约定与参考策略

`half_length/half_width/cg_height` 是有限正长度，标度一致且有实际接触/质心依据；矩形与质心投影居中是显式前提。

`ax_over_g/ay_over_g` 是货物局部两轴加速度与同场景重力之比，可为负。`mu_static` 是货物与货台的系数，不是轮地系数；未知填 `None`。`contact_model_valid` 为三态确认，不因“货物在车上”自动为真。所有数值保留来源，不接受布尔或非有限值。

```python
from math import hypot, isfinite


def check_cargo_retention(half_length, half_width, cg_height, ax_over_g, ay_over_g,
                           mu_static=None, contact_model_valid=None):
    result = {
        "status": "insufficient_evidence", "reason": "cargo_contact_model_unconfirmed",
        "checks": [],
        "next_steps": [{"kind": "review", "target": "settled_cargo_actual_support_and_motion"}],
    }
    if contact_model_valid is False:
        result.update(status="not_applicable", reason="outside_flat_uniform_contact_model")
        return result
    if contact_model_valid is not True:
        return result
    try:
        values = (half_length, half_width, cg_height, ax_over_g, ay_over_g)
        if any(type(v) not in (int, float) or not isfinite(v) for v in values):
            raise ValueError
        if min(half_length, half_width, cg_height) <= 0:
            raise ValueError
        if mu_static is not None and (
                type(mu_static) not in (int, float) or not isfinite(mu_static) or mu_static < 0):
            raise ValueError
        px, py = -cg_height * ax_over_g, -cg_height * ay_over_g
        mx, my = half_length - abs(px), half_width - abs(py)
        required = hypot(ax_over_g, ay_over_g)
        if not all(isfinite(v) for v in (px, py, mx, my, required)):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        result["reason"] = "missing_or_invalid_numeric_inputs"
        return result
    tipping_ok = mx > 1e-9 * half_length and my > 1e-9 * half_width
    sliding_ok = None if mu_static is None else (
        mu_static - required > 1e-9 * max(mu_static, required))
    result["estimates"] = {"required_mu": required, "pressure_center": [px, py],
                           "support_margins": [mx, my]}
    result["checks"] = [
        {"name": "tipping_reserve", "result": tipping_ok, "basis": "centered_support_rectangle"},
        {"name": "sliding_reserve", "result": sliding_ok,
         "basis": "coefficient_unknown" if mu_static is None else "reviewed_cargo_contact"},
    ]
    if not tipping_ok or sliding_ok is False:
        result.update(status="not_applicable", reason="cargo_contact_reserve_exhausted")
        result["next_steps"] = [{"kind": "review", "target": "reduce_demand_or_revise_support"}]
    elif sliding_ok is None:
        result["reason"] = "cargo_friction_unknown_not_assumed"
        result["next_steps"] = [{"kind": "validation_plan", "target": "same_cargo_deck_contact"}]
    else:
        result.update(status="candidate", reason="conditional_cargo_reserve_only")
        result["next_steps"] = [{"kind": "review", "target": "vehicle_rollover_and_drop_impact"}]
    return result
```

容差不是安全系数；边界仅表示没有正余量。对已确认模型的条件超限不能冒充游戏失败证据。

# 6. 最小自测

合成输入，未执行：

```python
ok = check_cargo_retention(2, 1, 1, 0.3, 0.4, 0.8, True)
assert ok["status"] == "candidate"
assert ok["estimates"]["required_mu"] == 0.5
assert ok["estimates"]["pressure_center"] == [-0.3, -0.4]
assert check_cargo_retention(2, 1, 1, 0.3, 0.4, 0.5, True)["status"] == "not_applicable"
assert check_cargo_retention(2, 1, 1, 0, 1, 2, True)["status"] == "not_applicable"
assert check_cargo_retention(2, 1, 1, -2, 0, None, True)["status"] == "not_applicable"
assert check_cargo_retention(2, 1, 1, 0.3, 0.4, None, True)["status"] == "insufficient_evidence"
assert check_cargo_retention(0, 1, 1, 0.3, 0.4, 0.8, True)["status"] == "insufficient_evidence"
assert check_cargo_retention(2, 1, None, 0.3, 0.4, 0.8, True)["status"] == "insufficient_evidence"
assert check_cargo_retention(2, 1, 1, True, 0.4, 0.8, True)["status"] == "insufficient_evidence"
assert check_cargo_retention(2, 1, 1, 0.3, 0.4, -0.1, True)["status"] == "insufficient_evidence"
assert check_cargo_retention(2, 1, 1, 0.3, float("nan"), 0.8, True)["status"] == "insufficient_evidence"
assert check_cargo_retention(2, 1, 1, 0.3, 0.4, 0.8, False)["status"] == "not_applicable"
assert check_cargo_retention(2, 1, 1, 0.3, 0.4, 0.8)["status"] == "insufficient_evidence"
```

# 7. Checklist

- 使用前：几何检查下落通道、实际承托区域和局部轴，逻辑核对模型前提。
- 使用后：分开记录滑移、货物自身倾覆和整车侧翻，不混用两种接触的摩擦系数。
- 仿真必须查看货物相对车辆的位置及接触状态；货物飞出后位移很大不算可靠运输。

# 8. 验证方案与证据

开发阶段固定货物、货台材料和落稳条件，分别观察低强度起步、制动和缓慢转向，每次只改变一个需求变量。记录相对滑移、边缘抬起、碰撞与离车。当前轨迹若不能区分接触受力或姿态，就将对应假设记为未验证，不从分析器分数反推出摩擦。此迁移模型及自测均未执行验证。

# 9. 交给下一角色的结论

`design_requirements` 保留 `transport_cargo_retention@0.1.0`、自由货物约束、实际支承区域与下落空间要求、货物局部轴和加速度限制来源。Controller 接收当前可用的动作限制或校准缺口，不能因车辆保持完整就略过货物检查。

动作限制与货物校准缺口还须简短写入 `overall_structure.motion_control`；当前 `script/run_simulation.py::init_simulation_db` 仅传递总计划功能与控制说明，不自动传递子结构全文。
