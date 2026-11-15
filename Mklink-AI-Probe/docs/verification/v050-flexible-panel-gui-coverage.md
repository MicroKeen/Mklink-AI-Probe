# 灵活面板：GUI 功能覆盖评审

日期：2026-11-15。评审对象：PR #80 的 v0.5.0 扩展，代码基线 b66ef612，加本轮命名修改；不是已发布安装包的验收。

**结论：尚未覆盖原 GUI 的完整工作流。** 234 项直接操作表示业务能力入口，不表示 234 项完整可视化功能已经组件化，也不表示真机通过。现有六种子面板是 `watch / variables / rtt / serial / controls / capability`。能调用读内存接口，不等于已经提供可组合的十六进制内存视图；能启动 Trace，不等于已经提供可组合的任务时间线。

本轮从全部路由、仪表盘标签、配置分区及其子组件反向核对，不以用户举例作为范围：5 个主页面，9 个仪表盘标签（含灵活面板自身），4 个配置分区。业务入口清单仍见[能力矩阵](v050-capability-matrix.md)，既有测试和实物证据见[场景报告](v050-capability-validation.md)。

## 判断口径

- **可组合视图**：在灵活面板内部实际渲染专用组件，具有可用的人类操作控件和状态显示。
- **部分覆盖**：已复用部分组件或动作，但设置、完整工作流、文件操作或语义动作仍有缺口。
- **原页面**：专用视图仍在原 GUI；Agent 可以导航并操作原控件，或调用业务接口，但不是灵活面板内的独立视图。
- **验证**：源码、自动测试、真实浏览器和设备证据分别记录。原正式版的独立验收不自动成为本扩展的验证。

通用操作面板支持标量、枚举、简单字符串数组等普通字段；复杂嵌套对象交由会话配置。结果表、状态和日志不能替代曲线、十六进制编辑器、任务时间线或多文件任务编排。没有面向用户的 JSON 编辑入口。

## 全 GUI 功能矩阵

