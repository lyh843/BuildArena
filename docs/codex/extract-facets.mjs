import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const workDir = path.dirname(fileURLToPath(import.meta.url));
const cfg = JSON.parse(fs.readFileSync(path.join(workDir, "map-config.json"), "utf8"));
const repo = cfg.repo;
const read = (rel) => fs.readFileSync(path.join(repo, rel), "utf8").replaceAll("\r\n", "\n");

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    return entry.isDirectory() ? walk(full) : [full];
  });
}

const primaryModules = new Set([
  "script.run_construction",
  "script.run_simulation",
  "script.find_coords",
  "analyze.sampling_path_analysis",
  "analyze.sim_common",
]);
const executableRoots = ["script", "scheduler", "simulation", "analyze", "spatial"];
const commands = executableRoots
  .flatMap((dir) => walk(path.join(repo, dir)))
  .filter((file) => file.endsWith(".py") && /if __name__ == ["']__main__["']/.test(fs.readFileSync(file, "utf8")))
  .map((file) => {
    const rel = path.relative(repo, file).replaceAll(path.sep, "/");
    const module = rel.slice(0, -3).replaceAll("/", ".");
    const src = fs.readFileSync(file, "utf8");
    const args = [...src.matchAll(/add_argument\(\s*(["'])([^"']+)\1/g)].map((m) => m[2]);
    return { module, args, primary: primaryModules.has(module) };
  })
  .sort((a, b) => Number(b.primary) - Number(a.primary) || a.module.localeCompare(b.module));

const buildSrc = read("spatial/build.py");
const operations = [...buildSrc.matchAll(/^\s*@operation(?:\(([^)]*)\))?\s*\n\s*def\s+(\w+)\s*\(/gm)].map((m) => ({
  name: m[2],
  group: m[1]?.match(/group\s*=\s*["']([^"']+)/)?.[1] ?? "default",
}));
const operationGroups = Object.groupBy(operations, (op) => op.group);
const operationGroupLabels = { build_only: "仅构建", build: "构建", default: "默认", refine: "优化", control: "控制" };

const dbSrc = read("scheduler/task_db.py");
const tables = [...dbSrc.matchAll(/^class\s+(Config|Task|Machine)\(SQLModel, table=True\):\n([\s\S]*?)(?=^class\s|^def\s)/gm)].map((m) => ({
  name: m[1],
  fields: [...m[2].matchAll(/^ {4}(\w+):/gm)].map((field) => field[1]),
}));

const runnerSrc = read("scheduler/runner.py");
const stages = [...runnerSrc.matchAll(/^\s*["'](\w+)["']:\s*run_(\w+)/gm)].map((m) => m[1]);
const runnerLines = runnerSrc.split(/\r?\n/);
const stageRows = stages.map((stage) => {
  const start = runnerLines.findIndex((line) => line.startsWith(`async def run_${stage}(`));
  let end = runnerLines.findIndex((line, index) => index > start && (line.startsWith("async def run_") || line.startsWith("runners:")));
  if (end < 0) end = runnerLines.length;
  const labels = { plan: "规划", draft: "草拟", build: "构建", assemble: "组装", control: "控制", refine: "优化", simulation: "仿真" };
  return { label: labels[stage] ?? stage, meta: `run_${stage} · ${end - start} 行`, bar: end - start };
});

const levelPairs = [...read("levels.yaml").matchAll(/^level:\s*(\w+)\r?\ncategory:\s*(\w+)/gm)].map((m) => ({ level: m[1], category: m[2] }));
const categoryLabels = { transport: "运输", support: "支撑", lift: "抬升" };
const levelLabels = { soft: "简单", medium: "中等", hard: "困难" };
const taskGroups = Object.entries(Object.groupBy(levelPairs, (pair) => pair.category)).map(([category, pairs]) => ({
  title: categoryLabels[category] ?? category,
  chips: pairs.map((pair) => levelLabels[pair.level] ?? pair.level),
}));

const cliTree = (primary) => commands.filter((cmd) => cmd.primary === primary).map((cmd) => ({
  label: `python -m ${cmd.module}`,
  badge: primary ? "主要" : "内部",
  children: cmd.args.map((arg) => ({ label: arg, badge: arg.startsWith("-") ? "选项" : "参数" })),
}));

const facets = {
  facets: [
    {
      id: "interfaces",
      nav: "命令行与工具",
      title: "本地接口总览",
      headline: `${commands.length} 个可执行模块 · ${operations.length} 个已注册智能体工具`,
      sub: "不包含 HTTP、GraphQL、gRPC、WebSocket 或 Webhook 端点",
      hero: { v: String(commands.length), l: "命令行模块", s: `${commands.filter((c) => c.primary).length} 个主要入口 · ${operations.length} 个智能体工具` },
      columns: 2,
      sections: [
        {
          kind: "tree",
          title: "可执行 Python 模块",
          sub: "展开分组可查看 argparse 参数",
          items: [
            { label: "文档化工作流", badge: "主要", children: cliTree(true) },
            { label: "内部与调试入口", badge: "内部", children: cliTree(false) },
          ],
        },
        {
          kind: "groups",
          title: "向 AutoGen 暴露的机器工具",
          sub: "从 spatial/build.py 的 @operation 装饰器中发现",
          groups: Object.entries(operationGroups).map(([group, ops]) => ({
            title: operationGroupLabels[group] ?? group,
            accent: group === "build",
            chips: ops.map((op) => op.name),
          })),
        },
      ],
    },
    {
      id: "data",
      nav: "数据模型",
      title: "SQLite 任务图与产物存储",
      headline: `${tables.length} 张 SQLModel 表 · 文件系统载荷`,
      sub: "scheduler/task_db.py 与 datacache/<project>/",
      hero: { v: String(tables.length), l: "SQLite 数据表", s: `${tables.reduce((sum, table) => sum + table.fields.length, 0)} 个声明字段` },
      columns: 2,
      sections: [
        {
          kind: "groups",
          title: "SQLModel 记录",
          groups: tables.map((table) => ({ title: table.name, accent: table.name === "Task", chips: table.fields })),
        },
        {
          kind: "groups",
          title: "文件系统载荷",
          groups: [
            { title: "智能体工作", chips: ["规划 JSON", "对话 Markdown", "消息 JSON", "异议记录"] },
            { title: "机器状态", accent: true, chips: ["操作历史 JSON", "完整历史 JSON", "Besiege BSG", "控制 JSON"] },
            { title: "评测结果", chips: ["轨迹 CSV", "指标 JSON", "分析表 CSV", "通过案例 BSG"] },
          ],
        },
      ],
    },
    {
      id: "pipeline",
      nav: "流水线",
      title: "调度阶段与基准矩阵",
      headline: `${stages.length} 个路由阶段 · ${levelPairs.length} 个基准任务`,
      sub: "SQLite 轮询配合多进程工作单元；仿真阶段串行执行",
      hero: { v: String(stages.length), l: "任务阶段", s: `${levelPairs.length} 个类别/难度组合` },
      columns: 2,
      sections: [
        { kind: "loclist", title: "阶段处理函数", sub: "函数行数仅用于视觉参考，不代表复杂度", rows: stageRows },
        {
          kind: "tree",
          title: "任务流转",
          items: [
            { label: "构建", badge: "流水线", children: [
              { label: "规划", badge: "LLM", children: [
                { label: "草拟", badge: "LLM", children: [
                  { label: "构建", badge: "工具", children: [{ label: "可旋转时进行优化", badge: "工具" }] },
                ] },
              ] },
              { label: "存在多个子结构时进行组装", badge: "汇合" },
            ] },
            { label: "运输反馈循环", badge: "流水线", children: [
              { label: "控制", badge: "LLM", children: [{ label: "仿真", badge: "Besiege", children: [{ label: "最多重复 3 次试验", badge: "反馈" }] }] },
            ] },
            { label: "支撑 / 抬升", badge: "流水线", children: [{ label: "仿真", badge: "Besiege" }] },
          ],
        },
        { kind: "groups", title: "基准任务", sub: "levels.yaml", groups: taskGroups },
      ],
    },
  ],
};

fs.writeFileSync(path.join(workDir, "facets.json"), JSON.stringify(facets, null, 2) + "\n");
console.log(`facets: ${commands.length} CLIs, ${operations.length} tools, ${tables.length} tables, ${stages.length} stages, ${levelPairs.length} tasks`);
