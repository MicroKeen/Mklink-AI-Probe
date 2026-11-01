# 固件命令审计的宿主修复

承接 [74 条固件命令审计](firmware-skill-command-audit-20261101.md)，在
`codex/v0.4.2-fixes` 实施；版本仍为 0.4.2，没有发布正式资产或升级探针固件。

## 修复对应表

| 审计缺口 | 处理结果 |
|---|---|
| 时钟文档只写四档，首次 SDK 校验发生在能力读取前 | Skill/MCP/CLI 指引统一按接口能力；CLI 支持 clock-hz；Device.flash、burn_hex_file 首次先协商。现代 SWD/JTAG 14 档、旧固件四档，10 MHz 默认，不把配置应答当物理测量 |
| 脱机低频和 HPM 新档位被拦截 | 预览允许完整目录；部署对新增档位核验绑定探针的能力；脚本检查 set_swd_clock 返回值后才访问目标。HPM 下拉去除 8 MHz，保留 4 MHz 兼容项 |
| 默认 MCP 供电、重启入口缺失 | 新增 set_power_on/off、reboot_probe；逐次确认、严格电压范围、5V 二次确认；捕获忙/共享客户端限制保留 |
| 脱机与 UART ISP MCP 工作流缺失 | offline_download status/preview/deploy/trigger 复用 GUI 管道；部署保留输入冻结/哈希/任务记录；触发单独记录任务，查询终态，unknown 不得标成功、不自动重发 |
| HPM OTP 入口缺失 | hpm_otp 连接既有 JTAG/ISP read/plan/program/lock/batch 受限路由；JTAG 原值核对、ISP 单次计划与绑定保留，不扩大字段白名单 |
| 实时连接、探针诊断、ISP 链路诊断缺失 | probe_presence 区分实时与缓存、负数保留未知；probe_diagnostics 有界读取探针堆/栈/复位报告；isp_link_probe 占用共享 UART 资源，限时查询，不声称烧录成功 |
| 探针扫描/蜂鸣/Vref 配置缺失 | probe_control 提供白名单控制和明确应答；允许关闭 Vref 跟随，开启暂拒绝并说明缺少电压确认契约 |
| 幽灵 capture_rtt、Flash 读取需 FLM、失效 save 示例 | 移除/修正，专用流程文档集中说明实际 MCP schema 和边界 |
| 本地 Skill 长期落后 | 本轮生成完整包并覆盖，最终安装清单与哈希另记于本机 installation.json |

共享后台协议升为 53，拒绝与协议 52 的旧桌面后台混用。仅覆盖 Skill 不替换旧 Windows
安装器；需要重启 MCP 使用新 Skill 后台，桌面新入口需下一次重新构建安装。
本轮没有任意 Pika 代码透传，也没有新增独立串口绕过共享锁的实现。

## 验证

- 749 项 Python 回归通过：真实 FastMCP→ASGI 调用、资源准入、离线部署/任务去重、
  unknown 保留、首次调频、全部时钟档位、HPM/ISP/OTP 脚本与 Skill 边界。
- 65 项离线 GUI 测试通过，vue-tsc 与 Vite 生产构建通过。产物在外部构建目录，
  源码受管 gui/dist 与已装 Windows 载荷保持不变。
- 真实 IAB 浏览器加载生产 Web 产物，在只读后端夹具中选择 HPM5301，确认 JTAG
  下拉含 14 档与 4 MHz 兼容档、不含 8 MHz，5 kHz 可选择。测试页和服务器已关闭。
- 证据目录：`firmware-skill-fixes-20261101`，含回归 XML、Web、打包/安装校验结果。
  wrapper 遇测试链接按规则保留目录，没有强制删除。
- 本轮无 USB/目标/VCC/OTP 实际操作；这些是软件回归和界面验证，不替代新入口的硬件验收。

## 固件边界

YMODEM receive 空实现假成功，以及 Vref 自动跟随缺少电压确认契约，已交用户指定
会话 `01a186cd-c52a-7ea0-af29-8de6775d143b` 处理；该会话仍在进行独立 V2 实测，
没有收到本轮固件修复与回验完成通知。宿主明确拒绝未支持路径，不宣布双向 YMODEM
或安全自动跟随已经可用。HPM_DEBUG 的 FPU/多 hart/watchpoint/CSR 写入不属于既有
公共契约，维持原边界；RISC-V 自动异常解码尚无独立工具，不误报 ARM HardFault 结果。
