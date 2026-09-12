# Codebase Overview: BuildArena

**生成时间**：2026-09-04 02:06 CST  
**目录**：`/home/lyh/BuildArena`

## 1. Project Identity

**类型**：Python 3.12+ 的多智能体工程构建研究基准，不是 Web 应用（[pyproject.toml](/home/lyh/BuildArena/pyproject.toml:1)，[README.md](/home/lyh/BuildArena/README.md:54)）。

**技术栈**：AutoGen 负责编排智能体；SQLModel + SQLite 管理任务状态；Trimesh、python-fcl、numpy-quaternion 处理三维几何与碰撞；PyAutoGUI/Pynput 操作 Besiege；Pandas/NumPy/Matplotlib/Seaborn 分析实验结果（[pyproject.toml](/home/lyh/BuildArena/pyproject.toml:6)）。

**数据库**：每次实验对应一个启用 WAL 的 SQLite 数据库（[task_db.py](/home/lyh/BuildArena/scheduler/task_db.py:148)）。  
**测试**：未发现自动化测试或覆盖率配置。  
**依赖管理**：`uv`。Node.js 不在运行链路中（[README.md](/home/lyh/BuildArena/README.md:81)）。  
**本地 Git remote**：`git@github.com:lyh843/BuildArena.git`。

## 2. Quick Start

**入口点**：

- [run_construction.py](/home/lyh/BuildArena/script/run_construction.py:50)：创建实验、数据库和构建任务。
- [run_simulation.py](/home/lyh/BuildArena/script/run_simulation.py:107)：派生仿真数据库并运行 Besiege。
- [sim_common.py](/home/lyh/BuildArena/analyze/sim_common.py:697)：按任务类别路由轨迹评分。
- [sampling_path_analysis.py](/home/lyh/BuildArena/analyze/sampling_path_analysis.py:634)：汇总构建成本、轮次和 token 使用。
- [find_coords.py](/home/lyh/BuildArena/script/find_coords.py:6)：校准游戏 GUI 坐标。

```bash
uv sync

uv run -m script.run_construction \
  --model gpt-4o \
  --category transport \
  --level soft \
  --n_sample 64 \
  --n_worker 4

uv run -m script.run_simulation --db path/to/task_database.db
uv run -m analyze.sampling_path_analysis path/to/task_database.db
uv run -m analyze.sim_common --csv_path path/to/simulation/trajectory.csv
```

**运行测试**：仓库没有提供测试命令。

## 3. Architecture Overview

**模式**：CLI 驱动、SQLite 持久化的多阶段任务状态机，结合多进程 worker、AutoGen 对话团队、命令式几何工具和外部游戏仿真（[scheduler.py](/home/lyh/BuildArena/scheduler/scheduler.py:94)，[runner.py](/home/lyh/BuildArena/scheduler/runner.py:310)）。

```text
/home/lyh/BuildArena/
├── script/       # 构建、仿真和坐标校准 CLI
├── scheduler/    # SQLite、任务状态机、多进程调度
├── agents/       # LLM provider/model 注册
├── spatial/      # 几何、Machine/Assembly、智能体团队
├── blocks/       # 积木元数据和动态描述器
├── simulation/   # Besiege 预处理和 GUI/Lua 自动化
├── analyze/      # 构建路径与仿真轨迹评分
└── asset/        # Support 自定义关卡
```

**典型数据流**：

1. [run_construction.py](/home/lyh/BuildArena/script/run_construction.py:78) 从任务和提示词配置创建 `task_database.db`。
2. [scheduler.py](/home/lyh/BuildArena/scheduler/scheduler.py:127) 生成 plan 任务并分配 worker；GUI simulation 串行执行。
3. [runner.py](/home/lyh/BuildArena/scheduler/runner.py:20) 推进 `plan -> draft -> build -> refine/assemble`。
4. [spatial/agent.py](/home/lyh/BuildArena/spatial/agent.py:178) 运行 planner、reviewer、builder、guidance 和 controller。
5. [spatial/build.py](/home/lyh/BuildArena/spatial/build.py:395) 执行积木操作、碰撞检测、控制编排并输出 JSON/BSG。
6. [operations.py](/home/lyh/BuildArena/simulation/operations.py:163) 驱动 Besiege/Lua 生成 CSV，再由分析模块评分。

Transport 额外执行最多三轮 `control <-> simulation` 反馈修正（[runner.py](/home/lyh/BuildArena/scheduler/runner.py:180)）。

## 4. Core Modules

