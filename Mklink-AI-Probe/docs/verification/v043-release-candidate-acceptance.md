# MKLink 0.4.3 Windows 发布候选验收

产品提交为 `6ec4e55301c9078c7101baf9ff1fc8722e42633a`，分支为 `codex/v0.4.3-fixes`。截至 2026-11-07，本轮验证了普通 V4 与 STM32F103 的桌面和 Skill 操作。PR #71 在该提交上的三项 CI 均通过，仍为草稿。原始文件保存在构建根的 `artifacts/v043-formal-rc-6ec4e553-20261107`。

## 实机操作

| 入口 | 操作及观测 |
|---|---|
| Windows 桌面 GUI | 启动本轮 NSIS 解出的 Tauri 程序，通过配置页选择普通 V4 并连接，在仪表盘 Memory 页填写地址和长度。逐字节核对页面显示和读取回执。页面断开成功，原生进程正常退出，子进程中没有外部 Python。 |
| 完整 Skill 启动 GUI | 从归档内的 `.mcp.json` 启动真实 stdio MCP。在无窗口、无探针会话时调用默认 `gui_open`，可见 Edge 收到启动请求并注册，状态从 `awaiting_window` 变为 `ready`。AI 显示 SuperWatch，重复打开复用同一窗口。验收进程将浏览器处理程序指向独立 Edge 配置。 |
| AI 与 GUI 共用实机 | 另一轮由 AI 使用一次性本机链接打开可见窗口，随后显式选择同一普通 V4。后台从 lobby 绑定到所选探针，实例和窗口身份保持一致。AI 调用 `gui_present` 切换 RTT、SuperWatch 和 Memory，每次均收到 `displayed` 且实际页面路由匹配。MCP 与页面先后读取下表所有地址，并与桌面结果比对。MCP 正常退出，物理连接已释放。 |

| 地址 | 长度 | 两条实机路径的结果 |
|---|---:|---|
| `0xE000ED00` | 4 B | Cortex‑M3 CPUID `0x411FC231` |
| `0xE0042000` | 4 B | 芯片标识寄存器 `0x10036414`，DEV_ID `0x414` |
| `0x1FFFF7E0` | 2 B | Flash 容量 512 KiB |
| `0x08000000` | 64 B | GUI、MCP、桌面三个读数一致 |
| `0x08005000` | 64 B | 三个读数一致，也与两份验收 HEX 的公共向量片段一致；识别整份镜像使用升级后的独立回读 |

**普通 V4.7.2 的睡眠访问限制。** 首次默认读 CPUID 时两条路径均收到 MUX 状态 5。单独查询 SWD 在位得到 DP IDCODE `0x1BA01477`。显式启用睡眠访问后，五处读取均成功，结束时关闭该模式。Skill 路径记录到旧固件切换至 100 kHz，关闭后恢复 10 MHz。此轮未修改 STM32F103 程序、供电或选项字节。这里对 RTT 和 SuperWatch 的检查涵盖窗口呈现，F103 新版高速采集与 H7 性能需按各自负载验证。

证据为 `native-hil.json`、`native-memory.png`、`ai-gui-hil.json`、`ai-memory.png`、`auto-gui-open.json` 和 `skill-auto-superwatch.png`。桌面脚本最初等待了错误的连接 API；实际 GUI 在共享模式走 `/api/runtime/select`。修正测试观察点后取得上述回执。

## 构建与回归

| 项目 | 本轮结果 |
|---|---|
| Windows NSIS 候选 | 186,131,258 B，SHA-256 `e8746f92cc5b67f43a62d7c440628c5795f2740bbe625b056982b9035835f9de` |
| 完整 Skill 候选 | 99,743,920 B，SHA-256 `ebc7c7015ed86e881fd349fba5164f2588e2e89c17492ad8e0c0497eaaa235a3`，2656 个归档文件逐一比对 |
| Windows Site Agent 便携候选 | 67,344,348 B，SHA-256 `b254d706197581500b8bf16a88849c6817837388d8f94c0e006d2305b41ec19e`，独立核心、GUI、ZIP 与外置 manifest 已构建。此项只记录打包结果。 |
| 生产 Web | 42 个文件在 Git、NSIS 载荷、完整 Skill 中逐文件 SHA-256 相同 |
| Python、GUI、桌面 Rust | Python 6757 通过、2 跳过、60 条警告；GUI 104 个文件、1202 项通过；桌面 Rust 23 项通过 |

## 固件升级对照

用于实机升级的专用桌面副本保留候选程序，仅替换两条 V4 内置固件目录记录。记录绑定普通与专用 family、各自构建时间、文件长度及 SHA-256，来源指向进程隔离的本机 HTTPS 测试通道。两款下载均经打包后端正式下载 API 返回 HTTP 200，逐文件核对各 1,639,936 B、3203 块及每块 UF2 family。原 NSIS、Skill 和公网目录保持原样。直接提供平铺 UF2 目录无法让原候选识别尚未发布的构建日期，不能用它确认升级成功。

