# Nyxuri Shell 路线图

> 本页只回答：现在在哪、下一步是什么、什么已定死。运行行为以源码与契约测试为准；
> 开发契约见 [AGENTS](AGENTS.md)；知识库索引见 [llms.txt](../llms-wiki/llms.txt)。
> 阶段状态仅在有可复现证据时更新，不以目录、字符串、Loader 存在或隐藏 UI 作为完成证明。
> 各阶段任务分解与逐项验收记录在追加式台账
> [shell-roadmap-ledger](../llms-wiki/archive/shell-roadmap-ledger.md)。
> 当前整体处于**实验性阶段**（BUG 多、外观未开发、暂不推荐日常使用）；
> 已知 BUG 与暂缓的基础设施缺口见 [KNOWN-ISSUES.md](KNOWN-ISSUES.md)。

## 目标与边界

- Shell 冷启动路径小而可解释；可选功能按需加载，停用后释放实例及其 Timer、Process、请求、连接、监听和回调。
- 模块按功能域自治；UI 通过 Action Gateway 表达桌面意图，领域服务拥有对应 I/O；全局 singleton 仅用于确有跨域共享状态的能力。
- 设置 UI 的 Default、Minimal、Dashboard 均是正式可选呈现，支持热切换；它们共享设置模型、路由、搜索、动作和持久化逻辑，不复制业务。
- 清理和重构不得降低视觉品质、动效、可读性、几何精度或对齐。
- 以原版 Niri 为基础兼容目标；外部能力缺失时局部降级，不让可选依赖阻断核心 Shell。
- Wiki 只保留能指导实现、审查、验证或排障的现行契约；历史资料归档，不冒充当前事实。

## 状态规则

任务状态只使用 `待开始`、`进行中`、`阻断`、`待验收`、`已完成`。合并前置、实现、行为验证和视觉验收分别记录；测试失败、环境跳过与未验证不得混为通过。每项任务明确旧实现的保留、迁移、归档或删除方式。

## 已交付基线台账

| 阶段 | 交付 | 状态 |
| --- | --- | --- |
| R1 | 状态与事实收口 | 已完成 |
| R2 | 启动闭包与可选模块 | 已完成 |
| R3 | 品牌、路径与构建边界 | 已完成 |
| R4 | 架构、生命周期与结构收敛 | 已完成 |
| R4-C | 结构收敛与全面去 C++ | 已完成 |
| R5 | 资源、文档与测试收口 | 已完成 |
| R6 | 能耗基线、事件循环与稳态治理 | 已完成 |
| R7 | 多套设置 UI 与 PR #120 前置审查 | 已完成 |
| R8 | 设置导航扁平化与 M3 信息架构 | 已完成 |
| R9 | 功能开关与真实生命周期 | 已完成 |
| R10 | Action Gateway 与模块自治 | 待验收 |
| R11 | 控制面与透明度 | 已完成 |
| R12 | 全局文档架构重塑 | 已完成 |

「已完成」表示该阶段按当时验收标准交付并留有行为证据，明细见归档台账。
R10 行为与契约测试全绿，待作者实机验收后改为已完成。

## 当前阶段：P4 主题契约、模板兼容与取色引擎分阶（待验收）

**目标：** 主题契约与渲染引擎自有、与 Noctalia v5 palette/template 规范兼容；
matugen 降格为纯取色位；深浅模式系统级写入收敛为 `nyxuri theme` 单一实现。

**实施（明细见台账 P4 实施记录）：**
- 契约层：一次生成双写 `colors.json`（50 token 热载，schema 不变）与
  `palette-modes.json`；16 角色 palette JSON 镜像至 Noctalia 自定义色板目录，
  双 Shell 默认各自独立取色，谁 active 谁写全部输出。
- 短期引擎：matugen 仅 `--json` 纯取色，Tera 渲染路径全量退役；纳入 doctor
  可选依赖检查。
- 渲染层：TemplateAdapter 落 `app/services/TemplateService.qml`，表达式子集
  （块/过滤器/`palettes.*` 显式拒绝）；kitty/btop/starship vendor 入库（MIT
  来源映射），yazi 取色模板删除。
- 深浅模式：Shell 侧系统写入清算，代调 `nyxuri theme`（CLI 缺失时内部照切
  并明示）；gsettings 只读观察回路保留。
- 色差实测：分歧矩阵已钉值（`on_*_container` 系 Noctalia tone 重锚定，
  ΔE00≈10）；对齐路径为镜像色板 + `color-scheme-set`。

