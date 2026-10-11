---
id: lift_mass_balance
title: 按质量而非块数布置质心与竖直推进轴
summary: "Lift center of mass centroid balance 质心配平：用完整质量清单估计质心与推进轴的横向偏差，优先重排火把和支架；配置质心代理不冒充游戏刚体质心，低质心不自动保证自由飞行稳定。"
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [lift]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance]
  stages: [plan, draft, build, assemble]
  triggers: [火把单侧布置, 增减支架或连接件, 复制发动机, 外形对称但仍偏转]
prerequisites:
  - 各块或模块质量及代表位置使用同一坐标和同一最终结构版本
  - 明确位置是实际块质心还是有待验证的几何代理
environment_constraints:
  - 没有公开读取实际刚体质心的构建工具
  - Brace的端点或起始位置不能无条件当成其质心
  - 不能依靠添加禁用Ballast实现配平
sources:
  - file: "skill/books/理论力学（第9版）（I） (哈尔滨工业大学理论力学教研室) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: 理论力学
    edition: "第9版 I，高等教育出版社；出版年未核实"
    chapter: "3-6 物体的重心；10-3 质心运动定理"
    pdf_pages: [129, 130, 293, 294, 295]
    printed_pages: [98, 99, 263, 264, 265]
    locator: "式3-29；质量中心定义；式10-13、10-14"
    license_status: unconfirmed
    supports: [质心是质量加权位置, 平行力中心与作用点和大小有关, 质心运动与单块运动不同]
  - file: "skill/books/Rocket Propulsion Elements (George P. Sutton, Oscar Biblarz) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: Rocket Propulsion Elements
    edition: "Ninth Edition, Wiley, 2017"
    chapter: "3.6 Nozzle Alignment; 4.9 Flight Stability"
    pdf_pages: [115, 172]
    printed_pages: [91, 148]
    locator: "thrust line through center of mass; restoring moments"
    license_status: unconfirmed
    supports: [推进轴应相对整机质心核对, 飞行稳定需恢复力矩条件]
code_evidence:
  - path: spatial/build.py
    symbol: Block.center_pos / Machine.get_block_details
    supports: 摘要位置由附着几何构造，不声明为实际质心
  - path: analyze/sim_common.py
    symbol: _calculate_center_of_mass_trajectory
    supports: 当前轨迹函数实际取被跟踪位置的算术均值，非质量加权质心
  - path: blocks/configs/ballast_.yaml
    symbol: disable
    supports: 配重块不属于Agent允许添加的基本块
validation:
  human_review: pending
  logic_tests: not_run
  geometry_checks: not_run
  physics_trials: not_run
  evidence: []
---

# 1. 何时使用与何时不用

推进轴已确定、需要布置火把和底盘时使用。完整刚性部件清单尚未给出时先补信息；已断裂的结构不能继续按原整机配平。

# 2. 原理与来源

《理论力学》页263–264给出 `r_C=sum(m_i*r_i)/sum(m_i)`。只有质量相同且代表位置正确时，块中心算术均值才等于质心。页98–99的平行力中心说明“推力中心”按推力加权，不能与按质量加权的质心混用。

Rocket 页91把推力线偏离质心与转动力矩联系起来；页148另要求稳定或控制力矩。沿竖直推进轴上下移动质量，不会消除该轴的横向偏心；“把重物放低”也不会凭空产生自由飞行中的重力恢复力矩。

# 3. 环境映射与限制

Agent 坐标 `[东,北,上]`。配置质量可作设计代理，`Block.center_pos` 并非所有块的实际质量中心。尤其连接件使用中点只是均匀杆近似，要显式注明；没有可靠近似时令位置缺失。

所有 Hard 发动机实例、各自起始块及总装 Brace 均要计入一次。水炮、火把不提供连接面。优先用现有允许块重排，避免为配平无限增加质量。几何配平不证明启动同步或气动稳定。

# 4. Procedure

1. 整理唯一ID、质量和世界代表位置；标明清单完整性和代理假设。
2. 计算质量中心，比较它与声明的竖直推进轴在水平面的偏差。
3. 偏差过大时优先对称重排非推进块或整体移动推进单元，再核对推力预算。
4. 改动后重新核对真实几何、版本和配平；不由函数直接执行移动。

# 5. 输入约定与参考策略

`parts` 是非空清单，各项 `{id: 非空字符串, mass: 有限正数, position: 三维有限向量}`。质量为同一游戏标度；位置为Agent世界坐标，注明实测或几何代理。`axis_xy` 为规划竖直轴的水平坐标。`tolerance` 为显式非负横向设计容差，非教材稳定阈值。`complete` 三态表示清单核对结果，未知不能按已完整处理。

