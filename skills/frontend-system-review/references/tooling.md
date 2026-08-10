# 确定性工具与机器报告

在正式、深度、可入库或需要重复执行的评审中使用这些工具。脚本本身不替代专业判断：仓库 inventory 和浏览器采集只提供证据，finding、影响与修复仍需结合业务确认。

## 目录

1. 输出目录与运行环境
2. 仓库盘点
3. 变更范围
4. 机器可读报告
5. 证据校验
6. 评分与 Markdown 渲染
7. 基线、门禁与 SARIF
8. 一键构建评审包
9. 运行时浏览器证据
10. 规则快照与版本
11. Eval 套件
12. 退出码与失败处理

## 1. 输出目录与运行环境

将产物写入目标项目的临时目录、用户指定目录或任务工作区，不要写回 skill 目录。

命令中的 `<skill>` 表示本 skill 根目录，`<repo>` 表示被评审仓库。Python 工具仅使用标准库。Windows 若 Python 默认编码不是 UTF-8，先设置 `PYTHONUTF8=1`。

浏览器脚本需要 Node.js 和 Playwright：

- 优先使用目标项目已有的 `playwright`；
- 或用 `--node-modules <目录>` 指向已有 `node_modules`；
- 不要为一次评审自动全局安装或下载浏览器；
- Playwright 自带 Chromium 不存在时，脚本会探测系统 Chrome/Edge；也可传 `--executable-path`。

评审模式下需要执行会生成缓存或构建产物的检查时，优先使用同卷的临时副本；pnpm junction/symlink 跨卷可能改变模块解析。无法保持生产等价时停止重试，记录为环境限制，不把隔离失败写成项目 finding。

## 2. 仓库盘点

```text
python <skill>/scripts/inventory_repo.py <repo> \
  --output <artifacts>/inventory.json
```

输出包括框架、工具、scripts、lockfile、配置、CI、文件统计和有限的风险信号。默认忽略 `.git`、`node_modules`、构建产物和 coverage。

注意：

- `observation` 表示需要人工确认的结构事实；
- `signal` 表示文本命中，不证明可利用性或用户影响；
- 扫描被 `--max-files` 截断时，在报告范围中披露。

## 3. 变更范围

PR、提交或工作区评审先生成变更范围：

```text
python <skill>/scripts/collect_change_scope.py <repo> \
  --base origin/main --head HEAD \
  --output <artifacts>/change-scope.json
```

可改用 `--staged`、`--working-tree` 或 `--diff-file <file>`。输出包含变更文件、增删行、hunk 新行范围、rename/binary 状态、风险类别和优先级。优先级只是调查顺序；必须继续追踪受影响的调用者、契约、测试和运行路径，不能把 diff 外代码一律视为无关。

## 4. 机器可读报告

以 `<skill>/scripts/report.schema.json` 为契约创建 `review.json`。结构包含：

- `review`：对象、模式、深度、结论、范围和摘要；
- `findings`：P0/P1/P2、置信度、状态、维度、证据、影响、修复和验证；
- `unverified_risks`：重要性、当前缺口和验证方法；
- `scoring`：可选维度分和证据充分性；
- `validation`：真实执行、失败、部分执行或未执行的检查。

源代码证据使用相对 `<repo>` 的路径，并包含当前行号。正式报告尽量附最小 `quote`，让校验器确认引用文本仍与文件一致。

需要跨版本稳定跟踪时，为 finding 提供显式 `fingerprint`。未提供时，工具会根据维度、标题和稳定证据锚点计算 `fsr1:` 指纹。不要把行号或当前 finding ID 当作长期身份；重命名、措辞大改或证据迁移时显式保留原指纹。

运行时 artifact 路径使用相对产物目录的路径。不要在 JSON 中记录 cookie、Authorization header、真实 token 或敏感查询值。

## 5. 证据校验

```text
python <skill>/scripts/verify_findings.py <artifacts>/review.json \
  --repo <repo> \
  --artifact-root <artifacts> \
  --strict
```

严格模式会检查：

- 报告顶层结构与枚举；
- finding ID 唯一；
- P0 必须是 `high + confirmed`；
- 源文件位于仓库内、存在且行号有效；
- `quote` 与所引行文本匹配；
- runtime 与 tool 证据都提供 artifact，artifact 不越界且存在；
- finding 有影响、修复和验证步骤。

运行项目命令时优先用标准采集器保存完整的脱敏 stdout/stderr、退出码、哈希和环境：

```text
python <skill>/scripts/capture_command.py \
  --cwd <repo> \
  --output <artifacts>/commands \
  --label typecheck \
  --fail-on-command-error \
  -- pnpm exec tsc --noEmit
```

`--fail-on-command-error` 使被捕获命令非零时采集器退出 1；省略时即使项目命令失败，只要证据完整写入，采集步骤仍退出 0。元数据指向独立 stdout/stderr 日志并记录是否超时与自动脱敏次数；严格报告校验会继续核对这些日志的字节数和 SHA-256。自动脱敏不是秘密扫描器，交付前仍要人工检查 artifact。