普通 V4 从 V4.7.2 升级至 MicroLink V4.7.3。真实桌面 GUI 只提交一次升级，进入 CHERRYUF2，回枚举到原设备，结果为 `updated`，读回构建时间 `2026-11-07T15:00:14`，普通 family 正确。升级后在 STM32F103 以 10 MHz 显式启用睡眠访问，CPUID、芯片标识及容量一致，6/6 次 16 B SRAM 哨兵正确，1024 B 的 100 ms WFI 镜像逐字节一致。详见构建根 `artifacts/ordinary-v4-hpmlink473-20261107/ordinary-gui/result.json` 和 `ordinary-f103-after.json`，候选通道下载凭据汇总为 `download-check.json`。

专用 HPMLink 也从正式 V4.7.2 升级到 HPMLink V4.7.3。GUI 一次确认，返回 `updated`，回枚举后的构建时间为 `2026-11-07T13:43:21`，UF2 family 为 `0x0B4D5048`。在 HPM5301 上，专用版 RTT 实收 183 B，SuperWatch 周期从 353 增至 1759，读取错误为 0。普通 V4.7.3 在 HPM5301 上通过 JTAG 硬件断点、ROM 烧录及 64 KiB 窗口回读，RTT 收发分别为 96,256 B、286 B，四路 SuperWatch 共采到 3347 个样本。对应记录为 `hpmlink-gui/result.json`、`hp-jtag-after.json` 和 HPM5301 工程验收目录中的 `microlink-v473-hpm-release-20261107/hpm-acceptance.json`。

## 普通 V4.7.3 构建 15:00:14 再接 STM32F103

| 验收项 | 实机结果 |
|---|---|
| 桌面 GUI | 显式开启睡眠访问，Memory 五处回读与 4.7.2 相同。两次读取间唤醒计数 779 → 789，`DBGMCU_CR` 为 0。桌面正常断开并退出。 |
| Skill 自动打开 GUI | 默认 `gui_open` 从冷启动请求浏览器，窗口完成注册。AI 在该实例内连接普通 V4、加载对应 AXF、呈现 Memory；10 MHz 原子睡眠访问下页面与 MCP 五处地址逐字节一致，另对照 Intel HEX 验证完整 1024 B 镜像。 |
| 原子模式的连续采集保护 | 请求 RTT 或 SuperWatch 都立即返回 HTTP 409。两项采集结束后可重新连接，CPUID 与已知 16 B SRAM 哨兵均正确，已关闭睡眠访问并释放设备。 |
| 普通模式，100 ms WFI | RTT 与 SuperWatch 先并行试用，再分别独立启动。RTT 两轮均收到 MUX 状态 5，接收 0 B。SuperWatch 周期设为 10 ms，两轮均为 0 个有效样本，分别累计 237、301 次读错，连续失败 3 秒后自动停止。 |
| 目标侧对照 | 单次原子读取确认 RTT 环形缓冲区有 255 B，内容恰为 51 条 `F103\n`。因此 0 B 不能归因为目标没有输出，也在单项启动时复现。 |

固件会话核对，V4.7.3 的 MUX `0x17` 支持限长的原子读、写后校验和探测；RTT 与 SuperWatch 的连续采集使用普通目标访问。此条件下可确认快照正确，**100 ms WFI 下连续 RTT 与 SuperWatch 验收失败**。本次未修改目标程序或厂商睡眠寄存器。早期在其他固件和模式取得的持续 RTT 数据有独立的适用条件。[睡眠访问的实现与历史实测](v043-cortex-m-sleep.md)

原始记录为 `native-v473.json`、`ai-v473.json`、`ai-v473-separate.json` 和 `final-recovery.json`。相应桌面和 AI 窗口截图为 `native-v473-memory.png`、`ai-v473-memory.png`、`solo-v473-rtt.png` 和 `solo-v473-superwatch.png`。

## 发布前的剩余范围

- 本轮桌面实测使用解包后的候选。精确版本的 Windows 覆盖安装、全局 Skill 更新及用户数据保留仍须在最终发版流程核验。
- 官方固件索引与候选通道独立。正式渠道一致性须在发布决策时复核。签名、标签、发布和公网索引更新尚未执行。
- 固件组正在为 V3.6.9 和两款 V4.7.3 更新设备盘 README 及帮助链接。本文的实测绑定上文两款 V4 的 SHA 和构建时间，新生成的包须另核身份、升级回执和目标回读。[固件候选 PR #22](https://github.com/Aladdin-Wang/MicroLink_Plus/pull/22)
- F103 每 100 ms 唤醒一次时，两项连续采集都未取得有效数据。涉及这个场景的功能说明和发布决定须保留上述限制。
- 既有普通 V4/H7 性能参照为 4 B SuperWatch 约 26.53 万次/秒、独立 RTT 中位 849.64 KiB/s、4096 B 连续读取约 1053–1056 KiB/s。本轮 F103 读数未重测这三项吞吐。普通请求 P95 稳定低于 1 ms 和视情况将采样最大间隔降至 20 µs 内仍是开放目标。[性能基线](v043-host-baseline.md) [V4 独立与并行对照](v043-v4-iar-exit-context.md) [4096 B 连续采集](v043-bulk-capture.md)
