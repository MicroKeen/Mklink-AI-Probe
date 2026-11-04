# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-11-04T16:04:28+08:00`
- 分支：`codex/v0.4.3-fixes`
- HEAD：`基于main 4f3be7a4；本轮接收/连续性修改对照c71d6995，本地安装源14160cc6；确切提交以Git为准。`
- 远端 HEAD：`microkeen/main已合并PR66、67、68，基线4f3be7a4；正式tag/包不变。`
- 工作树：复用E盘主工作区，保留旧v0.4.2分支和两个detached工作树；本轮及后续修复共用codex/v0.4.3-fixes。
- 当前任务：0a0c97b3接收修复后，内置浏览器四组40/100us波形/PNG及缺失回放完成；max47–62us，原始MUX与2369439个发布样本逐点相符。四组峰值均在ECHO回复前后批间，20us/40us零漏采未达。见v043-iab-waveforms.md；未更新安装版。
- 状态：`v043_iab_waveforms_verified_echo_gap_open`

## 里程碑

- **0.4.2正式版** — `complete`。PR66源0e82ba6f，七资产签名/正式覆盖、四固件三源哈希、三渠道/双固件索引、11文件COS及故障回退、0.4.1 Skill两源升级、官网通过。NSIS SHA5ff079bb/Skill SHA14af7a5f；见v042-release-handoff.md。
- **0.4.1正式版** — `complete`。PR61源514efb86，七资源签名/实装、三索引、Skill升级及原生退出通过；正式源见v041-release-handoff.md。
- **0.4.0正式版** — `complete`。PR58源0c9c2d97，七附件签名/实装/升级、21资源COS及故障备用通过，索引最后切换；Gitee安装包经MicroKeen备用。见v040-release-handoff.md。
- **0.3.6正式版** — `complete`。PR50/51源d000370b；Windows/Skill/SiteAgent签名、三渠道实装通过，preview撤下、临时SSH撤销。见v036-release-handoff.md。
- **0.3.5正式版** — `complete`。PR43源2f474f60372e；Windows/Skill/三平台/SiteAgent与17附件、签名/三渠道通过，全局Skill同步。V3.6.5/V4.6.9独立发布，见v035-release-handoff.md和v035-probe-firmware.md。
- **0.3.4正式版** — `complete`。源a8fd3fab0403/PR40已发布；PR41正式Web/交接、三渠道验签/实装及清理完成。见v034-release-handoff.md及v034-workspace-cleanup.md；更早发布见各版交接。

## 验证证据

