---
id: lift_heating_layout
title: 为每个水炮规划可核对的火把加热位置
summary: "Lift steam heating torch coverage 水炮蒸汽加热：用描述器的火焰球心检查已知炮体表面点，寻找逐炮加热候选；不把包围盒接近或点火按键当作实际受热，避开喷流熄火和木块着火风险。"
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [lift]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance]
  stages: [plan, draft, build, assemble]
  triggers: [选择火把位置, 冷态推力不足, 多炮加热覆盖不全, 蒸汽喷流熄灭火把]
prerequisites:
  - 炮体候选表面点有独立几何依据，不用空隙或包围盒角点替代
  - 火焰球心来自旋转后的实际描述器或相同公式
environment_constraints:
  - 火把和水炮均无附着面，需要分别附着在允许的支撑块上
  - 热区域是配置描述，不是几何引擎实现的热传导求解器
  - 不修改点火时序、积木热参数或工具权限来满足技能
sources:
  - file: "skill/books/Rocket Propulsion Elements (George P. Sutton, Oscar Biblarz) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: Rocket Propulsion Elements
    edition: "Ninth Edition, Wiley, 2017"
    chapter: "2.1 Definitions; 3.6 Nozzle Alignment"
    pdf_pages: [50, 116]
    printed_pages: [26, 92]
    locator: "Eq.2-1、2-2的恒推力前提；启动和停止瞬态"
    license_status: unconfirmed
    supports: [不能无条件忽略推力建立过程, 瞬态可能引入失配]
code_evidence:
  - path: blocks/configs/torch.yaml
    symbol: description / faces / weight
    supports: 热区半径0.3；可引燃木块；水和蒸汽可熄灭火把；无附着面
  - path: blocks/descriptors/torch.py
    symbol: descriptor
    supports: 热区球心等于块代表位置加世界朝向单位向量
  - path: blocks/descriptors/water_cannon.py
    symbol: descriptor
    supports: 入口在中心减0.75倍轴向，出口在中心加1倍轴向
  - path: blocks/configs/water_cannon.yaml
    symbol: description / faces
    supports: 炮体中部收窄且无附着面，包围盒不能当作真实受热表面
validation:
  human_review: pending
  logic_tests: not_run
  geometry_checks: not_run
  physics_trials: not_run
  evidence: []
---

# 1. 何时使用与何时不用

希望水炮进入蒸汽态时，为每个推进单元明确加热候选。只做几何候选筛选；缺少实际炮体表面位置时先核对，不假装已经实现热接触或知道加热需要几秒。

# 2. 原理与来源

Rocket 页26的恒推力简化有启动/停止瞬态可忽略的前提，页92强调瞬态失配。本技能据此要求单独检查游戏的推力建立条件。**火把热区、蒸汽倍数与熄火行为全部来自仓库配置，不是火箭教材结论**；球内点检测是本项目的几何筛选方法，不是传热模型。

# 3. 环境映射与限制

Agent `[东,北,上]`。热球中心 `torch_center + torch_direction`、半径0.3均来自描述器。水炮长度和中部收窄意味着“火把靠近炮体中心”并不充分；描述器的入口/出口轴心也不自动是经过核实的固体表面点。

可先安排火把从侧面接近较宽炮体，再用真实状态确认几何和火焰覆盖。不要让火把实体与水炮重叠，也不要把木支撑置于已知火焰区域。水/蒸汽回扫熄火是独立风险，静态球内点无法检查喷流遮挡或流体作用。

# 4. Procedure

1. 明确每个水炮对应的支撑块、朝向、加热候选表面点和火把位置。
2. 先以真实朝向算热球，再寻找球内的已核定表面点；没有命中仅表示样本不足，不能证明整个炮体都不受热。
3. 覆盖不全时优先改变火把与支架布局；所有候选都需现有碰撞预检及真实加热观察。
4. 不直接把13.76记为已实现推力；停止于逐炮受热和喷流观察，保留原有固定点火协议。

# 5. 输入约定与参考策略

`cannons` 为非空清单 `{id, surface_points}`，点为已核实炮体表面的世界三维坐标；`torches` 为清单 `{id, flame_center}`。ID在各自清单内唯一，点坐标有限。`surface_reviewed` 三态说明表面证据；`False` 表示选点已知无效。半径0.3为本次配置事实，模型仅返回候选配对，不返回构建指令。

