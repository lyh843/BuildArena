---
id: support_contact_friction
title: 区分静摩擦需求、滑移边界和未知摩擦参数
summary: 在单个接触的法向载荷与切向需求有依据时计算所需摩擦系数，已知系数时检查余量；未知时不猜参数，也不把摩擦满足等同于不会倾覆。
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [support]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance]
  stages: [plan, draft, build, refine, assemble]
  triggers: [桥端可能滑移, 货物可能滑落, 方案依赖摩擦, 将静摩擦始终设为极限值]
prerequisites:
  - 接触局部法线已知，法向载荷和切向需求指向同一接触与同一工况
  - 输入来自有依据的接触模型或独立测量，不能从几何摘要猜测力
environment_constraints:
  - 构建工具不提供实测法向力、切向力或摩擦系数
  - 桥端和货物都是接触放置，没有固定连接替代摩擦
  - 多接触受力分配和倾覆需独立检查
sources:
  - file: skill/books/statics.pdf
    title: "Engineering Statics: Open and Interactive"
    authors: [Daniel W. Baker, William Haynes]
    edition: "标题页日期 2026-09-12；未标数字版次"
    sha256: be09880aeac98e15ecfc2d1104659321b576e40fc2dfc1854f304d322a343c9b
    chapter: "9.1 Dry Friction; 9.2 Slipping vs. Tipping"
    pdf_pages: [331, 332, 333, 334, 335, 336, 337, 338, 339]
    printed_pages: [319, 320, 321, 322, 323, 324, 325, 326, 327]
    locator: "9.1.1 静摩擦与临界运动；9.1.4 非临界情形；图 9.2.2、9.2.3"
    license_status: "PDF 前言声明 CC BY-NC-SA 4.0；人工审核待完成"
    supports: [静摩擦在非临界状态由平衡需求决定, 极限值为摩擦系数乘法向力, 滑移和倾覆应分别检查]
code_evidence:
  - path: levels.yaml
    symbol: support 的三个 task
    supports: 桥与地形及货物无固定连接
  - path: spatial/build.py
    symbol: Machine.get_machine_summary / Machine.get_block_details
    supports: 返回几何与操作文本，不是接触力传感器
  - path: simulation/simulation_support.py
    symbol: main
    supports: 添加配重并返回轨迹日志，未提供接触摩擦系数查询
  - path: analyze/sim_support.py
    symbol: _analyze_ballast_support
    supports: 当前分析输入为货物位置和载荷，不能直接反演每个接触的力
validation:
  human_review: pending
  logic_tests: passed
  geometry_checks: not_run
  physics_trials: not_run
  evidence: ["2026-09-14: tests/test_skills.py::SkillTests.test_trusted_repository_reference_policies"]
---

# 1. 何时使用与何时不用

用于检查“依赖摩擦保持不动”的设计论证，或者比较同一接触模型下不同方案所需的摩擦水平。若参数未知，最有用的输出是所需信息和条件指标，而不是虚构一个系数。

已有滑移、接触分离、撞击或强烈振动时，不使用此静摩擦近似。它不模拟滑动距离，也不处理胶结、机械锁止或多个接触之间未确定的力分配。

# 2. 原理与来源

第 321–322 页区分静摩擦、临界运动和动摩擦。第 324 页明确：尚未达到滑移边界时，摩擦力由平衡所需的切向力决定，不能总写成 `mu_s * N`。

令同一接触的切向需求模为 `T`，压缩法向载荷为 `N > 0`，条件检查为：

```text
T <= mu_s * N
required_mu = T / N
sliding_margin = mu_s * N - T
```

`required_mu` 是由教材关系整理得到的需求指标，不是从环境测得的摩擦系数。第 325–327 页要求滑移与倾覆分别检查；摩擦有余量不能证明接触压力合力仍在接触区域内。

# 3. 环境映射与限制

对南岸、北岸或货物接触分别建立模型。不能把整桥重量分给单个接触，也不能把全部切向力随意分到多个接触。二维反力估算仅在其假设成立时才能作为这里的条件输入。

输入 `N/T` 使用同一明确标度，比例才有意义；方向先在已标明的局部法线与切平面中分解。不能混用 Agent 的竖直轴与游戏的竖直轴。

当前 API 没有读取摩擦系数或接触力的工具。未知系数应输出待校准，不使用现实木材、石材的经验值。增加接触面积也不能被直接声称会增加教材模型中的 `mu_s*N`。

# 4. Procedure

1. 区分静止接触、已经滑移和接触丢失，并确认 Coulomb 近似及力分配的依据。
2. 有 `N/T` 时计算 `required_mu`；缺少它们时停止数值判断并记录观测缺口。
3. 有独立依据的 `mu_static` 才计算余量；达到或越过边界时不继续声称有保持静止的余量。
4. 调整方案时优先减少切向需求、核对加载偏心和接触姿态。不能用地面固定连接绕过任务约束。
5. 分开检查倾覆、接触区域变化和结构内部失效。

# 5. 输入约定与参考策略

