# 跨平台安装指南

`frontend-system-review` 遵循 [Agent Skills 开放规范](https://agentskills.io/specification)(Anthropic 2025-10 发布、2025-12-18 开放为标准),`SKILL.md` 使用标准的 `name`/`description` frontmatter,因此可被 Codex、Claude Code、OpenCode、Gemini CLI、Cline、Cursor、Copilot、Windsurf、Zed 等主流平台直接识别——**各平台只差安装目录,格式零改动**。

- 中文站点:https://linkingoscar.github.io/frontend-system-review/
- 英文版本文档:见 [INSTALLATION.en.md](./INSTALLATION.en.md)

---

## 快速安装

### 方式一:直接把仓库交给 AI(最简单)

把本仓库链接粘贴给你正在使用的 AI 工具,让它自行安装或直接按 SKILL.md 工作:

- 在支持 skill 的编码代理(Codex、Claude Code、OpenCode 等)会话中直接说:**"安装 https://github.com/linkingoscar/frontend-system-review 这个 skill"**,AI 会自行克隆到对应平台的目录;
- 或直接把 [SKILL.md](./skills/frontend-system-review/SKILL.md) 的内容粘贴进对话,AI 即可按其中的评审纪律与工作流执行——适用于任何对话式 AI(ChatGPT、Claude、Gemini 等),无需本地安装。

### 方式二:skills CLI(推荐)

使用 [skills CLI](https://www.skills.sh/docs/cli) 安装，可以保留统一的来源记录和更新流程：

```bash
npx skills add linkingoscar/frontend-system-review --skill '*' -g -y
npx skills list -g
npx skills update -g -y
```

去掉 `-g` 可安装到当前项目。只需要总控时，把 `--skill '*'` 改成 `--skill frontend-system-review`。CLI 会从仓库规范目录识别 1 个总控和 6 个专项 skill。

### 方式三:仓库自带安装脚本

```bash
# macOS / Linux
./install.sh                          # 默认把 7 个 skill 安装到 ~/.agents/skills
./install.sh --platform all           # 显式安装到全部平台目录
./install.sh --skill frontend-system-review   # 只安装总控
./install.sh --platform claude,opencode   # 只安装指定平台
./install.sh --dry-run                # 先预览将执行的操作
./install.sh --scope project --project-dir /path/to/project   # 项目级安装
```

```powershell
# Windows(PowerShell 5.1+,推荐 pwsh 7)
powershell -ExecutionPolicy Bypass -File .\install.ps1
.\install.ps1 -Platform generic,claude,opencode
.\install.ps1 -DryRun
.\install.ps1 -Scope project -ProjectDir D:\my-project
```

脚本参数:

| 参数 | 说明 |
|---|---|
| `--platform <list>` / `-Platform` | 逗号分隔的平台列表:`generic,codex,claude,opencode,gemini,cline,cursor,copilot,all`(默认 `generic`) |
| `--skill <list>` / `-Skill` | 逗号分隔的 skill 名称或 `all`(默认安装整套) |
| `--scope user\|project` / `-Scope` | `user`:安装到当前用户目录(默认);`project`:安装到项目目录 |
| `--project-dir <dir>` / `-ProjectDir` | 与 `--scope project` 配合的项目目录(默认当前目录) |
| `--dry-run` / `-DryRun` | 只显示将执行的操作,不复制 |
| `--force` / `-Force` | 目标已存在时先删除再安装 |
| `--link`(仅 install.sh) | 用符号链接代替复制(默认复制) |
| `--help` / `-Help` | 显示帮助 |

> 两个安装器只复制 `skills/` 下的规范 skill，并在复制后逐个校验文件一致性；发布校验会确保该集合与 release manifest 相同。Unix 版可用 `--link` 保持实时同步。

### 方式四:克隆仓库后安装

```bash
git clone https://github.com/linkingoscar/frontend-system-review.git
cd frontend-system-review
./install.sh --platform generic --skill all

# 固定到可复现版本
git checkout v2.0.0
./install.sh --platform generic --skill all --force
```

> 不要把仓库根目录直接克隆为 skill 目录；仓库根目录是发布与文档工程，可安装内容只在 `skills/frontend-system-review/`。

### 方式五:平台原生命令

```bash
# Gemini CLI
gemini skills install linkingoscar/frontend-system-review --scope user

# skills CLI 也支持按 agent 分发
npx skills add linkingoscar/frontend-system-review --skill '*' -a codex -g -y
```

### 方式六:symlink Hub(一次安装,所有 agent 可见)

以 `~/.agents/skills` 为唯一真实目录,其余目录全部符号链接过去(Codex、Gemini、Cursor、Copilot、Zed、Windsurf、OpenCode 原生读取 `~/.agents/skills`):

```bash
ln -s ~/.agents/skills ~/.claude/skills
ln -s ~/.agents/skills ~/.codex/skills
ln -s ~/.agents/skills ~/.gemini/skills
ln -s ~/.agents/skills ~/.cursor/skills
ln -s ~/.agents/skills ~/.copilot/skills
```

> 操作前若目标目录已存在内容,先合并备份再替换链接。

---

## 各平台安装详情

### Codex(OpenAI Codex CLI)

| 级别 | 路径 |
|---|---|
| 用户级 | `~/.agents/skills/frontend-system-review/`(官方文档现行路径) |
| 项目级 | `.agents/skills/frontend-system-review/`(从当前目录向上扫描到 git 根) |
| 社区常用(未在官方文档列出) | `~/.codex/skills/frontend-system-review/` |

- **引用**:显式 `$frontend-system-review` 提及或 `/skills` 命令;任务匹配 `description` 时自动调用。ChatGPT 桌面端用 `@skill` 选择。
- **验证**:会话内输入 `/skills`,应列出 `frontend-system-review` 及其描述。
- **注意事项**:
  - 本仓库的 `agents/openai.yaml` 是 **skill 级产品配置**(ChatGPT 桌面端 UI 元数据:display_name、short_description、default_prompt 等),由 harness 读取,**不是 Codex agent 定义**,原位保留即可——这正是 Codex 官方 skill 仓库的标准布局。
  - Codex 自定义 subagent 是 TOML 格式(`~/.codex/agents/*.toml`,字段 `name`/`description`/`developer_instructions`),与本 skill 无关;如需"评审代理"角色,请另行定义。
  - Codex 的 AGENTS.md 是纯文本拼接,官方无 `@agent` 引用语法(`@path` 扩展为社区请求,是否已合并未确认)。
  - 修改 SKILL.md 后重启 Codex 生效;支持符号链接(跟随链接)。
  - 技能列表预算:最多 2% 上下文或 8000 字符,过多技能会截断描述。

### Claude Code

| 级别 | 路径 |
|---|---|
| 用户级 | `~/.claude/skills/frontend-system-review/` |
| 项目级 | `.claude/skills/frontend-system-review/` |
| 插件 | `<plugin>/skills/<name>/SKILL.md`(经 marketplace 安装) |

- **引用**:自动(模型按 description 决定加载);手动 `/frontend-system-review`。
- **验证**:会话内 `/skills`(技能管理器),或直接触发 `/frontend-system-review`。
- **注意事项**:
  - 目录名即命令名;frontmatter `name` 字段须与目录名一致(`frontend-system-review` 已符合规范:小写+数字+连字符)。
  - SKILL.md 中引用支撑文件用相对路径(`references/checklist.md`),Claude Code 会按相对路径解析。
  - 旧 `.claude/commands/*.md` 仍兼容,但新技能推荐 skills 目录。
  - 同名冲突优先级:Enterprise > Personal > Project > 内置。

### OpenCode

| 级别 | 路径 |
|---|---|
| 全局 | `~/.config/opencode/skills/frontend-system-review/` |
| 项目 | `.opencode/skills/frontend-system-review/`(从 CWD 向上到 git 根) |
| 兼容目录 | `~/.claude/skills/`、`~/.agents/skills/`(全局);`.claude/skills/`、`.agents/skills/`(项目) |

- **引用**:模型通过 `skill` 工具按 ID 精确加载;V2 CLI 中作为 `/frontend-system-review` 斜杠命令。
- **验证**:检查 `skill` 工具描述中的可用技能列表。
- **注意事项**:frontmatter 仅识别 `name`、`description`、`license`、`compatibility`、`metadata`(本 skill 全部兼容);`name` 须匹配目录名;排查要点:SKILL.md 全大写、name/description 存在、权限非 deny、重启。

### Gemini CLI

| 级别 | 路径 |
|---|---|
| 用户级 | `~/.gemini/skills/frontend-system-review/`(别名 `~/.agents/skills/`) |
| 工作区 | `.gemini/skills/frontend-system-review/`(别名 `.agents/skills/`) |

- **安装命令**:`gemini skills install linkingoscar/frontend-system-review --scope user`
- **验证**:`gemini skills list --all` 或会话内 `/skills list`。
- **注意事项**:
  - 技能名取自 frontmatter `name` 字段(而非目录名)。
  - 只发现一层子目录(`skills/<name>/SKILL.md`),嵌套超过一层不会发现;文件名必须精确 `SKILL.md`(大小写敏感)。
  - 工作区技能需要目录被信任(`/trust`);自动调用时会请求用户批准后注入。

### Cline

| 级别 | 路径 |
|---|---|
| 项目级(推荐) | `.cline/skills/frontend-system-review/` |
| 备选 | `.clinerules/skills/`、`.claude/skills/` |
| 全局 | `~/.cline/skills/`(Windows:`C:\Users\<用户名>\.cline\skills\`) |

- **启用**:Settings → Features → Enable Skills(实验性功能)。
- **引用**:自动(`use_skill` 工具按 description 激活)或 `/frontend-system-review` 斜杠命令。
- **验证**:输入 `/` 查看技能斜杠命令列表,或面板 Skills 标签页。
- **注意事项**:同名时全局优先于项目(与 Claude Code 相反);`.clinerules/` 是常驻规则(≠ 按需加载的技能)。

### Cursor

| 级别 | 路径 |
|---|---|
| 项目级 | `.cursor/skills/frontend-system-review/`、`.agents/skills/` |
| 全局 | `~/.cursor/skills/`、`~/.agents/skills/` |
| 兼容读取 | `.claude/skills/`、`.codex/skills/`(项目与用户级) |

- **引用**:自动匹配或 `/frontend-system-review`;支持分类子目录(如 `.cursor/skills/review/frontend-system-review/SKILL.md`)。
- **验证**:Settings(Ctrl+Shift+J)→ Rules → "Agent Decides" 列表。

### GitHub Copilot(VS Code / Visual Studio)

| 级别 | 路径 |
|---|---|
| 项目级 | `.github/skills/frontend-system-review/`、`.claude/skills/`、`.agents/skills/` |
| 个人 | `~/.copilot/skills/`、`~/.claude/skills/`、`~/.agents/skills/` |

- **生效面**:Copilot 编码代理、Copilot CLI、云代理、VS Code 代理模式。
- **引用**:`/frontend-system-review` 斜杠命令或自动调用。
- **验证**:Chat 视图齿轮 → Agent Customizations → Skills 标签页。
- **注意事项**:frontmatter `name` 含非法字符会静默失败(本 skill 名称合规)。

### Windsurf / Zed(简表)

| 平台 | 用户级 | 项目级 | 激活 |
|---|---|---|---|
| Windsurf | `~/.codeium/windsurf/skills/` | `.windsurf/skills/` | `@frontend-system-review`(手动更可靠) |
| Zed | `~/.agents/skills/` | `.agents/skills/` | 自动(`skill` 工具)/ `/frontend-system-review` / `@frontend-system-review` |

- Zed 仅支持扁平布局(不支持 `group/name/` 嵌套);SKILL.md 改动实时重载;项目技能需工作树受信任。
- Windsurf 跨代理兼容 `.agents/skills/`、`~/.agents/skills/`。

---

## 用户级 vs 项目级

- **用户级**:安装一次,所有项目可用。适合个人工作流。
- **项目级**:随仓库检入(如 `.agents/skills/` 或 `.claude/skills/`),团队共享,配合 git 管理。
- 多数平台支持两级;优先级与同名覆盖规则各平台不同,详见上方各平台注意事项。

## 验证清单

1. 安装后进入目标工具会话,输入 `/skills`(Codex/Claude Code/Gemini)或对应 UI 面板,确认 `frontend-system-review` 出现且描述正确;
2. 触发一次评审(如 `用 frontend-system-review 评审我的项目`),确认 SKILL.md 被加载;
3. 检查支撑文件可访问:`references/checklist.md`、`scripts/inventory_repo.py` 是否随 skill 一起存在;
4. 若技能未出现:确认目录名 = `frontend-system-review`、SKILL.md 首行为 `---` frontmatter、平台实验开关已启用、会话已重启。

## 卸载

```bash
# 删除各平台目录(示例:Claude Code)
rm -rf ~/.claude/skills/frontend-system-review
# Windows
Remove-Item -Recurse -Force "$env:USERPROFILE\.claude\skills\frontend-system-review"
```

## 参考资料

- Agent Skills 开放规范:https://agentskills.io/specification
- Codex skills 文档:https://developers.openai.com/codex/skills
- Claude Code skills 文档:https://code.claude.com/docs/en/skills
- OpenCode skills 文档:https://opencode.ai/docs/skills/
- Gemini CLI skills 文档:https://geminicli.com/docs/cli/skills/
- Cline skills 文档:https://docs.cline.bot/customization/skills
- Cursor skills 文档:https://cursor.com/docs/skills
- VS Code Agent Skills:https://code.visualstudio.com/docs/agent-customization/agent-skills
- Zed skills 文档:https://zed.dev/docs/ai/skills
