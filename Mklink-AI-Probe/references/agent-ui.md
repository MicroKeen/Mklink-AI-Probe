# 自由面板与连续对话接入

新会话从本页开始，无需上次聊天的端口、令牌或私有会话文件。此入口适用于基于
v0.5.0 的自由面板扩展；原版 v0.5.0 仅有通用 GUI 控制，不包含本扩展。
必须核对运行时公布了 `gui_frontend_pages/read/call/receipt`，不能只看版本号。

可复制的激活语句：

> 使用 MKLink skill 的 Agent UI 接入说明，找到我指定项目的运行后台与窗口，打开自由面板。后续在当前会话中连续接收文字或宿主语音请求，执行已授权能力，并把真实结果更新到同一界面。

## 发现、选择、接入

1. `ping` 核对版本及能力；只读 `runtime_status` 或 CLI `python -m mklink runtime status`
   列出后台，按实际项目与用户目标选择 `runtime_id`，多实例不得默认取第一项。
2. 用户要求显示界面时，`gui_open(runtime_id=...)` 复用该后台；没有实例时按
   [安装说明](install.md)使用实际运行目录的解释器，以
   `python -m mklink gui --project-root <项目绝对目录> --no-browser` 启动。
   打开启动返回的本地入口；私有登录链接不放入公开文档或提交。
   `gui_open` 不连接设备，当前 MCP 持有 GUI 附着直到 `detach`。
3. `gui_control(action="windows")` 获取窗口，明确选择 `window_id`，确认
   `gui_protocol=2`。用 `gui_control(action="navigate", window_id=..., page="dashboard", tab="workbench")`
   打开组合工作台，再 `snapshot`，读取 `panels.workbench` 中的
   `connected/protocol/session_id/page_id/target`，把选定窗口与语义页面对应起来。
4. `gui_call("gui_frontend_pages")` 检查该页面在线且目标一致，再
   `gui_call("gui_frontend_read", {"page_id":"..."})` 读取实际目录和当前 revision。
   `connected=false`、窗口关闭、页面刷新、后台重启、切换项目或探针后重新发现；不复用旧 ID。
   能力缺失说明正在使用旧后台或原版 GUI，应报告版本/能力缺口，不能猜测调用。

CLI 复用同一发现与认证机制，使用所选运行时的解释器；这些调用只附着已有后台，
不会为了操作界面而连接探针，也不会自动选择另一个后台：

```powershell
python -m mklink runtime status
python -m mklink runtime call gui_windows --runtime-id <后台ID>
python -m mklink runtime call gui_action --runtime-id <后台ID> --arguments '{"window_id":"窗口ID","action":"navigate","page":"dashboard","tab":"workbench"}'
python -m mklink runtime call gui_snapshot --runtime-id <后台ID> --arguments '{"window_id":"窗口ID"}'
python -m mklink runtime call gui_frontend_pages --runtime-id <后台ID>
python -m mklink runtime call gui_frontend_read --runtime-id <后台ID> --arguments '{"page_id":"页面ID"}'
```

## 每轮操作

从 read 中的 `catalog.panels` 和 `actions` 找实际动作 ID、参数 schema 与 effect。
不要从名称推算哈希 ID。用 `gui_frontend_call` 提交包含 `protocol`、`session_id`、
`page_id`、唯一 `command_id`、`expect_revision`、未来 30 秒内的 Unix 毫秒 `deadline`、
`action`、`args` 的命令；查询 `gui_frontend_receipt({command_id})`，再回读页面状态。
`queued/accepted` 不是完成；`unknown` 只查原命令，不能换 ID 重做。
通用 `gui_control` 仍可操作原控件；指定子面板优先使用语义目录中的稳定 panel ID。

创建面板、组件、设置参数与执行动作分开。调用真实 CLI/skill 后，记录原任务及结果，
使用目录中已提供的展示能力回写；缺少展示动作时按 Agent UI 开发技能补齐实现，
不能伪造设备结果。设备读写、采集、发送、文件及供电仍走原业务权限与本次用户授权。
GUI 附着不表示自动连接或授权硬件操作，前端回执也不代替后台任务终态。

## 完整能力目录与能力面板

先调用 `gui_frontend_capabilities` 获取当前后台的能力目录（名称、原入口、参数、契约版本和可用状态），
不要把 MCP 包装函数名或 CLI 参数原样当作 HTTP 参数。自由面板的 `panel.add` 支持
`{"type":"capability","title":"调试能力"}`。从新面板的实际动作目录取 `capability.select`，
选择后回读 `selected`，再调用公布的 `mklink.<能力名>`，参数是 `arguments_json` 字符串。
选择本身不执行；界面上的执行按钮和可绑定按钮/表单共用同一动作。

