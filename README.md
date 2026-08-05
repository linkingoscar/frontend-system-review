# Frontend System Review

> 证据驱动的前端系统评审 Skill —— 面向仓库、架构、PR 与运行中 Web 界面的系统级评审。

覆盖业务匹配、技术栈与依赖、模块边界、类型与 API 契约、状态与数据流、渲染与性能、UI/UX 与设计系统、可访问性、测试、CI/CD、发布、安全与可观测性。以资深前端架构师、Web 质量工程师和产品设计审查者的视角工作,优先判断系统是否**正确、可访问、可维护、可度量并能安全发布**;不要把"采用热门技术"当作成熟度证明。

[English README](./README.en.md) · [GitHub Pages 站点](https://linkingoscar.github.io/frontend-system-review/)

---

## 特性

- **证据驱动** —— 每条发现都带 `file:line`、工具输出或运行时测量;事实、推断与未知严格分离,绝不编造文件、行号、命令结果、截图或指标。
- **四种评审模式** —— 仓库系统评审 / 变更评审 / 运行时体验评审 / 方案评审。
- **三种深度** —— 快速扫描 / 标准评审 / 深度审计(默认标准评审)。
- **严格质量门** —— P0/P1/P2 分级、严重度与置信度分离、12 维度评分、证据覆盖率、上线结论,支持机械校验与 CI 门禁。
- **确定性工具链** —— 13 个仅依赖标准库/Python + Node 的脚本:盘点、变更范围、证据校验、评分、渲染、基线对比、门禁、SARIF 导出、一键评审包。
- **可重复审计** —— Playwright 运行时证据采集(截图、console、网络、LCP/CLS、对比度、axe),32 项 eval 测试保障工具行为。

## 评审模式

| 模式 | 适用输入 | 默认产出 |
|---|---|---|
| 仓库系统评审 | 完整项目、目录或技术栈 | 架构与工程质量报告 |
| 变更评审 | PR、diff、提交或若干文件 | 仅报告变更新增或放大的问题 |
| 运行时体验评审 | URL、本地页面、截图或可启动应用 | 响应式、交互、a11y、性能与视觉问题 |
| 方案评审 | RFC、架构图、选型说明 | 决策风险、替代方案和验证计划 |

## 核心纪律

1. 先检查现有材料,再提问。可从仓库或运行页面获得的信息不要让用户重复提供。
2. 将事实、推断和未知分开。不要把源码推断写成运行时事实,也不要编造文件、行号、命令结果、截图或指标。
3. 每条问题都给出证据、用户或业务影响、具体修复和验证方法;不能定位的泛泛意见不要进入 findings。
4. 将严重度与置信度分开。高影响但证据不足的事项标为"待验证",不要直接判为 P0。
5. 先报告会改变结论的问题,再报告打磨项。不要用长篇优点冲淡风险。
6. 只在用户要求时修改代码。评审、诊断或解释请求默认只读。
7. 匹配业务与团队约束。不要默认推荐微前端、Monorepo、大型设计系统或重写。

## 工作流

```text
定义边界 → 建立项目画像 → 风险优先扫描 → 收集可复核证据 → 执行相关维度
→ 运行时验证 → 并行调查与独立验证 → 校准发现 → 评分与上线结论 → 交付结果
```

- **风险优先**:先检查会阻断使用、发布或回滚的事项(泄密/XSS、核心流程正确性、构建失败、阻断型 a11y、布局破裂、发布不可追踪),再检查打磨项。
- **冲突顺序**:安全与数据正确性 > 核心任务可用性与可访问性 > 发布和恢复能力 > 性能与布局稳定性 > 可维护性与交付效率 > 视觉一致性与打磨。
- **运行时验证**:优先生产构建;至少检查桌面与移动视口;状态变化结论必须引用操作前后两份可区分证据;无法运行时明确列出"静态可确认 / 需要运行时验证 / 本次未覆盖"。
- **独立验证**:候选 P0/P1 与上线门禁由未参与编写的验证者复现与反证,防止确认偏差。

## 评分与结论

| 维度 | 说明 |
|---|---|
| 证据状态 | 已确认 / 高可能 / 待验证 / 不适用 |
| 严重度 | P0 阻断上线 / P1 重要 / P2 改进 |
| 评分 | 12 个维度各 0–5 分,默认权重合计 100;等级 A(85+) B(70+) C(55+) D;证据覆盖率 <70% 标"暂定" |
| 上线结论 | 阻断上线 / 修复后可上线 / 可上线但需跟进 / 可接受 / 无法判断 |

任何已确认 P0 优先于总分;未检查维度标 `N/A`,不自动记 0 分;分数不能伪装成客观测量,报告须说明评分依据与限制。

## 工具链

| 脚本 | 功能 |
|---|---|
| `inventory_repo.py` | 确定性仓库盘点(框架/工具/配置/风险信号),输出 observation 与 signal 供人工确认 |
| `collect_change_scope.py` | 收集 PR/提交/工作区的变更文件与行范围,打风险类别 |
| `verify_findings.py` | findings 严格机械校验(结构、枚举、源码引用、quote 匹配、P0 证据门),`--strict` |
| `capture_command.py` | 运行项目命令并保存完整脱敏 stdout/stderr、退出码、哈希与环境元数据 |
| `score_report.py` | 按 12 维度默认权重计算总分、等级与证据覆盖率 |
| `render_report.py` | 将 JSON 报告确定性渲染为中文 Markdown |
| `gate_report.py` | CI 门禁判定;默认策略阻止 `block`、`ready_after_fixes`、`unable_to_determine` 结论与已确认 P0 |
| `export_sarif.py` | 导出 GitHub Code Scanning 兼容的 SARIF 2.1.0(默认仅 confirmed 且有源码位置) |
| `compare_reports.py` | 用稳定 fingerprint 对比基线与当前报告,区分 new / resolved / changed / regressed / unchanged |
| `build_review_bundle.py` | 一键构建评审包(已校验 JSON、Markdown、SARIF、门禁结果、基线差异、SHA-256 manifest) |
| `verify_review_bundle.py` | 校验评审包 manifest 哈希、证据与门禁(篡改检测) |
| `review_common.py` | 共享常量(12 维度权重、严重度/置信度/结论枚举)与 JSON 工具 |
| `runtime_audit.cjs` | Playwright 浏览器证据采集(截图/DOM/console/网络/LCP/CLS/对比度/可选 axe);启发式证据,不自动判定严重度 |

## 参考资料

| 文件 | 用途 |
|---|---|
| `references/checklist.md` | 工程与架构评审清单(12 章节:业务、依赖构建、架构边界、类型数据、状态渲染、组件设计系统、测试、CI/CD、安全、可观测性、场景增补、红旗反证) |
| `references/web-quality.md` | Web 运行时质量(8 维度:路由任务矩阵、a11y、表单交互、响应式、性能 CWV、SEO、内容国际化、验证协议) |
| `references/visual-design.md` | 视觉与设计系统评审指南(10 个评审维度、设计系统细节、视觉反模式、截图报告方法) |
| `references/evidence-and-scoring.md` | 证据状态、严重度、finding 质量门、评分模型与上线结论判定 |
| `references/report-template.md` | 报告模板(正式 10 节 / 紧凑 / 无 findings 三种格式) |
| `references/tooling.md` | 工具链使用说明、输出目录、退出码约定 |
| `references/orchestration.md` | 并行调查与独立验证的编排(角色、上下文隔离、证据交接、合并与停止条件) |

## 测试

```bash
python -m unittest discover -s evals
```

32 项测试通过 subprocess 真实调用脚本,覆盖:仓库盘点、证据校验(越界行号/路径逃逸/重复指纹)、P0 门、评分与覆盖率、Markdown 渲染稳定性、命令脱敏与退出码、运行时浏览器采集(桌面+移动视口、溢出/对比度/axe)、`--fail-on-budget`、基线门禁、SARIF、评审包构建与 SHA-256 篡改检测。运行时相关测试在设置 `FRONTEND_REVIEW_NODE_MODULES` 后执行,否则自动跳过。

## 跨平台安装

兼容 [Agent Skills 开放规范](https://agentskills.io/specification),支持 Codex、Claude Code、OpenCode、Gemini CLI、Cline、Cursor、Copilot、Windsurf、Zed 等主流平台——各平台仅安装目录不同,格式零改动。完整指南见 [INSTALLATION.md](./INSTALLATION.md)。

```bash
./install.sh            # macOS / Linux 一键安装到全部平台
# Windows:
powershell -ExecutionPolicy Bypass -File .\install.ps1
# 仅安装指定平台:
./install.sh --platform claude,opencode
```

| 平台 | 用户级目录 | 会话内验证 |
|---|---|---|
| Codex | `~/.agents/skills/` | `/skills` |
| Claude Code | `~/.claude/skills/` | `/skills` |
| OpenCode | `~/.config/opencode/skills/` | `skill` 工具列表 |
| Gemini CLI | `~/.gemini/skills/` | `gemini skills list` |
| Cline | `~/.cline/skills/` | Skills 标签页 |
| Cursor | `~/.cursor/skills/` | Rules → Agent Decides |
| Copilot | `~/.copilot/skills/` | Skills 标签页 |
| 通用(推荐) | `~/.agents/skills/`(Codex、Gemini、Cursor、Copilot、Zed、Windsurf、OpenCode 原生读取) | `/skills` |

## 快速开始

1. **安装**:见 [跨平台安装](#跨平台安装) 与 [INSTALLATION.md](./INSTALLATION.md)。
2. **发起评审**:提供仓库路径、PR 链接、线上 URL 或方案文档;skill 自动选择评审模式与深度。
3. **正式交付**:报告保存为符合 `scripts/report.schema.json` 的 JSON,通过 `build_review_bundle.py` 一键生成已校验评审包(JSON/Markdown/SARIF/门禁/manifest)。

## 目录结构

```text
frontend-system-review/
├── SKILL.md                     # skill 主定义(评审纪律、模式、工作流)
├── agents/openai.yaml           # skill 前端展示配置(Codex/ChatGPT 桌面端元数据)
├── INSTALLATION.md / .en.md     # 跨平台安装指南(中/英)
├── install.sh / install.ps1     # 一键安装脚本(macOS/Linux / Windows)
├── references/                  # 7 份按需加载的评审参考资料
├── scripts/                     # 13 个确定性工具脚本 + 3 个 schema 契约
├── evals/                       # 32 项 unittest 测试与 fixtures
└── docs/                        # GitHub Pages 站点
```

## License

未指定。使用前请与作者确认许可。

---

*Frontend System Review — 证据驱动的前端系统评审。*