- **0.4.3接收、连续性与性能**：0a0c97b3：382后端/307GUI，最终记录9/回放164及Web通过。搜索1.75–1.87s→35–72ms，同负载八组max14–86ms→46–56us、队列丢弃0。RTT两份10MiB全验853.3→853.5–853.8KiB/s；DAP300+Watch+RTT通过，P95 1.2515→1.135ms，见v043-receive-backpressure.md。内置浏览器四图/缺失回放完成，原始MUX与2369439样本相符，max47–62us均关联ECHO，见v043-iab-waveforms.md；20us/40us零漏采未达。旧MUX1234/48宽度见v043-mux-sampling-contract.md；安装14160cc6见v043-desktop-waveforms.md，普通读见v043-tail-latency.md。
- **0.4.2正式构建安装及公开发布**：正式源0e82ba6f，Windows/完整Skill/SiteAgent及四固件正式覆盖、签名、三渠道与故障回退验证通过；PR66/67/68已合并，正式资产不可变。安装器元数据修复cb30b703/PR63已纳入。详细计数/SHA见v042-release-handoff.md、installer-metadata-cleanup-20261027.md。后续清理29目录约6.587GiB、629保留文件哈希不变，135含链接组保留人工检查，见v042-postrelease-handoff.md。
- **0.4.2正式候选最终资格**：90e676db与产品1ca9b8fd等价：6453Python/2skip、1182GUI、生产Web/冻结/Rust/NSIS/覆盖及真实界面交互通过。HPM时钟/镜像/RAM/XML/RTT/Watch/串口、Trace独立并行、烧录后三流恢复与原生退出通过。完整计数及限制见v042-formal-qualification.md、v042-traffic-replay.md，历史Trace溢出失败保留。
- **HPM AI Skill能力核实**：源cafe835f：749Python/65GUI、生产Web/浏览器与完整Skill覆盖校验通过，56 MCP/126能力/协议53一致。时钟、离线门禁、探针诊断/供电/ISP/OTP入口和文档已补齐。该轮无USB操作，详见firmware-skill-fixes-20261101.md；后续正式固件范围见发布报告。
- **RTT自动恢复与在线静默收尾**：14417715：347相关+17发现测试通过。V4/HPM5301两次49700B烧录成功，RTT/Watch自动暂停恢复、零恢复错误及零Watch读错；覆盖/载荷/冻结MCP/Web/退出通过。当时为0.4.1测试包，修复后续纳入正式0.4.2。原始包/详细计数见rtt-auto-restore-20261030.md；静默面板d1cf16ec见online-flash-receipt-20261029.md。
- **Linux/macOS 0.4.1测试包**：Linux a6bdacbc、Mac arm64 eefc6842：CI USB各58/1skip及冻结CLI/MCP/健康/Web/退出通过。DEB SHA7309f377、DMG SHA56dc8e0a，均旧0.4.1；Mac ad-hoc未公证，实机安装/UI/USB待测。见linux-deb-test-20261028.md、macos-arm64-test-20261028.md。
- **H743正式固件与双核候选边界**：H743正式V4.7.1在线/四脱机/19采集调试通过。私有V4.7.2单核兼容、双核误选写前拒绝、2MiB不变及M7/M4 HEX在线通过；V4.7.2/V3.6.8/V2.9.3双核候选交付，46回归通过。无双核实板正向脱机，V3历史掉线未闭环，当时候选不公开替换；后来明确发布的四个build以v042-release-handoff.md为准，不外推双核验收。见known-limits-20261030.md。
- **共享RTT/SystemView及480量子**：共享MUX/480/二进制订阅996回归及浏览器、76307模板104回归/真实H7头文件通过。H7八份10MiB全字节核对，新799–801/旧528–633KiB/s，独立SV307134事件和有限共存零计数通过。旧Watch末组失败及饱和丢失保留，不能外推。详见h7-rtt-control-20261031.md、systemview-rtthread-template-20261031.md及known-limits-20261030.md。

## 架构决策