- `normal_load`：有限正值，当前接触的压缩法向载荷。
- `tangential_demand`：有限非负值，保持所声明状态所需的切向力模，不是任意一个全局分量。
- `mu_static`：可为 `None`，否则是对同一材料、接触条件和模型有依据的有限非负系数。无上限为一的硬限制。
- `static_model_valid`：`True/False/None`，表示静止接触、准静态工况和采用 Coulomb 模型的前提已经接受、已被否定或未知。为真也不表示物理成功。

每个数值须在阶段记录中附上来源；此输入约定不是新增的状态观测 API。

```python
from math import isfinite


def check_contact_friction(normal_load, tangential_demand, mu_static=None,
                           static_model_valid=None):
    result = {
        "status": "insufficient_evidence", "reason": "",
        "checks": [], "next_steps": [],
    }
    if type(static_model_valid) is not bool:
        result["reason"] = "static_contact_model_unconfirmed"
        return result
    if not static_model_valid:
        result.update(status="not_applicable", reason="outside_static_contact_model")
        return result
    try:
        values = (normal_load, tangential_demand)
        if any(type(v) not in (int, float) or not isfinite(v) for v in values):
            raise ValueError
        if tangential_demand < 0:
            raise ValueError
        if normal_load <= 0:
            result.update(status="not_applicable", reason="no_compressive_contact")
            return result
        required_mu = tangential_demand / normal_load
        if not isfinite(required_mu):
            raise ValueError
        result["estimates"] = {"required_mu": required_mu}
        result["checks"] = [
            {"name": "sliding_reserve", "result": None, "basis": "coefficient_unknown"},
            {"name": "tipping_reserve", "result": None, "basis": "not_computed"},
        ]
        if mu_static is None:
            result["reason"] = "coefficient_missing_not_assumed"
            result["next_steps"] = [{
                "kind": "validation_plan", "target": "calibrate_same_contact_conditions",
            }]
            return result
        if type(mu_static) not in (int, float) or not isfinite(mu_static) or mu_static < 0:
            raise ValueError
        capacity = mu_static * normal_load
        margin = capacity - tangential_demand
        if not isfinite(capacity) or not isfinite(margin):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        result["reason"] = "missing_or_invalid_numeric_inputs"
        return result
    tolerance = 1e-9 * max(capacity, tangential_demand)
    reserve = margin > tolerance
    result["checks"][0] = {
        "name": "sliding_reserve", "result": reserve,
        "basis": "reviewed_coefficient_and_contact_load",
    }
    result["estimates"].update(sliding_margin=margin, friction_limit=capacity)
    result["status"] = "candidate" if reserve else "not_applicable"
    result["reason"] = (
        "conditional_friction_reserve_only" if reserve else "at_or_beyond_sliding_limit"
    )
    result["next_steps"] = [{
        "kind": "review",
        "target": "tipping_and_contact_retention" if reserve else "reduce_tangential_demand",
    }]
    return result
```

容差只是浮点分类阈值，不是物理安全系数。“边界”不等于已经发生滑移；它表示本次不能给出正余量结论。`candidate` 也只描述这一摩擦检查。

# 6. 最小自测

合成输入，未执行；先加载函数：

```python
within = check_contact_friction(10, 2, 0.5, True)
assert within["status"] == "candidate"
assert within["estimates"]["required_mu"] == 0.2
assert within["estimates"]["sliding_margin"] == 3
assert within["checks"][1]["result"] is None
assert check_contact_friction(10, 5, 0.5, True)["status"] == "not_applicable"
assert check_contact_friction(10, 6, 0.5, True)["status"] == "not_applicable"
unknown = check_contact_friction(10, 2, None, True)
assert unknown["status"] == "insufficient_evidence"
assert unknown["estimates"]["required_mu"] == 0.2
assert check_contact_friction(0, 2, 0.5, True)["status"] == "not_applicable"
assert check_contact_friction(10, -2, 0.5, True)["status"] == "insufficient_evidence"
assert check_contact_friction(10, 2, float("nan"), True)["status"] == "insufficient_evidence"
assert check_contact_friction(10, 2, 0.5, False)["status"] == "not_applicable"
assert check_contact_friction(10, 2, 0.5)["status"] == "insufficient_evidence"
```

# 7. Checklist

- `N/T/mu` 来自同一接触条件；正常静止状态没有被强制设为极限摩擦。
- 未知参数没有被零值或经验常数填充；法向反力不是无依据地平均分配。
- 切向余量、倾覆余量、连接强度和货物下落结果分别记录。
- 修改接触姿态后重新核对参数适用性，不沿用旧场景结论。

# 8. 验证方案与证据

逻辑：检查正余量、边界、超限、零法向力及未知参数分支。几何：核对接触法线和实际接触区域。

开发阶段的局部仿真可比较相同材料与接触配置在不同已知侧向需求下的滑移趋势，但若没有独立力数据，不能从高度曲线直接标定 `mu`。同时观察抬起、倾斜与接触丢失，避免把倾覆误判成摩擦不足。

本轮未仿真、未校准摩擦参数；没有滑移预测准确率或承载改善的实测证据。

# 9. 交给下一角色的结论

保留接触对象、输入来源、`required_mu`、系数是否已知、条件余量和未检查的倾覆风险。在相关子结构的 `design_requirements` 中写出需保持的接触姿态与待验证项，不写“摩擦保证稳定”。