| 功能域 | 原 GUI 应覆盖的操作与观察 | 灵活面板现状 | 完整覆盖缺口 |
| --- | --- | --- | --- |
| 设备连接与 SWD/JTAG | 发现/选择探针、连接/断开、接口、支持的时钟及当前频率、睡眠访问、复位和探针重启 | **部分覆盖**：保留仪表盘共享连接栏；`device.clock.read/set` 已是语义动作，可绑定控件；通用能力有连接/状态等入口 | 没有可组合的完整连接设置组件；支持频率与连接状态联动选择仍依赖配置页。不能说“不支持设置时钟”，也不能说已提供完整设置面板 |
| SuperWatch 波形 | 变量选择、采样启停、实时图、缩放/平移、触发、游标、阈值、图例/坐标轴、PNG、记录/回放 | **可组合视图，工作流部分覆盖**：复用 WaveformViewer；真实记录已回放 | 采集配置、完整工作区分组及配置文件工作流仍有原页面入口；所有图形手势与 Agent 动作的逐项对应尚未验收 |
| 变量与符号表 | AXF/ELF 加载/重解析、树搜索展开、地址/类型/成员、读写、固定变量、数组快照、自定义 C 布局、采样选择 | **部分覆盖**：复用 SymbolVariablePanel，具有相关语义动作 | 独立 SymbolsTab 与完整工作区/文件管理尚不能声称等价；所有类型和错误路径未逐项实测 |
| RTT View | 地址/自动搜索、连接与采集启停、多通道；日志/终端/HEX、编码、发送、数值图、丢弃状态、记录/回放 | **部分覆盖，已有完整度较高的通道视图**：复用 RttChannelPanel，包括 TrafficLogControls、RttRawView、发送栏 | RttViewTab 的地址/搜索/采集配置没有一起组合；通道语义目录只有显示、暂停、清空、图范围、编码、发送等七项，回放文件/游标等未成为同一套面板语义动作；本扩展未做实际 RTT 收发验收 |
| 串口助手 | 端口发现/开关、波特率/数据位/校验/停止位；接收/发送、文本/HEX、记录/回放；广播、文件发送、YMODEM、发送队列、解析与自动应答 | **部分覆盖**：SerialPortPanel 只显示已有串口会话，可切换显示/暂停/清空/发送；业务接口有更多能力 | 面板明确要求先在串口助手打开端口；串口配置、自动化、记录、队列、文件和 YMODEM 专用组件没有复用进来；不是完整串口助手 |
| Memory | 地址/长度读取、十六进制与 ASCII 对照、指定地址写入 | **原页面**：内存读写/转储能力可调用 | MemoryTab / HexMemoryView 未注册为子面板；通用结果表不能代替地址行与字节视图 |
| RTOS Trace | RTT 通道和地址、采集控制、任务时间线、CPU/任务统计、上下文、缩放/跟随/时间窗、事件与丢弃、保存/导入/回放 | **原页面**：业务生命周期、历史/离线解析可调用；原页有 `systemview.window/pause/resume/zoom-in/zoom-out/fit` | SystemViewTab 和时间线未组合；实时数据、回放游标、统计与时间窗联动未在灵活面板验收 |
| HardFault / CPU | 故障摘要、CFSR/HFSR、异常栈、调用栈、寄存器、符号/源码定位、报告 | **原页面**：故障与寄存器业务接口可调用 | HardFaultTab 专用解释视图未组合；fixture 测试不能证明真实 HardFault 注入 |
| 外设寄存器 | 芯片/描述文件、SVD/XML/Pack、外设和寄存器搜索、字段解释、读取与采样映射 | **原页面**：外设列举/读取/采集业务入口可调用 | PeripheralWatchPanel 仍在 SuperWatch 原页；缺少可组合的寄存器/位域视图 |
| Modbus | RTU 串口参数、站号、超时/重试、功能码、寄存器读写/掩码、循环、类型解释、收发帧与 CRC、记录导出 | **原页面**：启停、事务、读写、探测、历史和循环等能力可调用 | ModbusTab 的配置、表格、事务状态和帧监视未组合；无本扩展物理链路验收 |
| 日志与记录管理 | 实时操作记录、采集保存、原文件保留、格式转换、导入/回放、速度/进度、损失提示 | **部分覆盖**：通用操作日志、波形回放、RTT 日志/回放已有；记录业务入口可调用 | 串口、Trace 及各类文件流程未统一完成；前端回放状态不都可经面板语义目录独立控制；回放不能重发历史 TX |
| 在线烧录 | 探针/连接设置、目标 Pack/FLM、镜像导入/检查/地址、Flash 区域/扇区、擦除/写入/校验/复位、任务进度/取消、读回保存 | **原页面**：多数业务动作可调用 | OnlineFlashView 的文件工作区、区域图、任务日志与流式回读组件未组合；上传/下载/流不能用普通表单等价替代 |
| 脱机烧录 | MCU/接口/时钟/复位/电压/校验/蜂鸣/次数、多个镜像和算法、USB 卷、配置预览/部署/触发、未知任务核对 | **原页面**：预览、部署、触发等业务能力可调用 | OfflineFlashView 多文件排序与部署流程未组合；不能把接口回执当作烧录终态 |
| HPM 配置、OTP、设备配置字 | Flash 四字配置，OTP 字表/导入导出/读取/计划，永久编程与锁定位，配置字描述/脚本 | **原页面**：对应读/计划/编程/描述等业务入口存在 | 专用表格、文件导入和不可逆操作确认仍在原组件；当前扩展没有永久编程验证 |
| 文件和配置来源 | AXF/ELF 路径与选择、自动跟踪、解析状态、工作区配置保存/恢复；Pack/FLM/SVD 与镜像在各专用页 | **部分覆盖**：变量组件与业务动作已有部分路径操作 | 原生/浏览器文件选择、目录、上传、导出、配置迁移及错误恢复不能由 API 数量证明完成 |
| 固件与客户端更新 | 探针固件检查/升级/手动路径、兼容性提醒、客户端更新进度/重启 | **保留应用公共 UI，专用设置在原页面** | 没有独立子面板；Tauri、操作系统及重启流程不是可任意绑定的普通业务调用；本轮没有升级测试 |
| 运行时与诊断 | 后台/项目/探针状态、别名、共享客户端/占用、停止采集、分离/释放/退出、诊断导出 | **原页面**：状态及部分控制有业务入口 | RuntimePanel 管理界面未组合，诊断下载与生命周期终态仍需原流程；不能因窗口离线而重放操作 |
| 远程服务与远程窗口 | LAN/VPN/STCP、监听配置、启停、令牌/凭据、连接与绑定窗口 | **原页面/宿主能力**：状态可调用，窗口发现和选窗已有协议 | SiteAgentView 与 RemoteConnectPanel 没有组合，宿主设置不等于通用业务动作；远程模式只允许原产品开放的仪表盘能力，串口/Modbus 等仍受限 |
| 全局界面与灵活布局 | 主题/语言、健康与版本提示、页面导航；面板增删/排序/缩放/停靠、控制组件绑定、保存/恢复 | **公共 UI 保留，布局已实现**：GridStack、显式编辑模式、设置弹窗、Agent 控制与结果记录 | 尚无全功能组件目录；原生 WebView、触屏、读屏及所有多实例组合未完成当前扩展验收 |

