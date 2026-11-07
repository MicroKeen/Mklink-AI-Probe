# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-11-07T13:04:00+08:00`
- 分支：`codex/v0.4.3-fixes`
- HEAD：`SuperWatch cfb1bae8、RTT菜单 bb2c8d27、睡眠访问/复位时限 87085550；生产Web e83ecc12。`
- 远端 HEAD：`PR69已合并main/186b6a0f。0.4.3继续共用修复分支和草稿PR71。`
- 工作树：复用E盘主工作区，保留旧v0.4.2分支和两个detached工作树；本轮及后续修复共用codex/v0.4.3-fixes。
- 当前任务：HPMLink/H743 100ms WFI，上位机87085550实板6轮96/96、整段Flash一致、复位2→8。777项回归及普通10MHz对照见v043-cortex-m-sleep.md。
- 状态：`host_and_h743_verified`

## 里程碑

- **0.4.2正式版** — `complete`。PR66源0e82ba6f，Windows/完整Skill/SiteAgent、四固件正式签名与发布、覆盖安装、渠道及故障回退已完成，PR67/68已合并。资产不可覆盖；完整SHA/计数见v042-release-handoff.md。
- **0.4.1正式版** — `complete`。PR61源514efb86已发布，签名/索引/实装资格见v041-release-handoff.md。
- **0.4.0正式版** — `complete`。PR58源0c9c2d97已发布，签名/实装/渠道备用资格见v040-release-handoff.md。
- **0.3.6正式版** — `complete`。PR50/51源d000370b已发布，preview撤下、临时SSH撤销；资格见v036-release-handoff.md。
- **0.3.5正式版** — `complete`。PR43源2f474f60372e已发布，V3.6.5/V4.6.9独立发布；资格见v035-release-handoff.md和v035-probe-firmware.md。
- **0.3.4正式版** — `complete`。源a8fd3fab0403/PR40已发布、PR41交接完成；资格见v034-release-handoff.md、v034-workspace-cleanup.md。更早发布见各版交接。

## 验证证据

