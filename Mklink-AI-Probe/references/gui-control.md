# GUI 操作与验收

实时曲线分析、RTT 监看以及桌面/Web GUI 操作使用本页。两者共用同一协议，无需鼠标坐标或
Computer Use。设备采集、烧录、内存、符号、串口和 Modbus 优先使用已有共享能力；
GUI 接口负责窗口、页面、表单、显示、回放及结果核对，不另开设备连接。

## 选择窗口

先 `gui_open` 或 `connect`，再 `gui_control(action="windows")`。根据用户意图选择
`window_id`；多窗口不能取第一项。`kind` 区分 desktop/web，`gui_protocol=2`
表示新版控制协议；旧窗口需更新并重新打开。后台选择沿用 `gui_open(runtime_id=...)`。

`gui_control(action="snapshot", window_id=...)` 从该页面实时取得 page、tab、section、
backend、connected、device_generation、visibility、focused、panels 和 alerts。
这是窗口状态，不是后台状态的代替品，也不证明像素布局或恒定帧率。

单项演示优先使用已有页面和控件，例如通过文件来源加载符号、从 SuperWatch 看变量、从 RTT 看日志、从 SystemView 看任务与中断。需要同时观察两种现象时，用[灵活面板](agent-ui.md#组合已有视图进行演示)复用这些视图。优先使用 GUI 已提供的曲线、仪表、回放和导出；只有用户要求单独交付其他界面或现有能力确实不足时，再讨论额外实现。

## 边展示边分析

按问题选择能检验判断的证据，用户的措辞和问题类别都不限。先想清楚哪项观测会影响答案：数值如何变化可用波形，事件有没有发生、先后顺序如何可用日志，需要核对二者的关系再并排。比如设备偶尔没响应，已有 RTT 收发日志就能帮助判断请求是否到达；用户只提供历史采集时可用 GUI 回放，并标明来源。源码或已有证据足以回答时直接解释。

1. 需要实时证据时，先按工程和探针选定后台。复用其可见桌面或浏览器窗口；还没有窗口时调用 `gui_open` 打开，等返回 `ready`。使用 `gui_control(action="navigate", window_id=..., page="dashboard", tab="superwatch")` 展示变量，用 `tab="rtt"` 展示 RTT 文本与波形。用户正在使用灵活面板时，可复用其中匹配的视图。
2. 用窗口快照核对实际页面、可见性和实时/回放状态。按任务配置变量或 RTT 通道，已有采集直接订阅。SuperWatch 用 `superwatch(action="values")` 读取已采样值，比较递增的 `sample.sequence`；RTT 用 `rtt_read_channel` 读取同一通道，为 AI 单独延续返回的 `session` 和 `cursor`。用户可以在 GUI 看实时变化，AI 用同期数值、时间或日志行解释观察结果。
3. 后台已运行但窗口未接入、暂停、处于回放或尚无新数据时，说明实际状态，核对数据源再判断。完成分析后用 `detach` 退出 AI 会话，保留用户继续查看的窗口及共享采集。用户另有停止、只在后台分析或导出图片的要求时按其要求执行；静态图片可用 GUI 的 PNG 导出。

## 导航与显示

`gui_control(action="navigate", window_id=..., page="dashboard", tab="systemview")`。

| 页面 | 子页 |
|---|---|
| config | section=local/files/firmware/runtime |
| dashboard | tab=rtt/superwatch/hardfault/memory/serial/modbus/systemview/symbols/workbench |
| online-flash / offline-flash / remote-service | 无必填子页 |

`focus` 请求前台；浏览器可能拒绝，核对 focused，不能仅凭调用成功宣称已置顶。
SystemView 显示动作：`systemview.window`（seconds=0.5/1/2/5/10/30/60）、
`systemview.pause/resume/zoom-in/zoom-out/fit`。SuperWatch 显示动作：
`superwatch.pause/resume`。这些暂停只影响该窗口绘图，不停止共享采集。

## 所有页面的原有控件

1. `gui_control(action="controls", window_id=..., offset=0)` 返回可见按钮、输入框、
   选择框、展开菜单和文件输入。按 next_offset 翻页；每页至多50项，有响应大小上限。
2. 用 label、test_id、context（例如 RTT 通道）识别唯一控件；disabled/readonly
   不能绕过。保留返回的控件 id 和页面 context。
3. `gui_control(action="control.set", window_id=..., control_id=..., expected_context=...,
   value=...)` 设置输入/选择框。复选框传布尔值；下拉选项须来自实际 options。
4. `control.click` 调用原有按钮/菜单处理程序。页面、设备代次、控件内容变化会拒绝旧
   控件；重新读取后按当前意图决定，不能自动重放烧录、写入、发送或升级操作。
5. 在 JTAG 或 UART ISP 的 OTP 读视图，点击标签为 `Word N` 的单元格并重新获取 controls。选中控件的 `description` 包含界面当前显示的熔丝值、影子值和锁状态。换选单元格只读取窗口中已有的结果。
6. 再取 snapshot/controls，并查询对应共享任务的终态。`applied` 仅确认前端已执行
   指令，不代表异步设备操作、文件解析或烧录成功。unconfirmed 不自动重试。

这条路径包含配置、在线/脱机烧录、OTP 配方、串口/Modbus 表单、日志、显示偏好、
符号/内存/HardFault 和确认对话框；使用原有禁用条件、校验与确认，不接受任意 JS、
CSS 选择器或外部 URL。按用户授权操作；不能以界面点击绕过供电、擦除、OTP 等边界。
连接/升级/烧录仍用共享任务状态和读回结果判定。外部商店链接不是测试功能。

## 文件与回放

`file.select` 传 control_id、expected_context 和后台电脑上的绝对 path；目标须是
file_picker=true 的输入框或文件选择按钮。文件通过有界、短期、单次且绑定窗口的
本地通道交付，最多256 MiB，原有解析器保留更小的限制。轮询 snapshot.file：
loading/delivered/failed；delivered 仅代表交给控件，还要核对面板的解析状态。
桌面记录目录选择可对 directory_picker=true 的按钮调用 `directory.select(path=...)`。
Web 的记录目录对话框使用普通输入/浏览控件。导出/转换优先用已有共享日志接口，
读取返回的文件路径；不要对未知的系统“保存”对话框发送点击。

- **SystemView**：导航 systemview，file.select 指向 `systemview-replay-file`。
  用 controls 操作播放/暂停、倍速、重新播放和返回实时；snapshot.panels.systemview.replay
  给出文件、进度、状态与解析错误。Timeline 显示动作继续可用。
  导入只让该窗口退订实时流，其他窗口仍可采集；返回实时重新订阅已有采集。
- **RTT**：导航 rtt，展开目标通道“日志”，选择其中的 JSONL file_picker。
  当前兼容流量日志分段上限16 MiB；用播放/暂停、回放速度、日志通道、位置及退出
  控件操作。`panels["rtt.replay.<通道>"]` 返回 cursor/frames/source/speed/playing。
  RX/TX 都仅作历史显示，绝不重发捕获的 TX。
- **SuperWatch**：导航 superwatch，使用日志回放文件输入及原有播放/速度/定位/返回实时
  控件，保留格式校验与 Worker 缓冲限制。不停止后台采集。
- **串口**：导航 serial，流量回放与 RTT 使用同一组件，按日志源选择端口；不发送历史数据。

## CLI / SDK 同源

MCP `gui_control` 映射到共享 `gui_windows`、`gui_snapshot`、`gui_action`；原
`gui_present` 保持兼容。SDK 使用 `RuntimeClient.call` 调用同名能力。

```powershell
python -m mklink runtime call gui_windows --runtime-id <后台ID>
python -m mklink runtime call gui_snapshot --runtime-id <后台ID> --arguments '{"window_id":"窗口ID"}'
python -m mklink runtime call gui_action --runtime-id <后台ID> --arguments '{"window_id":"窗口ID","action":"navigate","page":"dashboard","tab":"systemview"}'
```

GUI 显示调用只附着已有后台，不连接硬件；结束 detach。Web 与桌面各有独立窗口 ID、
回放与显示状态。远程服务中的异地窗口不接受本机窗口控制，保留原远程权限边界。
