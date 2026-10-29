# HPM AI Skill 能力核实与修复

2026-10-29，产品源 `05e73101`，继续使用 `codex/v0.4.2-fixes` / 草稿 PR #66，版本仍为 0.4.1。
本次不发布、不更新正式资产、不刷探针或目标程序，不操作 VCC/OTP。
Windows 已安装的在线烧录修复包及此前 Linux/macOS 测试包不包含本次改动。

## 用户功能表的更正

| 功能 | 源码核实与本次验证 |
| --- | --- |
| HPM 在线烧录 | 已有 HPM ROM BIN/HEX 路径，不能使用 ARM FLM。上一轮在线实测有效；本轮未再次烧写，完整回读 49,700 字节与对应 BIN 一致。 |
| 内存读取/写入 | 共享内存读取、批量 dump、写入/flush 接口存在。Flash/RAM 读取及 dump 本轮通过；未进行任意 RAM 写入，不能扩大写入验收。 |
| ELF、符号、变量 | 支持 RISC-V ELF/DWARF，默认内置 pyelftools 0.32，无需外部 readelf。当前 ELF 解析 1,528 个变量、26 个结构体、65 个枚举，读到 hpm_core_clock=360000000。 |
| 外设寄存器 | 支持 HPM SVD，通过 HPM5301 目录读取 UART0.GPR.DATA。SCB/NVIC 等 ARM 核心寄存器不适用于 HPM，不代表外设接口缺失。 |
| halt / resume / step / 断点 / CPU 寄存器 | 硬件/底层 RISC-V 引擎有能力，旧 Pika ARM 控制命令未暴露对应接口。新增共享 hpm_debug 适配 HPM_DEBUG v1，软件测试通过。当前私有 V4.7.2 缺少新绑定，实机正确拒绝；新固件正向验收待固件会话完成。 |
| 异常分析 | Cortex-M HardFault 检测不适用于 HPM；“无异常”没有依据。新接口可读 RISC-V PC/mepc/mcause/mtval 等，尚无自动 RISC-V 异常解码报告。 |
| RTT | 目标须集成 RTT。当前 ELF 解析出控制块，活动通道确认后通道 0 实际收到文本，停止成功。 |
| SuperWatch / dump | hpm_core_clock 连续采集约 2 秒、196 序列，值 360000000；dump 96 个完整协议样本、暖机后 76 个，约 96 Hz，CRC/解析/读取错误为零。此短测不代表任意负载无损。 |
| SystemView | 目标已有 RTT/RTOS 实现。发现并修复 U32 任务地址还原溢出；修复后约 5 秒 38,351 事件 / 193,892 字节，四个任务名正常，解析丢弃及流丢弃为零，无自动重试。 |
| UART ISP / 脱机 / OTP / VCC | 保留既有实现和边界；本轮没有实体操作，不能由软件回归推断新实机资格。 |

## JTAG 频率

原始 `cmd.set_swd_clock(8000000)` 对 HPM 私有 JTAG 路径只选择通用固定延时
C 后端（JTAG profile=0），不保证 8 MHz TCK。受支持的 DMI 档位为 4/10/20/30 MHz，
还取决于 41 位扫描、TAP 链、目标 ID 和探针 CPU 条件；CMSIS-DAP 是另一路径。

AI 可自行选 low=4 MHz / medium=10 MHz，必要时按接线条件选 high/ultra；不再逐次
询问普通档位选择。烧录、脱机 JTAG、Device 路径拒绝不支持的 HPM 频率，HPM 默认
10 MHz；ARM 任意低速设置保持可用。显式 profile=0/不匹配/错误回执不再作为成功。
JTAG 失败回退只在确认 4 MHz 档位应答后记入状态，不能宣称已恢复到 1 MHz JTAG。

实机 low/medium 均收到 JTAG 档位确认并成功通信，4 MHz 下 Flash 全量一致。
未用示波器/逻辑分析仪测量物理 TCK，20/30 MHz 未作本轮实体资格验证。

## 实现与测试

- 新 HPM 参考页纠正工具名称、CPU/外设寄存器区别、冷启动/缓存 ID、符号上下文、
  ROM 复位行为和各项验证边界；工具索引改为当前共享 MCP schema。
- 新 `hpm_debug` 经共享后台独占准入，先协商版本/能力，严格解析带标记回执。
  支持 RV32 hart 0 状态、暂停/继续/单步、GPR/只读 CSR、显式槽位硬件执行断点。
  不抢停其他采集、不调用 ARM 回退、不复位恢复、不重放未知修改；保留 issued、
  cleanup 和 outcome_unknown。寄存器/单步/触发器访问必须已暂停。
- SystemView 按 SEGGER 的 U32 减法规则还原 ID，处理 RAMBase 大于局部 RAM 地址
  的回绕；覆盖带/不带长度、分片输入、shift 0/2。目标示例仍有其他板型的静态文本，
  不把文本当成精确芯片识别；未修改用户工程。
- 1,139 项相关 Python 回归通过，包含 HPM、时钟、共享调试/MCP、烧录、脱机、
  SystemView 和 Skill 边界。另有实际 FastMCP → HTTP → 共享后台 → 探针的正向
  采集/读取及旧固件拒绝验证；模拟测试不代替新固件 CPU 调试实体资格。

## 仍需跟进

固件修复由用户指定会话负责，内容含冷启动 SBA 初始化和新增 HPM_DEBUG v1。
其最终契约已更新为实现及 HPMLINK 构建完成，生产引擎故障注入、实际 Pika VM/绑定
及相关回归通过，新包尚未刷入。本会话按该契约对接，尚未获得新固件
halt/step/断点/核心寄存器的实体成功证据。
同为 V4.7.2 的旧镜像不能仅凭版本号当作支持新接口。

新调试接口需要配套共享后台与固件。正式 Skill、正式安装包未更新；本地测试 Skill
不得当成正式 0.4.1 资产。后续正式发布仍需明确指令。

本地完整测试 Skill 包 `Mklink-AI-Probe-v0.4.1-HPM-test-05e73101.zip`：98,214,003 字节，
SHA-256 `44df3e58dd6cbcf7a7436f96817d6422ec661eeb086ab0977dc53a60937afb0b`。
2,625 个公共运行时文件、7,059 FLM 型号/2,224 blobs、4,800 SVD 型号资格校验通过，
无维护文档/测试泄漏。已备份并更新本机全局 Skill，2,625 个安装文件逐字节一致，
5,339 个工程配置/缓存文件保持不变；新安装路径的实际 FastMCP 列出 47 工具，包含
hpm_debug，ping 仍为 0.4.1。安装标记注明 local_test_only；需重启 AI/MCP 会话加载。

首次 runtime_status 受 97 个历史失效 endpoint 串行探测影响而超时；显式选择当前探针
后连接及后续操作正常。本轮保留原记录，未通过清空状态掩盖问题，此性能问题待跟进。

完整原始输出保留在本机 F 盘 `hpm-skill-audit-20261029` 证据目录，不将设备身份、
会话凭据、用户工程路径、固件或 Pack 二进制提交仓库。
