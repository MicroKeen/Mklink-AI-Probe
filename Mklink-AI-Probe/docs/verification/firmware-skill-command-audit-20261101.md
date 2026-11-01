# 固件命令与 Skill / MCP 核对

后续用户已授权实施；修复及安装状态见 [宿主修复记录](firmware-skill-fixes-20261101.md)。
以下保留修复前的审计基线。

2026-11-01。用户要求核对遗漏及不支持项。本轮是审计，没有修改产品、Skill、固件、
安装内容或版本，没有连接下载器、暂停目标、烧录、修改 VCC/OTP 或重新打包。

## 结论

HPM 常用下载调试能力已有实现：ROM BIN/HEX 烧录、内存、ELF/DWARF、XML 外设、
RTT、SuperWatch、SystemView，以及暂停/继续/单步/核心寄存器/硬件执行断点。
不能再把后三项笼统列为“RISC-V 不支持”。但当前 Skill 和 MCP **尚未完全对齐固件**，
发现文档过期、安装包同步滞后、时钟入口限制及若干未开放能力；另有一个固件接收空实现。

“原始命令没有同名 MCP 工具”不直接算缺失。高层烧录任务、共享 MUX、USB UART 等
会替代或组合原始命令。MCP 注册清单也不代表每个型号和固件都支持相应功能。

## 核对基线和方法

| 层 | 基线 |
| --- | --- |
| 固件源码 | MicroLink_Plus `main` / `4dcdb8a`，包含 `a36a192` 时钟与并行采集改动；只读，原有用户修改保留 |
| HPMLink 参考包 | V4.7.2 / Oct 31 2026 17:41:04；既有 UF2 SHA256 `ebbc11f2d429e815e6c1a2b67ac1a53c821b17af89aed38ab29677be1f7ecec0`，本轮不重新刷写或实测 |
| 上位机源码 | `codex/v0.4.2-fixes` / `c3479a23`；已 fetch，远端一致，`microkeen/main=3cc474bb` |
| 本机完整 Skill | 安装标记 `0d680d90e2bb1ac99d370de6f6578f5c9a96801c`，0.4.2 本地候选 |
| 本机 Windows | 已验收产品源 `8a09b32e`；安装器及验收见 [安装记录](v042-clock-install-20261031.md) |

检查 `.pyi`、生成的 `__pikaBinding.c`、C 实现及 HPMLINK 条件编译，而不是只搜索命令名。
八个设备模块共 **74 个入口**：cmd 30、hpm 26、load 4、RTTView 2、SystemView 2、
vofa 1、serial 6、ym 3（包含类构造函数）。这些入口均有绑定及 C 函数；这不等于全部
功能已实现。Pika 标准库、RTOS 任务库及固件内部非公开 C 函数不计入设备 API。

同时检查 MUX 会话操作 1–4、目标操作 0x10–0x16、RTT 0x20–0x25、Watch 0x31/0x32，
共 19 个请求码，以及 0x40/0x41 数据事件。HPM_DEBUG 的 0–9 十个操作均有宿主映射。
CMSIS-DAP/OpenOCD 的外部调试通道与共享 MCP 分开，不把 IDE 支持等同于 MCP 支持。

使用真实 FastMCP `tools/list` 加载两份运行时，没有调用连接/版本查询硬件入口：

- 源码：**47 个工具、107 个共享能力**。
- 已装完整 Skill：**47 个工具、106 个共享能力**。
- 工具名称集合相同；`set_debug_speed` 参数不同；已装 Skill 缺少 `watch_runtime_stats`。
- 测试 `set_debug_speed(clock_hz=5000)` 时用隔离的假后台：源码向后台传递参数成功，
  已装 Skill 在 MCP schema 层报 `profile` 缺失 / `clock_hz` 未知，未调用后台。

## 确认的问题和建议顺序

### 1. 时钟说明与当前固件不符

`SKILL.md`、`references/hpm.md`、`references/shared-runtime.md`、
`references/tool-index.md`、`references/commands-memory.md` 仍将 HPM 限制为
4/10/20/30 MHz，部分还写“14 档不要用于 V4/HPM”。`runtime_mcp.py` 的
`set_debug_speed` 和 `start_job` 描述也保留四档限制。界面位置仍被部分文档称为仪表盘。

当前固件 `cmd.get_version()` 已声明 JTAG_CLOCKS/JTAG_CLOCK_ACK；宿主
`capture_clock.py` 根据两个能力共同协商 14 档：
1/5/10/20/50/100/200/500 kHz，1/2/5/10/20/30 MHz。旧 4 MHz 作为兼容数值保留。
应按接口和实际能力选择，默认 10 MHz；旧固件仍保持旧边界并提示升级。
8 MHz 不属于当前 JTAG 支持档位，仍不能随意设置。应答不是本次物理 TCK 测量。