VOFA 的后端能力及 WaveformViewer 中的模式分支仍存在，但当前仪表盘没有独立 VOFA 标签，灵活波形固定使用 SuperWatch；不能因为代码中有 VOFA 支持，就把它记为现有可组合 VOFA 视图。

## 语义控制与多面板边界

原 GUI 自动化覆盖全部 5 个主页面和 9 个仪表盘标签的导航，以及原生控件、文件和目录选择。灵活面板自己的 `navigate` 动作只列出部分仪表盘目标。因此，“Agent 能打开原页面”与“功能可以留在同一灵活布局内”是两个验收项。

RTT 通道组件已带记录和回放按钮，不应误报为完全缺失。但 TrafficLogControls 的 `useGuiPanel` 使用 `${kind}.replay.${channel}` 注册快照，且没有专用 actions；同一通道多个实例会争用快照键（注册表是 Map）。这属于源码确认的语义隔离缺口，尚未做多实例浏览器复现；不能宣称所有 RTT 子视图都可独立寻址控制。补齐时应使用现有稳定面板 ID，继续保留共享采集与本地回放的边界。

## 完整覆盖的后续验收矩阵

以下是缺口对应的验收项目，**不是本轮已通过结果**。优先复用现有业务组件和共享状态，不能以新增通用 JSON 操作页代替。

| 优先级 | 功能组合 | 最少应证明的结果 |
| --- | --- | --- |
| P1 | 连接设置 + SWD/JTAG | 选择设备后读取支持频率；设置、状态回读、失联/目标变更拒绝；不影响其他探针 |
| P1 | RTT 完整配置 + 多通道/同通道多实例 | 配置并开始采集；文本/HEX/终端/编码与发送；通道状态和各视图独立；保存/回放/退出不重发、不干扰另一视图 |
| P1 | 串口完整助手 | 配置打开/关闭；普通发送、队列、广播、文件、YMODEM、解析/应答；录制/回放；端口占用/拔插、取消与部分发送的明确结果 |
| P1 | Memory + 变量 + 外设 | 十六进制/ASCII 与原字节一致；符号和类型一致；授权写入回读；越界/只读/目标变更拒绝；面板刷新不触发写入 |
| P1 | RTOS Trace | 真实任务流的时间线、CPU/任务统计、缩放/暂停/跟随；保存回放与原事件一致；解析/目标溢出可见；多视图不重复启动采集 |
| P2 | HardFault + Modbus | 已知故障栈与符号匹配；事务/CRC/超时/异常码与物理帧对应；错误可解释而不是仅展示原始对象 |
| P2 | 文件/记录全流程 | 选择、保存、导出、导入、格式转换、回放游标/速度；取消、损坏、缺文件、权限错误；原文件保持、状态可恢复 |
| P2 | 在线/脱机/HPM/OTP | 复用专用表单与原确认边界；任务进度/取消/未知终态核对；永久编程单独授权与验证 |
| P2 | 远程/运行时/升级 | 正确发现并绑定窗口与后台；断线、换目标、版本/能力不足有明确状态；宿主能力与远程限制保留 |
| 横向 | 每一类子面板 | 人工操作与自然语言操作达到同一结果；状态与错误可读；保存/恢复不执行动作；多实例、窄窗、键盘、单位、留白和展开态复核 |