- **`script`**：用户工作流入口。
- **`scheduler`**：数据库、任务状态机和多进程 worker（[worker.py](/home/lyh/BuildArena/scheduler/worker.py:48)）。
- **`agents`**：OpenAI-compatible 和 Anthropic 模型客户端注册（[agents/__init__.py](/home/lyh/BuildArena/agents/__init__.py:23)）。
- **`spatial`**：坐标、积木、碰撞、机器装配和智能体团队（[components.py](/home/lyh/BuildArena/spatial/components.py:6)，[build.py](/home/lyh/BuildArena/spatial/build.py:395)）。
- **`blocks`**：8 种积木/连接器的形状、质量、能力、成本及游戏 XML。
- **`simulation`**：Transport、Support、Lift 的游戏预处理和运行逻辑（[runner.py](/home/lyh/BuildArena/scheduler/runner.py:253)）。
- **`analyze`**：轨迹清洗以及运输距离、承重时间、升力/高度评分（[sim_transport.py](/home/lyh/BuildArena/analyze/sim_transport.py:27)，[sim_support.py](/home/lyh/BuildArena/analyze/sim_support.py:20)，[sim_lift.py](/home/lyh/BuildArena/analyze/sim_lift.py:23)）。

## 5. Data Layer

SQLModel 定义三个核心实体：

- **Config**：实验配置、状态、通过率、平均成本、耗时和用量（[task_db.py](/home/lyh/BuildArena/scheduler/task_db.py:75)）。
- **Task**：stage/status、父任务、重试、结果和绑定关系，是状态机主记录（[task_db.py](/home/lyh/BuildArena/scheduler/task_db.py:100)）。
- **Machine**：蓝图、操作历史文件、审批状态、积木数和成本（[task_db.py](/home/lyh/BuildArena/scheduler/task_db.py:129)）。

Task 用 `parent_id` 形成后继链，以 `bind_plan` 汇聚一次采样路径。Machine/Config 主要通过字符串 ID 关联；只有 Task 自引用声明了数据库外键（[task_db.py](/home/lyh/BuildArena/scheduler/task_db.py:106)）。

Schema 通过 `SQLModel.metadata.create_all()` 创建，没有 Alembic 等正式迁移系统（[task_db.py](/home/lyh/BuildArena/scheduler/task_db.py:157)）。

## 6. API Surface

**类型**：CLI + Python 领域工具 API。追踪源码中没有 REST、GraphQL 或 gRPC endpoint；Flask 虽被声明为依赖，但没有发现 Flask app 或路由实现（[pyproject.toml](/home/lyh/BuildArena/pyproject.toml:12)）。

智能体可调用的主要领域操作包括：

- `start`
- `attach_block_to`
- `connect_blocks`
- `twist_block` / `shift_block`
- `change_control_key`
- `add_control_sequence`

这些方法通过 `@operation(group=...)` 动态注册为 AutoGen 工具（[utils.py](/home/lyh/BuildArena/spatial/utils.py:118)，[build.py](/home/lyh/BuildArena/spatial/build.py:429)）。

**身份验证**：没有应用用户认证层；LLM provider 使用本地 `config.py` 设置（[agents/__init__.py](/home/lyh/BuildArena/agents/__init__.py:8)）。  
**文档**：[intro.ipynb](/home/lyh/BuildArena/intro.ipynb:4) 是 `Machine` 和 `Assembly` API 教程。

## 7. Configuration

- [prompt.yaml](/home/lyh/BuildArena/prompt.yaml:1)：各智能体的系统提示和模型槽位。
- [levels.yaml](/home/lyh/BuildArena/levels.yaml:1)：3 个类别 × 3 个难度，共 9 个任务。
- [blocks/configs](/home/lyh/BuildArena/blocks/configs)：积木几何、连接面、碰撞体、质量、能力和成本。
- [pyproject.toml](/home/lyh/BuildArena/pyproject.toml:1)：Python 版本和运行依赖。
- `config.py`：本地游戏路径、模型 provider 设置和 GUI 坐标；实际内容未读取（[README.md](/home/lyh/BuildArena/README.md:95)）。

外部依赖包括 LLM provider、商业游戏 Besiege 和 Lua Scripting Mod。Support 还需要 `asset/` 内的自定义关卡。构建阶段可脱离游戏，仿真仅声明在 Windows 上验证（[README.md](/home/lyh/BuildArena/README.md:151)，[README.md](/home/lyh/BuildArena/README.md:185)）。

## 8. Testing

未发现：

- 标准测试文件或 `tests/` 目录
- pytest/unittest 配置
- coverage 配置
- CI workflow
- lint 或 format 配置

`intro.ipynb` 是教程，不是自动化测试。本次 overview 遵循只读约束，没有运行应用或测试。

## 9. Key Patterns and Conventions

- **Stage dispatch**：`runners` 字典把七个 stage 映射到异步 handler（[runner.py](/home/lyh/BuildArena/scheduler/runner.py:310)）。
- **持久化命令日志**：`@operation` 记录调用参数和结果，Machine 可重放历史（[utils.py](/home/lyh/BuildArena/spatial/utils.py:118)，[build.py](/home/lyh/BuildArena/spatial/build.py:1381)）。
- **配置驱动工厂**：Blocks 扫描 YAML，并创建 Block、Connector 或 Pointer（[build.py](/home/lyh/BuildArena/spatial/build.py:350)）。
- **对话式协作**：智能体使用 RoundRobinGroupChat，以 `TERMINATE` 或最大轮次结束（[agent.py](/home/lyh/BuildArena/spatial/agent.py:135)）。
- **并发模型**：普通任务多进程并行，GUI simulation 一次只执行一个（[scheduler.py](/home/lyh/BuildArena/scheduler/scheduler.py:155)）。
- **失败恢复**：Task 默认最多重试三次；仿真错误累计超过两次时停止调度（[task_db.py](/home/lyh/BuildArena/scheduler/task_db.py:114)，[scheduler.py](/home/lyh/BuildArena/scheduler/scheduler.py:183)）。

