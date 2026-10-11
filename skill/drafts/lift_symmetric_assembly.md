---
id: lift_symmetric_assembly
title: 为Hard规划对称发动机实例与独立连接接口
summary: "Lift hard symmetric assembly chassis engine interfaces 对称总装：由已配平的同型发动机提出对称安装目标，分别保留底盘连接面、加热空间和喷口通道；用实际Brace端点复查，复制不等于已经连接或稳定。"
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [lift]
  levels: [hard]
  roles: [planner, drafter, draft_reviewer, guidance]
  stages: [plan, draft, build, assemble]
  triggers: [两子结构分工, 复用发动机, 用Brace连接底盘, 装配后朝向或质心变化]
prerequisites:
  - 总计划明确发动机与底盘两个独立子结构及复用实例数
  - 同型发动机的局部推进轴与质量中心水平投影已对齐参考点
  - 底盘质量中心位于声明的总装竖直轴，复制实例预期推力相等
environment_constraints:
  - 水炮和火把没有附着面；接口必须留在起始块或木支架等真实有面块上
  - 装配目标坐标不是add_machine的可直接调用参数
  - Brace需要两个实际面且端点距离至少0.01，不证明强度和抗扭刚度
sources:
  - file: "skill/books/理论力学（第9版）（I） (哈尔滨工业大学理论力学教研室) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: 理论力学
    edition: "第9版 I，高等教育出版社；出版年未核实"
    chapter: "3-4 空间任意力系；3-6 平行力系中心"
    pdf_pages: [118, 119, 129, 130]
    printed_pages: [87, 88, 98, 99]
    locator: "式3-18、3-19、3-29"
    license_status: unconfirmed
    supports: [平行同向载荷的对称位置可抵消水平偏心, 模块总装需保留力和力矩信息]
  - file: "skill/books/Rocket Propulsion Elements (George P. Sutton, Oscar Biblarz) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
    title: Rocket Propulsion Elements
    edition: "Ninth Edition, Wiley, 2017"
    chapter: "2.5 Multiple Propulsion Systems; 3.6 Nozzle Alignment"
    pdf_pages: [62, 115]
    printed_pages: [38, 91]
    locator: "同向同时推力相加；相对整机质心对准"
    license_status: unconfirmed
    supports: [多推进系统组合需检查共同方向和工况, 独立模块合格不等于整机对准]
code_evidence:
  - path: levels.yaml
    symbol: lift / hard
    supports: 两个子结构，发动机和底盘，通过Brace形成对称火箭
  - path: spatial/build.py
    symbol: Assembly.add_machine / Assembly.update_blocks / Machine.check_connection
    supports: 从已有机器实例化，实际变换和碰撞检查后分配组合ID，连接端点必须非重合
  - path: spatial/construction.py
    symbol: Blueprint.patch_blueprint
    supports: 修复需保留已执行前缀及装配接口，不能假定可随意重写接口
validation:
  human_review: pending
  logic_tests: not_run
  geometry_checks: not_run
  physics_trials: not_run
  evidence: []
---

# 1. 何时使用与何时不用

仅用于 Hard 的发动机与底盘分工及总装布局。Soft/Medium限制一个子结构，不能借本技能增加独立构建任务。两个独立设计与多个发动机复用实例必须在原计划中明确，不把新增独立设计伪装成复制。

# 2. 原理与来源

《理论力学》页88、99与 Rocket 页38给出条件组合关系：对称位置的相等竖直推力可以抵消相应偏心力矩。这里选择中心、对置或十字安装目标是项目设计候选，不是教材规定必须安装某个数量的发动机。

总装必须重新计算整体质量中心和力系，包含底盘、所有实例与连接件。偏心加载、热不一致或接口变形时，几何对称的前提不足。Brace的连接强度、局部刚度和热损伤不由这些刚体公式给出。

# 3. 环境映射与限制

使用Agent世界坐标 `[东,北,上]`。函数给出**发动机参考轴的目标点**，不是机器原点偏移；实际 `add_machine` 涉及已有模板的位置和旋转，必须由装配角色解析并读取结果。不要猜测新实例的字母前缀或块ID。

蓝图应在支架上预留至少能明确描述的连接接口和力矩传递路径；不能把水炮/火把当成有连接面的结构节点。接口分散布置可作为抵抗相对转动的候选，但不宣称若干根杆自动约束六个自由度。直接接触面的同一点不能再作为零长度Brace的两个端点；既有面是否可用于连接以真实工具为准，面已被附着不等于Brace一概不可使用。

# 4. Procedure

1. 发动机给出参考点、推进轴、质量、热区、喷流通道和支架接口；底盘根据相同坐标约定布置对应面。
2. 在已配平同型模块前提下提出一组对称目标。初版函数只提供1、2、4个实例候选，这是策略范围，不是任务数量硬上限。
3. 检查模块外形、火把与喷口通道；接口选择必须基于实际面中心、法向和端点间距。
4. 装配角色逐步读取实际组合ID与反馈，再连接。遇到失败保留证据，按原有局部修复边界处理，不自动扩大任务或重写固定接口。
5. 完成总装后重新做整机质量、推力、热失配检查；单独发动机通过不能替代总装审核。

# 5. 输入约定与参考策略

