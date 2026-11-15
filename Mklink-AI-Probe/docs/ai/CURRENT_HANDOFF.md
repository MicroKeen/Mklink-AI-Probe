# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-11-15`
- 分支：`codex/v0.5.0-fixes`
- HEAD：`65826071`
- 远端 HEAD：`65826071`
- 工作树：修订候选已覆盖；Python7190/2跳过、GUI1294、完整Skill及已绑定V2脱机刷新通过。PR #84待合并授权；固件解释器边界修复中，云端未改。
- 当前任务：6523d0e7主机候选的覆盖迁移、快捷方式、原生/Web、完整Skill和最终全量通过；已绑定V2脱机页20秒静默与手动刷新通过。RST重接后硬件复位通过；固件会话另发现64参数旧文本命令卡住解释器，正修复重编，继续独占设备。用户待确认PR #84合并，云端仍等待新固件最终联测。见[修订验收](../verification/v050-install-path-offline-refresh.md)。
- 状态：`V0.5.0 修订主机门禁通过，等待固件修复与PR合并授权`

## 里程碑

- **MKLink 0.5.0** — `正式`。2026-11-15 双渠道发布完成；[PR #79](https://github.com/MicroKeen/Mklink-AI-Probe/pull/79) 合并源和 v0.5.0 为 1097f98e。Windows、完整 Skill、Site Agent 及 MicroLink V2.9.4 / V3.7.0 / V4.7.4、HPMLink V4.7.4 已上线。先更新客户端、重载 MCP，再按型号更新固件。原生补充包源 8d532019，Mac ARM/Intel 与 Linux x64 已补齐并支持签名更新；正式标签/旧附件保留。
- **0.5.0 上位机开发基线** — `已合入 main`。2026-11-09，[PR #78](https://github.com/MicroKeen/Mklink-AI-Probe/pull/78) 以 `2861d7a6` 合入，新增 CLI 显式重载 AXF/ELF 符号，[Issue #77](https://github.com/MicroKeen/Mklink-AI-Probe/issues/77) 已关闭（Completed）。随后 [PR #76](https://github.com/MicroKeen/Mklink-AI-Probe/pull/76) 以 `cf034fe1` 合入，修复 Windows 普通用户因 jobs.json 访问受限而无法连接探针的问题，[Issue #75](https://github.com/MicroKeen/Mklink-AI-Probe/issues/75) 已关闭（Completed）。
- **MKLink 0.4.3** — `正式`。`v0.4.3` 指向 `3905a68b`。Windows 上位机、完整 Skill、Site Agent、MicroLink V3.6.9、MicroLink V4.7.3 和 HPMLink V4.7.3 已发布。MicroLink V2 沿用 V2.9.3。

## 验证证据

- **GUI共享控制、回放与多窗口健康**：ba3a334b实现5主页面/4配置分区/8仪表盘标签控制，原生/Web回放、显式选窗、探针身份/代次失效保护通过；取消SystemView冗余状态SSE解决浏览器连接池耗尽。最终安装版6受控窗口72/72正常，645064事件/9任务，解析和目标/主机丢弃0。GUI1290项及最终13项、后端245项/71边界/最终17项通过，存在重叠。NSIS普通用户覆盖3686文件一致，本机Skill同步，见[完整验收](../verification/v050-gui-control.md)。 此前IRQ锁/8KiB缓冲/采集中重启见[前轮](../verification/v050-systemview-loss-reboot.md)，显示及历史优化见[刷新报告](../verification/v050-systemview-refresh.md)。
- **HPM Flash 配置、连接设置与脱机 OTP**：HPM 四字配置与接口/OTP 源码验证见[Flash 配置](../verification/v050-hpm-flash-config.md)及[前轮](../verification/v050-hpm-interface-otp.md)。现已包含在 db81241d 安装包；真实生产浏览器指定串口可选接口/时钟、配置导入/跨页复用、OTP 读取与4/8列/写确认保护通过。HPMLink V4.7.4 / HPM5301 在线校验、脱机和 52988 字节完整回读一致，见[最终覆盖](../verification/v050-usb-hpm-overwrite.md)。未做 OTP 永久编程或其他 NOR 验收。
- **ELF 解析与完整 UART 波特率**：ELF 可写范围合并 PT_LOAD，客户 ELF 的结构体成员恢复，400 项解析/共享关联及真实浏览器通过，未操作客户板，见[ELF 报告](../verification/v050-elf-load-segments.md)。串口助手/Modbus 按 UART、RS485 独立声明使用 34 档至 10M，870 后端/25 GUI/69 Skill 及双 V4 实读通过，未发高速载荷，见[波特率报告](../verification/v050-uart-baud.md)。两项已随 ad00c962 普通用户覆盖并复验，见[覆盖报告](../verification/v050-elf-baud-overwrite.md)。
- **固件能力提醒与采集中写入**：同一V4/STM32F103RC实测V4.7.3与V4.7.4写入前后最大采样间隔0.195/0.208/0.192ms；RTT并行为1.562ms，各轮10次写入成功且无序号/读错。真实Web写入保持约15.9kHz，三端警告一致，状态检查无设备I/O，见[能力报告](../verification/v050-firmware-capabilities.md)。V2.9.4与云端V2.9.3不误报降级；版本缓存/提醒/跳转验收见[提醒报告](../verification/v050-firmware-update-notice.md)。客户端先行、MCP重载与重启失败互斥恢复见[更新顺序](../verification/v050-update-order.md)。专项用例有重叠，最终全量结果以发布交接为准。
- **macOS 兼容性与跨平台回归**：最终原生包源8d532019；Mac ARM/Intel DMG与Linux AppImage/DEB的冻结后台、真实WebView/MCP操作、错误签名拒绝、有效更新与重启通过。USB各73项通过/1项Windows专属跳过。Windows Python7175/2跳过、GUI1291和生产构建通过；两渠道13附件及5平台索引验证完成。设施边界见[原生验收](../verification/v050-native-release.md)。
- **SuperWatch 配置与手动日志转换**：手动转换 56 项、共享后台/流/边界 296 项、GUI 152 项通过，生产构建通过。冻结安装版实物记录 1,114,032 组，Excel 两页 1,048,575 / 65,457 行、4,456,128 个值与 JSONL 对应；RTT 505 行 TXT 对应，7 个原始文件哈希不变。GUI 手动触发、实际 CLI/MCP 重复请求复用任务且不停止采集。见[转换报告](../verification/v050-manual-recording-export.md)。符号旁配置原有软件/浏览器证据见[配置报告](../verification/v050-superwatch-profile.md)；前一安装候选已验证真实 AXF 重启恢复，本候选解析 6,718 个变量并保存四变量、500000 缓存与 1 µs 间隔。 TXT 精简追加：转换/记录器 37 项、Skill 69 项通过；既有 505 行时间和正文等价，63,996→40,304 字节，原始文件哈希不变。见[TXT 报告](../verification/v050-rtt-txt-readable.md)。
- **V0.5.0 发布、安装与升级**：正式源1097f98e：Python7173通过/2跳过、GUI1291、Rust23、生产构建与CI通过。普通用户新装/卸载/覆盖exit0，3686载荷一致，6配置及USB名称/机器登记保留。原始0.4.3原生GitHub回退下载、签名、安装、重启0.5及二次无更新通过；Skill腾讯云/备用GitHub升级2680文件一致。原生/Web页面与四类回放通过，冻结59工具MCP/算法/SVD通过。双渠道11新文件全量SHA/HEAD/Range、索引及历史11文件COS归档通过；见[发布交接](../verification/v050-release-handoff.md)。前轮强制活动覆盖与实物见[安装验收](../verification/v050-installer-force-acceptance.md)，双V4/500ms恢复见[USB报告](../verification/v050-usb-hpm-overwrite.md)。 本轮修订：已定位跨安装范围漏读 HKLM 与后台轮询触发忙碌状态；此前发布测试使用 /D 或已有 HKCU，不能代表该迁移路径。本轮专项解析器/脱机轮询测试已过，完整软件、实际覆盖和固件协同验收进行中，见[报告](../verification/v050-install-path-offline-refresh.md)。
- **V3 / V4 SuperWatch 恢复**：普通 V4 修复候选实物拔插跨 12.637 秒缺口原订阅恢复，V4.7.4 健康检查通过，223,728 组、零读错及队列丢弃，中位 43,486.6 组/秒。V3.6.10 实刷及拔插恢复通过，1,484,544 组，零队列丢弃、序号异常和时间倒退，恢复后中位 43,056.7 组/秒。旧 V3.6.8 缺采样能力，无同条件旧版基线。版本及未验范围见[恢复验证记录](../verification/v050-superwatch-swclk.md)。

## 架构决策

- 采集或调试改动须按[上位机基线](../verification/v043-host-baseline.md)同条件核对数据完整性和性能。SystemView每次附着刷新INIT/任务列表，按实际通道，不猜选；RT-Thread模板锁覆盖可记录的高优先级IRQ，保留嵌套掩码。时间窗口仅控制可视跨度，连续跟随不补造事件；统计限频不影响精确检查，暂停显示仍可缩放且不暂停采集。用户显式重启所选MKLink时停止其采集、重启一次并退役会话/释放占用，其他探针与独立UART隔离，不自动重连或重放。 桌面与Web GUI操作共用gui_control/gui_action；先显式选择窗口和新鲜控件，路由/探针身份/代次变更后重读。页面回执仅说明指令执行，异步设备任务仍核对共享终态，unconfirmed不自动重放。GUI回放仅影响本窗口；RTT/串口历史TX不重发。SystemView状态只用原有1Hz轮询，不再占用长期HTTP SSE连接，数据仍走WebSocket。
- 默认仅构建 Windows。用 PowerShell 7、UTF-8 和 `scripts/build_workspace.ps1`，构建根为 `F:/MKLink-Build`。
- Windows NSIS默认currentUser；不自动命名USB端口，只有用户确认修改/恢复名称才调用UAC助手。按2026-11-14最终指令，覆盖安装直接强制结束当前用户MKLink桌面/共享后台/Skill/MCP及其WebView，含活动任务，不依赖旧版API，不杀AI宿主或无关Python；无权限时明确失败，不自动提权。覆盖安装先恢复有效的原机器级目录，尊重显式 /D 和目录页选择；机器登记/目录权限不更改，受保护目录无权限时明确失败而非另建用户副本。损坏历史仍原样备份核验后初始化；有效未知结果不清空，权限/占用/链接异常跳过，不重放旧操作。
- 后续发布只到腾讯云和 MicroKeen/Mklink-AI-Probe GitHub，Gitee 与旧 GitHub 保留历史，不上传新附件/标签/索引。AI / Skill / 固件按腾讯云、GitHub 顺序回退，不并发查询；备用 Skill 文件须匹配所选版本、大小、SHA-256。上海服务器直供最新版，COS/Git 存历史；COS 189 GiB 告警、207.9 GiB 停止，无日期截止。见[下载策略](tencent-updates.md)。
- 跨会话固件联测固定上位机提交并核对 mklink/runtime 模块导入路径；主工作区和全局 editable 入口不自动代表当前任务版本。
- project-init 是可选离线配置工具；通用工程可显式传型号和文件，直接烧录不依赖初始化。型号或镜像不明确时要求补充输入，不猜测，也不自动迁移已有芯片配置。 ELF 可写范围合并 SHF_WRITE/ALLOC 节及 PF_W 的 PT_LOAD 段，使用 p_vaddr/p_memsz；不凭 AX 或 RAM 地址放宽，不把 Flash 装载镜像当 RAM。已知只读映射不走通用回退。 HPM 四字 Flash 配置按实际 NOR 设置，GUI 可编辑/按器件保存/JSON 导入导出；无默认值时手填，不沿用旧型号。GUI/Python 共用参考表，显式 hpm_flash_cfg 优先于 board，已知默认值也走 flash_cfg；未知显式板名保留旧入口。XPI 控制器基址不等于 BIN 地址，USART ISP 配置独立。JTAG 脱机 OTP 只生成已确认的 hpm_user_otp 配方，读取绑定身份与代次；修改、断开或换设备后重新确认，系统字段只读。
- RTT / SuperWatch 实时记录 JSONL；停止记录不自动转换。用户手动将 SuperWatch 转为 Excel、RTT 转为带主机时间戳的 UTF-8 TXT，三端共用低优先级后台转换；Excel 保留采样相对时间，开始日期写在 Info 页。JSONL 保留作无损回放源。 RTT TXT 普通行仅含时间、CH 通道、RX/TX 和正文；session 在每个分段首次输出或切换时单列注释，JSONL 保留完整字段。
- SuperWatch 配置由共享后台保存在 AXF/ELF 旁，名称为原文件名加 .superwatch.json；三端共用名称与修订协议，不存变量地址、不自动开始采集。显示修改防抖，样本接收不写配置；浏览器上传只能保存到后台副本旁。
- macOS 原生包使用 ad-hoc 签名且不启用 Hardened Runtime；Developer ID 发布须在冻结阶段正确签内嵌库。0.5.0 原生补发与CI验收已完成，正式标签/旧附件不变。在线烧录身份枚举已移到工作线程，查询前后核对身份/代次；其他发现接口不据此宣称已全部异步化。
- 缺固件能力按已有文本/HELLO 缓存判断，版本号不替代协商；Web/CLI/SDK/MCP 共用 firmware_compatibility 和 firmware_warning。未知型号或未协商状态不猜测；status 5/6、超时、目标及硬件限制不误报升级可解决。SuperWatch 运行或暂停时缺 MUX 写能力则提示升级并保留采集，不自动停流写入；地址限制提示显式停止。未知写结果不重放，不自动升级固件。 串口助手与 Modbus 共用完整 34 档预设（300～10M）；已识别 UART / RS485 分别按自身固件声明限制选择。列表刷新只用缓存，显式查询走物理探针共享所有者且不停止采集；缺声明提示升级，第三方预设不保证支持。已有连接的自定义速率只读保留。 固件云端提醒复用有序握手缓存，后台延迟 3 秒检查、成功缓存 6 小时/失败 15 分钟；无产品标识默认 MicroLink，显式 HPMLink 独立匹配。不能解析时直接提示升级但不猜版本/镜像。弹窗仅跳转，不停止采集或刷写，同窗口/设备/版本去重；能力协商保留。 更新顺序推荐客户端先行，重载 MCP/空闲旧后台后再重连检查固件；应用内更新保留空闲预约，外部覆盖安装按用户最终要求强制结束旧进程；重启失败暂缓固件。Skill 首次异步检查并主动提醒，未连接固件待查，不自动安装。

## 真机环境

- **操作前**：重新核对下载器型号、目标和占用。固件变更由指定会话协调，升降级按本次授权执行。VCC、OTP 操作分别确认。
- **普通 V4**：沿用V4.7.4 / STM32F103RC及此前IRQ锁/CH2 8KiB目标；本轮没有刷写、供电或应用变更。ba3a334b安装版SWD10MHz，四变量1ms+RTT CH0/1+Trace CH2，645064事件/9任务且无解析/目标/主机丢弃。RTT没有文本载荷，UART/RS485未接；采集停止、断开、测试窗口关闭，下次重新核对占用。
- **普通 V3**：固件会话已回读 V3.6.10 / 2026-11-10T14:14:14，原 STM32F103 的一次 SWCLK 拔插恢复通过；测试结束时后台退出、设备释放。下次仍需重新核对占用。
- **普通 V2**：2026-11-13 提醒验证时实际仅接入一只 V2.9.4，无产品标识。当前版本取首行而非历史版本，真实云端返回 V2.9.3，未提示降级；正常分离后后台退出释放设备。未刷写、改电源或目标程序，未启动采集；下次操作重新核对占用。
- **HPMLink V4**：固件会话本轮交回V4.7.4 / 2026-11-14 11:35:00，HPM5301；上位机本轮未占用或改目标。前轮db81241d JTAG10MHz/flash_cfg在线脱机与52988字节回读证据见[覆盖报告](../verification/v050-usb-hpm-overwrite.md)。固件会话RS485互测是单独证据，10Mbps大帧边界仍保留；下一轮重新核对接线/固件/占用。

## 下一动作

1. 等待用户对PR #84的明确合并回复，检查确切头CI后合入；从干净main重建修订。固件会话须完成解释器参数边界修复及新候选最终联测，之后才更新腾讯云/官方GitHub备用源。已有0.5.0者手动覆盖，保留原标签/附件及其他平台。
2. 客户可直接运行新版覆盖安装器，自动结束当前用户旧MKLink与Skill/MCP，不要求手动先关旧版；活动任务会结束。安装后AI宿主需重新加载被结束的MCP。损坏历史备份保留，仍失败时收集installation-history-report.json、history-backups和诊断包，区分权限/占用/格式；不手工删除有效未知结果，不重放烧录。
3. 客户SystemView先核对实际CH、目标IRQ锁及元数据。1µs三路溢出先采集0x40 CH2设备时间戳/长度/序号与主机单调到达时间，低频读0x10错误和0x14批次耗时；诊断开销保持一致，再判断背压、重试或调度，不直接假定80ms停读或给CH2固定优先级。多视图假离线已完成修复与安装版六窗口复验。保留目标构建快照供AXF源码路径使用，原工程重编后再清理；见[静态补充](../verification/v050-systemview-loss-reboot.md)。
4. 有Linux/Mac实物后补验真实USB、Gatekeeper首次安装和交互式提权；不能把本轮CI结果当作这些硬件/系统验收。
5. 固件会话继续维护 STOP 状态码补丁；客户信息齐备并获得明确实物安排后再做同条件 STOP/唤醒验证，不自动抢占调试器或刷写设备。

## 已知限制

- 普通读取 P95 和间隔读取稳定低于 1 ms、最大采样间隔 20 µs、40 µs 翻转零漏采仍是未达目标。
- 公网远程中继继续延期。独立 [S3 PR #65](https://github.com/MicroKeen/Mklink-AI-Probe/pull/65) 仍开放。其他硬件的[历史未验范围](known-limits-20261030.md)按需查阅。
- 转换入口针对后台最近一次记录，应在开启下一次记录前触发；没有历史文件选择器或全局转换并发上限。Excel 约 15 位有效数字，原始 JSONL 不变。转换仍消耗 CPU/磁盘，本轮未做完整真机性能 A/B；冻结 Excel 父进程退出后仍运行的时间窗口未直接观测，详见报告。 RTT TXT 精简已包含在 V0.5.0 / 3a3fb298 安装包。
- Mac/Linux 实物 USB、Gatekeeper/Finder 首次安装、交互式提权及历史原生客户端升级未验；维护者接受CI原生验证。合成旧版本AppHandle的真实签名安装与最终包窗口操作已通过，见[原生验收](../verification/v050-native-release.md)。
- 客户旧版长停流未复现；14b86cd0同固件安装前后短测SW单独约15.793kHz、RTT共存约13.816kHz，40次写入无序号/读错，但不能证明所有负载零退化。普通HTTP读取P95含代理约4.463/4.921ms。未完成外部调试器共存、全部性能目标、8通道字节全量或长期压力。用户确认UART/RS485未接，本轮串口/Modbus未验。正式0.4.3→0.5.0签名自动更新和重启已验；覆盖安装按明确要求会中断活动任务，普通用户无法结束管理员进程或突破目录权限。
- STOP 案例中，V4 源码确认 0x17 重连失败会误报 6；固件会话提供修正为 5 的独立补丁和离线证据，尚未应用或刷写。客户固件版本、完整芯片型号与电气条件未齐备；持续 STOP 的调试访问不保证可唤醒，status 5 可能包含恢复未确认。
- STM32F103RC旧锁导致的SystemView解析丢字节/异常ISR已修复；客户丢名需芯片、RTOS、通道和原始流。1µs四变量SW+RTT+Trace约60秒仍有5次目标溢出/895丢包，MUX/主机队列0。固件静态复核未见固定80ms停顿，但USB背压/内部重试/调度无最大服务间隔保证；现有快照无法归因，不自动降采样。多视图假离线已定位并修复，见GUI控制验收；长期低延迟/恒定60FPS、HPM/FreeRTOS实物和全部性能门禁未验。
- ELF与34档波特率已在Windows候选包含；客户ELF仅离线解析/配置，未操作客户板。本轮没有高速串口/Modbus物理验收；固件会话RS485双V4测试不等同本轮/客户快速应答验证，10Mbps大帧丢包边界仍保留，第三方驱动可拒绝高档位。

## 延续协议

- 继续PR #84集成及同版本修订发布，合并确认已发出，未答复前不合并。主机候选已覆盖，完整Skill仅包内验证，全局Skill未替换；最终测试临时目录已清理。固件会话正在修复V2解释器边界，禁止覆盖或抢占硬件；云端未改。