- 0.4.2正式源0e82ba6f/PR66与0.4.1正式源514efb86及所有已发布资产不可变。2026-11-02明确发布授权已完成Windows/完整Skill/SiteAgent、V2.9.3/V3.6.8/普通V4.7.2/HPMLinkV4.7.2的腾讯云/Git发布。用户2026-11-03覆盖旧分支约定：后续多个修复共用codex/v0.4.3-fixes，不直接修改main，不逐任务建分支；后续正式发布须另有明确指令。公网中继延期。
- 后台协议 53：一个 GUI 客户端持有一个固定后台，同窗口切换只改下载器，RTT/Watch/Trace 跟随当前设备并清空旧目标状态；另开客户端才建独立后台。已有 URL 的额外页面共享该后台。工程上下文固定，换工程须停止原后台后重开。
- 物理探针唯一 OS 所有权、USB 身份核对和 epoch 隔离保留。GUI/AI 明确断开或切换自动停止采集、排空在途操作并释放端口；旧会话不得跨设备，未知结果不得自动重放，不偷取其他后台占用。MCP disconnect 物理断开，detach 仅退出自身；独立 UART 保留。
- SuperWatch 变量写入只认写应答，不做自动回读；烧录/显式内存校验仍保留，真实写错误不得吞掉或重放。外设 ID 基于 Pack 版本/芯片/SVD 相对路径；失效选择不得阻断物理连接，无法迁移时重选。 在线型号提供脱机/外设默认值，各页可独立修改；Pack操作完成自动刷新。下载先预留唯一物理身份，不要求先连接目标；自身预留不重建下载表单，其他设备切换仍清理。 HPM SDK的*_svd.xml按CMSIS-SVD支持；九系列共用目录不要求精确型号，精确Pack优先，型号扩展可手动导入XML；SES CPU寄存器XML不作为外设SVD。保留厂家原始字节/许可证及SHA校验。用户允许旧协议清理；在线采样强制MUX能力0x618，禁DMPM/SW01回退，离线旧记录仍可解析。有限dump/HPM Flash回读迁到MUX分块，校验完整才返回；变量MUX写仍限目标RAM且不重发，deadline/取消不发布部分结果。
- 腾讯云优先、GitHub/Gitee备用；上海私有COS签短链，90GiB告警/95GiB锁停，保留累计账本。套餐到期北京时间2026-11-26零点，未核验续费不恢复；监控延迟使阈值非账单上限。只用现有控制台/TAT，不申请私钥/SSH。preview撤下、旧桶获授权清理，香港桶已删除，只留上海；叠加110GB不提高90/95阈值。2026-10-25停止旧Aladdin-Wang GitHub的新发布，保留历史资产；新版本仅MicroKeen GitHub和既有Gitee。旧0.4.0草稿转换未完成，不自动操作。云迁移和Dot确认见v040-release-handoff.md，当前正式版见v042-release-handoff.md。
- 测试直接使用用户原工程及 build/keil/Obj ELF，允许修改且无需备份还原，不复制工程；硬件路径只留本地。HPM 使用 ROM API，不使用 FLM/第二次通用 SWD reset；VCC 每次改动需确认具体电压，固件修改另开会话。 HPM AI可选固件声明的JTAG档位；旧4/10/20/30、新能力14档，默认10MHz。SWD/JTAG配置独立，不声称切换接口或物理测量。固件修复由用户指定会话01a186cd-c52a-7ea0-af29-8de6775d143b负责，用户后续允许提供本会话ID、通知和更新固件；指定会话已协作完成固件测试；明确授权的四个build已发布，见v042-release-handoff.md。后续仍双向核对占用，不自动升级或降级。
- 默认只构建Windows；仅明确要求Linux/macOS时才构建或触发对应原生CI。完整Skill仍须FLM/Pack资格检查。构建使用scripts/build_workspace.ps1和F:/MKLink-Build，保留正式包、唯一证据、依赖与缓存。历史获授权本地Unix清理不影响线上正式附件；过时可再生产物仅依清理授权处理，链接/不可访问目录不强删。 通用请求延迟：每线程HTTP keep-alive按后台instance/port/probe/token隔离，空闲2秒或EOF前置退役，失败绝不重放。路径完全一致时不重复resolve；准入只读活动AXF路径，继续核验目录generation/fingerprint。无批量替代独立请求，无客户专用快照协议，无固件修改。
- 工程上下文固定；物理唯一OS锁/身份/epoch保留。被动枚举不遍历占用设备；普通内存身份检查同活跃CDC最多复用250ms，错误/恢复即失效，生命周期仍全枚举。共享RTT/SV同CB掩码合并、独立有界队列；bit7增量，bit8协商480，短帧含CRC≤512；bit6独立4096读不变，旧量子128。未知操作不重放，失败不自动raw回退，worker退出才关串口，背压/丢失不隐瞒。指定固件会话负责实机，双方协调占用，宿主只导出不可变源码/离线验收；清除临时日志代码，保留移植说明。
- 原MK-Firmware及用户固件工程改动保留，不自动恢复旧备份。2026-10-18授权的0.3.5、V3.6.5/V4.6.9发布已完成；未知操作不重放。用户要求未解决项保留交接，未扩大验收或宣称客户故障已闭环。
- 编译完成不代表目标已下载：文件变化仅发待重载提示，不后台解析。用户明确加载/重载文件时自动停止目标采集，确认worker退出后原子换表，保持停止；失败保留旧目录/选择。不要求连接下载器；断开保留文件和选中变量但清空旧采样。公式只改变可视化，原始记录不变；不恢复旧地址采集或重放写操作。

## 真机环境

