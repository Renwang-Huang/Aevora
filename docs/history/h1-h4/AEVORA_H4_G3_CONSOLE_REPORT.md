# Aevora H4-G3 Console Gate

**结论：PASS（本地、只读、公共投影范围）**。实际独立 Chromium156.0.8078.4 / Playwright1.64.0 完成三页、三幕和六类状态验收。用户明确授权使用独立测试浏览器，未读取个人浏览器资料。

## 当前工程与实际运行

- `console/web/app.js` 三页：Activity & Decisions、Experience Explorer、Governance Timeline；共享 Case/Run/Mode/Stage Deep Link。
- Cytoscape3.34.3、esbuild0.28.2、Node24.15.0/npm11.12.1 锁定版本；当前构建文件哈希见 `console/src/aevora_observatory/static/BUILD_MANIFEST.json`。
- 独立 Chromium直接访问实际 Uvicorn HTTP / 实际 FalkorDB，未拦截响应或生成假 API。
- `python3 -m scripts.aevora_h4_browser --label browser-validation-06`：退出0，17/17检查PASS，22个真实API响应收据。
- `npm --prefix console test`：退出0，6/6前端行为测试。
- `npm --prefix console run build`：退出0。
- `python -m pytest -q tests/test_aevora_h4_api.py tests/test_aevora_h4_console.py --junitxml=…/g3/API_STATIC_JUNIT.xml`：实际可信隔离运行，退出0，36/36，零skip/error。

全部 argv/UTC/退出码/日志SHA见新H4档案对应 `g3-*` 命令目录。源码提交见 `release-g3-console/SOURCE_MANIFEST.json`。

## 动态与视觉证据

`g3/browser-validation-06/browser/RESULT.json`、`browser-trace.zip`、PNG和真实响应原文均归档。实际截图逐页检查了 Activity的三个历史原生子Agent、Explorer1280布局和Governance的三段查询比较。三幕为不同实际案例，REPLAY标识及来源SHA明显。节点/边列表检查、实际canvas节点指针点击、放缩、Fit、三个时间阶段、Deep Link刷新、键盘Enter/Tab均通过。

六状态分别来自真实网络节流中的Loading、独立空图EMPTY、浏览器实际offline的DISCONNECTED、真实私有proof403的FORBIDDEN、实际受限图PARTIAL、当前图缺少自然发布的UNKNOWN。LIVE断网后旧APPLY被清除，恢复后重新从Core读取。1440/1280/1080/390像素实际检查无水平溢出。

图默认聚焦最多24个真实邻接节点，清楚标注显示与已加载数量；可展开已加载图和使用可访问列表。没有为了补齐故事新增节点或关系。Case C当前页只显示选定实际阶段的Core结果，Governance保留三段比较。

## 失败与修复（全部保留）

1. inspect01在Chromium安装尚未结束时启动，真实exit1/缺少可执行文件；不是功能成绩。
2. inspect02发现Cytoscape默认inline样式被CSP阻止。固定外部CSS预加载其容器样式；未增加unsafe-inline。
3. browser01：ACT II文字选择器同时匹配ACT III；browser02：多个真实历史APPLY导致严格选择器歧义；browser03：主页面ready错误地包含proof对话框预期403；修正测试对象范围，未修改预期业务数据。
4. browser04：390像素时canvas保留旧尺寸，真实水平宽812；新增实际ResizeObserver重排/fit和viewport边界。
5. browser05及最终06：17/17PASS。最终只有预期403/offline控制台错误，零未预期脚本/CSP错误。

## 权威与限制

WHEN/WHY仍来自Core。原始日志、受限候选正文、Host操作、私有Oracle和凭据不进入浏览器。界面保留原NO_PATCH/PROVIDER_FAILURE；两组普通pilot均7/7且EXTERNAL_UNVERIFIED。采纳/因果收益UNKNOWN；浏览器轨迹只证明Viewer实际交互，不证明新模型协作。H3安全、RPO与可观测性限制保留。

字段映射：`docs/UI_COMPONENT_EVIDENCE_MATRIX.csv`。用户要求当前仅本地验证，不向GitHub等远程发布。