## 10. Development Activity

最近 10 个 commit 主要集中在文档、论文/品牌素材和窄范围 bug 修复：

- `455abae`，2026-05-04：README 更新。
- `bb7e55e`，2026-02-25：修复采样全部完成后的处理逻辑。
- `8513dc2`，2025-11-04：修复智能体消息占位符。
- `addf607`，2025-10-21：修复 demo notebook 相关问题。

## 11. Contributing Quick Start

新增任务类别时：

1. 在 [levels.yaml](/home/lyh/BuildArena/levels.yaml:1) 添加目标。
2. 参照 [simulation_transport.py](/home/lyh/BuildArena/simulation/simulation_transport.py:16) 编写仿真预处理器。
3. 在 [runner.py](/home/lyh/BuildArena/scheduler/runner.py:253) 添加仿真分派。
4. 参照 [sim_transport.py](/home/lyh/BuildArena/analyze/sim_transport.py:27) 编写评分器。
5. 在 [sim_common.py](/home/lyh/BuildArena/analyze/sim_common.py:697) 添加分析路由。

依赖安装命令是 `uv sync`。仓库未提供独立 build、lint、format 或数据库 migration 命令。

## 12. Dependencies

主要依赖来自 [pyproject.toml](/home/lyh/BuildArena/pyproject.toml:7)：

- `autogen-agentchat/core/ext >=0.7.4`：智能体、消息、模型和工具调用。
- `openai >=1.82.0`、`anthropic >=0.52.0`：模型 SDK。
- `sqlmodel >=0.0.24`：SQLite 实体和查询。
- `trimesh >=4.6.10`、`python-fcl >=0.7.0.8`：三维网格和碰撞。
- `numpy-quaternion >=2024.0.8`、`scipy >=1.15.3`：旋转和数值计算。
- `pandas >=2.2.3`：轨迹与实验分析。
- `pyautogui`、`pynput`、`keyboard`、`pywin32`：游戏 GUI 自动化。
- `PyYAML >=6.0.2`：任务、提示词和积木配置。
- `matplotlib`、`seaborn`、`Pillow`：分析与可视化。
- `jupyter >=1.1.1`：教程 notebook。

没有单独的开发依赖组。

## 13. Files Examined

共检查 **38 个文件**：

- 配置/文档：7 个
- CLI 入口：3 个
- 调度和数据层：4 个
- 智能体及空间内核：5 个
- 仿真：4 个
- 分析：5 个
- 积木配置和描述器：10 个
- HTTP API：不存在
- 测试：不存在

没有任何单一类别超过 20 个文件，因此未采用代表性抽样。

## Where to Add New Code

| 想添加 | 放置位置 | 参照文件 |
|---|---|---|
| 新任务或难度 | `/home/lyh/BuildArena/levels.yaml` | [levels.yaml](/home/lyh/BuildArena/levels.yaml:1) |
| 新智能体角色 | `/home/lyh/BuildArena/prompt.yaml`、`spatial/` | [agent.py](/home/lyh/BuildArena/spatial/agent.py:178) |
| 新模型 provider | `/home/lyh/BuildArena/agents/` | [agents/__init__.py](/home/lyh/BuildArena/agents/__init__.py:23) |
| 新积木 | `/home/lyh/BuildArena/blocks/configs/` | [powered_wheel.yaml](/home/lyh/BuildArena/blocks/configs/powered_wheel.yaml:1) |
| 新构建/控制工具 | `/home/lyh/BuildArena/spatial/` | [build.py](/home/lyh/BuildArena/spatial/build.py:687) |
| 新任务 stage | `/home/lyh/BuildArena/scheduler/` | [runner.py](/home/lyh/BuildArena/scheduler/runner.py:310) |
| 新仿真类别 | `/home/lyh/BuildArena/simulation/` | [simulation_transport.py](/home/lyh/BuildArena/simulation/simulation_transport.py:16) |
| 新评分器 | `/home/lyh/BuildArena/analyze/` | [sim_transport.py](/home/lyh/BuildArena/analyze/sim_transport.py:27) |

## Notes

不需要更新 Node.js。这个项目的实际前置条件是 Python 3.12+、`uv`、本地 `config.py`，以及完整仿真时所需的 Windows、Besiege 和 Lua Mod。

主要工程风险是缺少自动化测试、CI、lint/format 约束和正式数据库迁移机制。代码使用 CC BY-NC 4.0，包含非商业限制（[LICENSE](/home/lyh/BuildArena/LICENSE:1)）。

敏感信息扫描已通过。
