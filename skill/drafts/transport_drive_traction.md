---
id: transport_drive_traction
title: 判断驱动轮的附着需求，不把轮子转动当作有效牵引
summary: "Transport wheel traction adhesion slip：核对 PoweredWheel 朝向、接地与载荷，计算直线驱动所需附着率；未知摩擦或轮端力时提出校准，不靠增加轮数保证运输能力。"
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [transport]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance, controller]
  stages: [plan, draft, build, control, refine]
  triggers: [轮子空转但车不走, 加载后无法起步, 增加驱动轮, 判断轮轴与行驶方向]
prerequisites:
  - 定量检查限于同一工况下一个驱动轮或已核定分配的驱动轮组
  - 法向载荷与地面纵向力需求有独立依据，直线附着模型已经核对
environment_constraints:
  - PoweredWheel 的配置参数不是实测扭矩、摩擦系数或车速
  - 几何摘要没有接触力传感器，面字母不等于世界方向
  - 轮子数量、接地状态、牵引能力和转向能力需要分别检查
sources:
  - file: "skill/books/汽车理论 (余志生) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: 汽车理论
    authors: [余志生主编]
    edition: "第 5 版，机械工业出版社，2009 年 3 月"
    sha256: 671ecf1257274f39a1818b32822cc7d46edc7a648d60b594699e3a5203870420
    chapter: 第一章第二节、第四节
    pdf_pages: [19, 22, 38]
    printed_pages: [3, 6, 22]
    locator: "图 1-2；车轮的半径；驱动附着条件 Fx <= Fz * phi"
    license_status: unconfirmed
    supports: [轮端转矩与驱动力的条件关系, 几何半径和滚动半径应区分, 地面纵向力受到附着限制]
code_evidence:
  - path: blocks/configs/powered_wheel.yaml
    symbol: geo / spin / locomotion / data
    supports: 轮轴平行局部 E 面法线，存在前后转动动作和自动制动配置
  - path: spatial/components.py
    symbol: Vector.real / Vector.virtual
    supports: Agent 坐标为东、北、上，内部第二与第三分量互换
  - path: spatial/build.py
    symbol: Machine.get_block_details / Machine.get_machine_summary
    supports: 可核对构建状态，但不能读取实测轮地接触力
  - path: levels.yaml
    symbol: transport
    supports: 一个子结构，需要驱动与替代转向机制
validation:
  human_review: pending
  logic_tests: not_run
  geometry_checks: not_run
  physics_trials: not_run
  evidence: []
---

# 1. 何时使用与何时不用

Planner 选择轮组与载荷位置、Drafter 明确轮轴方向、Controller 排查“有转动无位移”时使用。直线起步和转弯必须分开：已经侧滑、离地、碰撞或同时强烈转向时，不使用下面的一维附着判据。

# 2. 原理与来源

教材印刷页 3 用 `Ft = Tt / r` 表达轮端转矩的驱动力尺度，同时脚注明确实际地面切向反力不总等于该值；轮系惯性及阻力不能随意省略。页 6 区分自由半径、静力半径与由滚动距离测得的滚动半径。页 22 给出：

```text
required_adhesion = longitudinal_force_demand / driven_normal_load
longitudinal_force_demand <= adhesion * driven_normal_load
```

这不是“驱动越强越好”：超过附着能力可能增加滑转。公式提供条件需求，不提供 Besiege 材料常数。

# 3. 环境映射与限制

PoweredWheel 的碰撞圆柱半径配置为 1，不自动等于落稳后的有效滚动半径。`bmt-speed`、`bmt-acceleration`、`bmt-contact` 也不能分别直接解释成物理车速、实测加速度和摩擦系数。

采用 Agent `[东, 北, 上]` 坐标。先核对实际旋转后的轴线是否水平、滚动平面是否与预定前进方向相容，再用后续短脉冲观测确认动作符号；不能将局部 E 面直接当作世界东侧。规划建议是让应参与驱动的轮子能接地并分别保留左右轮组控制，而非盲目增加轮数。

同样总重量下，增加轮数并不自动增加总附着上限；整车法向力不能重复计入每个轮子。构建几何不能证明轮子确实承受载荷。

# 4. Procedure

1. 列出真实轮子、局部轴线、计划接地位置和前后动作；缺失时先提出几何核对要求。
2. 区分轮子卡住、轮子离地、动作方向相互抵消和可能滑转。仅凭位移小不能诊断摩擦不足。
3. 力与载荷有依据时计算所需附着率；否则给出载荷布置、轮轴核对和短脉冲校准计划。
4. 越界时优先重新检查轮组载荷与驱动需求，不虚构调扭矩 API。
5. 每次修改后只进行一个待观察的校准动作；正式控制尝试计入原有最多三次反馈机会，不私自增加实验轮数。

# 5. 输入约定与参考策略

`normal_load` 为同一轮或轮组的有限正法向力；`force_demand` 为有限非负纵向地面力需求，二者使用同一力标度，并记录测量或模型来源。不能输入木块数量或配置成本代替力。

