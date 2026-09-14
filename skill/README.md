# BuildArena 工程技能

本目录集中存放工程技能的来源记录、技能内容，以及后续的检索和接口代码。

## 当前阶段

- 主题：Support 的桥梁跨越、接触支承、中央承载、结构稳定性与模块连接。
- 状态：已从本地 `statics.pdf` 提炼五条 Support 技能草案；纯函数自测通过，人工审核与物理验证待完成。
- 来源清单：[book_candidates.md](book_candidates.md)。
- 原始文件位置：`skill/books/`，该目录中的原书默认由 Git 忽略。
- 提炼提示词：[EXTRACT_PROMPT.md](EXTRACT_PROMPT.md)。
- 首批技能与来源、检查记录：[drafts/README.md](drafts/README.md)。
- 已提供 Planner 专用的可关闭检索接口；实验启用草案需明确授权，书目审核勾选项未代替人工确认。

## 接口与开关

实现位于 `skill/library.py`，不依赖新服务或新增软件包：

- `SkillLibrary`：解析 YAML frontmatter，校验 ID、适用范围、只读策略与保留终止标记；加载后仅从内存返回文本。
- `SkillSession.search_skills(query)`：按任务、难度、角色、阶段过滤，返回 ID、版本、摘要、前提、验证状态、分数与词项匹配理由。
- `SkillSession.read_skill(skill_id)`：只能读取本次会话检索到的 ID，返回完整正文、版本、校验和与验证状态。不会执行正文中的 Python。
- `configure_planner_skills(...)`：复制实验技能快照，将路径、版本及 SHA-256 写入任务配置；运行时拒绝内容漂移。

首版采用 `tfidf_v1`：英文词项和中文双字词项的稀疏 TF-IDF 余弦相似度。这是**词法向量检索，不是语义 embedding**；同义词召回有限，尚未启用 `relations.json` 中的待审核边。每次规划最多检索 2 次、每次 Top-5、读取 2 次、成功知识响应合计 200,000 字符（以 `json.dumps(..., ensure_ascii=False)` 计数，不是 token 数，简短错误响应不计）。工具循环上限 4 轮，最后强制转为文本生成；格式错误最多再生成 1 次，读取预算不重置。调度器原有整任务重试会创建新会话并单独记录 attempt ID。

仅 Planner 获得技能工具和技能附加指令；技能开关不改变下游角色的提示词与权限。Planner 将适用结论、技能版本、假设和待验证项写入各子结构原有 `design_requirements`，下游沿原有交接路径接收。关闭时不附加技能指令、不绑定技能工具。两组共用相同的角色模型配置、格式重试修复、完整日志记录和下述构建拒绝证据校验。

当前 `qwen3.8-max-0902` 的 Planner 请求超时为 600 秒，其他角色为 1200 秒；SDK 重试一次的设置不变。Draft 和 Build 消息流不再逐条固定等待 5 秒。新成对实验的 manifest 通过 `planner_model_settings` 单独记录 Planner 的实际参数。skill 成对实验入口默认总时限为 `--timeout 7200`（2 小时），覆盖 Plan、Draft 和 Build，不是单次请求时限；已冻结实验的 1800 秒上限保持原样。新知识会话默认使用 200,000 字符预算；已冻结实验配置中的 20,000 字符预算保持不变，不应通过续跑旧实验混合新旧协议，应创建新的 manifest。

```bash
conda run -n BuildArena python -B -m script.run_construction \
  --model qwen3.8-max-0902 --category support --level soft \
  --n_sample 1 --n_worker 1 --timeout 7200 \
  --skills --allow-draft-skills
```

去掉 `--skills --allow-draft-skills` 即为无技能模式。未显式允许草案时，只加载 `human_review: approved` 的技能；当前五条仍为 `pending`。不要仅为运行而改写审核状态。

## 成对实验

首轮实际结果见 [EXPERIMENT_20260914.md](EXPERIMENT_20260914.md)：Support Soft 各一个样本，无技能组完成 33 块构建；技能组搭建到 15 块后被原有 Guidance 拒绝。物理未测，不能据此判断承载收益。

## 构建拒绝的证据校验

`spatial/agent.py` 的 `Objection` 现对 build、refine、assemble 统一校验，不随技能开关变化，也不会改写旧实验结果：

