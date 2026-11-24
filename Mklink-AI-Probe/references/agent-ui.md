# 灵活面板与连续对话接入

新会话从本页开始，无需上次聊天的端口、令牌或私有会话文件。此入口适用于基于
v0.5.0 的灵活面板扩展；原版 v0.5.0 仅有通用 GUI 控制，不包含本扩展。
必须核对运行时公布了 `gui_frontend_pages/read/call/receipt`，不能只看版本号。

界面名称为“灵活面板”（Flexible Panels）；兼容路由和协议标识仍是 `workbench`。
保留波形、变量、RTT 通道、已有串口会话、控制组件和通用操作六类视图，并增加
`tool` 完整工具视图：connection、superwatch、rtt、serial、memory、trace、hardfault、
symbols、peripherals、modbus、online-flash、offline-flash、files、firmware、runtime、remote-service。
它们直接复用原 GUI 的表单、图表、确认和任务处理；远程模式保留原能力限制。
另有 `log` 日志问答、`information` 信息、`chart` 数据图表。按运行时实际目录选择入口；
控件可操作不代表设备任务已完成，必须核对原组件结果和任务终态，不能把入口数量当作验证覆盖率。

可复制的激活语句：

> 使用 MKLink skill 的 Agent UI 接入说明，找到我指定项目的运行后台与窗口，打开灵活面板。后续在当前会话中连续接收文字或宿主语音请求，执行已授权能力，并把真实结果更新到同一界面。

## 发现、选择、接入

1. `ping` 核对版本及能力；只读 `runtime_status` 或 CLI `python -m mklink runtime status`
   列出后台，按实际项目与用户目标选择 `runtime_id`，多实例不得默认取第一项。
2. 展示实时曲线、RTT 或用户指定的界面时，`gui_open(runtime_id=...)` 复用该后台；没有实例时按
   [安装说明](install.md)使用实际运行目录的解释器，以
   `python -m mklink gui --project-root <项目绝对目录> --no-browser` 启动。
   打开启动返回的本地入口；私有登录链接不放入公开文档或提交。
   `gui_open` 不连接设备，当前 MCP 持有 GUI 附着直到 `detach`。
3. `gui_control(action="windows")` 获取窗口，明确选择 `window_id`，确认
   `gui_protocol=2`。用 `gui_control(action="navigate", window_id=..., page="dashboard", tab="workbench")`
   打开灵活面板，再 `snapshot`，读取 `panels.workbench` 中的
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

## 布局保存、加载与模板

灵活面板位于 Dashboard 标签最右侧。“保存布局”写入目标工程 `.mklink/frontend_layout.json`，用于下次打开；“另存为…”保存命名副本；“加载布局”按名称搜索并选择。
命名布局默认存于目标工程 `.mklink/frontend_layouts.json`；选择“全局模板”则存于当前用户 `~/.mklink/frontend_layouts.json`，跨工程共享。弹窗展示实际路径，不把用户路径写死为某个开发工程。
当主目录本身被选为目标工程时，工程库使用 `.mklink/frontend_project_layouts.json`。原有主目录布局文件仍可通过“全局模板”打开。
全局目录包含只读的“RTT 与变量波形”“串口调试”“内存与 RTOS Trace”预置模板；不包含设备地址、串口号或用户变量名，不会自动连接或启动采集。自定义模板保留变量名与绑定，跨工程加载后须核对。

自然语言直接复用当前会话 Agent，先发现 `workbench` 的实际动作 ID：

| 用户请求 | 语义动作与参数 |
| --- | --- |
| 保存当前布局 | `layout.save({})` |
| 把当前布局另存为“电机调试” | `layout.save({name:"电机调试"})`，默认 project 范围 |
| 保存为全局模板“串口观察” | `layout.save({name:"串口观察", scope:"global"})` |
| 找一下电机相关布局 | `layout.search({query:"电机"})`；需要模板时指定 `scope:"global"` |
| 加载“电机调试” | 搜索确认名称和范围后 `layout.load({name:"电机调试", scope:"project"})` |
| 更新已有模板 | 搜索读取其 revision，再 `layout.save({name, scope, revision})`；冲突后重新读取，不能自动覆盖 |

加载替换本页未保存配置，并保持当前布局保存版本的冲突检查。用户要下次打开仍用它时，再执行无参数 `layout.save`。`layout.restore` 兼容原来的“恢复最近保存当前布局”。运行中或结果未知的组件操作不能因加载不同绑定而丢失。
调用均须等待 receipt 并回读；搜索结果为空、存储失败或冲突要反馈，不宣称完成。全局模板最多 64 份用户布局，预置模板不占名额；满额时更新已有布局。文件写入使用原子替换和跨进程锁，异步接口在线程中执行存储。

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
不要把 MCP 包装函数名或 CLI 参数原样当作 HTTP 参数。灵活面板的 `panel.add` 支持
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
## 灵活面板布局操作

