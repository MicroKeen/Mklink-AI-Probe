# Agent 语义工作台

本功能为现有 MKLink Web GUI 增加可组合子面板和可发现的业务动作。Agent 可以通过同一个共享运行时读取页面状态、操作指定面板、查询执行回执，并处理用户从页面提交的协作请求。浏览器中不运行 LLM。

本文描述开发分支中的实现和明确边界；自动测试、真实浏览器和真机证据由[本次验证报告](verification/agent-ui-workbench.md)分别汇总。存在接口不代表相应硬件操作已经验收。

## 用户入口与共享边界

在 Dashboard 打开“组合工作台”，添加 SuperWatch 波形、变量、RTT 或串口面板。每张卡片有稳定 ID，可拖动位置、拖动右下角改变尺寸，也可在配置中用数字输入位置和宽高。网格为 12 列，窄屏按顺序排列。信号路径留空表示跟随所有已选采集项；RTT 绑定通道，串口绑定已有端口。原 SuperWatch、RTT View 和串口助手入口继续保留。

“保存布局”保存当前项目的面板、来源、几何位置及受支持的视图设置；“恢复已保存布局”替换当前未保存配置。面板恢复、增加和关闭都不连接设备、不开始采集、不打开新的硬件 reader、不发送数据，也不自动开始录制或回放。关闭最后一个视图也不等于停止后台采集。

| 状态 | 作用域 | 示例 |
| --- | --- | --- |
| 面板显示 | 单个 `panel_id` | 信号子集、显示暂停、图例、坐标范围、游标、触发、回放、RTT/串口显示模式 |
| 共享显示配置 | 当前项目 | 常用变量、信号分组、默认别名/颜色/公式；`signals.*` 会影响使用共享配置的面板 |
| 面板样式覆盖 | 单个波形面板 | `waveform.style`、`waveform.plot`；区别于共享 `signals.style.set` 和 `signals.group.*` |
| 采集与设备 | 既有共享后台/目标 | 采集项增删、启停、间隔、变量写入、连接时钟、RTT 发送和解码设置 |
| 记录 | 既有共享记录器 | 任一面板的开始/停止记录都会作用于同一个后台记录器 |

变量卡片可独立订阅现有 SuperWatch 流的摘要；它不依赖另一张波形卡片才能显示数值。RTT 和串口卡片复用原有流和发送 API。串口的端口打开、波特率、YMODEM、发送序列、自动应答、文件发送等高级配置继续在原串口助手操作；新子面板不另建串口会话。

## 无 GUI Agent 的调用方式

先按 [共享运行时说明](../references/shared-runtime.md) 选择、附着用户指定的后台，并在需要展示时打开 GUI。`gui_present` 的 `displayed` 仅表示导航，不能作为任何图表动作完成的证明。语义动作要求目标页面在线；纯后台、未打开页面时仍可使用原有后台能力，但没有可操作的前端实例。

MCP 使用 `gui_call(capability, arguments)`；已附着的 Python `RuntimeClient` 使用同名能力的 `client.call(capability, arguments)`。二者都经过原有认证和运行时准入，不提供任意 URL、JavaScript 或 shell 透传。

| 能力 | 参数 | 用途 |
| --- | --- | --- |
| `gui_frontend_pages` | `{}` | 发现 `session_id`、当前目标和各页面在线状态 |
| `gui_frontend_read` | `{page_id}` | 读取实际目录、严格参数 schema、状态及 revision |
| `gui_frontend_call` | 完整 `agent-frontend/1` 命令 | 提交一个定向操作 |
| `gui_frontend_receipt` | `{command_id}` | 查询原命令回执 |
| `gui_frontend_layout` | `{}` | 读取当前项目的已保存布局 |
| `gui_frontend_save_layout` | 完整布局对象 | 带 revision 保存布局；不操作设备 |
| `gui_frontend_intents` | `{}` | 读取项目协作请求列表 |
| `gui_frontend_intent` | `{request_id}` | 查询一条请求和原答复 |
| `gui_frontend_reply` | `{request_id, revision, reply}` | 回答原请求；答复本身不会执行动作 |