例如先选择 `systemview_decode`，再用 `{"arguments_json":"{\"hex_bytes\":\"00000000000000000000\"}"}`
执行离线解码。设备控制仍需明确目标及本次授权；`job_start`、`flash_job_start`、`offline_deploy`
使用稳定 `request_id` 和原业务确认。任务的 `running/queued` 不等于成功，应使用 `job_status`
或 `flash_job` 查询原 ID；结果为 `unknown` 时禁止重新提交。选择变化或参数契约变化会使旧绑定失效。

单次面板参数上限 32768 字符，还受原能力字节上限约束；大文件沿用原上传/日志路径。
面向用户的面板使用按钮、类型化表单、结果信息表与可读操作记录；不得让用户编辑参数 JSON、阅读原始 JSON 结果或打开所谓高级 JSON 模式。
复杂参数由当前会话按真实 schema 配置，原 `arguments_json` 和 `capability.export` 只保留为 Agent 兼容协议，不是用户操作界面。
按钮绑定固定参数也用普通字段配置；复杂绑定由 Agent 设置。数据量较大时分层、限量显示，完整结果仍可通过 Agent 查询或显式保存。
布局只恢复能力选择，不保存输入草稿、执行结果，也不连接设备或开始采集。

需要绘图时使用 `watch` 面板的 `waveform.replay.load`：实际记录优先传后端绝对 `path`；
短 CSV/JSONL 可传 `filename` 和 `text`。回放不发送数据到探针。`recording.start/stop`
及 `superwatch_recording_export` 复用原记录器；文件关闭和转换完成须分别检查。
转换时原样使用记录状态返回的路径，不改写分隔符；原处理器会核对最近记录的身份。
采样期间查询最新数值使用 `superwatch_values`，核对 `running`、样本序号、通道和新鲜度；
不要用独立 `watch` 重开硬件读取。`live_write_supported` 应在开始采样后检查实际协商结果，空闲值不代表固件能力。

文件导入/下载、连续流、宿主安装配置、源码集成与远程站点管理不经任意 shell/URL 面板执行。
沿用 `gui_control` 的原页面/原控件，或使用面板 Agent 请求，由当前会话读取可信上下文、
调用原 CLI/工具，再通过 `gui_frontend_reply` 回写真实结果。此类入口尚不是全部可直接绑定的子面板动作。
完整入口与覆盖边界由维护侧矩阵生成器核对；不能仅凭“目录已收录”宣称真机验收通过。

宿主直接对话无需先在页面发问；页面 Agent 请求用 `gui_frontend_intents/intent`
读取可信上下文，再按原 `request_id/revision` 用 `gui_frontend_reply` 回复。
语音识别与工具调用由宿主提供，本产品不负责唤醒已结束的 Agent。

显示配置按面板隔离，保存/恢复布局不启动采集或执行绑定动作。结束时 `detach`
只释放本 Agent 附着；关闭视图不会停止其他窗口采集。后台停止按
[控制权与恢复](runtime-recovery.md)显式执行，不根据旧 PID 或端口猜测服务身份。
## 自由面板布局操作

工作台默认用于观察和操作。选择“编辑布局”后，用标题栏移动面板、边缘缩放；“面板配置”和组件“配置”用于修改标题、信号来源、位置尺寸与绑定。配置使用标准模态对话框，Esc 关闭并返回原按钮。缩放不显示装饰箭头，边缘保留指针提示和轻量悬停角标。

面板与内部组件共用 GridStack 碰撞引擎，移动会给相邻项让位；Agent 的 `panel.move`、`component.move` 使用同一引擎，原布局版本及身份保持兼容。位置调整不执行业务动作，视图、草稿与绑定保持；“保存布局”后才能跨刷新恢复。窄窗口以单列阅读且停用拖动缩放，仍可通过配置输入精确位置，视口变化不改写保存的桌面几何。


### 自由面板的控件尺寸

普通工具栏和配置表单的按钮、输入框、选择器共用 32px 高度与 14px/20px 字体；标题栏和图表工具栏使用 28px 紧凑层级。面板标题左右、控制区、信息区及回放条使用 12px 留白，操作间距 8px、表单组间距 16px、模态弹窗内边距 24px。规则集中在 `gui/src/assets/workbench.css`；新增控件应沿用对应角色，不能依赖浏览器默认尺寸。窄窗允许工具栏换行，配置几何字段切换为两列；不因此修改保存的桌面网格坐标。