## 本轮变更与证据边界

“组合工作台”更名为“灵活面板”（英文 Flexible Panels），同步仪表盘标签、面板标题、Agent 目录的展示名与当前接入说明。`workbench` 路由、稳定 ID、布局存储及动作协议保持兼容，不迁移用户布局。

本轮只修改命名并补齐覆盖评审，没有将上述缺口标记为已实现，也没有执行新的设备写入、采集、升级、复位、烧录或 OTP 操作。

- 自动验证：DashboardView、WorkbenchTab、useFrontendWorkbench 三文件 **37 项通过**；首次运行发现英文旧名称期望未更新，修正后重跑上述三文件通过。TypeScript 与生产构建通过，既有大分块提示保留。改动文档本地链接及 Skill 前言检查通过。
- 真实浏览器：刷新后中文标签/标题为“灵活面板”；切换英文显示 Flexible Panels，再恢复中文。原有六面板恢复、没有旧名称、控制台无 error。恢复显示已保存的真实波形，回放进度到 34.679 / 34.680 s；保留界面供继续对话。截图 `flexible-panels-final.jpg` 留在用户工程验证目录，不提交到公开仓库。
- 只读设备核对：页面 0、亮度 10、拒绝计数 4、采样已停止；这只证明状态未被本轮改名操作改变，不新增任何 RTT、串口、Trace 或其他功能真机通过项。
- 全局技能：当前安装通过 Junction 指向 agent-ui-dev 源码；已同步“灵活面板”名称和覆盖限制，不改技能运行时。未升级已安装 MKLink 或发布产品安装包。

浏览器还显示通用操作目录部分条目直接采用英文接口说明、存在同名操作；这些虽可路由，不代表面向工程师的命名、分组和参数引导已完整验收，仍需在完整能力交付中整改。

## 源码核对入口

- 页面全集：[router.ts](../../gui/src/router.ts)、[DashboardView.vue](../../gui/src/views/DashboardView.vue)、[ConfigView.vue](../../gui/src/views/ConfigView.vue)、[App.vue](../../gui/src/App.vue)。
- 六类面板与实际渲染：[workbenchLayout.ts](../../gui/src/lib/workbenchLayout.ts)、[WorkbenchPanel.vue](../../gui/src/components/dash/WorkbenchPanel.vue)。
- 语义目录与原 GUI 操作：[useFrontendWorkbench.ts](../../gui/src/composables/useFrontendWorkbench.ts)、[guiAutomation.ts](../../gui/src/lib/guiAutomation.ts)、[CapabilityPanel.vue](../../gui/src/components/dash/CapabilityPanel.vue)、[capabilityPresentation.ts](../../gui/src/lib/capabilityPresentation.ts)。
- RTT 与串口：[RttViewTab.vue](../../gui/src/components/dash/RttViewTab.vue)、[RttChannelPanel.vue](../../gui/src/components/dash/RttChannelPanel.vue)、[TrafficLogControls.vue](../../gui/src/components/dash/TrafficLogControls.vue)、[SerialPortPanel.vue](../../gui/src/components/dash/SerialPortPanel.vue)、[SerialMonitorTab.vue](../../gui/src/components/dash/SerialMonitorTab.vue)。
- 专用调试视图：[MemoryTab.vue](../../gui/src/components/dash/MemoryTab.vue)、[SystemViewTab.vue](../../gui/src/components/dash/SystemViewTab.vue)、[HardFaultTab.vue](../../gui/src/components/dash/HardFaultTab.vue)、[PeripheralWatchPanel.vue](../../gui/src/components/dash/PeripheralWatchPanel.vue)、[ModbusTab.vue](../../gui/src/components/dash/ModbusTab.vue)。
- 烧录/宿主管理：[OnlineFlashView.vue](../../gui/src/views/OnlineFlashView.vue)、[OfflineFlashView.vue](../../gui/src/views/OfflineFlashView.vue)、[SiteAgentView.vue](../../gui/src/views/SiteAgentView.vue)、[RuntimePanel.vue](../../gui/src/components/config/RuntimePanel.vue)。