`read.actions` 的键是传输层动作 ID，必须从当前目录取得。其描述符的 `name` 是下表中的语义名称，`panel_id` 指向具体实例，`inputSchema` 是实际允许的参数，`effect` 为 `view`、`file` 或 `device`。不要拼接动作 ID，也不要把另一个页面的 schema 或 revision 用到当前页面。

以下 Python 片段假定 `client` 已通过原有流程附着到经过确认的共享后台，且 `chosen_page_id`、`chosen_panel_id` 已根据返回目录和用户场景选定。例子只暂停一张波形的显示：

```python
import time
import uuid

gui_call = client.call
discovery = gui_call('gui_frontend_pages', {})
report = gui_call('gui_frontend_read', {'page_id': chosen_page_id})
if not report['online'] or report['session_id'] != discovery['session_id']:
    raise RuntimeError('目标页面已离线或目标已改变，请重新发现')

action_id = next(
    key for key, action in report['actions'].items()
    if action['panel_id'] == chosen_panel_id and action['name'] == 'waveform.pause'
)
command = {
    'protocol': 'agent-frontend/1',
    'session_id': report['session_id'],
    'page_id': report['page_id'],
    'command_id': uuid.uuid4().hex,
    'expect_revision': report['state']['revision'],
    'deadline': int(time.time() * 1000) + 10000,
    'action': action_id,
    'args': {'paused': True},
}
receipt = gui_call('gui_frontend_call', command)
until = time.monotonic() + 30
while receipt['status'] in {'queued', 'accepted'} and time.monotonic() < until:
    time.sleep(0.5)
    receipt = gui_call('gui_frontend_receipt', {'command_id': command['command_id']})
print(receipt)
# 仅 applied/completed 是完成；随后重新 read 核对指定面板的实际状态。
# 超时、unknown 或传输错误保留 command_id，查询原结果，不创建新命令重放。
```

命令 deadline 使用 Unix 毫秒，提交时必须在未来 30 秒内。`queued` 表示排队，`accepted` 表示页面已开始异步处理，均不是完成。`rejected` 表示未通过检查；`failed` 表示业务失败；`unknown` 表示结果无法确认，会阻止该页面继续接受可能重复的动作。重复提交完全相同的命令返回原记录；同 ID 改参数会被拒绝。已提交后不要刷新 deadline 再重发。

页面和命令绑定后台实例、探针、设备 generation 与项目。设备/项目改变、页面重建、离线、旧 revision、错误参数或未知对象必须重新发现或明确报错，不能回退操作其他存活页面。声明 `effect=device` 不会绕过原来的设备占用、采集所有权、类型和读写限制。

## SuperWatch 19 组功能映射

“读取”默认返回有界配置摘要，不连续传输全部采样；完整对象细节和当前数据使用 `*.inspect`、`symbols.describe` 或原有后台读取能力按需查询。始终以在线目录为准，组件未就绪时某些动作不会出现。

