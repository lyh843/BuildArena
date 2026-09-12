import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const workDir = path.dirname(fileURLToPath(import.meta.url));
await import("./extract-facets.mjs");
execFileSync("node", ["/home/lyh/.codex/skills/codebase-map/scripts/build.mjs", path.join(workDir, "map-config.json")], { stdio: "inherit" });

const out = path.join(workDir, JSON.parse(fs.readFileSync(path.join(workDir, "map-config.json"), "utf8")).out);
let html = fs.readFileSync(out, "utf8");
const fix = ".arch-layout > div { min-width: 0; }\n.rt-badge { white-space: nowrap; }\n";
if (!html.includes(fix)) html = html.replace(".arch-layout { display:", fix + ".arch-layout { display:");

const replacements = [
  ["<html lang=\"en\">", "<html lang=\"zh-CN\">"],
  [">theme: auto</button>", ">主题：跟随系统</button>"],
  ["Module dependency graph", "模块依赖图"],
  ["Hover a module to trace its imports · click for details · layers = dependency depth (a module only imports downward)", "悬停模块可追踪依赖 · 点击查看详情 · 层级表示依赖深度（模块只向下依赖）"],
  ["File explorer — lines of code treemap", "文件浏览器 — 代码行数矩形树图"],
  ["Cell area = lines of code · click a directory to zoom in · breadcrumb to zoom out", "单元格面积 = 代码行数 · 点击目录可放大 · 点击面包屑可返回"],
  ["Largest files in view", "当前视图中的最大文件"],
  ["const fmtNum = (n) => n.toLocaleString(\"en-US\");", "const fmtNum = (n) => n.toLocaleString(\"zh-CN\");"],
  ["themeBtn.textContent = \"theme: \" + theme;", "themeBtn.textContent = \"主题：\" + ({ auto: \"跟随系统\", light: \"浅色\", dark: \"深色\" }[theme] || theme);"],
  [" · Codebase Map", " · 代码库地图"],
  [" || \"codebase atlas\"", " || \"代码库图谱\""],
  ["/ codebase map", "/ 代码库地图"],
  ["`snapshot ${EMBED.generated}", "`快照 ${EMBED.generated}"],
  ["const kindCounts = {};", "const KIND_LABELS = { app: \"入口\", service: \"服务\", core: \"核心\", integration: \"集成\", analysis: \"分析\", data: \"数据\", assets: \"资源\" };\nconst kindLabel = (kind) => KIND_LABELS[kind] || kind;\nconst kindCounts = {};"],
  ["`${n} ${k}`", "`${n} 个${kindLabel(k)}模块`"],
  ["\"lines of code\", \"counted source only\"", "\"代码行数\", \"仅统计源码\""],
  ["\"source files\", \"see footer for scope\"", "\"源文件\", \"统计范围见页脚\""],
  ["\"modules\", kindSummary", "\"模块\", kindSummary"],
  ["`Generated ${EMBED.generated} from a static scan", "`生成于 ${EMBED.generated}，数据来自静态扫描"],
  ["`Line counts cover source files only; dependency dirs, build output, and configured generated paths are excluded. `", "`代码行数仅覆盖源文件；依赖目录、构建输出和配置中排除的生成路径均不计入。`"],
  ["`Module descriptions were written from reading each module's entry points at generation time.`", "`模块说明基于生成时读取的各模块入口文件。`"],
  ["label: \"Architecture\"", "label: \"架构\""],
  ["label: \"File explorer\"", "label: \"文件浏览\""],
  ["${esc(k)}</span>", "${esc(kindLabel(k))}</span>"],
  ["test-time only", "仅测试时"],
  ["imports (what it uses)", "依赖（使用了什么）"],
  ["imported by (who uses it)", "被依赖（谁在使用）"],
  ["${fmtLoc(n.loc)} loc", "${fmtLoc(n.loc)} 行"],
  ["${fmtNum(n.loc)} loc · ${fmtNum(n.files)} files · ${fmtNum(n.commits)} commits", "${fmtNum(n.loc)} 行 · ${fmtNum(n.files)} 个文件 · ${fmtNum(n.commits)} 次提交"],
  ["imports ${importsOf.get(n.id).length} · imported by ${importedBy.get(n.id).length} — click for details", "依赖 ${importsOf.get(n.id).length} 个模块 · 被 ${importedBy.get(n.id).length} 个模块依赖 — 点击查看详情"],
  ["how it runs", "运行方式"],
  ["Request → response → background", "请求 → 响应 → 后台处理"],
  ["full runtime story", "完整运行流程"],
  ["reading the graph", "如何阅读此图"],
  ["Every module sits one layer above the deepest thing it imports, so height = dependency depth.", "每个模块位于其最深依赖的上一层，因此纵向高度表示依赖深度。"],
  ["Hover any node: <span style=\"color:var(--slot-1)\">blue edges</span> point at what it imports,", "悬停任意节点：<span style=\"color:var(--slot-1)\">蓝色边</span>指向它依赖的模块，"],
  ["<span style=\"color:var(--slot-8)\">orange edges</span> come from who imports it. Click to pin details here.", "<span style=\"color:var(--slot-8)\">橙色边</span>来自依赖它的模块。点击可在此固定详情。"],
  [">none</span>", ">无</span>"],
  ["<b>Runs:</b>", "<b>运行位置：</b>"],
  ["<div class=\"l\">loc</div>", "<div class=\"l\">代码行</div>"],
  ["<div class=\"l\">files</div>", "<div class=\"l\">文件</div>"],
  ["<div class=\"l\">commits</div>", "<div class=\"l\">提交</div>"],
  ["<h4>key areas</h4>", "<h4>关键区域</h4>"],
  ["<h4>imports (", "<h4>依赖模块（"],
  ["<h4>imported by (", "<h4>被以下模块依赖（"],
  [")</h4>", "）</h4>"],
  ["Explore files →", "浏览文件 →"],
  ["${esc(n.kind)}</span>", "${esc(kindLabel(n.kind))}</span>"],
  ["? kinds.join(\"·\") : \"L\" + layer;", "? kinds.map(kindLabel).join(\"·\") : \"层 \" + layer;"],
  ["${esc([...stripKinds].join(\"/\"))}", "${esc([...stripKinds].map(kindLabel).join(\"/\"))}"],
  ["[\"code\", \"Code\"", "[\"code\", \"代码\""],
  ["[\"ui\", \"UI / markup\"", "[\"ui\", \"界面 / 标记\""],
  ["[\"data\", \"Data / config\"", "[\"data\", \"数据 / 配置\""],
  ["[\"docs\", \"Docs\"", "[\"docs\", \"文档\""],
  ["[\"styles\", \"Styles\"", "[\"styles\", \"样式\""],
  ["[\"other\", \"Other\"", "[\"other\", \"其他\""],
  ["<optgroup label=\"${esc(kind)}\">", "<optgroup label=\"${esc(kindLabel(kind))}\">"],
  ["${fmtLoc(m.loc)} loc</option>", "${fmtLoc(m.loc)} 行</option>"],
  ["tests / fixtures", "测试 / 固定数据"],
  ["% of view", "%（当前视图）"],
  [" — click to zoom", " — 点击放大"],
  ["area = lines of code", "面积 = 代码行数"],
  ["<h4>current view</h4>", "<h4>当前视图</h4>"],
  ["<span>lines of code</span>", "<span>代码行数</span>"],
  ["<span>files</span>", "<span>文件</span>"],
  ["<span>share of ${esc(pkg.dir)}</span>", "<span>占 ${esc(pkg.dir)} 的比例</span>"],
  [">by value</button>", ">按数值</button>"],
  [">a–z</button>", ">按名称</button>"],
];

for (const [from, to] of replacements) {
  if (!html.includes(from)) throw new Error(`localization marker missing: ${from}`);
  html = html.replaceAll(from, to);
}
fs.writeFileSync(out, html);
console.log(`refresh: Chinese UI and responsive graph containment applied to ${out}`);