- **state**：普通V4 USB7源465a9b69/H743映像77e05091不变；30MHz/4us采样，只改TIM7 ARR39/99并回读，最终99。流已停止并断开，内置浏览器保留RAM100us真实记录的离线回放；GUI后台可仍有租约但不持有探针，操作前重核占用。20us/长期资格未达，USB背压未证实。
- **installer**：本机Windows已覆盖为0.4.3本地未签名测试版，源14160cc6，NSIS SHA2fb705ce，安装/载荷/冻结MCP/Web/正常退出通过；正式0.4.2资产保留不变。全局Skill及独立SiteAgent仍0.4.2，未覆盖。没有合并/签名/发布。
- **backups**：保留正式包/七资产/四固件、CI ZIP、唯一验收证据、Skill备份、缓存及旧detached树。29目录清理/135含链接组人工检查清单见v042-postrelease-handoff.md及本机v042-postrelease-handoff-20261102/START_HERE.txt。

## 下一动作

1. 继续codex/v0.4.3-fixes/草稿PR69。安装版仍14160cc6，本轮Web试构建仅F盘。普通读P95/间隔<1ms、采样最大间隔<20us仍开放；合并/签名/正式发布须新授权。
2. GPIO搜索阻塞/队列删除已修复；内置浏览器补齐PNG。原始MUX确认127点批边界，普通批间PE2/RAM中位22/21us，四组峰值在ECHO回复附近。固件会话01a1a1a2-9adc-79e2-b30e-07c07d5f90c6继续分析调度/热点布局；不停心跳、不改目标迁就采集、不自动刷固件，见v043-iab-waveforms.md。
3. 保留正式包、唯一验收证据及含链接目录；本机新START_HERE与v042-postrelease-handoff.md记录清理清单和接手入口。历史V3掉线/冷插拔/长稳等仍按known-limits-20261030.md和最终资格报告处理。
4. 监控上海90GiB告警/95GiB停止，套餐截止北京时间2026-11-26 00:00。未核验续费不清除停止锁、不清零账本、不申请新私钥。

## 已知限制

