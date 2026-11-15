# v0.5.0 自由面板整合验收

日期：2026-11-15。沿用隔离的 `codex/agent-ui-workbench` 与 [PR #80](https://github.com/MicroKeen/Mklink-AI-Probe/pull/80)。正式标签 v0.5.0 对应 `1097f98eb9025b38b16cd32095bced7dd65ecdcd`；本轮合入 `microkeen/main` 的发布交接提交 `1c4453c2781a7862d77a6035ff8f823c0be6bdd7`。

这是正式源码基线上的自由面板候选，尚未进入正式安装包。版本号 0.5.0 不代表具有扩展，须检查 `gui_frontend_*` 能力。本轮没有覆盖已安装程序、发布标签、固件或更新索引；生产 Web 资源输出到忽略目录，通过现有 `MKLINK_GUI_DIST` 指定。受跟踪的 `gui/dist` 保留上游正式资源。

## 改动与回归问题

- 合并新版 `gui_action/gui_snapshot`、GUI 协议 2、SuperWatch AXF/ELF 旁配置及旧语义能力；兼容原工作区/固定变量保存名称。
- 新版共享显示配置原本会覆盖命名子面板，且多个 WaveformViewer 会替换原 `superwatch` GUI 控制器。先用双面板回归复现，再将配置加载、保存通知和原 GUI 注册限制为默认视图；命名子面板继续保存各自显示状态。最终补齐命名面板不显示共享配置提示的断言。
- `runtime status` 原来不返回文档需要的 `runtime_id`。真实独立 CLI 发现链路暴露此问题后，在两个状态接口返回公开选择 ID，并测试不泄露凭据或访问设备。
- 新版导航加入 `workbench`；窗口快照公开对应的 `protocol/session_id/page_id/target`。CLI 的 `gui_frontend_*` 调用使用已有 GUI 附着，不隐式连接探针；会话、参数、页面代次、截止时间和业务检查保留。
- 增加公共 [Agent UI 发现与接入说明](../../references/agent-ui.md)，从 SKILL 与 AGENTS 均可进入。新会话无需知道上一会话的私有文件或端口。

## 自动测试

所有构建和套件通过 `scripts/build_workspace.ps1 -Action run`，使用现有依赖，日志与临时项目保留在主检出忽略的 `.build`。

| 范围 | 结果 |
| --- | --- |
| GUI 全量，126 个文件 | 1356 项通过 |
| 最终配置提示调整后的相关 3 文件 | 154 项通过，与全量重叠；含 SuperWatchTab、WaveformViewer、useFrontendWorkbench |
| Python 10 个相关套件 | 381 项通过；3 条依赖弃用警告 |
| 最终生产构建 | `vue-tsc -b` 和 Vite 通过；Dashboard 约 765 kB，仍有既有大分块提示 |

Python 范围：`test_runtime_frontend`、`test_runtime_cli`、`test_runtime_uart`、`test_runtime_presentation`、`test_frontend_storage`、`test_runtime_mcp`、`test_runtime_gui`、`test_runtime_gui_files`、`test_shared_runtime`、`test_skill_context_boundaries`。覆盖原 GUI 与语义接口共存、界面附着不连接硬件、旧会话拒绝、直接设备访问仍受限、布局和公共 Skill 边界。

初次使用系统 Python 因缺少 FastAPI/FastMCP 收集失败，改用已有完整虚拟环境后重跑。公共 SKILL 入口文字一度超过原字符预算，精简入口后上述边界套件全部通过；未放宽预算或添加依赖。

## 真实浏览器与独立 CLI

使用最终生产资源、实际 FastAPI 认证后台、隔离项目和浏览器。CLI 每次新建进程，以实际 `runtime status` 选择 ID，再通过窗口快照找到页面，按公布的 schema 发命令并查询终态；没有替换业务 HTTP 为 mock。

- 独立创建左右两张波形和控制面板，设置不同图例状态；实际页面按钮改变右侧图例，Agent 调用参数表单关闭右侧图例，左侧保持不变。
- 按钮、状态灯、参数表单绑定到真实目录；页面状态灯显示右侧结果。将已有表单移到第二控制面板、停靠为标签后，输入草稿仍为 false，Agent 执行使用原草稿；分离并移回同样保留身份与绑定。
- 保存后刷新：重新发现新 page ID；三张面板与三个绑定恢复，左右显示保持独立，临时执行状态为空，表单回到保存的固定默认参数，未自动执行绑定动作。
- 同时打开两个真实窗口，各窗口快照映射到不同语义 page ID。命令只改变选定窗口；另一个窗口保持原状态。验证后关闭第二测试窗口。
- 使用可见配置编辑器通过键盘修改标题与高度，再点击保存成功。低于最小高度的语义请求返回明确失败，布局未部分更改；改用允许的尺寸完成示例排列。
- 最终窗口浏览器错误日志为空。截图与私有命令/回执记录仅留在本地忽略目录。后台重启后使用新的登录入口，未复用旧凭据。

## 边界

本轮没有连接探针、启动采集、写变量、发送串口或修改供电。既有硬件、延迟和吞吐限制继续按 [0.4.3 基线](v043-host-baseline.md)保留。没有重跑全仓 Python、Rust、NSIS 覆盖安装或原生桌面；没有实际语音输入验收。语音转写与唤醒由 Agent 宿主提供，本轮证据是同一会话的真实 CLI 与 Web 交互。当前已加载的旧 MCP 不自动升级，验证使用本候选源码入口；后续安装/发布需对应授权与完整门禁。
