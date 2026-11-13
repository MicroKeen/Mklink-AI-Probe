# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-11-13T14:13:43+08:00`
- 分支：`codex/v0.5.0-fixes`
- HEAD：`ad00c962`
- 远端 HEAD：`ad00c962`
- 工作树：ad00c962 Windows 本地候选已覆盖安装，包含 ELF 与完整波特率修改；安装报告、记忆和交接另行提交。当前任务分支已推送，无合并或发布。
- 当前任务：按用户要求将 ELF 可写段与 UART/RS485 34 档修复打成 ad00c962 普通用户 NSIS 并覆盖安装。3676 文件、6 份配置、冻结 CLI/MCP、生产 Web 两页 10M 及 ELF 成员选中/重解析通过，配套 Skill 资源一致。见[安装验收与哈希](../verification/v050-elf-baud-overwrite.md)。继续 codex/v0.5.0-fixes / [PR #79](https://github.com/MicroKeen/Mklink-AI-Probe/pull/79)。
- 状态：`ELF / 波特率 Windows 包覆盖验收完成，PR #79 待审阅`

## 里程碑

- **0.5.0 上位机开发基线** — `已合入 main`。2026-11-09，[PR #78](https://github.com/MicroKeen/Mklink-AI-Probe/pull/78) 以 `2861d7a6` 合入，新增 CLI 显式重载 AXF/ELF 符号，[Issue #77](https://github.com/MicroKeen/Mklink-AI-Probe/issues/77) 已关闭（Completed）。随后 [PR #76](https://github.com/MicroKeen/Mklink-AI-Probe/pull/76) 以 `cf034fe1` 合入，修复 Windows 普通用户因 jobs.json 访问受限而无法连接探针的问题，[Issue #75](https://github.com/MicroKeen/Mklink-AI-Probe/issues/75) 已关闭（Completed）。
- **MKLink 0.4.3** — `正式`。`v0.4.3` 指向 `3905a68b`。Windows 上位机、完整 Skill、Site Agent、MicroLink V3.6.9、MicroLink V4.7.3 和 HPMLink V4.7.3 已发布。MicroLink V2 沿用 V2.9.3。

## 验证证据

- **ELF 可写加载段与结构体成员**：真实 ELF 复现 AX .data 被旧节权限范围遗漏；STO_PLL_M1 本身仍为 STT_OBJECT。默认解析器修复后 API 返回 1184 个变量，成员 hAvrMecSpeedUnit 为 int16_t / 2 字节 / 0x200004C4，Runtime 和生产浏览器均能加入；配置落在测试副本旁。ELF/DWARF/目录/共享 watch/RTT 等 400 项通过；原 ELF 哈希不变，未连接或操作客户板。清理 445 个测试链接、3 个临时目录，零失败。见[报告](../verification/v050-elf-load-segments.md)。 ad00c962 冻结 CLI、API 和安装版生产 Web 再次通过，重解析保留已选成员；见[覆盖验收](../verification/v050-elf-baud-overwrite.md)。
- **UART / RS485 完整波特率档位**：后端关联 870 项、GUI 定向 25 项、Skill 边界 69 项及生产构建通过。两只 V4 的 UART、RS485 共四个接口均实际返回 34 档，最高 10M；生产浏览器验证 UART / RS485 独立查询、两页选择 10M、第三方预设和中英文提示。该轮未发送串口数据；固件会话双 V4 互测属于独立证据。见[报告](../verification/v050-uart-baud.md)。 后续 ad00c962 覆盖安装后，两接口 34 档查询、两页选择 10M 再次通过，仍未发送载荷；见[覆盖验收](../verification/v050-elf-baud-overwrite.md)。
- **SystemView 重启与时序图缩放**：关联后端 651 项、最终状态/编码 30 项（重叠）通过，GUI 全量 1226 项及生产构建通过。V4.7.4 / STM32F103RC 源代码 5 轮 RTT 共存和安装版 3 轮启停均恢复 9 个任务名，Flash 117760 字节匹配 AXF。真实浏览器验证 CH2 重启及重载保留、约 19 µs 视窗缩放、暂停平移；安装版亦通过。目标/MUX 丢弃计数为零，但解析器仍有对齐丢字节及偶发异常区间，不宣称无损。见[完整报告](../verification/v050-systemview-restart-zoom.md)。
- **固件能力提醒与采集中写入**：同一 V4 / STM32F103RC：V4.7.3、V4.7.4 修改前/后最大采样间隔分别 0.195/0.208/0.192 ms；RTT 并行为 1.562 ms，各轮 10 次写入均成功且原始值对应，无序号断裂或读错。真实 Web 写 123 后保持约 15.9 kHz，结束恢复原值 0，后台已释放。后端广泛关联 1711 项通过，修正新增入口断言后相关 271 项通过，Skill 边界 69 项、GUI 全量 1222 项及生产构建通过；数量有重叠。真实 HTTP/RuntimeClient/FastMCP 警告一致，状态检查无设备 I/O；中英文横幅及跳转通过浏览器验收。见[完整结果与限制](../verification/v050-firmware-capabilities.md)。
- **macOS 兼容性与跨平台回归**：Windows Python 全量 6929 通过、2 个 hil_core.observe 跳过；唯一剩余的 DLL 路径审计夹具修正后，独立包完整 6 项复测通过。GUI 全量 1219 项、最终相关 280 项及生产构建通过。两种 Mac 原生 USB 各 73 项通过、1 项 Windows 专属跳过；最终 DMG 的签名、冻结 CLI/MCP、内置算法、Web 健康与正常退出通过，ARM/Intel 启动约 5.593/11.6 秒。DMG 和配套 Skill 已下载/生成并校验，见[报告及哈希](../verification/v050-macos-compatibility.md)。浏览器验证中英文更新提示与重试；Mac 原生 GUI、Gatekeeper 和实物 USB 未验。
- **SuperWatch 配置与手动日志转换**：手动转换 56 项、共享后台/流/边界 296 项、GUI 152 项通过，生产构建通过。冻结安装版实物记录 1,114,032 组，Excel 两页 1,048,575 / 65,457 行、4,456,128 个值与 JSONL 对应；RTT 505 行 TXT 对应，7 个原始文件哈希不变。GUI 手动触发、实际 CLI/MCP 重复请求复用任务且不停止采集。见[转换报告](../verification/v050-manual-recording-export.md)。符号旁配置原有软件/浏览器证据见[配置报告](../verification/v050-superwatch-profile.md)；前一安装候选已验证真实 AXF 重启恢复，本候选解析 6,718 个变量并保存四变量、500000 缓存与 1 µs 间隔。
- **Windows 安装与工程初始化**：ad00c962 本地候选已覆盖 54e03336，NSIS/桌面均 RID 8192，安装退出 0，3676 文件匹配，6 份配置、USB 端口名和机器级登记不变。仅 Windows PATH 下冻结 CLI、58 个 MCP 工具、FLM/Pack、原生健康与正常退出通过；生产 Web 的 ELF 成员与 34 档波特率通过，配套 Skill 的 2342 个资源文件一致。哈希见[本轮安装验收](../verification/v050-elf-baud-overwrite.md)。既有 SystemView 安装实物证据见[报告](../verification/v050-systemview-restart-zoom.md)，旧安装边界见[用户安装](../verification/v050-user-installer.md)。通用工程 424 项与真实/冻结 CLI 初始化通过，见[工程报告](../verification/v050-project-init.md)。正式包与历史清理见[发布报告](../verification/v043-release-handoff.md)和[清理记录](../verification/v043-postrelease-cleanup-20261108.md)；2026-11-12 C/E 清理回执保留。
- **V3 / V4 SuperWatch 恢复**：普通 V4 修复候选实物拔插跨 12.637 秒缺口原订阅恢复，V4.7.4 健康检查通过，223,728 组、零读错及队列丢弃，中位 43,486.6 组/秒。V3.6.10 实刷及拔插恢复通过，1,484,544 组，零队列丢弃、序号异常和时间倒退，恢复后中位 43,056.7 组/秒。旧 V3.6.8 缺采样能力，无同条件旧版基线。版本及未验范围见[恢复验证记录](../verification/v050-superwatch-swclk.md)。

## 架构决策

- 采集或调试改动须按[上位机基线](../verification/v043-host-baseline.md)同条件复测 SuperWatch、RTT 和调试共存，核对数据完整性。 SystemView 每次附着刷新 INIT/任务列表，通道以显式选择及后台状态为准；暂停显示仍可缩放，视窗查询合并且不暂停采集。
- 默认仅构建 Windows。用 PowerShell 7、UTF-8 和 `scripts/build_workspace.ps1`，构建根为 `F:/MKLink-Build`。
- Windows NSIS 默认 currentUser；安装不自动命名 USB 端口。只有用户确认修改或恢复端口显示名称时，才调用独立 UAC 助手。旧机器级登记与受保护目录不自动迁移。
- 上海轻量服务器直供最新版，历史文件由 COS 和 Git 保存。COS 累计 189 GiB 告警、207.9 GiB 停止，已取消日期截止。账本和停止锁按[下载策略](tencent-updates.md)维护。
- 跨会话固件联测固定上位机提交并核对 mklink/runtime 模块导入路径；主工作区和全局 editable 入口不自动代表当前任务版本。
- project-init 是可选离线配置工具；通用工程可显式传型号和文件，直接烧录不依赖初始化。型号或镜像不明确时要求补充输入，不猜测，也不自动迁移已有芯片配置。 ELF 可写范围合并 SHF_WRITE/ALLOC 节及 PF_W 的 PT_LOAD 段，使用 p_vaddr/p_memsz；不凭 AX 或 RAM 地址放宽，不把 Flash 装载镜像当 RAM。已知只读映射不走通用回退。
- RTT / SuperWatch 实时记录 JSONL；停止记录不自动转换。用户手动将 SuperWatch 转为 Excel、RTT 转为带主机时间戳的 UTF-8 TXT，三端共用低优先级后台转换；Excel 保留采样相对时间，开始日期写在 Info 页。JSONL 保留作无损回放源。
- SuperWatch 配置由共享后台保存在 AXF/ELF 旁，名称为原文件名加 .superwatch.json；三端共用名称与修订协议，不存变量地址、不自动开始采集。显示修改防抖，样本接收不写配置；浏览器上传只能保存到后台副本旁。
- macOS 候选仅 ad-hoc 签名且不启用 Hardened Runtime；正式 Developer ID 构建必须在 PyInstaller 冻结阶段正确签内嵌库。候选不发布到正式更新索引。慢 USB 枚举移出事件循环，心跳有界等待；实际操作仍检查身份、代际和占用，不重放未知结果。
- 缺固件能力按已有文本/HELLO 缓存判断，版本号不替代协商；Web/CLI/SDK/MCP 共用 firmware_compatibility 和 firmware_warning。未知型号或未协商状态不猜测；status 5/6、超时、目标及硬件限制不误报升级可解决。SuperWatch 运行或暂停时缺 MUX 写能力则提示升级并保留采集，不自动停流写入；地址限制提示显式停止。未知写结果不重放，不自动升级固件。 串口助手与 Modbus 共用完整 34 档预设（300～10M）；已识别 UART / RS485 分别按自身固件声明限制选择。列表刷新只用缓存，显式查询走物理探针共享所有者且不停止采集；缺声明提示升级，第三方预设不保证支持。已有连接的自定义速率只读保留。

## 真机环境

- **操作前**：重新核对下载器型号、目标和占用。固件变更由指定会话协调，升降级按本次授权执行。VCC、OTP 操作分别确认。
- **普通 V4**：固件会话于 2026-11-13 将两只普通 V4 更新为 V4.7.4 RS485 修正版并完成 34 档双向测试；本轮上位机独立读取四个 UART/RS485 接口均返回完整 34 档，未再次刷写、复位或改电源。生产浏览器未连接目标或发送数据，测试后台已全部退出。先前 STM32F103RC / SystemView 证据见对应报告；后续操作重新核对版本、接线和占用。 ad00c962 安装验收时枚举一只下载器，UART/RS485 分别返回 34 档；未连接目标或发送串口数据，正常退出后无占用。
- **普通 V3**：固件会话已回读 V3.6.10 / 2026-11-10T14:14:14，原 STM32F103 的一次 SWCLK 拔插恢复通过；测试结束时后台退出、设备释放。下次仍需重新核对占用。

## 下一动作

1. 取得客户目标芯片、RTOS 和原始 SystemView 流后，确认其丢名是否命中元数据/通道修复，并单独排查解析对齐及异常运行片段；不把现有板测试扩大为所有平台保证。
2. 在用户 Mac 上验收对应 ARM/Intel 候选的首次启动、覆盖安装、探针接口/卷身份和真实查询耗时，再核对共享会话及 MCP 重载。当前软件与包内自检不替代真实环境门禁。
3. 固件会话继续维护 STOP 状态码补丁；客户信息齐备并获得明确实物安排后再做同条件 STOP/唤醒验证，不自动抢占调试器或刷写设备。
4. 审阅 PR #79 的 ELF 可写段、完整波特率、SystemView、能力提示及既有修复。Windows ad00c962 已覆盖安装并包含最新 ELF/波特率修改；Mac 候选仍不含最新几轮修复。继续 codex/v0.5.0-fixes；合并、签名和正式发布须明确指令。

## 已知限制

- 普通读取 P95 和间隔读取稳定低于 1 ms、最大采样间隔 20 µs、40 µs 翻转零漏采仍是未达目标。
- 公网远程中继继续延期。独立 [S3 PR #65](https://github.com/MicroKeen/Mklink-AI-Probe/pull/65) 仍开放。其他硬件的[历史未验范围](known-limits-20261030.md)按需查阅。
- 转换入口针对后台最近一次记录，应在开启下一次记录前触发；没有历史文件选择器或全局转换并发上限。Excel 约 15 位有效数字，原始 JSONL 不变。转换仍消耗 CPU/磁盘，本轮未做完整真机性能 A/B；冻结 Excel 父进程退出后仍运行的时间窗口未直接观测，详见报告。
- Mac ARM/Intel DMG 是 0.4.3 标记的未公证候选，未做 Finder 覆盖安装、Gatekeeper、原生窗口及 macOS 27 真机 USB 验收。Mac 修复轮未覆盖安装 Windows，也未做新的硬件吞吐/P95/调试共存 A/B；客户 ioreg 3.7→0.15 秒未独立复现。
- 客户旧上位机/固件组合导致的长停流未复现；本轮 V4 写入短测不证明所有负载零退化。未重测 HPM/V2/V3 实物能力矩阵、RTT 原始字节全量比对或独立吞吐 A/B，也未完成 CMSIS-DAP 共存及全部性能门禁。54e03336 Windows 安装包已包含能力修复。
- STOP 案例中，V4 源码确认 0x17 重连失败会误报 6；固件会话提供修正为 5 的独立补丁和离线证据，尚未应用或刷写。客户固件版本、完整芯片型号与电气条件未齐备；持续 STOP 的调试访问不保证可唤醒，status 5 可能包含恢复未确认。
- 客户 SystemView 完全丢名未在 STM32F103RC 基线复现，客户芯片/RTOS 尚未确认，HPM/FreeRTOS 实物未验。短测解析器仍有对齐丢字节，长 GUI 采集偶见不合理 ISR/运行片段；需要原始流另查，当前修复不证明所有时序统计正确。
- ELF 与波特率修复已在 ad00c962 Windows 普通用户包覆盖验收；macOS 候选尚不含这两项。ELF 仅完成离线解析和变量配置验证，未做客户板采集或写入。本轮未做高速物理收发、持续吞吐或 SWD/RTT 共存性能 A/B；固件会话双 V4 测试不等同于客户 1.5 µs 快速应答验证，第三方驱动可拒绝预设高档位。

## 延续协议

- 后续合并、签名或正式发布须有新的明确指令。