- **0.4.3接收、连续性与性能**：0.4.3基线/1µs见v043-host-baseline.md、v043-superwatch-1us.md。IAR退出后V3/V4混合RTT约355→420/354→416KiB/s，Watch约10→11.7万/s，四调试器共存通过。V4独立849.64KiB/s、26.53万/s，4096B约1053–1056KiB/s。见v043-mux-heartbeat-recording.md、v043-iar-exit-context.md、v043-v4-iar-exit-context.md。V3/F103 Cortex-M3 72MHz/100ms WFI，NRST未接，两种复位启动计数递增、双向烧录独立校验、RAM 12/12、持续RTT通过，DBGMCU_CR=0。见v043-cortex-m-sleep.md。
- **0.4.2正式发布及腾讯云下载**：正式源0e82ba6f，Windows/完整Skill/SiteAgent和四固件发布、覆盖、签名及三渠道/回退通过，PR66/67/68已合并，资产不可变。详细资格见v042-release-handoff.md；安装元数据cb30b703/PR63见installer-metadata-cleanup-20261027.md。清理29目录6.587GiB、629保留哈希不变、135含链接组保留，见v042-postrelease-handoff.md。11/4轻量11文件341MiB哈希/HEAD/Range/回退、25保护/18GUI通过；更新32过/1开发版本不一致，Skill检查通过。99%及无日期截止部署回读通过，见tencent-download-cost-20261104.md（含误部署恢复/限制）。
- **0.4.2正式候选最终资格**：90e676db与产品1ca9b8fd等价：6453Python/2skip、1182GUI、生产Web/冻结/Rust/NSIS/覆盖及真实界面交互通过。HPM时钟/镜像/RAM/XML/RTT/Watch/串口、Trace独立并行、烧录后三流恢复与原生退出通过。完整计数及限制见v042-formal-qualification.md、v042-traffic-replay.md，历史Trace溢出失败保留。
- **AI Skill与共享GUI**：GUI/回收/UART及实装见v043-gui-open.md、v043-uart-baud-options.md、v043-gui-uart-local-install.md。3655/2655载荷匹配，5339数据不变。全量与打包补验见v043-merge-cleanup.md，MCP强杀进程树边界保留。SuperWatch三列表写入/移除/帮助174项与Edge通过，见v043-superwatch-list-actions.md。RTT日志菜单在8种宽度×2通道×3模式，裁剪20/48→0/48，记录/回放入口均可点击。验收在构建根artifacts/v043-rtt-log-menu-20261107。
- **RTT自动恢复与在线静默收尾**：14417715：347相关+17发现测试通过。V4/HPM5301两次49700B烧录成功，RTT/Watch自动暂停恢复、零恢复错误及零Watch读错；覆盖/载荷/冻结MCP/Web/退出通过。当时为0.4.1测试包，修复后续纳入正式0.4.2。原始包/详细计数见rtt-auto-restore-20261030.md；静默面板d1cf16ec见online-flash-receipt-20261029.md。
- **Linux/macOS 0.4.1测试包**：Linux a6bdacbc、Mac arm64 eefc6842：CI USB各58/1skip及冻结CLI/MCP/健康/Web/退出通过。DEB SHA7309f377、DMG SHA56dc8e0a，均旧0.4.1；Mac ad-hoc未公证，实机安装/UI/USB待测。见linux-deb-test-20261028.md、macos-arm64-test-20261028.md。
- **H743正式固件与双核候选边界**：H743正式V4.7.1在线/四脱机/19采集调试通过。私有V4.7.2单核兼容、双核误选写前拒绝、2MiB不变及M7/M4 HEX在线通过；V4.7.2/V3.6.8/V2.9.3双核候选交付，46回归通过。无双核实板正向脱机，V3历史掉线未闭环，当时候选不公开替换；后来明确发布的四个build以v042-release-handoff.md为准，不外推双核验收。见known-limits-20261030.md。
- **共享RTT/SystemView及480量子**：共享MUX/480/二进制订阅996回归及浏览器、76307模板104回归/真实H7头文件通过。H7八份10MiB全字节核对，新799–801/旧528–633KiB/s，独立SV307134事件和有限共存零计数通过。旧Watch末组失败及饱和丢失保留，不能外推。详见h7-rtt-control-20261031.md、systemview-rtthread-template-20261031.md及known-limits-20261030.md。

## 架构决策