```python
from math import hypot, isfinite


def check_mass_balance(parts, axis_xy, tolerance, complete=None):
    out = {"status": "insufficient_evidence", "reason": "inventory_unconfirmed",
           "checks": [{"name": "axis_offset", "result": None, "basis": "mass_inventory"}],
           "next_steps": [{"kind": "review", "target": "all_masses_and_position_basis"}]}
    if complete is False:
        out["reason"] = "inventory_known_incomplete"
        return out
    if complete is not True:
        return out
    def vector(v, size):
        return (isinstance(v, (list, tuple)) and len(v) == size
                and all(type(x) in (int, float) and isfinite(x) for x in v))
    try:
        if not vector(axis_xy, 2) or type(tolerance) not in (int, float):
            raise ValueError
        if not isfinite(tolerance) or tolerance < 0 or not isinstance(parts, (list, tuple)) or not parts:
            raise ValueError
        ids, total, moments = set(), 0.0, [0.0, 0.0, 0.0]
        for part in parts:
            ident, mass, pos = part["id"], part["mass"], part["position"]
            if not isinstance(ident, str) or not ident or ident in ids:
                raise ValueError
            if type(mass) not in (int, float) or not isfinite(mass) or mass <= 0 or not vector(pos, 3):
                raise ValueError
            ids.add(ident)
            total += mass
            moments = [moments[i] + mass * pos[i] for i in range(3)]
        center = [v / total for v in moments]
        offset = hypot(center[0] - axis_xy[0], center[1] - axis_xy[1])
        if not all(isfinite(v) for v in [total, *center, offset]):
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        out["reason"] = "missing_invalid_or_duplicate_inventory"
        return out
    acceptable = offset <= tolerance
    out.update(status="candidate" if acceptable else "not_applicable",
               reason="conditional_mass_alignment" if acceptable else "declared_axis_tolerance_exceeded")
    out["estimates"] = {"total_mass": total, "center": center, "horizontal_offset": offset}
    out["checks"] = [{"name": "axis_offset", "result": acceptable,
                      "basis": "declared_mass_positions_and_design_tolerance"}]
    out["next_steps"] = [{"kind": "review" if acceptable else "redesign",
                          "target": "thrust_moments" if acceptable else "rearrange_mass_or_propulsion_axis"}]
    return out
```

# 6. 最小自测

合成数据，未执行：

```python
parts = [{"id": "a", "mass": 1, "position": [-1, 0, 0]},
         {"id": "b", "mass": 3, "position": [1, 0, 0]}]
assert check_mass_balance(parts, [0.5, 0], 0, True)["status"] == "candidate"
assert check_mass_balance(parts, [0, 0], 0.1, True)["estimates"]["center"] == [0.5, 0, 0]
assert check_mass_balance(parts, [0, 0], 0.1, True)["status"] == "not_applicable"
assert check_mass_balance(parts, [0, 0], 0.5, True)["status"] == "candidate"
assert check_mass_balance(parts + parts, [0, 0], 1, True)["status"] == "insufficient_evidence"
assert check_mass_balance([], [0, 0], 1, True)["status"] == "insufficient_evidence"
assert check_mass_balance(parts, [0], 1, True)["status"] == "insufficient_evidence"
assert check_mass_balance(parts, [0, 0], float("inf"), True)["status"] == "insufficient_evidence"
assert check_mass_balance(parts, [0, 0], 1, False)["reason"] == "inventory_known_incomplete"
assert check_mass_balance(parts, [0, 0], 1)["status"] == "insufficient_evidence"
```

# 7. Checklist

- 逻辑：唯一ID、质量来源、全部复制实例、推进轴与容差明确。
- 工具：旋转和装配后重新获取位置；不能把局部坐标混进最终清单。
- 物理：验证代表位置假设与实际偏转；几何对称不是动态稳定证据。

# 8. 验证方案与证据

开发对照保持总质量与推力单元不变，仅重排火把或支架。记录升空前姿态、横向漂移及结构完整性；若质量中心仅为代理，明确只比较设计估计。不使用分析器的算术均值作为质心测量真值。未执行逻辑、几何或物理验证。

# 9. 交给下一角色的结论

`design_requirements` 保留 `lift_mass_balance@0.1.0`、质心估计及其来源、轴位置、容差、优先重排项。Hard 的发动机和底盘分别收到对应质量预算及总装坐标要求。