不要只在 evidence.summary 中声称“命令已通过/失败”，也不要用摘要替代失败原因。若受工具限制不能完整保存，明确记录截断位置、原始字节数、原因与剩余风险。

把无法满足这些门槛的事项移到 `unverified_risks`，不要删掉验证规则。

## 6. 评分与 Markdown 渲染

需要评分时：

```text
python <skill>/scripts/score_report.py <artifacts>/review.json --write
```

需要强制列出全部维度时增加 `--require-all`。`score: null` 表示不适用，不进入分母。

校验通过后生成 Markdown：

```text
python <skill>/scripts/render_report.py <artifacts>/review.json \
  --output <artifacts>/review.md
```

以 JSON 为事实源，不要分别手改 JSON 与 Markdown。若必须修订，改 JSON、重跑校验和渲染。

## 7. 基线、门禁与 SARIF

用上一次已接受的 `review.json` 做基线：

```text
python <skill>/scripts/compare_reports.py baseline.json current.json \
  --output <artifacts>/baseline-diff.json
```

结果区分 `new / resolved / changed / regressions / unchanged`。基线用于识别增量，不用于隐藏存量问题；正式报告仍保留当前全部 findings。

默认门禁阻止 `block`、`ready_after_fixes`、`unable_to_determine` 结论或已确认 P0，使“通过”与报告的上线语义一致：

```text
python <skill>/scripts/gate_report.py current.json \
  --output <artifacts>/gate-result.json
```

团队确认门槛后，可依据 `scripts/gate-policy.schema.json` 提供 JSON policy。增量 CI 通常采用 `evaluation: new_or_regressed` 并传 `--baseline`。不要擅自把主观总分或所有 P2 设为合并阻断项；政策应有 owner、校准样本和例外流程。

导出 GitHub Code Scanning 可显示的源码 finding：

```text
python <skill>/scripts/export_sarif.py current.json \
  --output <artifacts>/review.sarif
```

SARIF 默认只导出 `confirmed` 且有源码位置的 finding，并包含稳定 `partialFingerprints`。运行时或只有 artifact 的问题保留在 JSON/Markdown 中；不要为满足 SARIF 伪造源码位置。上传或发布外部评论仍需用户明确授权。

## 8. 一键构建评审包

完成 JSON 后，优先一次生成最终产物：

```text
python <skill>/scripts/build_review_bundle.py <artifacts>/draft-review.json \
  --repo <repo> \
  --artifact-root <artifacts> \
  --output <artifacts>/bundle \
  [--baseline baseline.json] [--policy gate-policy.json]
```

输出 `review.json`、`review.md`、`review.sarif`、`verification.json`、`gate-result.json`、可选 `baseline-diff.json` 和带输出文件及核心引擎 SHA-256 的 `manifest.json`。命令严格校验证据并计算已有评分；验证失败或门禁失败时退出 1。把证据 artifact 放在 `--artifact-root` 可解析的位置，评审包不会复制认证状态或任意外部文件。

传递、归档或复检评审包时验证哈希，并可重新检查证据与门禁：

```text
python <skill>/scripts/verify_review_bundle.py <artifacts>/bundle \
  --repo <repo> \
  --artifact-root <artifacts> \
  --require-gate-pass
```

manifest 证明所列文件自生成后未变化，不等同于作者身份签名。需要加密签名时使用组织已有的可信发布/制品签名系统，不在本 skill 中自造密钥体系。

## 9. 运行时浏览器证据

先创建路由清单：

```json
{
  "routes": [
    { "id": "home", "path": "/" },
    {
      "id": "checkout",
      "path": "/checkout",
      "budgets": { "lcpMs": 2500, "cls": 0.1, "transferSize": 500000 },
      "viewports": [
        { "name": "desktop", "width": 1440, "height": 900 },
        { "name": "mobile", "width": 375, "height": 812, "isMobile": true, "hasTouch": true }
      ],
      "scenarios": [
        {
          "id": "validation-and-recovery",
          "steps": [
            { "id": "submit-empty", "action": "click", "target": { "role": "button", "name": "Pay" }, "waitFor": { "target": { "role": "alert" } } },
            { "id": "enter-email", "action": "fill", "target": { "label": "Email" }, "valueEnv": "FSR_TEST_EMAIL" },
            { "id": "retry", "action": "click", "target": { "role": "button", "name": "Retry" } }
          ]
        }
      ]
    }
  ]
}
```

先 dry-run：

```text
node <skill>/scripts/runtime_audit.cjs \
  --base-url http://127.0.0.1:4173 \
  --manifest routes.json \
  --output <artifacts>/runtime \
  --dry-run
```

确认范围后执行：