**验收：** 契约测试全绿（golden master + MD3 向量 + 分歧矩阵 + 注册表行为测试，
宿主 550 测试、分类 111 测试、check.sh 全绿）；壁纸切换/深浅代调链路/模板
hooks 的实机行为证据与视觉验收待作者确认。镜像色板是否长期作为 Noctalia
对齐策略（`source = custom`）留验收拍板。

## 后续阶段

- **原 P5 完整宿主、部署与双轨生态 → 已吸收为主线 KM4，已交付**（2026-10-17，
  明细见 [roadmap-history](../llms-wiki/archive/roadmap-history.md) KM 存档与本台账追加节）：P5 验收标准原样
  平移——六动作经 `nyxuri-shell --action` 通路保持零改动（单元 off 时 IPC 目标
  消失 = 真实失败明示）；部署契约经 `units/theme`（merge 共享生活区）与部署流程
  自动 `on theme` 接入；共享池位置中立化（`~/.config/nyxuri/templates/`）与双
  Shell 输出仲裁（kitty include 去重 + noctalia 主题块剥离已有；切换后活动 Shell
  启动即全量重渲）随部署落地；切换失败不损失配置、不留受管残留由既有
  `shell set` 回滚契约承担。「Shell 内部完全单元化 + 微内核插槽架构」交付：
  `AppShell` 零按名实例化、`SlotHost` 槽驱动、`StateProjection` 单一开关投影、
  单元自有 IPC、lock 安全守护、12 单元全景开关页。行为、视觉实机验收待作者
  确认后转「已完成」。
- **P6 整体验收与未来移植**（前置：主线 KM5）：固定机器与版本基线，验收离线、缺插件/设备、锁屏、SIGTERM、目标崩溃和失败恢复；视觉、行为、资源和文档证据齐备后才接纳封存功能或多合成器移植。

## 已确认的历史决策

以下决策已由作者确认并落实，不是待拍板事项；保留它们是为避免后续重构反复打开已关闭的问题。

- 自有 C++ 构建链已移除；运行实现收敛为纯 QML/JS/脚本，公开标识统一为 `nyxuri`。
- 原版参考树仅本地查阅，不进入运行时；上游历史材料与 Nyxuri 契约分开维护。
- Cava、地图、歌词和窗口预览不属于核心能力，相关死代码已清理。
- 资源策略区分运行时资产、生成文件、缓存和测试 fixture；天气图标采用 Material Symbols。
- 文档体系按 [docs-charter](../llms-wiki/docs-charter.md) 分层治理；归档只进不改。

## KM4.5 拆迁与正名（2026-10-17，随主线 KM4.5）

> 起因：`modules/`（16 域，混居 4 个非单元支撑目录）与 `units/`（12 个纯 manifest
> 存根）两棵树表达同一概念且数目对不上，"bar 在哪"要查三处——文件树不表达架构，
> KM3.5 的成果在 Shell 侧未兑现。本阶段模仿 KM3.5：先处决、再正名、一次契约同步。
> 单元 ID（`shell.<domain>`）不变，ledger/state/IPC 零影响；实机验收与 KM4 合并。

**处决清单（全部落地）**：
`hotcorners/` → `app/services/HotCorners.qml`（唯一消费者 AppShell，宿主能力面）；
`filepicker/` → `app/services/FilePickerWindow.qml`（keystone + settings 共用对话框
能力）；`quicksettings/` → 并入 `sidebars/quicksettings/`（唯一消费者）；`systemcards/`
拆分——纯展示 27 文件 → `shared/cards/`，直读 app 单例的 6 文件
（SystemCardContent、SystemWeatherCard、SystemBatteryTank、SystemClockCard、
SidebarCookieClock、NetworkInterfaceHistoryService）→ `app/services/`，其中两时钟卡
按 LIFE002 服务层规则补齐 `Component.onDestruction` teardown；SlotHost 重复注释块、
全树 `__pycache__` 清除。

**正名**：`modules/<12 域>` 物理并入 `units/<域>/`，manifest.toml 与代码同目录——
目录即单元，兑现内核「Adding a unit = adding a directory」承诺；顶层目录 10 → 8，
`shell/modules/` 消失；`qs.modules.*` → `qs.units.*` 全量正名（实树 96 行 import +
SlotHost 预热 12 行 + UnitCatalog source ×12 + 工具链与测试）。

**契约同步**：shell/AGENTS 三层边界重写（app/units/shared + 支撑代码归宿规则）；
architecture-matrix 重写（12 单元矩阵）；unit-model §6 承载修订；shell/development
分层词表；audit-lifecycle / generate-search-catalog / run-tests / check.sh /
test_unit_catalog 路径改判；契约测试改测新真相（test_shell 61 绿、
test_bugfix_regressions 109 绿，含 app/ 56 文件收敛断言与 units/ 死刑断言：
`shell/modules/` 必须不存在、4 个已处决支撑目录不得复辟）。