- 0.4.2正式源0e82ba6f/PR66与0.4.1正式源514efb86及所有已发布资产不可变。2026-11-02明确发布授权已完成Windows/完整Skill/SiteAgent、V2.9.3/V3.6.8/普通V4.7.2/HPMLinkV4.7.2的腾讯云/Git发布。用户2026-11-03覆盖旧分支约定：后续多个修复共用codex/v0.4.3-fixes，不直接修改main，不逐任务建分支；后续正式发布须另有明确指令。公网中继延期。
- 后台协议 53：一个 GUI 客户端持有一个固定后台，同窗口切换只改下载器，RTT/Watch/Trace 跟随当前设备并清空旧目标状态；另开客户端才建独立后台。已有 URL 的额外页面共享该后台。工程上下文固定，换工程须停止原后台后重开。
- 物理探针唯一 OS 所有权、USB 身份核对和 epoch 隔离保留。GUI/AI 明确断开或切换自动停止采集、排空在途操作并释放端口；旧会话不得跨设备，未知结果不得自动重放，不偷取其他后台占用。MCP disconnect 物理断开，detach 仅退出自身；独立 UART 保留。
- SuperWatch写入只认写应答、不自动回读；显式校验保留，未知写不重放。外设ID按Pack/芯片/SVD，失效选择不阻断连接；厂家原字节/许可证/SHA保留，HPM九系列CMSIS-SVD支持，SES CPU XML不能冒充SVD。在线型号提供默认，脱机/外设页可独立修改；Pack刷新与下载身份预留保留。默认MUX小Watch0x618；11/5恢复显式DMPM，须能力声明和空闲连接，不自动回退或SW01写。capture/benchmark用0x800扩至4096B，GUI/VOFA容量保持；时间/DAP元数据不保证原子快照。离线旧记录可读；有限dump/HPM Flash经MUX完整校验，取消/deadline不返回部分结果。
- 腾讯云：2026-11-04授权上海无限流量轻量服务器仅存/直出最新正式应用、Skill、SiteAgent及各型号固件；历史COS/Git，已有旧文件未清理。上位机启动/Skill首次加载默认查stable，当前0.4.2。COS210GiB，189告警/207.9(99%)锁停；用户明确取消套餐日期截止，保留累计账本、180秒短链和持久监控，不自动清零或扩大额度。套餐到期可按量计费，非账单硬上限。仅现有控制台/TAT，无新SSH。后续发布核验新集及归档后退役旧本地副本，不自动发布。旧桶及Git迁移边界见v040-release-handoff.md；新策略见tencent-download-cost-20261104.md、tencent-updates.md。
- 测试直接使用用户原工程及 build/keil/Obj ELF，允许修改且无需备份还原，不复制工程；硬件路径只留本地。HPM 使用 ROM API，不使用 FLM/第二次通用 SWD reset；VCC 每次改动需确认具体电压，固件修改另开会话。 HPM AI可选固件声明的JTAG档位；旧4/10/20/30、新能力14档，默认10MHz。SWD/JTAG配置独立，不声称切换接口或物理测量。固件修复由用户指定会话01a186cd-c52a-7ea0-af29-8de6775d143b负责，用户后续允许提供本会话ID、通知和更新固件；指定会话已协作完成固件测试；明确授权的四个build已发布，见v042-release-handoff.md。后续仍双向核对占用，不自动升级或降级。
- 默认只构建Windows；仅明确要求Linux/macOS时才构建或触发对应原生CI。完整Skill仍须FLM/Pack资格检查。构建使用scripts/build_workspace.ps1和F:/MKLink-Build，保留正式包、唯一证据、依赖与缓存。历史获授权本地Unix清理不影响线上正式附件；过时可再生产物仅依清理授权处理，链接/不可访问目录不强删。 通用请求延迟：每线程HTTP keep-alive按后台instance/port/probe/token隔离，空闲2秒或EOF前置退役，失败绝不重放。路径完全一致时不重复resolve；准入只读活动AXF路径，继续核验目录generation/fingerprint。无批量替代独立请求，无客户专用快照协议，无固件修改。
- 工程上下文固定；物理唯一OS锁/身份/epoch保留。被动枚举不遍历占用设备；普通内存身份检查同活跃CDC最多复用250ms，错误/恢复即失效，生命周期仍全枚举。共享RTT/SV同CB掩码合并、独立有界队列；bit7增量，bit8协商480，短帧含CRC≤512；bit6独立4096读不变，旧量子128。未知操作不重放，失败不自动raw回退，worker退出才关串口，背压/丢失不隐瞒。指定固件会话负责实机，双方协调占用，宿主只导出不可变源码/离线验收；清除临时日志代码，保留移植说明。
- 原MK-Firmware及用户固件工程改动保留，不自动恢复旧备份。2026-10-18授权的0.3.5、V3.6.5/V4.6.9发布已完成；未知操作不重放。用户要求未解决项保留交接，未扩大验收或宣称客户故障已闭环。
- 编译完成不代表目标已下载：文件变化仅发待重载提示，不后台解析。用户明确加载/重载文件时自动停止目标采集，确认worker退出后原子换表，保持停止；失败保留旧目录/选择。不要求连接下载器；断开保留文件和选中变量但清空旧采样。公式只改变可视化，原始记录不变；不恢复旧地址采集或重放写操作。

## 真机环境

- **state**：11/7 V3最终UART r6在用、V4上次为普通r4；固件会话已释放硬件并合并V3 #9–11/V4 #18–20，详见v043-merge-cleanup.md。每次重核身份/占用；LA CH0/CH1为SWCLK/SWDIO。
- **installer**：Windows/完整Skill为0.4.3/b8a1f658（产品等价4c890205），NSIS SHA08109b2d、Skill abb5797a，验证见v043-gui-uart-local-install.md。SiteAgent仍旧，正式资产不变；未发布。
- **backups**：最新b8a1f658应用/Skill、f9b1ae8a基准、正式包/固件、原始测试记录及公共缓存保留。11/7清理29.558GiB，4383保留哈希一致；112含链接组未删，见v043-space-cleanup-20261107.md。旧ELF/试包退役；11/4历史清理见v043-workspace-cleanup.md。