| 功能组 / 用户入口 | 已实现语义名称 | 作用域、状态与边界 |
| --- | --- | --- |
| 1. 搜索变量、展开目录、仅已选、查看类型 | `symbols.search`、`symbols.expand`、`symbols.describe`、`symbols.inspect` | 搜索/展开属于变量面板；describe 从当前符号目录解析类型、地址和写权限。未知分支须先展开父项。摘要带总数，inspect 支持分页。 |
| 2. 符号加载、重新解析、C 布局 | `symbols.source.load`、`symbols.source.parse`、`symbols.reload`、`symbols.reparse`、`symbols.c-layout.apply` | 复用原加载器/重绑定；load 使用后台可访问的已有 AXF/ELF 路径。不会烧录或自动重新开始采集。`symbols.connection.connect` 对应原快速连接入口。 |
| 3. 添加/移除采集项 | `symbols.select`、`peripherals.select` | 共享采集项；显式区别于仅隐藏。路径/失效符号/业务返回错误会拒绝。 |
| 4. 类型化变量写入 | `symbols.write` | `value` 是原类型编辑器文本：数值/十六进制、枚举名或 `true`/`false`。保持只读、位域、generation 检查；结果 `acknowledgedValue` 不是自动读回样本。 |
| 5. 外设目录、目标/SVD、寄存器观察 | `peripherals.targets`、`peripherals.source.select`、`peripherals.search`、`peripherals.inspect`、`peripherals.select` | 原外设目录和共享观察项。source 接受 target ID 或后台 SVD 路径二选一，不能仅凭显示名猜设备。 |
| 6. 数组快照窗口 | `symbols.array.set`、`symbols.array.clear`；后台 `superwatch_snapshot` | 共享一维数组窗口，校验真实长度、起始索引和数量；不是标量采样项。工作台同步选择状态，只有跟随全部信号或显式包含该数组路径的波形面板显示快照。 |
| 7. 采集开始/停止、间隔和状态 | `superwatch.start`、`superwatch.stop`、`superwatch.interval`、`superwatch.status` | 后台共享操作，保留原所有权/冲突检查。interval 单位为秒；动作返回实际后端结果。 |
| 8. 暂停/继续显示 | `waveform.pause` | 只冻结该波形面板；不映射成共享后台 pause/stop。 |
| 9. 调试连接时钟 | `device.clock.read`、`device.clock.set` | Dashboard 全局连接时钟入口，按实际支持的 SWD/JTAG 频率校验。最新主线已不在 SuperWatchTab 单独轮询/设置旧速度档位。 |
| 10. 常用变量、排序 | `symbols.pins.set`、`symbols.inspect` | 替换项目常用路径的有序集合；保留缺失符号提示，按原 revision 保存，冲突不覆盖。 |
| 11. 分组、成员、拆并与高度 | `signals.group.add/rename/remove/move/merge/split/configure`、`signals.style.set` | `signals.*` 写共享项目分组；成员通过 style 的 group 字段迁移。`waveform.plot` 则只拆分/合并/调整当前面板的图窗。删除分组不删除采集项。 |
| 12. 别名、颜色、强调、线/点、公式 | `signals.style.set`、`signals.inspect`；`waveform.style` | 前者是共享默认样式，后者是本面板覆盖。复用受限公式解析器，不执行任意 JavaScript。 |
| 13. 曲线、图例、监视表 | `waveform.channels`、`waveform.channel`、`waveform.legend`、`waveform.column`、`waveform.inspect` | 当前面板信号集合、可见性、格式/精度、列显隐和宽度；隐藏不移除采集项。 |
| 14. 时间窗、Y 轴、缓冲 | `waveform.viewport`、`waveform.y`、`waveform.buffer` | 当前面板；返回实际设置。范围、点数和内存边界仍由渲染器/worker 校验，抽样显示不等于原始采集丢失。 |
| 15. 触发器 | `waveform.trigger`、`waveform.trigger.control` | 当前面板配置及 arm/force/reset；`triggerState` 区分触发阶段，接受命令不代表信号已触发。 |
| 16. A/B 游标、阈值与测量 | `waveform.cursor`、`waveform.threshold`、`waveform.inspect` | 当前面板；inspect 按需返回范围、游标和通道测量，调用上下文同时保留 page/panel/target 身份。 |
| 17. PNG 导出 | `waveform.png` | 导出指定面板实际 canvas，返回保存/下载结果；原生选择器取消不宣称已保存，浏览器下载不证明用户已将文件落到某个路径。 |
| 18. 后台记录与日志回放 | `recording.refresh/start/stop`；`waveform.replay.load/control/seek/speed` | 记录器共享；回放局限于指定面板。load 使用后台日志 `path` 或短文本 `filename`+`text` 二选一；后台文件和原 GUI 文件选择都复用已有回放 worker。 |
| 19. 阅读布局、目录、状态 | `superwatch.catalog.set/focus/width/visibility`；`symbols.view.set`、`symbols.sections.resize/reset`；`panel.*`、`layout.*` | 默认 SuperWatch 页与工作台面板分别暴露对应状态。变量目录宽度/分区高度保留键盘控制；工作台几何参数可用键盘编辑数字。 |

