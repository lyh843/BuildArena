# BuildArena Codex 产物

本目录集中存放 Codex 为 BuildArena 生成的代码库分析与可视化文件。

## 分析文档

- `codebase-overview.md`：代码库结构和核心实现概览。
- `SUMMARY.md`：结构化架构总结、模块地图和 API 清单。
- `summary.json`：结构化总结的机器可读版本。

## 交互地图

`BuildArena-map.html` 是完全离线的交互式代码地图，包含以下视图：

- Architecture：模块依赖关系与运行时主链路
- File explorer：按目录浏览源码，并用矩形树图查看代码量分布
- CLI & tools：命令行入口和 `@operation` 工具清单
- Data model：SQLModel 数据表及字段
- Pipeline：构建阶段、处理函数规模和任务难度矩阵

直接打开 [`BuildArena-map.html`](./BuildArena-map.html) 即可使用。该文件完全自包含，不依赖服务器或外部资源。

## 刷新地图

推荐在本目录运行：

```bash
node refresh.mjs
```

该命令会重新提取专题数据、调用 codebase-map 的标准构建脚本，并应用移动端容器修正。

底层标准构建命令是：

```bash
node /home/lyh/.codex/skills/codebase-map/scripts/build.mjs map-config.json
```

单独运行标准构建命令不会刷新 `facets.json`，也不会执行本地图的移动端后处理，因此日常更新应使用 `node refresh.mjs`。

## 文件与维护边界

- `map-config.json`：扫描范围、模块分组和主依赖关系，人工维护。
- `meta.json`：架构说明、运行时流程和模块职责，人工维护。
- `extract-facets.mjs`：专题数据提取规则及领域分组，人工维护。
- `facets.json`：由 `extract-facets.mjs` 自动生成。
- `codebase-data.json`：由标准扫描器自动生成。
- `BuildArena-map.html`：最终自包含地图，由刷新命令自动生成。

## 范围与说明

- 地图扫描 7 个源码模块、36 个源文件；代码行数仅用于可视化比例，不作为精确统计指标。
- 仓库中未跟踪的 `docs/` 目录不在地图范围内。
- 架构图展示主要运行时所有权方向。为保持层次清晰，省略了实现层面的循环反向引用，包括 `spatial -> scheduler.task_db` 和 `blocks.descriptors -> spatial`；源码浏览器仍会展示对应文件。