```python
from math import dist, isfinite


def check_heating_layout(cannons, torches, surface_reviewed=None):
    out = {"status": "insufficient_evidence", "reason": "surface_basis_unconfirmed",
           "checks": [{"name": "sample_coverage", "result": None, "basis": "real_surface_points_required"}],
           "next_steps": [{"kind": "review", "target": "cannon_surface_and_flame_centers"}]}
    if surface_reviewed is False:
        out.update(status="not_applicable", reason="surface_samples_known_invalid")
        return out
    if surface_reviewed is not True:
        return out
    def vector(v):
        return (isinstance(v, (list, tuple)) and len(v) == 3
                and all(type(x) in (int, float) and isfinite(x) for x in v))
    try:
        if not isinstance(cannons, (list, tuple)) or not cannons or not isinstance(torches, (list, tuple)):
            raise ValueError
        for rows in (cannons, torches):
            ids = [row["id"] for row in rows]
            if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
                raise ValueError
        if any(not vector(t["flame_center"]) for t in torches):
            raise ValueError
        pairs, checks = [], []
        for cannon in cannons:
            points = cannon["surface_points"]
            if not isinstance(points, (list, tuple)) or not points or not all(vector(p) for p in points):
                raise ValueError
            hits = []
            for torch in torches:
                gap = min(dist(p, torch["flame_center"]) for p in points)
                if not isfinite(gap):
                    raise ValueError
                if gap < 0.3:
                    hits.append(torch["id"])
                    pairs.append({"cannon": cannon["id"], "torch": torch["id"], "sample_distance": gap})
            checks.append({"name": cannon["id"], "result": True if hits else None,
                           "basis": "reviewed_point_strictly_inside_config_heat_sphere"})
    except (KeyError, TypeError, ValueError, OverflowError):
        out["reason"] = "missing_or_invalid_geometry_samples"
        return out
    out["checks"], out["candidate_pairs"] = checks, pairs
    if not torches:
        out.update(status="not_applicable", reason="no_torch_in_declared_layout")
    elif all(c["result"] is True for c in checks):
        out.update(status="candidate", reason="sample_coverage_only_not_heat_validation")
        out["next_steps"] = [{"kind": "review", "target": "collision_plume_fire_risk_then_heat_observation"}]
    else:
        out["reason"] = "uncovered_samples_do_not_prove_no_heating"
        out["next_steps"] = [{"kind": "review", "target": "more_surface_evidence_or_reposition_torches"}]
    return out
```

严格球内要求只避开理想相切边界，不是经过验证的加热裕量。没有声称一个样本的覆盖代表全时段可靠供热。

# 6. 最小自测

合成点，未执行，也不是某个真实水炮的形状：

```python
cannons = [{"id": "c", "surface_points": [[0, 0, 0]]}]
near = [{"id": "t", "flame_center": [0.2, 0, 0]}]
assert check_heating_layout(cannons, near, True)["status"] == "candidate"
assert check_heating_layout(cannons, [{"id": "t", "flame_center": [0.3, 0, 0]}], True)["checks"][0]["result"] is None
assert check_heating_layout(cannons, [{"id": "t", "flame_center": [1, 0, 0]}], True)["status"] == "insufficient_evidence"
assert check_heating_layout(cannons, [], True)["status"] == "not_applicable"
assert check_heating_layout(cannons + cannons, near, True)["status"] == "insufficient_evidence"
assert check_heating_layout([{"id": "c", "surface_points": []}], near, True)["status"] == "insufficient_evidence"
assert check_heating_layout(cannons, [{"id": "t", "flame_center": [float("nan"), 0, 0]}], True)["status"] == "insufficient_evidence"
assert check_heating_layout(cannons, near, False)["status"] == "not_applicable"
assert check_heating_layout(cannons, near)["status"] == "insufficient_evidence"
```

# 7. Checklist

- 逻辑：每炮有独立覆盖记录，所用点确实属于炮体，球心取自最终朝向。
- 工具：无实体重叠，不向火把/水炮无面位置继续附着；木支架和热区分别检查。
- 物理：逐炮热状态、蒸汽、持续喷射及火把是否熄灭仍需观察。

# 8. 验证方案与证据

开发验证固定发动机质量、炮数和原有时序，只改变一个火把位置，观察对应水炮热状态和喷流。当前Medium/Hard超过四个非起始块时只随机跟踪四块，未记录某炮的热状态属于缺失，不能当作未加热。扩展仪器须作为单独诊断协议，不能混同正式评分。本轮没有几何或物理试验，函数也未执行。

# 9. 交给下一角色的结论

各 `design_requirements` 保留 `lift_heating_layout@0.1.0`、逐炮加热候选、支撑面要求和热区/喷流风险。向下游传覆盖结论与缺口，不传教材热力学推导，也不承诺两秒内必定加热完成。
