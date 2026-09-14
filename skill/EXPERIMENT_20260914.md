# Planner Skill 首轮构建对照

日期：2026-09-14。这是开发诊断实验，不是正式成功率评估。

## 配置

- 环境：本地 Conda `BuildArena`，Python 3.12；AutoGen 0.7.5。
- 任务：原版 `levels.yaml` 的 Support Soft；有、无技能各一个新构建样本，没有使用历史结果代替基线。
- 全部角色模型：`qwen3.8-max-0902`；`max_tokens=16384`、`timeout=180`、`max_retries=1`、`enable_thinking=true`、`thinking_budget=4096`。未设置 temperature、top_p 或 seed。
- 两个样本并行运行，各一个 worker、总构建时限 1800 秒。额外技能调用计入成本，不是等总 token 比较。
- 只有 Planner 启用技能工具；词法 TF-IDF、Top-5，每次规划最多搜索两次、读取两次、成功知识响应 20,000 字符，最多四轮工具循环。未启用关系图。
- 五条 `0.1.0` 技能以内容哈希冻结；人工审核仍为 pending，显式允许草案。运行中没有更改 Agent、检索器、原始角色提示词或技能快照。

## 结果

| 指标 | 无技能 | 有技能 |
| --- | ---: | ---: |
| 通过原构建审查的机器 | 1 / 1 | 0 / 1 |
| 保存的积木数 | 33，完整构建 | 15，被拒绝的部分构建 |
| 调度器结束耗时（秒，monotonic） | 1190.06 | 1210.07 |
| Planner 尝试次数 | 1 | 2，一次 API 超时重试 |
| Planner 已返回的模型响应数 | 1 | 5，含失败尝试已返回的响应 |
| Planner 可观测输入 / 输出 token | 2537 / 5532 | 27458 / 8789 |
| 全流程可观测输入 / 输出 token 下界 | 757711 / 28135 | 271681 / 27326 |
| 完整操作日志中的失败操作记录 | 0 | 0 |
| 物理仿真、最大承载 | 未测 | 未测 |

两组调度器均正常退出，但 **exit code 0 不代表构建通过或物理成功**。无技能机器为 `approved=1, status=unverified`；有技能机器为 `approved=0, status=objected`。报告中的样本结果分别为 `null`（缺少物理结果）和 `false`（构建被拒绝），两组物理结果均为 `null`，不是实测零分。

有技能组总体 token 较少源于较早停止搭建，不能视为效率提升。其 Planner 可观测 token 从 8069 增至 36247；API 超时请求、供应商内部重试等未返回的 usage 无法完整恢复，表中不是最终账单。统计将失败 Planner 尝试补入下界，但不会与数据库中的成功尝试重复相加。

## 调用与失败证据

1. 第一次规划并行执行两次检索，读到 `support_midspan_bending`；读取 `support_truss_model_gate` 时超过字符预算，完整正文未返回。随后模型生成超时，原调度器进行整任务重试，没有调整实验参数。
2. 第二次规划执行一次检索，成功读取 `support_midspan_bending` 与 `support_contact_fbd`，返回知识累计 19,702 个 JSON 序列化字符。最终 XML 中的子结构 `design_requirements` 记录了版本、设计假设、几何后果及待验证项，这些内容实际进入了 Draft 任务。
3. 无技能计划是 5×5 桥面；技能计划采用 9×3 桥面、向下阶梯加深和跨中加固，并明确接触支承与模型条件。这表明知识影响了设计，不证明设计更正确或承载更强。
4. 技能组在构建到 15 块时，Guidance 认为蓝图后续连接面已被占用，调用原有 objection 工具。异议中的表述涉及 Blocks 16–27 的连接顺序。这是**角色的审查结论**；日志中未记录实际失败的碰撞操作，尚未独立证实所有所述几何冲突。
5. 两次只读 Windows 检查都没有找到标题为 `Besiege` 的窗口，未发送游戏输入，没有启动物理测试。参考策略的纯函数断言通过不替代这部分验证。

本轮没有观察到构建收益；也不能用每组一个样本推断技能普遍有效或无效。下一轮应先核对复杂方案的蓝图编号与连接面交接，再做独立重复和正确场景下的物理验证。

## 本地记录

原始数据位于 Git 忽略的 `datacache/skill_comparison_20260914/`：

- `manifest.json`：两组数据库、运行参数、输入代码哈希和冻结技能清单。
- `runtime_checks.json`：环境及窗口检查；补录 thinking 参数。初始 AutoGen `dump_component()` 漏掉 `extra_body`，已从实际客户端请求参数核对；未来实验记录代码已修正，本轮运行参数未变。
- `skills_snapshot/`：实际使用的五份技能全文和版本哈希。
- `skill_comparison_report.json`：阶段状态、积木、读取记录和去重后的可观测 token 下界。
- 各项目的 `plan/planner_<task_id>.jsonl`：逐次查询、返回全文、模型事件、最终计划及失败尝试。
- 拒绝证据：技能组项目 `machine/aa7dq917/objection_aa7dq917_to_irqpexn4.txt`。

两组各三个阶段消息 JSON 均可解析，运行使用的 Agent、检索器、模型注册和日志代码哈希核对一致。33 项离线回归测试通过，其中包含五条参考策略的 51 个断言。

重新汇总：

```bash
conda run -n BuildArena python -B -m script.run_skill_comparison report \
  --manifest datacache/skill_comparison_20260914/manifest.json
```

`simulation_ready.json` 只列入通过构建审查的无技能机器。打开并确认 Support Soft 场景、匹配已校准窗口后，可用原仿真入口继续；拒绝样本仍保留在比较的分母内：

```bash
BUILD_ARENA_WINDOWS_PROFILE=datacache/windows_profile_support.json \
conda run -n BuildArena python -B -m script.run_simulation \
  --todo datacache/skill_comparison_20260914/simulation_ready.json \
  --max-workers 1 --timeout 300
```

该命令尚未执行。游戏与桌面准备要求见 `docs/windows-simulation.md`。