- Guidance 可直接调用只读 `get_block_details` 和 `inspect_geometry(block_ids)`，核对当前坐标、面法向、可附着状态和碰撞。面字母不是固定的全局方向。
- Builder 的实际失败才可能生成证据：碰撞、面已占用、连接端点距离不足，或确实不可用的零件。错误 block ID、面名和不适用的操作只要求纠正，不能据此拒绝蓝图。
- Guidance 必须在失败后核对状态，取得 `evidence_id`，再传入 `raise_objection_build` / `raise_objection_refine`。所有构建拒绝都要求证据，不能通过自称“非几何问题”绕过。草图阶段不受此规则影响。
- 每次修改尝试都会使旧证据失效，reset / 重放也不例外；同时比较实际几何快照，防止未经过操作接口的位置变化漏检。读取状态不会使证据过期。
- 缺失、伪造或过期证据返回继续构建提示，不更新任务拒绝状态、不产生拒绝文件，也不返回终止标记。核对与拦截记录保存在 `machine/<任务绑定目录>/geometry_checks_<task_id>.jsonl`；获准拒绝的文件另附完整操作参数、引擎反馈与状态快照。

这是“拒绝必须有证据”的执行约束，不是完整蓝图可行性证明，也不代替 Besiege 物理仿真。碰撞结果沿用现有几何引擎的碰撞体与检查范围；单次失败仍可能只是构建顺序或操作选择错误。离线回归包含原误拒状态的 16–27 号块连续搭建，以及 AutoGen 收到拒绝拦截后继续构建的工具回放。首轮有/无技能实验使用的是加入该校验之前的流程，后续比较需重新生成两组实验。

## 实验运行

```bash
conda run -n BuildArena python -B -m script.run_skill_comparison build \
  --manifest datacache/skill_comparison_example/manifest.json \
  --level soft --pairs 1 --timeout 7200 --allow-draft-skills
conda run -n BuildArena python -B -m script.run_skill_comparison report \
  --manifest datacache/skill_comparison_example/manifest.json
```

每对独立构建包含有、无技能各一个样本，固定任务、全部角色模型、单请求配置、工作进程数及总构建时限；技能组额外调用照实计费，**并非等总 token 实验**。每个样本独立数据库，技能组共用冻结快照。manifest 保存模型设置白名单（不含 API key）、输入代码哈希、版本与全部尝试，不用旧实验替代新基线。默认模型沿用仓库原有配置，不声明其为最新模型。

构建脚本不会操作游戏窗口。游戏准备好对应 Support 场景后，按 `docs/windows-simulation.md` 使用现有 `script.run_simulation` 分别仿真两个数据库，再执行 `report`。未测物理结果为 `null`，构建被拒绝或预算内未完成则保留在失败样本中。`construction_complete` 只表示原构建流程完成，不表示桥梁物理通过；小样本只用于开发诊断。

每个任务的 `plan/planner_<task_id>.jsonl` 保存查询、候选、读取全文、版本、逐模型/工具事件、最终计划与已观察到的 token；`plan_*_messages.json` 保留可解析的工具事件。报告区分数据库阶段 token 与 Planner 全尝试 token，不将两者直接相加；`observed_token_*_lower_bound` 仅补入尚未计入数据库的 Planner token。中断请求、供应商重试及失败下游阶段的 token 可能无法从现有日志恢复，不能当作零成本。

```bash
conda run -n BuildArena python -B -m unittest discover -s tests -v
```

覆盖检索、预算、草案与适用性过滤、快照篡改、只读边界、AutoGen 工具循环、原始关闭路径、XML 格式重试、日志序列化及五条参考策略的 51 个断言。纯函数测试不等于几何或游戏验证。

## 审核与导入

1. 在候选清单中勾选通过审核的资料，确认版本、章节、获取方式与许可信息。
2. 从清单中的官方入口获取资料，将 PDF、EPUB 或其他原始文件放入 `skill/books/`。
3. 记录实际文件名、版本和需要优先处理的章节；文件命名建议采用 `书目ID_简短书名_版本.pdf`。
4. 提炼时为每条技能保留来源页码、适用前提、Besiege 环境映射与验证状态。
5. 在任务仿真中验证技能适用性，再冻结用于对照实验的技能版本。

接口代码统一放在 `skill/` 下，暂未实现语义 embedding、图扩展或运行时执行策略代码。
