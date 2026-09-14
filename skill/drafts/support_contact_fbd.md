---
id: support_contact_fbd
title: 将桥梁支承还原为有证据的接触自由体模型
summary: 在规划或构建审核时列全桥梁载荷与两岸接触，排除虚构固定端，并区分设计假设、落稳观测和信息不足。
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [support]
  levels: [soft, medium, hard]
  roles: [planner, drafter, draft_reviewer, guidance, builder]
  stages: [plan, draft, build, refine, assemble]
  triggers: [建立整体受力模型, 桥端接触不明, 设计依赖地形锚固, 接收新构建状态]
prerequisites:
  - 明确隔离对象为整个桥梁，货物作为外部载荷
  - 每项判断标明来自设计假设还是实际观测
environment_constraints:
  - 桥梁与地形及货物均无固定连接
  - Agent 坐标为东、北、上，游戏内部交换后两分量
  - 设计位置不是导出放置和落稳后的接触状态
sources:
  - file: skill/books/statics.pdf
    title: "Engineering Statics: Open and Interactive"
    authors: [Daniel W. Baker, William Haynes]
    edition: "标题页日期 2026-09-12；未标数字版次"
    sha256: be09880aeac98e15ecfc2d1104659321b576e40fc2dfc1854f304d322a343c9b
    chapter: "5.2 Free-Body Diagrams"
    pdf_pages: [174, 175, 176, 177, 178, 179]
    printed_pages: [162, 163, 164, 165, 166, 167]
    locator: "自由体图五步骤；图 5.2.1、5.2.2、5.2.3"
    license_status: "PDF 前言声明 CC BY-NC-SA 4.0；人工审核待完成"
    supports: [隔离对象与列全外载荷, 按实际约束选择反力, 可提供反力与实际参与受力不同]
code_evidence:
  - path: levels.yaml
    symbol: support 的三个 task
    supports: 接触支承、中央货物、跨度和子结构约束
  - path: spatial/components.py
    symbol: Vector.real / Vector.virtual
    supports: 坐标轴转换
  - path: simulation/simulation_support.py
    symbol: main
    supports: 放置变换与配重添加
  - path: spatial/build.py
    symbol: Machine.get_machine_summary
    supports: 默认分组工具，返回结构状态文本而非接触力
  - path: spatial/agent.py
    symbol: MultiAgents.build
    supports: builder 获得默认工具，guidance 不获得搭建工具
validation:
  human_review: pending
  logic_tests: passed
  geometry_checks: not_run
  physics_trials: not_run
  evidence: ["2026-09-14: tests/test_skills.py::SkillTests.test_trusted_repository_reference_policies"]
---

# 1. 何时使用与何时不用

在 Planner 选择支承方案、Drafter 落实桥端几何、Guidance 审核落点或构建反馈时使用。它输出自由体模型的准备状态，不计算承载上限，也不检测游戏接触。

默认隔离整个桥梁，货物作用力属于外力。若改为“桥梁加货物”，货物接触力变为内力，应重画自由体图，不能沿用本函数的载荷清单。

# 2. 原理与来源

- 教材第 163–164 页要求先隔离对象、选坐标、列外载荷，再用相应反力替代支承。桥自重不能因没有写入目标描述而消失。
- 第 165–166 页区分普通接触、摩擦接触和固定端。接触不自动提供固定端的全部约束。
- 第 166–167 页区分反力“可以存在”和“实际参与受力”。桥伸到地形上方不证明地形已经支承桥梁。

环境映射：建立南岸、北岸和货物接触清单，记录法向方向、接触区域及位置来源。有限接触区域可通过压力分布和合力位置产生转动约束，不能把它简化为无依据的独立固定端力矩。

# 3. 环境映射与限制

任务跨度为 5/10/20 游戏单位，地形顶高为 5，跨度沿 Agent 的 `y` 轴。Soft 一个子结构，其他难度最多三个；这些不是反力位置的实测值。桥端应具有实际接触区域，间隙边缘不必等于接触合力作用点。

`scope=design` 表示仅审核设计假设；`scope=observed` 必须附实际观测依据。摘要只能辅助清点几何和积木，不能证明接触法向力、摩擦系数或已经落稳。知识读取本身不开放任何新工具。

# 4. Procedure

1. 隔离整个桥梁，统一为 Agent 坐标，列出自重、货物和其他外载荷；未知量可保留符号。
2. 为南北两岸分别列接触区域及其证据，删除未经支持的地面锚固假设。
3. 区分设计接触和实际接触；自由落体、明显振动阶段不采用准静态模型。
4. 模型完整时，将压缩法向反力、待定切向力及接触合力位置交给后续分析。未知接触不得默认通过。

# 5. 输入约定与参考策略

`stage` 是当前阶段。`evidence` 是人工或角色整理的字典，不是仓库 API；所有标志只能取 `True/False/None`：