## 下一动作

1. PR69已合并186b6a0f；后续共用codex/v0.4.3-fixes并保留工作树。性能/数据基线不降，允许调试占带宽合理下降；P95<1ms/最大间隔<20us仍开放。新合并/发布须授权。
2. 固件V3 #9–11/V4 #18–20已合并，main为d46ccdf7/affba5d0；UART34档资格仅普通V3/V4。应用/完整Skill仍b8a1f658；RS485/其他硬件不外推。
3. 11/7历史清理完成，F余30.758GiB；含链接112组/10.910GiB保留，完整CSV在构建根reports/space-cleanup-20261107。公共缓存/正式原包/唯一证据不删，旧实验ELF与测试安装包已退役，见v043-space-cleanup-20261107.md。
4. 按tencent-updates.md维护最新本地集；COS189GiB告警/207.9停止，已取消日期截止，关注实际扣量/到期后费用。不清零/扩大额度/恢复停止锁；监控断档超30天须账单重锚定。

## 已知限制

- 新MUX整块读普通V4/H7已实测，V3/H7指定会话候选复测通过；HPM本轮映像回读及480B RAM核对通过，未扩全内存区矩阵。安装后20次调用仍有明显调度抖动，前次dce包4KiB最大39.074ms，不承诺固定低延迟。HPM九系列XML已解析/匹配/浏览器导入；用户接回HPM5301后的六GPIO寄存器实读/采集通过，其他系列及IO输出驱动未测；客户F411仍待实板复测。dump定时截止可留半个样本，完整性门槛保留。HPM CPU仅RV32/hart0/HPM5301/槽0实测，其他触发器/型号、新值写入、20/30MHz及断电冷启未扩展，TCK未测。11/6已补进程身份预检/失效endpoint回收，保留日志/未知记录；旧端口HTTP异常保护见runtime-endpoint-errors-20261030.md。客户3.11.9、CDC首次离线、F405 PROGRAM100%退出、GD32受限AI、RTT后MUX、HEX2%未知结果及PyInstaller权限故障保持未闭环，详见known-limits-20261030.md及v032-postrelease-incidents.md；不重放未知操作。 旧dce/4be FPBv2曾422，新包已含修复；7843双半字命中及Keil共存已验。采集中共享断点仍409；V2本轮共享step已实测，其他型号不由Keil单步替代验收；见h7-fpbv2-systemview-idle-20261031.md。
- 30MHz RTT/Watch/UART并行历史存在目标读错：V4.6.8 1kHz +1/最大+273，10MHz0；V4.7.0/F103先Watch后RTT11762周期1错、反顺序12297周期0，10MHz两顺序0。发布接受不等于问题关闭，完整记录见known-limits-20261030.md。
- HPM/SES未发Disconnect可留占用，完整SES矩阵/RTT下行未覆盖；status6截图只证busy。IAR9.70.1退出尾包已证无Disconnect/CONNECTED=false，V3/V4上下文修复保留所有权并消除逐批借还，四调试器共存/退出恢复通过。其他IDE/芯片、长期睡眠拔插及旧固件未复现硬锁不外推。原E Watch停止边界457314B队列淘汰未闭环。4096B允许已建立DAP只读，新Connect/Disconnect按契约status7终止，须显式新采集，非原子快照。
- 共享MUX并行SV仍有容量边界：旧饱和768/drop17371，流水线28/1330、burst26/1164、control15/1442，重启归零不抹去；control独立62.679秒零丢失计数通过。RTT661.208KiB/s为特定配置观测值，H7限定实测新799–801KiB/s、独立/有限并行SV零计数；单次API20样本中位有12.90→20.03ms等退化未归因，旧Watch末组失败保留。采集暂停/下载丢观测、多变量非原子、无时序保证。COS207.9GiB(99%)非账单上限；已取消套餐日期截止，到期可按量计费，存储/请求/SCF另计；旧0.4.0固件Git备用未迁，签名资产不改。
- V3无屏幕且不支持HPM；V3.6.4 Keil/OpenOCD共存已测。V4最终无诊断固件完整SES矩阵未完成。旧V3.6.8/build17:56:49的CRLF六轮及1800.028秒空RTT证据见v3-crlf-final-review-20261030.md和v3-empty-rtt-review-20261030.md，不计入新build11:00:39复验。新V3限定RTT/FPB/Keil通过见v3-rtt-systemview-review-20261031.md；历史掉线根因、legacy/睡眠拔插/更长时长仍未测，再现先保存现场。 旧1ms Watch相位跳变归因未闭环；本轮HPM5301周期矩阵已通过，不能外推历史全部场景。
- 最后客户端退出约5秒租约后开始排空/关闭，不保证硬实时5秒。每GUI独立后台；单探针仅一个后台持有；已有URL共享页面跟随明确切换。独立操作另开客户端。 Keil BL重载由2增9；用户确认未操作，原因未明。仅恢复重载后9个状态，最初配置未恢复；见h7-fpbv2-systemview-idle-20261031.md。 Windows MCP宿主若强制清理整个Job进程树，会带走其启动的GUI后台；标准stdio正常EOF已验证独立存活，详见本轮安装报告。
- UART5 TTL Modbus历史读写通过，RS485电气层未测；本次仅虚拟串口双向字节/日志，不能替代物理UART。跨主机Agent/全芯片未认证。Unix包仅CI冻结检查，USB/原生UI/升级待测；Mac ad-hoc未公证，Windows无Authenticode，不承诺消除SmartScreen。日志文件回放与原生目录现已通过；Trace最终独立/并行各三轮零新增丢失通过，历史初始溢出1保留且不外推全部负载；HPM HardFault页面仍限Cortex-M。早期浏览器清理未确认的现场记录保留；本轮官网下载验收通过。详见v042-traffic-replay.md。
- nRF54L15保护闭环、全部擦除/拔插/休眠/断电、电源精度未全测。每次VCC需确认具体电压。26个无可靠扇区FLM禁用扇区操作，Bank模式须匹配。HPM5301 OTP组18/19历史永久锁定；128字读取及批准Word69 0→1已实测，其余型号/区域不继承授权，锁最后写/逐项校验，多Word不可回滚；熔丝/影子/临时锁语义未知，UART按ROM状态及回读为准。详见hpm-offline-otp-handoff.md及known-limits-20261030.md。

