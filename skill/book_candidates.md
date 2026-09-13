# Support 技能来源：候选书目与人工审核

检索日期：2026-09-12。

状态：候选资料等待人工审核；本次核对依据为官方书目、在线目录、许可说明与下载入口。原书文件由用户审核后下载，正文逐章阅读与技能提炼在后续进行。

## 选择依据

本项目的 Support 任务要求桥梁跨越 5、10、20 个游戏单位的间隙，在桥梁中央承受逐渐增加的载荷；桥梁与地形、货物与桥梁之间均采用接触放置。Soft 使用一个子结构，Medium/Hard 最多使用三个子结构。

本地依据：`levels.yaml:79`、`levels.yaml:104`、`levels.yaml:129`。

据此优先选择静力平衡、支承条件、桁架、梁的内力与变形、稳定性相关教材，并将模块接口作为后续环境适配重点。每条技能的构建合法性与承载效果需要分别验证。

## 候选概览

| ID | 优先级 | 资料 | 语言 | 获取方式 |
| --- | --- | --- | --- | --- |
| S01 | 第一批主教材 | Engineering Statics: Open and Interactive | 英文 | 官网在线阅读、PDF |
| S02 | 第一批主教材 | Structural Analysis，Felix Udoeyo | 英文 | Temple University 在线阅读、PDF、EPUB |
| S03 | 第一批补充 | Modules in Mechanics of Materials，David Roylance | 英文 | MIT OCW 教材汇编及分模块 PDF |
| S04 | 中文主教材备选 | 结构力学Ⅰ——基础教程（第4版） | 中文 | 高等教育出版社书目与纸书购买入口 |
| S05 | 后续补充 | Mechanics of Materials, SI Edition, 11th edition | 英文 | Pearson 纸书及电子书入口 |
| S06 | 概念性补充 | Structures: Or Why Things Don't Fall Down | 英文 | Penguin 纸书及电子书入口 |

优先级是面向当前 Support 原型的选材建议。各书的章节重叠可用于交叉核对；第一批可以先选 S01、S02，随后按需求补充 S03。

## S01 — Engineering Statics: Open and Interactive

