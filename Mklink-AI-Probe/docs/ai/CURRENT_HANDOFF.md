# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-11-14T09:44:40+08:00`
- 分支：`codex/v0.5.0-fixes`
- HEAD：`db81241d`
- 远端 HEAD：`db81241d`
- 工作树：db81241d 已推送；本次单独提交项目记忆与验收报告。已覆盖安装，未合并或发布。
- 当前任务：新版安装器空闲时备份并初始化格式损坏的 jobs.json，保留有效未知记录和用户配置；实际 NSIS 夹具通过，本机 17 份正常历史不变。已包含 HPM Flash、接口/OTP 和 USB 0.5 秒恢复；两 V4 独立连接/切换通过，同轮实物断线窗口 500 ms。最终冻结 HPM5301 在线/脱机及 52988 字节独立回读一致。设备和窗口已释放，347 链接及测试 U 盘文件已归档清理。安装包/Skill 哈希见[覆盖报告](../verification/v050-usb-hpm-overwrite.md)。未发布。
- 状态：`V0.5.0 / db81241d 普通用户覆盖及任务历史维护、USB/HPM 安装验收完成`

## 里程碑

- **0.5.0 上位机开发基线** — `已合入 main`。2026-11-09，[PR #78](https://github.com/MicroKeen/Mklink-AI-Probe/pull/78) 以 `2861d7a6` 合入，新增 CLI 显式重载 AXF/ELF 符号，[Issue #77](https://github.com/MicroKeen/Mklink-AI-Probe/issues/77) 已关闭（Completed）。随后 [PR #76](https://github.com/MicroKeen/Mklink-AI-Probe/pull/76) 以 `cf034fe1` 合入，修复 Windows 普通用户因 jobs.json 访问受限而无法连接探针的问题，[Issue #75](https://github.com/MicroKeen/Mklink-AI-Probe/issues/75) 已关闭（Completed）。
- **MKLink 0.4.3** — `正式`。`v0.4.3` 指向 `3905a68b`。Windows 上位机、完整 Skill、Site Agent、MicroLink V3.6.9、MicroLink V4.7.3 和 HPMLink V4.7.3 已发布。MicroLink V2 沿用 V2.9.3。

## 验证证据

- **HPM Flash 配置、连接设置与脱机 OTP**：HPM 四字配置与接口/OTP 源码验证见[Flash 配置](../verification/v050-hpm-flash-config.md)及[前轮](../verification/v050-hpm-interface-otp.md)。现已包含在 db81241d 安装包；真实生产浏览器指定串口可选接口/时钟、配置导入/跨页复用、OTP 读取与4/8列/写确认保护通过。HPMLink V4.7.4 / HPM5301 在线校验、脱机和 52988 字节完整回读一致，见[最终覆盖](../verification/v050-usb-hpm-overwrite.md)。未做 OTP 永久编程或其他 NOR 验收。
- **ELF 解析与完整 UART 波特率**：ELF 可写范围合并 PT_LOAD，客户 ELF 的结构体成员恢复，400 项解析/共享关联及真实浏览器通过，未操作客户板，见[ELF 报告](../verification/v050-elf-load-segments.md)。串口助手/Modbus 按 UART、RS485 独立声明使用 34 档至 10M，870 后端/25 GUI/69 Skill 及双 V4 实读通过，未发高速载荷，见[波特率报告](../verification/v050-uart-baud.md)。两项已随 ad00c962 普通用户覆盖并复验，见[覆盖报告](../verification/v050-elf-baud-overwrite.md)。
- **SystemView 重启与时序图缩放**：关联后端 651 项、最终状态/编码 30 项（重叠）通过，GUI 全量 1226 项及生产构建通过。V4.7.4 / STM32F103RC 源代码 5 轮 RTT 共存和安装版 3 轮启停均恢复 9 个任务名，Flash 117760 字节匹配 AXF。真实浏览器验证 CH2 重启及重载保留、约 19 µs 视窗缩放、暂停平移；安装版亦通过。目标/MUX 丢弃计数为零，但解析器仍有对齐丢字节及偶发异常区间，不宣称无损。见[完整报告](../verification/v050-systemview-restart-zoom.md)。
- **固件能力提醒与采集中写入**：同一 V4 / STM32F103RC：V4.7.3、V4.7.4 修改前/后最大采样间隔分别 0.195/0.208/0.192 ms；RTT 并行为 1.562 ms，各轮 10 次写入均成功且原始值对应，无序号断裂或读错。真实 Web 写 123 后保持约 15.9 kHz，结束恢复原值 0，后台已释放。后端广泛关联 1711 项通过，修正新增入口断言后相关 271 项通过，Skill 边界 69 项、GUI 全量 1222 项及生产构建通过；数量有重叠。真实 HTTP/RuntimeClient/FastMCP 警告一致，状态检查无设备 I/O；中英文横幅及跳转通过浏览器验收。见[完整结果与限制](../verification/v050-firmware-capabilities.md)。 后台提醒追加：最终后端 396 项及桥接 10 项、GUI 1241 项、生产构建及真实浏览器通过。V2.9.4 与云端 V2.9.3 比较不误报降级；保留原文修复历史版本集合歧义。清理 547 链接/5 目录，零失败。见[提醒报告](../verification/v050-firmware-update-notice.md)。 更新顺序追加：共享关联 1570 项通过，文档预算/位置修正后最终相关 149 项通过；GUI 全量 1248 项及最终相关 93 项、生产构建、浏览器互斥/重启失败恢复通过，数量重叠。原生安装和刷写均隔离，见[报告](../verification/v050-update-order.md)。
- **macOS 兼容性与跨平台回归**：Windows Python 全量 6929 通过、2 个 hil_core.observe 跳过；唯一剩余的 DLL 路径审计夹具修正后，独立包完整 6 项复测通过。GUI 全量 1219 项、最终相关 280 项及生产构建通过。两种 Mac 原生 USB 各 73 项通过、1 项 Windows 专属跳过；最终 DMG 的签名、冻结 CLI/MCP、内置算法、Web 健康与正常退出通过，ARM/Intel 启动约 5.593/11.6 秒。DMG 和配套 Skill 已下载/生成并校验，见[报告及哈希](../verification/v050-macos-compatibility.md)。浏览器验证中英文更新提示与重试；Mac 原生 GUI、Gatekeeper 和实物 USB 未验。
- **SuperWatch 配置与手动日志转换**：手动转换 56 项、共享后台/流/边界 296 项、GUI 152 项通过，生产构建通过。冻结安装版实物记录 1,114,032 组，Excel 两页 1,048,575 / 65,457 行、4,456,128 个值与 JSONL 对应；RTT 505 行 TXT 对应，7 个原始文件哈希不变。GUI 手动触发、实际 CLI/MCP 重复请求复用任务且不停止采集。见[转换报告](../verification/v050-manual-recording-export.md)。符号旁配置原有软件/浏览器证据见[配置报告](../verification/v050-superwatch-profile.md)；前一安装候选已验证真实 AXF 重启恢复，本候选解析 6,718 个变量并保存四变量、500000 缓存与 1 µs 间隔。 TXT 精简追加：转换/记录器 37 项、Skill 69 项通过；既有 505 行时间和正文等价，63,996→40,304 字节，原始文件哈希不变。见[TXT 报告](../verification/v050-rtt-txt-readable.md)。
- **Windows 安装与工程初始化**：V0.5.0 / db81241d 普通用户覆盖：RID8192、3683载荷文件一致、6配置及USB/机器登记不变；新 NSIS 异常历史原样备份/初始化、有效未知历史保留和幂等验证通过，本机保留17份有效历史。后端252、GUI73及生产构建通过；冻结CLI/MCP58工具、STM32F407VE 11601目录项、2345配套Skill资源、原生启动退出通过。两 V4 独立后台/占用/切换/不回退通过；同轮079b5115实物断线窗口500ms。见[报告及哈希](../verification/v050-usb-hpm-overwrite.md)，先前连接修复及工程初始化证据按链接查阅。
- **V3 / V4 SuperWatch 恢复**：普通 V4 修复候选实物拔插跨 12.637 秒缺口原订阅恢复，V4.7.4 健康检查通过，223,728 组、零读错及队列丢弃，中位 43,486.6 组/秒。V3.6.10 实刷及拔插恢复通过，1,484,544 组，零队列丢弃、序号异常和时间倒退，恢复后中位 43,056.7 组/秒。旧 V3.6.8 缺采样能力，无同条件旧版基线。版本及未验范围见[恢复验证记录](../verification/v050-superwatch-swclk.md)。

## 架构决策

- 采集或调试改动须按[上位机基线](../verification/v043-host-baseline.md)同条件复测 SuperWatch、RTT 和调试共存，核对数据完整性。 SystemView 每次附着刷新 INIT/任务列表，通道以显式选择及后台状态为准；暂停显示仍可缩放，视窗查询合并且不暂停采集。
- 默认仅构建 Windows。用 PowerShell 7、UTF-8 和 `scripts/build_workspace.ps1`，构建根为 `F:/MKLink-Build`。
- Windows NSIS 默认 currentUser；安装不自动命名 USB 端口。只有用户确认修改或恢复端口显示名称时，才调用独立 UAC 助手。旧机器级登记与受保护目录不自动迁移。 新版安装空闲时只将格式损坏任务历史原样备份并核验后初始化；有效未知结果不清空，权限/占用/链接异常跳过，不重放旧操作。
- 后续发布只到腾讯云和 MicroKeen/Mklink-AI-Probe GitHub，Gitee 与旧 GitHub 保留历史，不上传新附件/标签/索引。AI / Skill / 固件按腾讯云、GitHub 顺序回退，不并发查询；备用 Skill 文件须匹配所选版本、大小、SHA-256。上海服务器直供最新版，COS/Git 存历史；COS 189 GiB 告警、207.9 GiB 停止，无日期截止。见[下载策略](tencent-updates.md)。
- 跨会话固件联测固定上位机提交并核对 mklink/runtime 模块导入路径；主工作区和全局 editable 入口不自动代表当前任务版本。
- project-init 是可选离线配置工具；通用工程可显式传型号和文件，直接烧录不依赖初始化。型号或镜像不明确时要求补充输入，不猜测，也不自动迁移已有芯片配置。 ELF 可写范围合并 SHF_WRITE/ALLOC 节及 PF_W 的 PT_LOAD 段，使用 p_vaddr/p_memsz；不凭 AX 或 RAM 地址放宽，不把 Flash 装载镜像当 RAM。已知只读映射不走通用回退。 HPM 四字 Flash 配置按实际 NOR 设置，GUI 可编辑/按器件保存/JSON 导入导出；无默认值时手填，不沿用旧型号。GUI/Python 共用参考表，显式 hpm_flash_cfg 优先于 board，已知默认值也走 flash_cfg；未知显式板名保留旧入口。XPI 控制器基址不等于 BIN 地址，USART ISP 配置独立。JTAG 脱机 OTP 只生成已确认的 hpm_user_otp 配方，读取绑定身份与代次；修改、断开或换设备后重新确认，系统字段只读。
- RTT / SuperWatch 实时记录 JSONL；停止记录不自动转换。用户手动将 SuperWatch 转为 Excel、RTT 转为带主机时间戳的 UTF-8 TXT，三端共用低优先级后台转换；Excel 保留采样相对时间，开始日期写在 Info 页。JSONL 保留作无损回放源。 RTT TXT 普通行仅含时间、CH 通道、RX/TX 和正文；session 在每个分段首次输出或切换时单列注释，JSONL 保留完整字段。
- SuperWatch 配置由共享后台保存在 AXF/ELF 旁，名称为原文件名加 .superwatch.json；三端共用名称与修订协议，不存变量地址、不自动开始采集。显示修改防抖，样本接收不写配置；浏览器上传只能保存到后台副本旁。
- macOS 候选仅 ad-hoc 签名且不启用 Hardened Runtime；正式 Developer ID 构建必须在 PyInstaller 冻结阶段正确签内嵌库。候选不发布到正式更新索引。慢 USB 枚举移出事件循环，心跳有界等待；实际操作仍检查身份、代际和占用，不重放未知结果。
- 缺固件能力按已有文本/HELLO 缓存判断，版本号不替代协商；Web/CLI/SDK/MCP 共用 firmware_compatibility 和 firmware_warning。未知型号或未协商状态不猜测；status 5/6、超时、目标及硬件限制不误报升级可解决。SuperWatch 运行或暂停时缺 MUX 写能力则提示升级并保留采集，不自动停流写入；地址限制提示显式停止。未知写结果不重放，不自动升级固件。 串口助手与 Modbus 共用完整 34 档预设（300～10M）；已识别 UART / RS485 分别按自身固件声明限制选择。列表刷新只用缓存，显式查询走物理探针共享所有者且不停止采集；缺声明提示升级，第三方预设不保证支持。已有连接的自定义速率只读保留。 固件云端提醒复用有序握手缓存，后台延迟 3 秒检查、成功缓存 6 小时/失败 15 分钟；无产品标识默认 MicroLink，显式 HPMLink 独立匹配。不能解析时直接提示升级但不猜版本/镜像。弹窗仅跳转，不停止采集或刷写，同窗口/设备/版本去重；能力协商保留。 更新顺序推荐客户端先行，重载 MCP/空闲旧后台后再重连检查固件；桌面安装需后台空闲预约，重启失败暂缓固件。Skill 首次异步检查并主动提醒，未连接固件待查，不自动安装。

## 真机环境

- **操作前**：重新核对下载器型号、目标和占用。固件变更由指定会话协调，升降级按本次授权执行。VCC、OTP 操作分别确认。
- **普通 V4**：本轮实读 V4.7.4，STM32F103。最终安装版双窗口独立连接、占用保护、单窗口切换通过；同轮 USB 物理500ms恢复验收见[报告](../verification/v050-usb-hpm-overwrite.md)。未在普通 V4 上刷写或采集，两设备均插回且测试连接正常释放，下次重新核对占用。
- **普通 V3**：固件会话已回读 V3.6.10 / 2026-11-10T14:14:14，原 STM32F103 的一次 SWCLK 拔插恢复通过；测试结束时后台退出、设备释放。下次仍需重新核对占用。
- **普通 V2**：2026-11-13 提醒验证时实际仅接入一只 V2.9.4，无产品标识。当前版本取首行而非历史版本，真实云端返回 V2.9.3，未提示降级；正常分离后后台退出释放设备。未刷写、改电源或目标程序，未启动采集；下次操作重新核对占用。
- **HPMLink V4**：本轮 V4.7.4 / HPM5301，最终 db81241d 安装版 JTAG10MHz，以四字flash_cfg完成hello_world在线校验、脱机触发及52988字节独立回读一致。OTP仅读取，未改供电/下载器固件。测试U盘文件校验归档后删除，后台退出，目标保留hello_world；见[覆盖报告](../verification/v050-usb-hpm-overwrite.md)。

## 下一动作

1. 继续审阅 PR #79；本机及本轮可交付 Windows 安装包/完整 Skill 为 V0.5.0 / db81241d，见[最终报告](../verification/v050-usb-hpm-overwrite.md)。未发布，签名/发布须明确授权，仅腾讯云和 MicroKeen GitHub。HPM多轮自动换板的首次断开计数初始化路径待单独检查，当前实物验收为单轮；OTP永久操作须确认具体内容。Mac候选不含最新修复。
2. 请客户退出 MKLink/Skill 后台后覆盖安装 db81241d 或后继候选；安装器会原样备份并初始化损坏历史。仍失败时保留 installation-history-report.json、history-backups 与诊断包，区分权限/占用/格式原因，不手工抹除未知操作证据。若再报 WinError995，结合枚举和系统事件排查原始触发原因。
3. 取得客户目标芯片、RTOS 和原始 SystemView 流后，确认其丢名是否命中元数据/通道修复，并单独排查解析对齐及异常运行片段；不把现有板测试扩大为所有平台保证。
4. 在用户 Mac 上验收对应 ARM/Intel 候选的首次启动、覆盖安装、探针接口/卷身份和真实查询耗时，再核对共享会话及 MCP 重载。当前软件与包内自检不替代真实环境门禁。
5. 固件会话继续维护 STOP 状态码补丁；客户信息齐备并获得明确实物安排后再做同条件 STOP/唤醒验证，不自动抢占调试器或刷写设备。

## 已知限制

- 普通读取 P95 和间隔读取稳定低于 1 ms、最大采样间隔 20 µs、40 µs 翻转零漏采仍是未达目标。
- 公网远程中继继续延期。独立 [S3 PR #65](https://github.com/MicroKeen/Mklink-AI-Probe/pull/65) 仍开放。其他硬件的[历史未验范围](known-limits-20261030.md)按需查阅。
- 转换入口针对后台最近一次记录，应在开启下一次记录前触发；没有历史文件选择器或全局转换并发上限。Excel 约 15 位有效数字，原始 JSONL 不变。转换仍消耗 CPU/磁盘，本轮未做完整真机性能 A/B；冻结 Excel 父进程退出后仍运行的时间窗口未直接观测，详见报告。 RTT TXT 精简已包含在 V0.5.0 / 3a3fb298 安装包。
- Mac ARM/Intel DMG 是 0.4.3 标记的未公证候选，未做 Finder 覆盖安装、Gatekeeper、原生窗口及 macOS 27 真机 USB 验收。Mac 修复轮未覆盖安装 Windows，也未做新的硬件吞吐/P95/调试共存 A/B；客户 ioreg 3.7→0.15 秒未独立复现。
- 客户旧上位机/固件组合导致的长停流未复现；本轮 V4 写入短测不证明所有负载零退化。未重测 HPM/V2/V3 实物能力矩阵、RTT 原始字节全量比对或独立吞吐 A/B，也未完成 CMSIS-DAP 共存及全部性能门禁。54e03336 Windows 安装包已包含能力修复。 云端提醒和更新顺序已包含在 V0.5.0 / 3a3fb298，并通过普通用户覆盖和实际界面验收；固件提醒此前仅 V2 实机，V3/V4 为源码格式/夹具验证。签名自动更新/重启、实物并发及新性能 A/B 未验，预约到期/外部安装器不在持续互斥保证内。
- STOP 案例中，V4 源码确认 0x17 重连失败会误报 6；固件会话提供修正为 5 的独立补丁和离线证据，尚未应用或刷写。客户固件版本、完整芯片型号与电气条件未齐备；持续 STOP 的调试访问不保证可唤醒，status 5 可能包含恢复未确认。
- 客户 SystemView 完全丢名未在 STM32F103RC 基线复现，客户芯片/RTOS 尚未确认，HPM/FreeRTOS 实物未验。短测解析器仍有对齐丢字节，长 GUI 采集偶见不合理 ISR/运行片段；需要原始流另查，当前修复不证明所有时序统计正确。
- ELF 与波特率修复已在 ad00c962 Windows 普通用户包覆盖验收；macOS 候选尚不含这两项。ELF 仅完成离线解析和变量配置验证，未做客户板采集或写入。本轮未做高速物理收发、持续吞吐或 SWD/RTT 共存性能 A/B；固件会话双 V4 测试不等同于客户 1.5 µs 快速应答验证，第三方驱动可拒绝预设高档位。

## 延续协议

- 后续合并、签名或正式发布须有新的明确指令。