```text
node <skill>/scripts/runtime_audit.cjs \
  --base-url http://127.0.0.1:4173 \
  --manifest routes.json \
  --output <artifacts>/runtime \
  --runs 3 \
  --full-page \
  --fail-on-navigation-error \
  --fail-on-interaction-error \
  --fail-on-budget
```

可选参数：

- `--storage-state <file>`：使用已有认证状态；不要把该文件复制进报告。
- `--axe-script <axe.min.js>`：运行本地 axe-core。
- `--node-modules <dir>`：指定已有 Playwright/axe 包目录。
- `--trace`：为每个路由和视口保存 trace。
- `--headed`：需要人工视觉确认时显示浏览器。
- `--runs 3`：重复采样并为每个路由/视口生成中位数；默认 1，最多 10。
- `--fail-on-budget`：仅对 manifest 中由项目明确提供的预算门禁。
- `--fail-on-interaction-error`：声明式步骤无法定位、操作或等待目标状态时阻止该工具步骤。

manifest 契约见 `scripts/runtime-manifest.schema.json`。动作只允许 `click/fill/press/select/check/uncheck/hover/wait-for/goto/reload/wait`；定位优先 role、label、test id、placeholder 或可见文本。密码、token 和测试账号使用 `valueEnv` 引用环境变量，工具输出不会回显输入值。不要在 manifest 中嵌入任意脚本。

输出 `runtime-audit.json`、每个场景的 `state-film.json`、逐步截图/差异图和可选 trace。每一步记录前后 URL、焦点、文本/结构摘要哈希、dialog/alert、页面尺寸、截图 SHA-256 与机器可读 state diff；安装 `pngjs` 时生成洋红标记的 PNG diff 和变化比例，否则保留截图哈希与语义差异降级证据。动态时间、动画、随机数据和第三方内容可能制造视觉噪声，diff 不能自动升级为 finding。

基础快照还收集 DOM、布局、console、page error、失败请求、HTTP 错误、LCP/CLS/长任务实验室信号、资源分组、可选 axe 结果，以及带原始计算样本、公式、阈值和限制说明的文本对比度启发式证据。`controls.formControlTotal` 只计 `input/select/textarea`，`interactiveElementTotal` 计链接、按钮、表单控件和显式交互角色，`focusableCount` 才表示当前可聚焦元素；不要混写三者。axe 状态为 `not_run` 时表示该证据面未覆盖，不能解释为通过。

对比度采集只对可解析的纯色祖先背景做 sRGB 相对亮度和 alpha 合成，跳过图片、渐变、滤镜、混合模式和伪元素；每个候选都必须用同一路由、视口和状态的截图复核后才能升级为 finding。该工具不自动创建 findings。INP 需要真实交互，field 结论需要 RUM；不要把该快照写成真实用户 Core Web Vitals。

状态转换（例如登录与会话过期、菜单、表单错误、0/1/1000 条数据、A→B→A、失败/重试/撤销/恢复）优先固化为 `scenarios[].steps[]`。临时探索仍使用 Playwright 的 `snapshot → interaction → snapshot`。只有终态截图或单份 ARIA snapshot 时，只能确认终态，不能声称已经观察到转换过程。

## 10. 规则快照与版本

`<skill>/VERSION` 是工具输出、发布清单和标准快照的唯一版本源。不要在脚本中硬编码另一套版本号。

`references/standards-baseline.json` 固化本版本采用的 WCAG、Core Web Vitals、SARIF 与运行环境基线，同时记录权威来源、复核日期和最迟复核日。正式或深度交付前运行：

```text
python <skill>/scripts/check_standards_freshness.py
```

退出码为 `1` 表示快照已过期或契约不一致。此时不得继续把快照阈值称为“当前标准”；先核对权威来源，更新快照及相关测试，再重新发布。临近最迟复核日时脚本会给出 warning，CI 每月定时运行该检查。

## 11. Eval 套件

开发或修改本 skill 后运行：

```text
python -m unittest discover -s <repo>/evals -v
```

设置 `FRONTEND_REVIEW_NODE_MODULES` 后，浏览器集成 eval 会实际启动本地站点、访问桌面与移动视口并验证截图和 JSON；未设置时该项会明确 skip。

37 项 Eval 覆盖仓库识别、引用匹配、越界行号、路径逃逸、P0 证据门、finding 指纹、跨文件语义警告、完整命令证据、基线差异、增量门禁、SARIF、评审包哈希与篡改检测、变更范围、评分、渲染、运行时 dry-run、声明式交互胶片、视觉 diff、交互失败门禁、真实浏览器采集、版本一致性、发布边界与规则时效。

## 12. 退出码与失败处理

- `0`：命令完成且相应校验通过。
- `1`：报告、评分或运行时检查发现应阻止该工具步骤完成的问题。
- `2`：参数、输入文件、依赖或环境错误。

工具失败不等于被评审项目失败。将环境问题记录为未执行或部分执行，修复工具输入后重跑；不要把缺少 Playwright、axe 或浏览器误报成项目缺陷。