优先统一 Skill、工具描述、错误提示和 CLI 帮助；不要只更新下拉列表。

### 2. 已安装完整 Skill 落后于已安装上位机

已装 `runtime_mcp.py` 的 `set_debug_speed(profile: str)` 没有 `clock_hz` 参数；
源码已支持二选一。上述 FastMCP 调用已复现差异。升级上位机没有同步更新这份 Skill。
旧 Skill 的后台实现也没有后续共享 SystemView 增量订阅、480 B 传输和 Watch 时序等改动。
连接新 GUI 后台与由旧 Skill 自行启动后台的结果可能不同，不能只看相同的 0.4.2 版本号。

已有新后台时，通用 `gui_call("set_debug_speed", {"clock_hz": ...})` 是另一调用入口，
但不能据此声称旧的专用工具或旧 Skill 自建后台已更新。应在后续授权打包时同步完整
Skill，并核对实际导入路径、构建来源及工具 schema。

### 3. 脱机时钟入口仍拒绝新版支持的频率

`offline_download.py:191` 将时钟限制为 100 kHz–30 MHz；HPM debug 路径又在
`:243` 调用不带固件能力的 `validate_hpm_clock_hz()`，只接受旧四档。
隔离解析 14 档及兼容 4 MHz：14 档中仅 10/20/30 MHz 通过，4 MHz 兼容项通过，
其余 11 档拒绝。前五个低频先被 100 kHz 下限拒绝，其余被 HPM 四档检查拒绝。
这个最低频率限制也会影响其他支持低速档位的脱机路径。

此外，低层旧 SDK `burn_hex_file()` 在 `flash.py:631` 先验证 HPM 时钟，再到
`MKLinkFlash.set_swd_clock()` 内获取能力。空能力缓存下的 5 kHz 请求在预检就被拒绝；
隔离假连接复现，未发任何时钟/烧录命令。这是旧单次 SDK 路径的条件性问题，
不能扩大为已经初始化能力的共享 MCP 正常烧录必然失败。

应把离线配置、执行时能力检查和首次能力获取顺序一起修正；不能直接删除旧固件保护。

### 4. Skill 仍提到默认共享 MCP 不存在的工具

`SKILL.md` 要求调用 `set_power_on(..., confirm_user=True)`，但默认共享 MCP 的
47 个工具及 107 个共享能力都没有供电写入口。该同名工具只存在于旧独占
`mcp_server.py`；默认 `python -m mklink mcp` 使用 `runtime_mcp.py`。
低层 Device 和 REST `/api/device/power` 已有供电能力，属于尚未接入共享 MCP，
不是固件不支持。直接关电同样没有共享工具。

根 Skill 还残留旧 `capture_rtt.pattern` 参数限制；默认共享 MCP 没有 `capture_rtt`，
实际应使用 `rtt_start` / `rtt_read_channel` 等。`reboot_probe` 也不是默认共享工具，
不能因为旧模块注册过就指导 AI 调用。应移除失效指引，或实现有边界的共享入口；
供电仍须逐次确认具体电压，不能用原始命令透传绕过。

### 5. 已有后端但默认共享 MCP 未覆盖的工作流

| 功能 | 当前实现 | 缺口 |
| --- | --- | --- |
| 脱机预览、部署、触发 | offline-download REST、CLI、GUI 和生成的 `load.offline`/HPM 脚本 | 默认 MCP `start_job` 不接受 offline/ISP；`gui_call` 也没有对应能力。CLI/API 已覆盖，不能说整个 Skill 完全不能用 |
| HPM UART ROM ISP 下载 | `hpm.isp_config/program` 等已由 `hpm_isp.py` 生成，Skill 有 ISP 参考页 | 缺完整共享 MCP 任务入口 |
| HPM 用户 OTP / 锁组 / UART OTP | 有受限 REST、计划确认、型号限制和脱机配方；`read_configuration` 可读受限快照 | 缺共享 MCP 的计划/写入/锁定接口，Skill 缺集中说明；不能拿 ARM security 工具替代 |
| 实时目标 presence | `cmd.read_swd_idcode`、`hpm.read_idcode` 已用于脱机换板循环 | 没有统一的共享实时 presence 工具；`probe_idcode` 仍可能是缓存 |
| ISP 链路诊断 | 固件 `hpm.isp_link_probe` 有限时查询与结果记录 | 未找到宿主 wrapper、共享能力或 Skill 指引 |
| 探针内存/复位诊断 | 固件 `cmd.get_memory` 调用诊断报告 | 未找到宿主 wrapper、共享能力或 Skill 指引；不等于 MCU 内存读取 |
| 自动扫描、Vref 跟随、蜂鸣器 | 固件 setter；蜂鸣已在下载完成流程使用 | 前两项无宿主包装；无通用共享控制工具。需明确所有权和供电影响，优先级低于下载调试 |