在普通模式即可用标题栏的 × 关闭卡片、拖动边缘缩放。选择“编辑布局”后，用标题栏移动面板。“面板配置”和组件“配置”用于修改标题、信号来源、位置尺寸与绑定。配置使用标准模态对话框，Esc 关闭并返回原按钮。缩放不显示装饰箭头，边缘保留指针提示和轻量悬停角标。

面板与内部组件共用 GridStack 碰撞引擎，移动会给相邻项让位；Agent 的 `panel.move`、`component.move` 使用同一引擎，原布局版本及身份保持兼容。位置调整不执行业务动作，视图、草稿与绑定保持；“保存布局”后才能跨刷新恢复。窄窗口以单列显示，卡片底部分隔条支持拖动和上下方向键调整行高，也可通过配置输入精确位置。切换宽窄窗口保留桌面位置和列宽。独立变量面板内，“信号分组”和“常用变量”的分隔条可拖动扩展，向下滚动可继续浏览变量目录。


### 灵活面板的控件尺寸

普通工具栏和配置表单的按钮、输入框、选择器共用 32px 高度与 14px/20px 字体；标题栏和图表工具栏使用 28px 紧凑层级。面板标题左右、控制区、信息区及回放条使用 12px 留白，操作间距 8px、表单组间距 16px、模态弹窗内边距 24px。规则集中在 `gui/src/assets/workbench.css`；新增控件应沿用对应角色，不能依赖浏览器默认尺寸。窄窗允许工具栏换行，配置几何字段切换为两列；不因此修改保存的桌面网格坐标。


## 完整工具、日志与信息

- 读取实际 `workbench` 目录后用 `panel.add`，例如参数 `{type:"tool",tool:"memory",title:"内存"}`。完整表单在面板内操作；所有视图保留最小尺寸、滚动和原确认流程。
- 对目标实例调用 `view.controls`，分页获取可见控件和新鲜 ID。`view.control.set/click/check` 调用原事件处理；字段变更可能自动更新设备，不能把 set 当成纯显示动作。`view.action` 只提供该组件已注册的显示动作。
- 原事件返回 `dispatched` 不等于任务完成。用 `view.read` 分页读取结果、错误、通道回放和 Trace 状态，并核对原任务终态。控件变化、目标切换或弹窗出现后重新发现，禁止重放未知结果。
- 文件选择复用 `gui_action(action="file.select")`：先取所选窗口 `gui_snapshot` 的 `state.context`，再传实际控件 ID、`expected_context` 和文件路径。选择成功后仍检查组件的解析/回放状态。目录使用实例 `view.directory.select`。没有任意选择器、URL 或脚本执行入口。
- `log` 自动记录人类操作、Agent 操作、原组件通知和本窗口问答；`log.filter/read/export` 筛选、分页及导出文本。异步答复在提问框关闭后仍会进入日志，信息面板可跟随最新答复。
- `information/chart` 的 `content.set` 使用实际 schema，接收 `title/text/kind/unit/columns/rows/points`；kind 为 text/table/bar/line/pie。上限为文本 16000 字符、100 行×8 列、100 个有限数值点，总内容 24000 字符。饼图值非负且总量大于零。图表保留数据表和可访问名称，内容不执行代码。`content.follow` 恢复跟随答复；用户也可用普通编辑表单操作。
- 历史按本窗口、运行实例和目标隔离保存在 sessionStorage（最近 200 条、最多 32 份信息），有容量/恢复错误提示；不是跨机器审计库，也不写入布局文件。恢复不执行任何业务、文件发送或历史 TX。
- 视图实时计数仅通过显式结果读取提供，不参与配置 revision；配置、绑定、目录与目标校验继续有效。隐藏 Trace 页面取消本视图消费与绘制，后台采集由原生命周期管理。

## 可绑定的大字数值

`controls` 面板的组件注册表包含 `numeric`（大字数值）。用户通过“编辑布局 → 添加组件 → 配置”选择目标波形面板、数值来源、可选有效标志、单位、小数位数、过期时间和说明。没有按变量名后缀自动生成的业务组件，也不要求用户编辑 JSON。