`adhesion` 是相同接触条件下有依据的有限非负系数，未知填 `None`。`straight_model_valid` 为 `True/False/None`，分别表示前提已核对、明确不成立、尚未核对。输入约定不是新增工具。参考函数不处理滚动阻力或转弯的侧向附着分配。

```python
from math import isfinite


def check_drive_traction(normal_load, force_demand, adhesion=None,
                         straight_model_valid=None):
    result = {
        "status": "insufficient_evidence", "reason": "straight_model_unconfirmed",
        "checks": [],
        "next_steps": [{"kind": "review", "target": "wheel_contact_axis_and_load_basis"}],
    }
    if straight_model_valid is False:
        result.update(status="not_applicable", reason="outside_straight_contact_model")
        return result
    if straight_model_valid is not True:
        return result
    try:
        if any(type(v) not in (int, float) or not isfinite(v)
               for v in (normal_load, force_demand)):
            raise ValueError
        if normal_load < 0 or force_demand < 0:
            raise ValueError
        if normal_load == 0:
            result.update(status="not_applicable", reason="no_loaded_drive_contact")
            return result
        required = force_demand / normal_load
        if not isfinite(required):
            raise ValueError
        result["estimates"] = {"required_adhesion": required}
        result["checks"] = [{"name": "traction_reserve", "result": None,
                             "basis": "adhesion_unknown"}]
        if adhesion is None:
            result["reason"] = "adhesion_missing_not_assumed"
            result["next_steps"] = [{"kind": "validation_plan",
                                      "target": "same_wheel_ground_load_calibration"}]
            return result
        if type(adhesion) not in (int, float) or not isfinite(adhesion) or adhesion < 0:
            raise ValueError
        margin = adhesion - required
        if not isfinite(margin):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        result["reason"] = "missing_or_invalid_numeric_inputs"
        return result
    reserve = margin > 1e-9 * max(adhesion, required)
    result["checks"] = [{"name": "traction_reserve", "result": reserve,
                         "basis": "reviewed_longitudinal_contact_model"}]
    result["estimates"]["adhesion_margin"] = margin
    result.update(status="candidate" if reserve else "not_applicable",
                  reason="conditional_traction_reserve" if reserve
                  else "at_or_beyond_adhesion_limit")
    result["next_steps"] = [{"kind": "review",
                              "target": "turning_and_load_transfer" if reserve
                              else "reduce_demand_or_reconsider_driven_load"}]
    return result
```

`1e-9` 仅用于浮点边界分类，不是安全系数。条件超限不是已经观测到滑转，更不构成构建拒绝证据。

# 6. 最小自测

合成数据；函数与断言本轮均未执行：

```python
ok = check_drive_traction(10, 2, 0.5, True)
assert ok["status"] == "candidate"
assert ok["estimates"]["required_adhesion"] == 0.2
assert check_drive_traction(10, 5, 0.5, True)["status"] == "not_applicable"
assert check_drive_traction(10, 6, 0.5, True)["status"] == "not_applicable"
assert check_drive_traction(0, 1, 0.5, True)["reason"] == "no_loaded_drive_contact"
assert check_drive_traction(10, 2, None, True)["status"] == "insufficient_evidence"
assert check_drive_traction(None, 2, 0.5, True)["status"] == "insufficient_evidence"
assert check_drive_traction(True, 2, 0.5, True)["status"] == "insufficient_evidence"
assert check_drive_traction(10, -1, 0.5, True)["status"] == "insufficient_evidence"
assert check_drive_traction(10, 2, float("nan"), True)["status"] == "insufficient_evidence"
assert check_drive_traction(10, 2, 0.5, False)["status"] == "not_applicable"
assert check_drive_traction(10, 2, 0.5)["status"] == "insufficient_evidence"
```

# 7. Checklist

- 使用前：逻辑核对输入工况与单位；几何核对轮轴、间隙和轮组布置。
- 使用后：保留参数来源与未知项；实测轮地接触、位移与转动，不以“轮数够了”结束检查。
- 不把此直线结论扩展为转弯稳定、货物不滑落或最终任务通过。

# 8. 验证方案与证据

开发校准固定轮型、地面、机器和载荷，比较单次短驱动动作下车体位移及可观察轮子转动。没有轮角或力数据时，只记录“低位移、原因未分辨”，不反算确定摩擦系数。轮子离地、相互对抗或车体接地应先作为独立故障处理。本轮没有逻辑执行、几何或物理证据。

# 9. 交给下一角色的结论

在唯一子结构的 `design_requirements` 保留 `transport_drive_traction@0.1.0`、轮轴与接地要求、左右轮组分控要求、载荷假设、已知附着需求和待校准项。只传决定与证据缺口，不粘贴本篇代码。

控制相关的短结论同时写入 `overall_structure.motion_control`；`script/run_simulation.py::init_simulation_db` 只将总计划的 `functionality/motion_control` 送入控制任务，不自动传递子结构全文。