**验证**：全量引擎 970 测试绿（14 跳过 = 基线）+ Shell 分类 118 测试绿 +
audit-lifecycle clean（560 文件）+ 单例纯度扫描零 offender。实机行为/视觉验收与
KM4 合并进行。
- **KM4.6 Shell 结构微整**（2026-10-17，结构层不碰行为；先行提交 KM4.5 后开工）：
  处决——`packaging/`（死独立发行管线：release.py 已不存在，gen-deps 只写仓库根
  packaging/，dependencies.json 引用旧 modules 树）整目录处决；`fallback/` 解散
  （lottieqt 桩零消费者删除；M3Shapes 具名模块桩以真身份迁
  `shared/controls/shapes/M3Shapes/`，wrapper `FALLBACK_QML_PATH` →
  `SHAPES_QML_PATH` 指向 shapes 目录——桩紧邻其未来要吸收的 vendored 数学）；
  `assets/` Junk Drawer 解散——shaders 按域归 `units/{keystone,launcher,wallpaper}/
  shaders/`（frag+qsb 同迁，消费改 unit 相对 `Qt.resolvedUrl`），i18n 词典 →
  `app/i18n/`，icons → `app/icons/`，内置模板注册表 → `app/templates/`
  （matugen-registry.sh builtin 根同步），第三方许可证 12 件折入 `LICENSE`
  第三方附录（逐字保留）；Paths 死属性清算（builtinMatugenDir/audioScriptsDir/
  weatherIconsDir/weatherScriptsDir/scriptsDir 旁挂）。
  分池——`app/cards/` 新建：SystemCardContent/SystemWeatherCard/SystemBatteryTank/
  SystemClockCard/SidebarCookieClock 5 个直读单例的 UI 渲染件出 `services/`
  （services 50 → 45 只剩服务+配置+能力面；NetworkInterfaceHistoryService 留列）。
  scripts 收拢 9 → 5（dev/lib/media/system/theme）：build→dev、lyrics+cava→media、
  capture 解散（LockSnapshot.qml + lock-snapshot.sh 一体归 `units/lock/`——
  QML 混居 scripts 的错位纠正）。
  正名——`settings/dashboard` → `settings/dashwindow`（语义钉死：它是
  settingsPanelStyle==="dashboard" 的卡片窗变体，非页面）；`bar/quicksettings` →
  `bar/quickpanel`；`sidebars/{dashboard,quicksettings}` 保留（对齐
  `WidgetState.dashboardSidebarView` 的运行时 view id）。
  验证：全量引擎 970 + Shell 分类 118 + audit-lifecycle clean（562 文件）+
  单例纯度零 offender + check.sh + 沙箱部署绿。终态顶层：app/units/shared/scripts/
  tests 五目录 + 8 根文件。
  实机验收修正（同日）：settings 窗口 on/off 实测暴露 `shell.desktopcards`
  永久 compiled empty 刷屏——`qs.app.cards` 新池无顶层 import、首次解析落在
  Loader 内（0.3.2 约束①），SlotHost 预热名单补行；顺带坐实自愈上限（原 "/2"
  为写死字符串，无限重试刷到 pass 11/2）——per-unit `failedHeals` 计数、超限
  给决断性日志、unit-changed 清零重新武装。登记 KNOWN-ISSUES 已修复段；
  AGENTS 约束①增补推广条款：新 qs.* 池必须进预热名单。
  同日复核：上述修正未根治 compiled empty——真因是重构残留的失效相对 import
  （DesktopCardCanvas import `../systemcards/…`、SystemCardContent import
  `../shared/cards/…` 少一级 `../`，SystemCards 模块解散后真身在 `shared/cards/`），
  文件不存在属硬错误；两处正名后恢复，settings ShellPage 误引 `UnitControl`
  一并正名 `UnitControlService`（预热与自愈上限修正独立成立，保留）。
  开关无反应同场根治——`probe_running_shells` 误排 `getppid()`，shell 派生的
  nyxuri 探测不到自己的 qs 父进程，bridge 静默丢 unit-changed；修为只排除
  自身，真实进程拓扑回归测试坐实（tests/test_bugfix_regressions）。

## 当前门禁

- 每个保留文件必须有真实消费者；每个设置项和动作必须有唯一业务 owner。
- Niri 运行态只允许单一服务状态源；模块不得复制窗口、工作区或输出状态。
- 新抽象必须减少重复、状态或生命周期复杂度；仅转发的文件不得作为结构性成果保留。
- 每阶段完成前源码、测试、资源、部署和文档状态相互一致；测试跳过与环境阻断单独报告。