## 延续协议

- 后续多个修复共用codex/v0.4.3-fixes，先fetch核对实际状态；不直接修改main，不逐任务另建分支，不自动切回main。旧v0.4.2分支及两个detached工作树保留。0.4.2正式源0e82ba6f和全部已发布资产不可覆盖。
- 正式资格/渠道仍见v042-formal-qualification.md与v042-release-handoff.md；本机0.4.3应用/完整Skill已覆盖b8a1f658，见v043-gui-uart-local-install.md。测试页/原生窗口已正常关闭；AI/MCP重启后加载新Skill。固件会话已释放硬件，下次使用前重新核对占用。
- V2 RBL更新见v035-v2-rbl-update.md，用户回退2.8后真实升级2.9已经通过；最终应用2f474f60与Skill已同步。V3.6.5/V4.6.9本轮仅发布原始UF2并验证公开文件，未再次刷入实体探针，不重复升级或回退。
- CDC995和SDK10048根因保留待排查。恢复仅同身份CDC故障5秒内；超时不自动接回/新建AI会话，主动断开立即生效，未知写入不重放。历史实例释放记录见v035-transport-recovery.md；当前硬件占用以本交接真机状态及指定固件会话为准。
- 客户启动故障仅确认PyInstaller解压ucrtbase.dll时Permission denied，重启后恢复；未定位权限/杀软/占用的具体来源，按用户意见暂不做推测性修复。若再现，结合新startup/runtime日志复查。