- 作者：Daniel W. Baker、William Haynes。
- 官方来源：[教材主页](https://engineeringstatics.org/)。
- 获取入口：[官方 PDF](https://engineeringstatics.org/pdf/statics.pdf)。
- 许可：CC BY-NC-SA 4.0，见[前言许可说明](https://engineeringstatics.org/preface.html)。
- 版本：在线教材持续修订，正式提炼时记录实际 PDF 的版本、下载日期与页码。
- 优先阅读：[第 6 章「结构平衡」](https://engineeringstatics.org/Chapter_06.html)，重点为 6.2 构件间相互作用、6.3 桁架、6.4 节点法、6.5 截面法；[第 9 章](https://engineeringstatics.org/Chapter_09.html)重点为摩擦以及 9.2 滑移与倾覆；按需补读刚体平衡、内力和截面惯性矩。章节编号以实际下载版本为准。
- 候选提炼方向：整体与局部自由体图、受力与支承检查、杆件受拉/受压判断、接触滑移风险检查。
- 环境适配重点：书中的理想节点、构件与接触模型需要对照 Besiege 的积木和连接行为；适用条件与定量参数分别记录。

审核：
- [ ] 选为第一批来源。
- [ ] 确认下载版本、许可说明和优先章节。
- 实际文件名：待填写。
- 审核备注：待填写。

## S02 — Structural Analysis

- 作者：Felix Udoeyo；Temple University 开放教材项目。
- 官方来源与获取入口：[Temple University 教材页面](https://temple.manifoldapp.org/projects/structural-analysis)，页面提供 PDF 和 EPUB 下载。
- 许可：[官方版权页](https://temple.manifoldapp.org/read/structural-analysis/section/779c706d-f775-4a78-b880-d27670e134b1)列为 CC BY-NC-ND 4.0；ND 标识列入人工审核项，后续技能内容的引用、改写与公开发布方式另行确认。
- 优先阅读：第 3 章平衡、支承反力、静定性与稳定性；第 4 章梁和框架内力；第 5 章平面桁架内力；第 7、8 章位移计算。在线目录可在 Temple 教材页面核对。
- 候选提炼方向：支承与稳定性审核、桥梁内力路径分析、桁架方案比较、挠度风险与结构改进检查。
- 环境适配重点：Besiege 接触支承、中央加载与连接方式作为显式任务条件；公式使用范围和游戏中的实测效果分别记录。
- 配套资料：Temple 页面提供官方 errata，下载时一并核对。

审核：
- [ ] 选为第一批来源。
- [ ] 确认 CC BY-NC-ND 4.0 标识及后续材料使用方式。
- [ ] 核对官方勘误。
- 实际文件名：待填写。
- 审核备注：待填写。

## S03 — Modules in Mechanics of Materials

- 作者：David Roylance；MIT OCW 课程 3.11 的教材模块汇编，课程版本为 Fall 1999。
- 官方课程资料：[Course Modules](https://ocw.mit.edu/courses/3-11-mechanics-of-materials-fall-1999/pages/modules/)。
- 整份教材入口：[Course Textbook PDF 资源页](https://ocw.mit.edu/courses/3-11-mechanics-of-materials-fall-1999/resources/3_11_f_99_coursetextbook_pdf/)。页面提供下载按钮，课程 Modules 页面也提供各模块 PDF。
- 许可：MIT OCW 的 CC BY-NC-SA 框架；具体文件或第三方图示的单独标注需要在下载后核对，见[OCW 许可说明](https://ocw.mit.edu/pages/privacy-and-terms-of-use/)。
- 优先阅读：桁架模块，以及 Bending 分组中的剪力与弯矩图、梁应力、梁位移模块；整份汇编中的页码在下载后记录。
- 候选提炼方向：梁截面和构件布置的定性比较、跨度与变形风险检查、局部加强位置的分析步骤。
- 环境适配重点：将几何趋势、材料假设和数值公式分开提炼，定量判断通过游戏实验校准。

审核：
- [ ] 作为 S01/S02 的补充来源。
- [ ] 确认整份汇编或所选模块，保留文件内的来源与许可标注。
- 实际文件名：待填写。
- 审核备注：待填写。

## S04 — 结构力学Ⅰ——基础教程（第4版）

- 作者：龙驭球、包世华、袁驷。
- 出版信息：高等教育出版社，2018 年；ISBN 978-7-04-049930-8。
- 官方书目、目录与购买入口：[高等教育出版社选书页面](https://xuanshu.hep.com.cn/front/book/findBookDetails?bookId=5b4f7af0f18f967ee7f37412)。
- 获取状态：官方页面提供纸书与教学配套资源入口；整书合法 PDF/EPUB 下载渠道待确认。
- 优先阅读：第 2 章结构的几何构造分析；第 3 章静定结构的受力分析；第 5 章静定结构位移计算；第 9 章中的 9.7 静定结构的受力特性、9.8 各种结构形式的受力特点；后续可补读 9.3 空间体系构造分析与 9.5 空间桁架。
- 候选提炼方向：几何稳定性检查、传力路径表达、整体分析与局部分析结合、结构划分与方案比较。
- 环境适配重点：支座、刚接和铰接等教材模型需要明确映射到游戏接触、积木附着和连接件行为。
- 使用边界：商业出版教材，提炼时保留版本与页码，原书文件放入本地忽略目录。

审核：
- [ ] 作为中文主教材来源。
- [ ] 确认可以获取的正版纸书或授权电子版本。
- 实际文件名或纸书信息：待填写。
- 审核备注：待填写。

## S05 — Mechanics of Materials, SI Edition, 11th edition

- 作者：Russell C. Hibbeler。
- 官方书目、目录与购买入口：[Pearson 产品页](https://www.pearson.com/en-ca/subject-catalog/p/mechanics-of-materials-si-edition/P200000010352?view=educator)；[电子书格式入口](https://www.pearson.com/en-au/subject-catalog/p/mechanics-of-materials-si-edition/P200000010352)。
- 版本范围：本清单按官网第 11 版目录给出章节建议，实际下载或借阅版本另行记录。
- 获取状态：官网提供商业纸书与电子书入口；免费授权整书下载渠道待确认。
- 优先阅读：第 6 章弯曲；第 7 章横向剪切；第 11 章梁和轴的设计；第 12 章梁和轴的挠度；第 13 章压杆屈曲。
- 候选提炼方向：弯曲与剪切风险检查、细长受压构件的稳定性审核、加强方案的比较步骤。
- 环境适配重点：材料参数、连续梁假设与屈曲模型需要单独记录，技能的游戏适用范围通过仿真验证。
- 使用边界：商业出版教材，按实际获得的版本记录来源页码与使用范围。

审核：
- [ ] 在需要深化变形或失稳分析时加入。
- [ ] 确认正版版本与可读取格式。
- 实际文件名或纸书信息：待填写。
- 审核备注：待填写。

## S06 — Structures: Or Why Things Don't Fall Down

- 作者：J. E. Gordon。
- 官方书目与获取入口：[Penguin 产品页](https://www.penguin.co.uk/books/13564/structures-by-je-gordon/9780140136289)，提供纸书和电子书选项。
- 获取状态：商业出版读物；免费授权整书下载渠道待确认。
- 拟优先核对的主题：结构行为的直观解释，以及应力、受压构件、材料和连接问题；章节编号与具体覆盖内容待下载后核对。
- 候选提炼方向：面向 Planner 的结构行为解释、方案比较问题清单、失败原因分析提示。
- 环境适配重点：将概念解释转化为可检查的问题和明确适用条件，再对照游戏表现验证。
- 定位：概念性补充，可在静力学与结构分析技能初版完成后选读。

审核：
- [ ] 作为概念性补充来源。
- [ ] 确认实际版本、相关章节与可读取格式。
- 实际文件名或纸书信息：待填写。
- 审核备注：待填写。

## 第一批提炼范围草案

以下条目用于选章和审核，状态统一为“候选，待阅读正文与环境验证”：

| 方向 | 优先来源 | 应保留的环境条件 |
| --- | --- | --- |
| 载荷、接触区域与支承条件的显式列举 | S01、S02 | 间隙跨度、桥端接触、中央货物位置 |
| 整体及子结构自由体图的分析步骤 | S01、S02 | 任务坐标系、载荷与接触反力假设 |
| 几何稳定性与机构风险检查 | S02、S04 | 实际连接形式、可动自由度、装配状态 |
| 桁架构型与杆件受力的初步判断 | S01、S02 | 节点模型、连接强度与构件行为假设 |
| 梁布局与变形风险的定性比较 | S02、S03 | 跨度、截面、材料和连接假设 |
| 接触滑移与支承保持检查 | S01 | 接触方向、摩擦假设、加载过程 |

审核通过后，再根据实际阅读内容确定技能边界、名称、角色适用范围及图关系。