`engine_count` 是总计划明确的复用实例数，初版接受整数1/2/4。`radius` 为游戏长度；单实例要求0，多实例要求正数。`axis_xy` 与 `height` 为目标轴水平位置和模块参考点高度，全部有限。`matched_modules` 三态表示同型、同推力、模块质心对轴以及底盘质心居中等前提。此输入由计划与状态整理，不是现有API。

```python
from math import isfinite


def propose_symmetric_mounts(level, engine_count, radius, axis_xy, height,
                             matched_modules=None):
    out = {"status": "insufficient_evidence", "reason": "module_basis_unconfirmed",
           "checks": [{"name": "balanced_module_basis", "result": None,
                       "basis": "equal_thrust_and_reviewed_mass_alignment_required"}],
           "next_steps": [{"kind": "review", "target": "module_axis_mass_interfaces_and_chassis"}]}
    if level not in ("soft", "medium", "hard"):
        out["reason"] = "invalid_level"
        return out
    if level != "hard" or matched_modules is False:
        out.update(status="not_applicable", reason="outside_hard_matched_module_policy")
        return out
    if matched_modules is not True:
        return out
    if type(engine_count) is not int or engine_count < 1:
        out["reason"] = "invalid_instance_count"
        return out
    if engine_count not in (1, 2, 4):
        out.update(status="not_applicable", reason="outside_initial_layout_candidates")
        return out
    if not isinstance(axis_xy, (list, tuple)) or len(axis_xy) != 2:
        out["reason"] = "invalid_axis"
        return out
    try:
        valid = all(type(v) in (int, float) and isfinite(v) for v in [radius, height, *axis_xy])
    except OverflowError:
        valid = False
    if not valid:
        out["reason"] = "invalid_coordinates"
        return out
    if radius < 0 or (engine_count == 1 and radius != 0) or (engine_count > 1 and radius == 0):
        out["reason"] = "radius_incompatible_with_layout"
        return out
    offsets = [(0, 0)] if engine_count == 1 else [(1, 0), (-1, 0), (0, 1), (0, -1)][:engine_count]
    try:
        targets = [[axis_xy[0] + dx * radius, axis_xy[1] + dy * radius, height]
                   for dx, dy in offsets]
        valid = (all(isfinite(v) for p in targets for v in p)
                 and len({tuple(p) for p in targets}) == engine_count)
    except OverflowError:
        valid = False
    if not valid:
        out["reason"] = "nonfinite_or_indistinguishable_targets"
        return out
    out.update(status="candidate", reason="layout_targets_only_not_executable_assembly")
    out["targets"] = targets
    out["checks"] = [{"name": "balanced_module_basis", "result": True,
                      "basis": "declared_matched_modules_and_centered_chassis"},
                     {"name": "geometry_and_strength", "result": None,
                      "basis": "interfaces_collision_and_physics_still_required"}]
    out["next_steps"] = [{"kind": "review", "target": "resolve_actual_transforms_and_brace_faces"}]
    return out
```

# 6. 最小自测

合成目标，未执行；不表示这些坐标能容纳实际模块：

```python
assert propose_symmetric_mounts("hard", 2, 3, [0, 0], 1, True)["targets"] == [[3, 0, 1], [-3, 0, 1]]
assert len(propose_symmetric_mounts("hard", 4, 3, [0, 0], 1, True)["targets"]) == 4
assert propose_symmetric_mounts("hard", 1, 0, [0, 0], 1, True)["status"] == "candidate"
assert propose_symmetric_mounts("medium", 2, 3, [0, 0], 1, True)["status"] == "not_applicable"
assert propose_symmetric_mounts("hard", 6, 3, [0, 0], 1, True)["reason"] == "outside_initial_layout_candidates"
assert propose_symmetric_mounts("hard", True, 3, [0, 0], 1, True)["status"] == "insufficient_evidence"
assert propose_symmetric_mounts("hard", 2, 0, [0, 0], 1, True)["status"] == "insufficient_evidence"
assert propose_symmetric_mounts("hard", 2, 3, [0, 0], float("nan"), True)["status"] == "insufficient_evidence"
assert propose_symmetric_mounts("hard", 2, 3, [0, 0], 1, False)["status"] == "not_applicable"
assert propose_symmetric_mounts("hard", 2, 3, [0, 0], 1)["status"] == "insufficient_evidence"
```

# 7. Checklist

- 逻辑：两个独立子结构设计、明确复用数、独立质量预算、总装共同坐标。
- 工具：全部连接落在真实有面块上，非零Brace端点，实际变换、碰撞和热区分别检查。
- 物理：接口强度、相对转动、全机同步加热和升空待验证，不能以端点合法宣称通过。

# 8. 验证方案与证据

开发阶段先固定发动机模板和底盘，只改变一组连接布局，比较总装后的完整性和相对姿态；所加Brace质量全部进入预算。按当前原生Hard仿真协议评测，若增加全块跟踪只作为单独诊断。没有执行逻辑、装配预检或仿真。

# 9. 交给下一角色的结论

发动机、底盘的各自 `design_requirements` 写 `lift_symmetric_assembly@0.1.0`、参考轴、质量预算、接口位置/方向与保护范围；`overall_structure.assembly` 写复用数、目标位置及真实变换待核对项。不向单个Drafter发送整机所有块的重复正文。