- 新MUX整块读普通V4/H7已实测，V3/H7指定会话候选复测通过；HPM本轮映像回读及480B RAM核对通过，未扩全内存区矩阵。安装后20次调用仍有明显调度抖动，前次dce包4KiB最大39.074ms，不承诺固定低延迟。HPM九系列XML已解析/匹配/浏览器导入；用户接回HPM5301后的六GPIO寄存器实读/采集通过，其他系列及IO输出驱动未测；客户F411仍待实板复测。dump定时截止可留半个样本，完整性门槛保留。HPM CPU仅RV32/hart0/HPM5301/槽0实测，其他触发器/型号、新值写入、20/30MHz及断电冷启未扩展，TCK未测。374个历史probe目录启动扫描慢未修复；4551687d仅修复端口复用时HTTP异常中止发现，已含e29d候选，见runtime-endpoint-errors-20261030.md。客户3.11.9、CDC首次离线、F405 PROGRAM100%退出、GD32受限AI、RTT后MUX、HEX2%未知结果及PyInstaller权限故障保持未闭环，详见known-limits-20261030.md及v032-postrelease-incidents.md；不重放未知操作。 旧dce/4be FPBv2曾422，新包已含修复；7843双半字命中及Keil共存已验。采集中共享断点仍409；V2本轮共享step已实测，其他型号不由Keil单步替代验收；见h7-fpbv2-systemview-idle-20261031.md。
- 30MHz RTT/Watch/UART并行历史存在目标读错：V4.6.8 1kHz +1/最大+273，10MHz0；V4.7.0/F103先Watch后RTT11762周期1错、反顺序12297周期0，10MHz两顺序0。发布接受不等于问题关闭，完整记录见known-limits-20261030.md。
- HPM/SES未发DAP_Disconnect可遗留占用；显式退出后OpenOCD init/resume/shutdown或用户拔插可恢复，超时不得偷占。完整SES矩阵/RTT下行未覆盖。RTT status6截图只证busy，不推断与历史故障同因，待现场时序/显式重试。
- 共享MUX并行SV仍有容量边界：旧饱和768/drop17371，流水线28/1330、burst26/1164、control15/1442，重启归零不抹去；control独立62.679秒零丢失计数通过。RTT661.208KiB/s为特定配置观测值，H7限定实测新799–801KiB/s、独立/有限并行SV零计数；单次API20样本中位有12.90→20.03ms等退化未归因，旧Watch末组失败保留。采集暂停/下载丢观测、多变量非原子、无时序保证。COS95GiB非账单上限，存储/请求/SCF另计；旧0.4.0固件Git备用未迁，签名资产不改。
- V3无屏幕且不支持HPM；V3.6.4 Keil/OpenOCD共存已测。V4最终无诊断固件完整SES矩阵未完成。旧V3.6.8/build17:56:49的CRLF六轮及1800.028秒空RTT证据见v3-crlf-final-review-20261030.md和v3-empty-rtt-review-20261030.md，不计入新build11:00:39复验。新V3限定RTT/FPB/Keil通过见v3-rtt-systemview-review-20261031.md；历史掉线根因、legacy/睡眠拔插/更长时长仍未测，再现先保存现场。 旧1ms Watch相位跳变归因未闭环；本轮HPM5301周期矩阵已通过，不能外推历史全部场景。
- 最后客户端退出约5秒租约后开始排空/关闭，不保证硬实时5秒。每GUI独立后台；单探针仅一个后台持有；已有URL共享页面跟随明确切换。独立操作另开客户端。 Keil BL重载由2增9；用户确认未操作，原因未明。仅恢复重载后9个状态，最初配置未恢复；见h7-fpbv2-systemview-idle-20261031.md。
- UART5 TTL Modbus历史读写通过，RS485电气层未测；本次仅虚拟串口双向字节/日志，不能替代物理UART。跨主机Agent/全芯片未认证。Unix包仅CI冻结检查，USB/原生UI/升级待测；Mac ad-hoc未公证，Windows无Authenticode，不承诺消除SmartScreen。日志文件回放与原生目录现已通过；Trace最终独立/并行各三轮零新增丢失通过，历史初始溢出1保留且不外推全部负载；HPM HardFault页面仍限Cortex-M。早期浏览器清理未确认的现场记录保留；本轮官网下载验收通过。详见v042-traffic-replay.md。
- nRF54L15保护闭环、全部擦除/拔插/休眠/断电、电源精度未全测。每次VCC需确认具体电压。26个无可靠扇区FLM禁用扇区操作，Bank模式须匹配。HPM5301 OTP组18/19历史永久锁定；128字读取及批准Word69 0→1已实测，其余型号/区域不继承授权，锁最后写/逐项校验，多Word不可回滚；熔丝/影子/临时锁语义未知，UART按ROM状态及回读为准。详见hpm-offline-otp-handoff.md及known-limits-20261030.md。

## 延续协议

- 后续多个修复共用codex/v0.4.3-fixes，先fetch核对实际状态；不直接修改main，不逐任务另建分支，不自动切回main。旧v0.4.2分支及两个detached工作树保留。0.4.2正式源0e82ba6f和全部已发布资产不可覆盖。
- 正式资格/渠道仍以v042-formal-qualification.md和v042-release-handoff.md为准；本机0.4.3安装源14160cc6未更新，最新源码Web/40与100us复验见v043-iab-waveforms.md。设备已断开，内置浏览器仅回放；操作前重核占用。
- V2 RBL更新见v035-v2-rbl-update.md，用户回退2.8后真实升级2.9已经通过；最终应用2f474f60与Skill已同步。V3.6.5/V4.6.9本轮仅发布原始UF2并验证公开文件，未再次刷入实体探针，不重复升级或回退。
- CDC995和SDK10048根因保留待排查。恢复仅同身份CDC故障5秒内；超时不自动接回/新建AI会话，主动断开立即生效，未知写入不重放。历史实例释放记录见v035-transport-recovery.md；当前硬件占用以本交接真机状态及指定固件会话为准。
- 客户启动故障仅确认PyInstaller解压ucrtbase.dll时Permission denied，重启后恢复；未定位权限/杀软/占用的具体来源，按用户意见暂不做推测性修复。若再现，结合新startup/runtime日志复查。