建议增加受约束的高层工作流，不提供任意原始 Pika 命令执行工具。OTP/VCC 本轮未操作，
固件有命令不等于允许扩大白名单或继承历史不可逆操作授权。

### 6. Flash 读取文档有错误和失效示例

`references/commands-memory.md` 的 read-flash 小节仍写“读取需要 FLM”，并演示
`--save flash_dump.bin`。当前共享 `runtime_cli.py` 将 read-flash 路由到 read_memory，
不加载 FLM，且拒绝这种 `--save` 参数。HPM 指南中“Flash 读取无需 FLM”才与实现一致。
应修正文档，并明确通过共享 SDK 将读回数据保存到主机文件。

### 7. 固件 YMODEM 接收是空实现

`ym.pyi` 声明 `ym.ymodem.receive`，生成绑定也注册了它，但
`MicroLink/external/pikapython/pikascript-lib/ym/py_ymodem.c:211` 函数仅 `return 0;`，
没有接收逻辑。因此它是**未实现且误返回成功**，不是可用接收功能。
当前共享 MCP 的 `serial_ymodem_*` 仅支持发送，不依赖这个空实现，不能标成双向文件传输。
已按用户既有授权通知指定固件会话，仅报告问题，没有启动修复或硬件操作。

## 已覆盖和合理边界

| 能力 | 核对结果 |
| --- | --- |
| HPM CPU 调试 | `hpm.debug` 0–9 全部映射到 `hpm_debug`；14 个命名 CSR 和 dpc/pc 别名可达；不是缺少暂停/单步/断点 |
| HPM 核心边界 | RV32 hart 0；GPR/PC 可写，CSR 只读；执行断点显式槽位。FPU 寄存器、多 hart、数据读写 watchpoint、任意 CSR 写入不属于当前 HPM_DEBUG v1 公共契约，不能误判为 MCP 单独漏接 |
| 异常分析 | HPM 可读 mcause/mepc/mtval；没有 Cortex-M HardFault，尚无独立 RISC-V 异常自动解码工具。“无异常”与“不支持分析”应区分 |
| 内存、符号、外设 | 快照/写入/批量/类型化写入/ELF/DWARF/XML 已有入口。`cmd.read_cpu_reg` 实为内存读取，不应拿来代替核心寄存器工具 |
| MUX 内存 | 0x11/0x12 小块读写、0x16 单次 4096 B 读已接入；480 B 传输须按 bit 8 协商 |
| MUX RTT/SystemView | 配置、停止、增量 mask、上下行、128/480 量子已有宿主实现；两种上层采集复用 RTT 协议，不要求同名固件命令 |
| MUX Watch | 启动/停止、最快/周期模式、统计 0x14 已接入源码；安装 Skill 缺相应新能力，固件 bit 9 与 ACK 需同时核对 |
| UART/RS485/Modbus | 共享 serial/modbus 工具使用 USB 串口接口，功能不依赖暴露 `serial.uart/rs485` Pika 类 |
| Flash 页写、进度、FLM 装载 | 组合进高层烧录/下载流程；不必把内部 `program_page/program_progress/load.flm` 逐一变成 AI 工具 |
| 固件升级 | `probe_firmware` 已包装升级工作流，不需要裸露 `cmd.enter_bootloader` |
| 产品限制 | 普通 V4 未启用 HPMLINK 的构建对 HPM 命令返回不支持；V2/V3 不支持 HPM。版本字符串一致也不能替代能力查询 |

## 验证及证据

- 真实 FastMCP 的两份工具列表/schema 已保存；调频调用差异用假后台复现，未调用 USB。
- 74 条逐项分类表包括声明、生成绑定、C 实现、宿主引用和 Skill 引用；文本命中只作
  定位依据，分类经过高层路由核对，不用简单集合差集宣称功能遗漏。
- HPM 调试协议/准入、HPM 时钟、新 JTAG 档位、首次调频、共享 MCP、Skill 边界共
  **296 项回归通过**。这些是无硬件回归，不是新增的 HPM 实板资格。
- 本机审计目录 `firmware-skill-command-audit-20261101` 保存 `command-matrix.csv`、
  `classified-commands.json`、两份 schema/validation JSON、复现脚本及 `regression.xml`。
- wrapper 保留含测试链接的 `run-20261101-190646-c83f45ae`，未强删。
- 指定固件会话仍在处理其独立 V2 任务，本审计不占用该硬件、不沿用 HPM 历史设备状态。
  本结论针对表列的已归档 HPMLink / V4 源码基线，不替正在变动的 V2 候选作验收。

本轮只保存审计结果。建议先修复 Skill/schema 描述和时钟入口，再按用户实际需求补齐
共享 MCP 工作流；重新打包、固件修复和正式发布分别遵循后续明确任务。