RTT 子面板另外提供 `rtt.view.set/pause/clear/chart.reset/chart.range/encoding/send`；其中 encoding 是同通道共享解码配置，send 需要真实活动 Down Buffer。串口子面板提供 `serial.refresh/view.set/pause/clear/send`，仅向绑定的已有可写端口发送，并保留 YMODEM 占用检查。

## 布局与协作请求

布局保存在项目 `.mklink/frontend_layout.json`，具有独立 `version: 1`、递增 revision、最多 32 张面板、受限网格尺寸和受限 view 对象。保存使用原子写和乐观并发检查；版本错误、损坏数据、重定向存储路径、旧 revision 都拒绝。旧 `.mklink/superwatch_workspace.json` 和常用变量文件继续保留，不被新布局替代。

首次读取 revision 为 0 且没有面板的布局时，用旧共享分组/信号建立一个变量面板及各非空分组的波形面板；没有分组信号时建立默认波形面板。原 group ID、样式和常用变量不被改写，卡片 ID 由原分组 ID 派生。初始卡片明确标为“尚未保存”，只有用户或 Agent 显式保存才写新布局文件。超过 31 个非空波形组或单卡片 500 个信号时显示未生成卡片的数量，原配置仍保留。已保存的空布局（revision ≥ 1）不会被自动填回。初始迁移不自动猜选 RTT 通道或串口端口。

工作台卡片的 “Agent” 入口可提交解释、检查或方案请求。选择本身不会执行设备动作。后台从可信页面报告冻结该对象的目录信息、公开状态和 page revision，存入最多 64 KiB 的 `context`；后续切换视图不会改写这份上下文。Agent 在同一后台读 `gui_frontend_intents`，核对 `current_target`、请求对象和冻结上下文，再用 `gui_frontend_reply` 携带该请求 revision 回复。回复会在原请求中显示；重复相同答复返回原结果，旧 revision/旧目标拒绝。提交响应丢失后，页面先查询原 request ID；原目标结束且没有记录时允许用户显式放弃本页请求，不自动改 ID 重发。页面不会自动唤醒已结束的 Agent 会话，也不自动执行自然语言请求。当前实现是面板级入口，尚无尖峰、特定采样点或日志行的精确选区入口。

## 已知实现边界

- 32 是协议/布局数量上限，不是已验证的持续采集性能承诺。每个视图有独立 worker/有界缓冲，客户端资源随面板数增加；后台生产者不重复创建。
- `gui_frontend_call` 的整个命令最多 64 KiB；短日志 text 最多 8192 字符。完整日志使用 `waveform.replay.load({path})`，要求后台可访问的本地绝对路径、支持的 UTF-8 日志头、普通文件，拒绝网络路径/符号链接/junction，文件上限为既有回放器的 256 MiB。原 GUI 文件加载继续可用。
- 保存布局不保存待发送串口草稿、设备写入值、登录令牌或自动执行命令，也不自动恢复录制/回放任务。恢复完成需分别核对布局已载入与各面板就绪状态。
- 语义状态为配置摘要；最新采样值、计数、播放时钟通过显式读取取得，避免每批数据都改变操作 revision。
- 历史内部 Raw Log、CSV 导出、旧工程保存入口已被当前 GUI 隐藏，本次不恢复它们；没有新增 FFT。
- `unknown` 回执、断线后的设备写结果和发送结果需要查原回执及实际状态；不得通过新命令 ID 自动重放。

## A01–A20 验收映射

下表中的“实现”指代码路径已具备，验证结果待本次报告汇总；不把单元测试、模拟流或源码检查写成真机通过。

