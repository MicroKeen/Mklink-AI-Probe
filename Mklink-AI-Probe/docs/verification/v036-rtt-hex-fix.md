# 0.3.6 RTT HEX 日志修复验证

2026-10-19，基线 `55e0e5c6`，分支 `codex/0.3.6-fixes`。原故障、客户发送代码及授权见 [初始交接](v036-rtt-hex-handoff.md)。本记录是源码修复验证，不是 0.3.6 发布验收。

## 修复后的行为

- 遵照维护者补充要求，Web 终端模式只订阅 `rtt-terminal-N`，不订阅收发流；HEX 模式只读取字节缓存。收发模式订阅 `rtt-N`。切换模式不停止或重新启动设备采集。
- 后端按各通道的收发订阅需求运行行组装、自动检测和曲线解析。无收发订阅时跳过这些步骤，终端文本及原始字节缓存继续工作。另一个共享窗口显式订阅收发时，该通道仍可解析；不会由一个窗口的终端模式关闭其他窗口的收发。
- 订阅状态变化时清空未完成的行片段，避免把离开收发前的半行拼接到重新进入后的文本。终端使用独立的增量解码器，保留 CRLF、UTF-8 分块及原始控制字符。
- CSV 检测和转换共用完整有限十进制 token 规则，不再用 `rstrip` 剥离 `C/A/B` 等 HEX 字母。支持正负号、小数、科学计数法、括号；整行数值才是 CSV 数据。混合日志不会生成部分曲线，也不会抢占分隔符和列名。显式 CSV 标识符表头使用逗号或制表符；自定义列名、KV 单位文本和正则解析仍受支持。
- `RttLineParser.parse` 仅在数值解释范围内隔离 `ValueError` / `OverflowError`。原始日志和后续行继续输出；设备读取、hub 发布及资源错误不在捕获范围内。
- Web、独立 RTT 曲线 CLI、MCP sidecar 使用同一解析器；独立原始 RTT 终端没有数值解析调用。公开命令参考同步更新，未覆盖安装全局 Skill。
- 已更新受版本管理的生产 Web 资源，并将新增 HEX 回归加入 shared-runtime CI。

## 本地检查

PowerShell 7、UTF-8、Windows Python 3.14；全部测试和构建经 `scripts/build_workspace.ps1 -BuildRoot <MKLINK_BUILD_ROOT>`。本机根为 F 盘专用构建目录。

| 检查 | 结果 |
| --- | --- |
| HEX/解析器、RTT/SuperWatch、MCP、共享 RTT、订阅、hub/API、性能、反馈/Skill 边界 | 376 passed，1 skipped；`reports/v036-rtt-python.xml` |
| 最终 HEX 回归、启动、重连、RTT session、remote API | 266 passed；`reports/v036-rtt-lifecycle.xml`；与上组有重叠，不相加 |
| RTT 页面、终端、HEX、发送、binary stream GUI | 5 文件 85 passed |
| `npm run build` | TypeScript 与 Vite 生产构建通过；保留已有大 chunk 提示 |

新增回归覆盖客户原文、整段/逐字节/多种分块、跨批次 CRLF、中文 UTF-8、末尾无换行、多通道持续输出、异常数值行后的有效数据、终端零解析调用、共享窗口订阅需求、模式切换片段隔离、CLI/MCP 及真实错误仍触发停止/失败回调。

生命周期扩展组首次出现 265 passed / 1 failed：`test_failed_source_reload_requires_explicit_retry` 的 idle fixture 受先前测试遗留的全局 SuperWatch runtime 影响，进入其未实现的原子重载路径。已按相邻测试方式隔离该 fixture 的 `_runtime`，同组复验 266 passed；未修改符号重载产品逻辑。

Python 组有既有 websockets 弃用警告；一项 MCP 可选依赖测试跳过。含测试联接的运行目录由构建入口保留，没有绕过清理保护。

## 真实浏览器验证（离线设备夹具）

真实 Chrome 加载本分支生产 `gui/dist`，使用真实 API、WebSocket、StreamHub、RttStreamManager 和 decoder。设备端为本地 FakeDevice，无硬件读写。夹具和截图仅保存在构建根 `reports/v036-rtt-browser*` 与 `reports/v036-browser-*.json`。

1. 两通道均为终端：每通道收发订阅 0、终端订阅 1；`raw_lines=0`、`parsed_lines=0`、自动检测次数 0。CH0 连续显示含 `0C` 的客户 HEX 格式及递增后续日志。
2. CH0 保持终端、CH1 切换收发：CH0 仍零解析；CH1 正常显示两条曲线与日志，解析 52 行时采集仍运行，设备停止次数 0。
3. CH0 也切换收发：56 行 HEX/后续文本正常显示，曲线解析 0；CH1 已解析 104 行，采集仍运行。
4. 两通道切回终端：收发订阅均归零，计数停在 CH0 原始 114 行、CH1 数值/原始 138 行；设备读取从 4313 次继续到 4370 次，计数保持不变。
5. 关闭测试标签：所有订阅归零。显式停止后 `running=false`、设备停止次数 1。测试服务退出，监听端口释放；浏览器 error 日志为空。

截图展示 CH0 终端与 CH1 曲线并行。截图和夹具计数只证明真实 Web 与离线输入闭环，不代表客户硬件复验。

## 未覆盖与交付边界

客户电脑/目标板/下载器固件和完整现场日志未提供，尚未完成客户板回归；原截图中物理断开的其他原因仍待现场日志确认。没有运行本轮实体硬件、覆盖安装、全量发布资格或原生跨平台构建；未刷探针/目标固件、签名、合并、发布、移动标签或修改更新渠道。0.3.5 正式版与历史遗留项保持原结论。

纯数字字节串与十进制序列本身无法仅靠文本区分；带标签或 HEX 字母的本案日志已覆盖。数值策略仍按启动采样窗口选择，不承诺任意格式自动切换。