| 标志 | 为真所需的依据 |
| --- | --- |
| `real_coordinates` | 已标明并转换到东、北、上的坐标 |
| `bridge_isolated` | 整桥是隔离对象，内外力未混淆 |
| `loads_complete` | 已清点桥自重、货物和其他外载荷，允许符号量 |
| `south_contact`、`north_contact` | 当前 scope 下有对应桥端接触区域的依据 |
| `quasistatic` | 设计明确限定准静态阶段，或观测支持落稳近似 |
| `assumes_ground_fixity` | 当前方案是否依赖地面固定端；本任务要求为假 |

`scope` 必须是 `design` 或 `observed`。每个标志的证据及时间点应随阶段结论保存，不能将“设计中假设为真”改写成“已观测为真”。

```python
def plan_contact_fbd(stage, scope, evidence):
    required = (
        "real_coordinates", "bridge_isolated", "loads_complete",
        "south_contact", "north_contact", "quasistatic",
    )
    result = {
        "status": "insufficient_evidence", "reason": "",
        "checks": [], "next_steps": [], "scope": scope,
    }
    if stage not in ("plan", "draft", "build", "refine", "assemble"):
        result["reason"] = "unsupported_stage"
        return result
    if scope not in ("design", "observed") or not isinstance(evidence, dict):
        result["reason"] = "invalid_scope_or_evidence"
        return result
    keys = required + ("assumes_ground_fixity",)
    if any(evidence.get(k) is not None and type(evidence[k]) is not bool
           for k in keys):
        result["reason"] = "flags_must_be_boolean_or_none"
        return result
    for key in keys:
        value = evidence.get(key)
        ok = None if value is None else (
            not value if key == "assumes_ground_fixity" else value
        )
        result["checks"].append({
            "name": key, "result": ok, "basis": scope,
        })
    failed = [c["name"] for c in result["checks"] if c["result"] is False]
    missing = [c["name"] for c in result["checks"] if c["result"] is None]
    if failed:
        result.update(status="not_applicable", reason="model_conditions_failed")
        result["next_steps"] = [
            {"kind": "revise_model", "fields": failed},
        ]
    elif missing:
        result["reason"] = "model_evidence_missing"
        result["next_steps"] = [
            {"kind": "obtain_evidence", "fields": missing},
        ]
        if stage in ("build", "refine", "assemble") and "loads_complete" in missing:
            result["next_steps"].append({
                "owner_role": "builder", "tool": "get_machine_summary",
                "arguments": {},
                "expected_feedback": "inventory_text_only_not_contact_forces",
            })
    else:
        result.update(status="candidate", reason="conditional_fbd_ready")
        result["next_steps"] = [{
            "kind": "form_equilibrium_model",
            "normal_reactions": "compression_only",
            "tangential_reactions": "unknown_with_friction_constraints",
            "resultant_locations": "within_supported_contact_regions",
        }]
    return result
```

这些返回值是参考策略的输出约定，不由运行器自动执行。Planner/Drafter 只接收建议；工具提案仅面向已绑定该工具的 Builder。

# 6. 最小自测

合成输入，不是游戏观测；本轮未执行。授权后在同一 Python 命名空间中先加载上方函数，再运行：

```python
flags = dict.fromkeys((
    "real_coordinates", "bridge_isolated", "loads_complete",
    "south_contact", "north_contact", "quasistatic",
), True)
flags["assumes_ground_fixity"] = False
assert plan_contact_fbd("plan", "design", flags)["status"] == "candidate"
assert plan_contact_fbd("plan", "design", {
    **flags, "assumes_ground_fixity": True,
})["status"] == "not_applicable"
missing = plan_contact_fbd("build", "observed", {
    **flags, "loads_complete": None,
})
assert missing["status"] == "insufficient_evidence"
assert missing["next_steps"][-1]["tool"] == "get_machine_summary"
assert plan_contact_fbd("build", "observed", {
    **flags, "quasistatic": False,
})["status"] == "not_applicable"
assert plan_contact_fbd("plan", "design", {
    **flags, "south_contact": 1,
})["status"] == "insufficient_evidence"
```

# 7. Checklist

- 使用前：隔离边界、坐标系、作用载荷、接触区域、scope 和证据时间明确。
- 使用后：没有无依据的固定端、负压支承或摩擦常数；设计结论仍标记为假设。
- 工具只能辅助核对模型几何，真实接触和落稳状态需要独立物理证据。

# 8. 验证方案与证据

逻辑：上方自测检查缺失、错误假设和正常分支。几何：人工核对导出变换后的桥端接触候选区域，不能只用包围盒长度判断。局部物理：同一设计在开发场景中检查落稳前后两岸是否保持接触，再记录中央加载时的接触丢失和货物轨迹。

没有运行几何工具或仿真，没有物理通过记录。不能以源码检查替代人的模型审核。

# 9. 交给下一角色的结论

保留隔离对象、scope、南北接触区域、载荷清单、未知反力和失效假设。将各子结构负责的接触或传力职责写入其 `design_requirements`，由 `sub_structures` 继续传递；完整技能正文不必跨阶段复制。