| 编号 | 实现映射 | 尚需核对的证据/明确缺口 |
| --- | --- | --- |
| A01 发现/目录 | pages/read，真实 action schema、panel ID、target、revision | 实际认证后台 catalog，检查无令牌/草稿 |
| A02 多类组合 | panel.add/configure，watch/variables/rtt/serial 卡片 | 双波形、双 RTT、双串口浏览器同屏及来源绑定 |
| A03 布局交互 | 拖动、右下角缩放、数字配置、panel.move | 鼠标/键盘数字编辑/小屏截图；未增加专门方向键移动卡片 |
| A04 同源独立视图 | waveform.style/viewport/y/cursor/trigger/pause | 两实例互不串扰，区分共享 signals.* |
| A05 生命周期 | 每实例根节点、注册键、订阅和 dispose | 反复关闭/增加，监听器/worker/绘图资源回收 |
| A06 并发保存 | frontend layout revision、原 workspace revision | 两页面旧 revision 不覆盖，恢复冲突可见 |
| A07 变量/常用/数组 | symbols.*、原 typed catalog | 真实符号文件、数组边界、缺失项、隐藏与移除区别 |
| A08 重载/C 布局/换目标 | 原重绑定、设备 session 失效检查 | 后台回归；换设备/写入相关项需授权真机 |
| A09 外设观察 | peripherals.*、原 SVD/Pack 目录 | 真实匹配目录与适用目标，只读限制 |
| A10 共享采集/时钟 | superwatch.*、device.clock.* | 原准入/订阅冲突与真机；暂停显示不停止采集 |
| A11 类型写与未知结果 | symbols.write、一次派发、receipt | 故障注入不重放；真实类型写入需授权真机 |
| A12 共享分组/公式 | signals.group.*、signals.style.set、原保存器 | 多面板广播、非法公式拒绝、冲突不覆盖 |
| A13 坐标/缓冲/表列 | waveform.viewport/y/buffer/column/channel | 边界、实际生效设置及浏览器交互 |
| A14 触发/测量 | waveform.trigger/control/cursor/inspect | 已知信号夹具、阶段状态、来源与实例隔离 |
| A15 录制/回放 | recording.*、waveform.replay.*、后台受控文件读取、独立 worker | 原记录终态；seek 竞争；另一实时面板继续更新；路径/格式/容量拒绝边界 |
| A16 导出/持久化 | waveform.png、layout.save/restore、首次旧分组投影 | 实际图片/下载及往返；旧文件保留；首次迁移只读且待保存，有意保存的空布局不填回 |
| A17 RTT/串口 | 单通道/单端口卡片及原发送接口 | 端点隔离/只发送一次/Down Buffer/YMODEM；实际端点需授权 |
| A18 意图闭环 | 面板 Agent 入口、可信冻结 context、intents/intent/reply | 页面→收件箱→答复可见；精确尖峰/日志行选区未实现 |
| A19 协议异常 | 幂等记录、deadline、revision、target、unknown | 断线、错页、重复/冲突 ID、鉴权与设备切换 |
| A20 持续负载 | 有界流、局部暂停、独立 dispose；32 面板报告体积回归 | 持续采集资源与丢失统计实测；不得将数量上限当性能验收 |

相关测试包括 `frontendControl.test.ts`、`workbenchLayout.test.ts`、`WorkbenchTab.test.ts`、领域组件测试、波形/回放测试以及 `test_runtime_frontend.py`。构建与测试仍按仓库规定通过 `scripts/build_workspace.ps1` 运行；硬件测试与普通无设备回归分开记录。

本轮已在真实浏览器观察到 7 个面板同屏、独立回放/图例控制，通过后台路径加载 12,000 行约 313 KiB CSV，执行 seek、游标、Y 轴设置及约 48 KiB PNG 导出，保存布局到 revision 1，并完成页面请求→真实 broker 冻结上下文→Agent 答复→页面显示的往返。最终重建后的自动回归和浏览器复查以验证报告为准；这些结果不代表持续真机采集、多物理端口和变量写入已通过验收。