Agent 先在控制面板调用 `component.types`，再调用 `component.sources({panel_id: 目标波形面板ID})` 获取当前公布的信号。用 `component.add` 创建 `numeric`，用 `component.configure` 设置 `panel_id`、`state_path` 和展示字段；路径必须来自目录，形如 `signal:sensor.temperature`，点号属于完整信号名。`valid_path` 为空表示不使用有效标志，否则须绑定同一来源面板的信号，值为 1 才有效。`precision` 为 0–6，`stale_ms` 为 250–60000（默认 2000），`unit` 最长 32 字符，`note` 最长 200 字符。标题和位置尺寸沿用原组件配置；保存使用 `layout.save`。

`component.read` 返回只读样本及可选有效标志，包括 `value/session/sequence/received_at/connected/replay`。数据来自该波形面板已经解码的 SuperWatch 流，不发起新的采集、内存轮询或设备操作。公开样本与配置 `read()` 分离，采样不会推进布局 revision 或保存到布局。当前 provider 为 SuperWatch；扩展其他数据源时须提供同样的时间戳/来源代次协议，不能把刷新时刻伪装成样本时刻。

持续采到相同值仍算新鲜；重复序号或只刷新 UI 不续期。断连、重连、通道元数据变化和回放切换清除旧样本；有效标志须与数值属于同一代次和序号。未绑定、等待采样、过期、断连、回放或无效信号均显示文字状态，零与负数仍是合法数值。回放期间此卡片暂停实时数值，恢复后等待新帧，不把历史值冒充实时测量。

恢复现有布局不会自行添加数值卡。若旧页面曾用临时的业务专用显示，在控制面板显式新增、绑定并保存即可；原波形、RTT 和其他组件配置不变。


## 可绑定的组态仪表

同一 `controls` 注册表提供 `gauge`（径向仪表）与 `bar-meter`（条形表）。它们使用上面的 `component.sources/add/configure/read` 协议与相同数值有效性规则；不是另外的硬件采集器。普通配置表单增加“量程下限/量程上限”，Agent 对应 `min/max`，默认 0/100，要求有限数且 `-1e12 <= min < max <= 1e12`。量程是显示配置，不是报警阈值。

图形越界时停在量程边界，同时提示“超出量程”，大字仍显示真实值。无效、过期、断连或回放期间清除图形，仅显示文字状态；不保留看似有效的旧指针。坐标刻度使用紧凑表示，精确值由大字读数显示。默认按需加载 ECharts，自动适应容器与主题，移除组件释放绘图实例；无需配置脚本、HTML、第三方 URL 或 JSON 编辑器。

径向仪表最小 4×4、默认 6×4；条形表最小 4×3、默认 6×3。人类表单、Agent 配置及后端布局存储采用同一范围约束；保存布局不保存实时样本，也不自动开始采集。当前仍仅绑定公布的 SuperWatch 时间戳信号，RTT 文本解析、报警确认状态机与任意 SVG 动画不是本组件的能力。

## 分析图

`information/chart` 的 bar/line/pie 复用 ECharts + Vue-ECharts，与实时 `gauge/bar-meter` 共用已安装绘图依赖。`content.set` 的 schema 不变，不支持任意第三方 option 或脚本；超过 12 个分类项显示缩放条，原始精确数据可展开查看。极端有限数值按比例绘制，非饼图明确标出纵轴缩放系数，提示/数据表保持原值。这是文档分析图，不会自行开启采集或把静态内容变成实时信号。

## 定位、分栏与专注查看

从目标页面公布的动作中选择工作台操作。用 `panel.focus` 和 `panel_id` 定位卡片，也可激活已停靠的标签。用 `panel.split` 指定 `panel_id` 为左栏、`target_panel_id` 为右栏，可选 `columns` 为左栏网格列数。两栏原已相邻时沿用占用的总宽度。最小宽度按两侧的面板类型校验。分栏后用 `layout.save` 保存。

用 `panel.enlarge` 传入 `panel_id` 和布尔值 `open` 开关专注查看。读回工作台状态中的 `enlarged` 与 `floating` 可核对当前窗口。系统级置顶需要用户在专注模式实际点击“浮窗置顶”。浮窗使用原面板 ID 和同一个页面会话，继续向原来的页面、面板发送动作。

读取工作台的 `dirty` 判断当前布局是否有待保存更改。用 `panel.remove` 关闭指定视图，`panel.closed` 按最近关闭顺序返回精简的 ID、标题、类型，`panel.reopen` 按原 `panel_id` 恢复。需要下次打开时仍可找回或仍保持恢复状态时，执行当前布局的 `layout.save`。这些操作仅更改布局；保存冲突请保留草稿并核对当前 revision。
