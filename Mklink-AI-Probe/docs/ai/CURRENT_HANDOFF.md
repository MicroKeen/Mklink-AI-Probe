# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-10-19T16:47:34+08:00`
- 分支：`codex/0.3.6-fixes`
- HEAD：`SuperWatch修复1669348b；RTT修复5bd50041；记忆提交以git log为准。`
- 远端 HEAD：`microkeen/codex/0.3.6-fixes已推送1669348b；PR46待审核，未合并main。`
- 工作树：仅使用 E:/software/HPM5300/Mklink-AI-Probe，源码在其 Mklink-AI-Probe 子目录；当前为 codex/0.3.6-fixes。旧0.3.5修复工作区已移除，不重建。
- 当前任务：0.3.6 RTT与SuperWatch改进已推送PR46。RTT终端按通道跳过收发解析、严格十进制CSV已完成。SuperWatch桌面本机直接原生选目录，允许采集前启用记录并显示等待数据；222 Python/138 GUI及原生构建通过。原生弹窗和取消已验证，完整确认目录链被QMCapture覆盖阻挡，需补验。详见v036-rtt-hex-fix.md和v036-superwatch-recording.md；未安装/合并/发布。
- 状态：`complete`

## 里程碑

- **0.3.5正式版** — `complete`。PR43合并源2f474f60372e。Windows/Skill/三平台/SiteAgent与17附件、5签名、3渠道通过；全局Skill同步、原生退出资源释放。V3.6.5/V4.6.9独立发布。详见v035-release-handoff.md和v035-probe-firmware.md。
- **0.3.4正式版** — `complete`。不可变源a8fd3fab0403，PR40正式发布；PR41已保存正式Web/交接，合并提交185678c59623。17附件、5份验签、3渠道及实装/Skill通过。07846c1a记录后续清理完成，本次补入0.3.5；见v034-release-handoff.md及v034-workspace-cleanup.md。
- **0.3.3正式版** — `complete`。源11616f80，PR38；Windows/ARM/Linux/Intel包、五份签名、三渠道核对和本地Skill更新完成。正式归档已回原工作空间；见v033-release-handoff.md。
- **0.3.2正式版** — `complete`。源3d511e94，PR35/36；三平台原生构建38028928283。Windows实装、五份更新验签、三个渠道已核对，见v032-release-handoff.md。
- **0.3.1正式版** — `complete`。PR33合并，源1d61159d；签名NSIS/Skill/SiteAgent与三端索引完成，最终提取包检查通过。见v031-release-handoff.md。
- **0.3.0及2026-10-09固件归档** — `complete`。0.3.0发布及2026-10-09固件记录见历史交接和固件归档；不继承其硬件验收结论。

## 验证证据

- **0.3.6 RTT与SuperWatch日志**：1669348b/PR46：SuperWatch222 Python、4文件138 GUI、边界/记忆59通过，TS/Vite/Rust release exe成功。真实Windows源码候选直接弹出原生目录框，取消后idle；完整目录确认链被QMCapture64覆盖拦住，未碰截图工具，已仅结束测试实例。预先记录→真实manager采集→首样本落盘由DumpMemory夹具验证。RTT5bd50041：376通过/1跳过、扩展266通过（重叠），GUI85，Chrome终端零解析及多通道切换通过；旧头三个CI成功。新头CI待结果；未客户板/安装/发布。见两份v036验证报告，早前Pack见v035-peripheral-import.md。
- **0.3.5正式发布**：Python全量4926通过/2跳过/1旧Skill断言失败，修正后相关68通过；GUI94文件985通过和生产构建通过。最终源2f474f60 Windows实装198Python/40Web/四载荷、全局Skill2605文件、冻结CLI/MCP/Web与原生退出通过；SiteAgent实际包2项通过。原生CI39116320413三平台资格/归档digest通过，5签名、双GitHub17附件匿名hash、3索引与真实Gitee Skill回退通过。安装后F103八路RTT连续及各256B下行、UART109条连续及256B下行、5034行按需记录通过。文件选择器超时边界及未解清单见v035-release-handoff.md。
- **0.3.5 V2 RBL 自动升级**：V2独立索引双GitHub发布，旧UF2索引不变；用户回退后生产Web真实2.8→2.9升级。核心158/CLI相关127/V2专项29/GUI62及TS/Vite通过，组间重叠不相加。5be3dcf7 NSIS覆盖退出0，198Python/40Web/四载荷一致；Skill2605文件及CLI/SVD/MCP通过。安装Web、冻结/Skill实际MCP与CLI同版检查一致，F103 CPUID正确，已detach释放探针。原生正常关闭后进程/端点/端口全部释放；见v035-v2-rbl-update.md。
- **0.3.5 五秒意外断链恢复**：925cadc8/生产Web cb1223d2：最终恢复/重连49项、共享运行时133项及GUI54项通过。NSIS实装退出0，197Python/40Web/四载荷一致，Skill2604文件及CLI/SVD/MCP通过。V3.6.5/F103快拔插约3.1秒恢复RTT/SuperWatch、原冻结MCP会话CPUID正确；超时约5秒进入expired，晚插回保持断开，旧MCP不重附着。显式Web连接后采集保持停止，Skill CLI读数正确；用户关闭后进程/端点/端口释放。见v035-transport-recovery.md；旧995根因仍待排查。
- **0.3.5 手动符号重载与发布准备**：e577：GUI94文件978项及TS/Vite通过；Python全量4877通过、1交接条目预算失败、2可选跳过，预算修正后2项复验通过。NSIS覆盖退出0，196Python/40Web/4载荷一致；Skill2603文件及冻结/Skill CLI/SVD/MCP/HTTP通过。Keil原工程编译下载Verify OK；实际编译只提示，显式重载generation1→2零读错；CH0 ls15次完整、CH1 129行连续和256字节下行通过；UART两档各300帧序号CRC及256字节下行一致，首F0/FE另列未解。记录4957样本，原生原图播放/暂停/缩放、436209字节PNG通过。三平台native CI39002623711及独立SiteAgent包资格通过。正常退出全部资源释放，见v035-release-preparation.md。
- **0.3.5 串口文本续行**：100相关测试、TS/Vite通过；d9ac3a26 NSIS实装、196Python/40Web/四载荷一致，冻结CLI/SVD/MCP/HTTP通过；Skill 2d029f18的2603文件及CLI/SVD/MCP通过。Chrome实机周期文本完整，六段发送恢复三行，跨批次CRLF/UTF-8正确。原生导出49字节与输入逐字节一致。原生窗口正常关闭，全部MKLink进程、endpoint及8765/8766端口释放。2d029f18三个CI成功。详见v035-serial-lines.md。
- **0.3.5 串口即时显示与 MSH 安装实测**：串口Worker/页面89、RTT页面/终端69、相关后端372通过，TS/Vite通过。NSIS提取/实装196Python/40Web、四载荷、Windows-only CLI/SVD/MCP/HTTP通过，Skill2603文件匹配。安装F103 ls三尾端15次与Chrome整条/逐键完整，CH1 256字节校验/120周期连续；UART115200下1000帧、38400下300帧序号CRC一致，两轮反向256字节一致。重新配置UART后首帧前各有一个额外字节单列保留；Chrome无换行7字节即时显示，最终导出文件恰好4f4b000a0dfeff共7字节；原生关闭后全部进程/endpoint及8765/8766释放。Skill/冻结CLI/MCP目标回显与UART累计校验一致。026b0bf3三CI通过。详见v035-serial-immediate.md。
- **0.3.5 连接、RTT重载及下载流程**：拔插自动连接332 Python/89 GUI及用户实际换探针通过；RTT通道/显式符号重载490 Python/102 GUI及原工程Keil下载后实机通过，详见v035-auto-connect.md、v035-rtt-symbol-reload.md。最新下载免预连接/型号同步301 Python、185 GUI、TS/Vite通过；Chrome未连接时识别USB卷及算法，在线直接读取Flash64字节并保留结果；型号默认/独立修改及真实Pack导入后目录自动更新通过。未执行烧录，历史unknown仍保留。见v035-download-target-sync.md。

## 架构决策

- 0.3.5已经完成正式发布，源2f474f60372e及标签不可变；发布后正式Web/交接另经PR合入。新修改从最新microkeen/main创建codex/任务分支，保留必需CI、精确PR头和指定整合者边界；本轮授权不自动延伸到新版本发布。
- 后台协议 52：一个 GUI 客户端持有一个固定后台，同窗口切换只改下载器，RTT/Watch/Trace 跟随当前设备并清空旧目标状态；另开客户端才建独立后台。已有 URL 的额外页面共享该后台。工程上下文固定，换工程须停止原后台后重开。
- 物理探针唯一 OS 所有权、USB 身份核对和 epoch 隔离保留。GUI/AI 明确断开或切换自动停止采集、排空在途操作并释放端口；旧会话不得跨设备，未知结果不得自动重放，不偷取其他后台占用。MCP disconnect 物理断开，detach 仅退出自身；独立 UART 保留。
- SuperWatch 变量写入只认写应答，不做自动回读；烧录/显式内存校验仍保留，真实写错误不得吞掉或重放。外设 ID 基于 Pack 版本/芯片/SVD 相对路径；失效选择不得阻断物理连接，无法迁移时重选。 在线型号提供脱机/外设默认值，各页可独立修改；Pack操作完成自动刷新。下载先预留唯一物理身份，不要求先连接目标；自身预留不重建下载表单，其他设备切换仍清理。
- 应用主索引 MicroKeen/release，旧 GitHub/updates 和 Gitee/updates 兼容，固件使用独立索引。Gitee 仅要求 Windows 与 Skill；本次 Windows 超 100MB 被拒，索引指向 GitHub；Skill 已真实镜像，GitHub 不可达回退实测通过。其他平台仅 GitHub。
- 测试直接使用用户原工程及 build/keil/Obj ELF，允许修改且无需备份还原，不复制工程；硬件路径只留本地。HPM 使用 ROM API，不使用 FLM/第二次通用 SWD reset；VCC 每次改动需确认具体电压，固件修改另开会话。
- 构建使用scripts/build_workspace.ps1与F:/MKLink-Build，保留正式包、独有证据、依赖和缓存；联接或不可访问路径不强删。0.3.5清理已完成，仅保留原Mklink-AI-Probe工作区；历史联接run清单保存在构建根reports，不沿用旧清理任务。长期硬件跟进仍暂停，不因交接自动接管硬件或重复发布。
- 工程上下文固定于后台生命周期；被动MI_04枚举不遍历占用设备，底层自动连接只接受唯一候选；本机别名不写固件。未知结果不重放，worker实际退出后才发布串口关闭，取消前保留缓冲寿命，背压错误不隐瞒。
- 原MK-Firmware及用户固件工程改动保留，不自动恢复旧备份。2026-10-18授权的0.3.5、V3.6.5/V4.6.9发布已完成；未知操作不重放。用户要求未解决项保留交接，未扩大验收或宣称客户故障已闭环。
- 编译完成不代表目标已下载：所有稳定文件变化（包括地址不变/仅时间戳）仅发待重载事件，不后台解析或应用。SuperWatch每次变化弹窗一次，稍后保留顶部醒目按钮。用户明确重新加载后才执行共享符号迁移和采集恢复；用户主动停止不恢复。

## 真机环境

- **state**：最终安装版实机测试已停止，AI detach、设备释放；用户正常关闭原生窗口后进程/端点/监听端口均0。现为V2.9.0/F103八RTT通道测试程序，沿用板上固件并做AXF代码片段比对。
- **installer**：正式2f474f60签名NSIS已覆盖安装；Skill2605文件与正式ZIP一致，CLI/SVD/MCP通过；需要重启AI加载更新。证据在MKLINK_BUILD_ROOT/artifacts/v035-official，旧Skill备份保留。
- **backups**：0.3.4正式包/安装/渠道/Skill/HIL在MKLINK_BUILD_ROOT/artifacts/v034-official，相邻v034-official-native保存完整原生CI ZIP；0.3.5本机包见上述构建根。原Git根.build/artifacts/v033-official、v032-official及用户备份保持；清理前快照/删除清单在构建根reports/v034-cleanup-*.json、v034-deleted-branches.json、v034-memory-before-cleanup.json。不能再把F盘仅视为可删缓存。

## 下一动作

1. 审核PR46最终头及CI；补SuperWatch原生选目录确认→等待数据→停止完整链（弹窗/取消已过，QMCapture覆盖阻挡后续）。客户板RTT待复验；两修复见v036-rtt-hex-fix.md/v036-superwatch-recording.md。合并/安装/发布另需授权，不移动0.3.5标签。
2. 收集两位 RTT 客户的上位机/下载器固件版本、目标 ELF/芯片及 IDE 占用，用启动阶段耗时和 MUX 请求身份复核。历史 unknown 操作不得重放；原始 CDC/F405/受限 AI/GD32 仍待现场闭环。
3. 继续排查 30MHz 并行目标读错/Flash 偶发 status5，区分固件目标访问与主机队列；本次低负载 F103 结果不关闭该限制，需要固件改动另开会话。
4. 保持Gitee真实Skill回退：0.3.5已验证；Windows超过100MB被拒使用GitHub链接，其余平台仅GitHub。保留唯一发布/验收证据和Skill备份，联接run仅人工处理，不强删。
5. 收集 Mac/Linux USB/MSC 和原地升级反馈、外置 Flash 多算法实物验证；完整 SES/芯片/拔插断电组合仍待补充。供电每次确认具体电压，长期验证仍暂停。

## 已知限制

- 0.3.5时钟修复已通过偏差注入及本地Windows3.11/3.14实机短测；客户3.11.9原电脑仍待升级确认。原始CDC首次离线/F405 PROGRAM100%后退出、受限AI/GD32及RTT客户后续MUX超时仍未闭环；不宣称同一根因或任意负载无损。历史unknown操作不得重放。 位域当前仅little-endian、只读；曲线Float32对大整数有舍入。真实ELF只离线回放，F103使用专门测试固件；未把客户固件烧到该板。 原0.3.2故障链见docs/verification/v032-postrelease-incidents.md；CDC传输错误、目标status5与本次DLL解压拒绝不混为同一根因，不靠清空用户配置或全杀后台掩盖原因。 本轮后台HEX下载2% Failed to write file,addr:0x2000，unknown未重放；用户Keil下载后仅重载验证成功，下载故障仍待另案排查。
- V4.6.8 30MHz RTT8/Watch4/UART并行目标读错1kHz +1、最大+273；10MHz0。旧V4.6.6原始+1/+224，报告此前漏记已更正。采集不停止、不误断、UART完整；用户明确继续发布，限制交接下版处理，不写公开发布说明。
- HPM/SES退出未发送DAP_Disconnect时可遗留占用，后续legacy握手等待；明确退出后正常OpenOCD init/resume/shutdown可恢复，用户可重插USB。禁止任意超时偷取调试所有权。完整SES矩阵和RTT下行未全部覆盖；V3.6.4/V4.6.8仿真中新启采集及负载读回通过，V4.6.8已完成Keil及相关矩阵。详见release handoff；长期目标暂停。 2026-10-17新增RTT status6截图仅证下载器忙返回；用户不清楚IDE占用/固件版本，不能认定与历史问题同因，待现场时序和显式重试结果。
- 性能和功能证据按docs/verification/v030-release-handoff.md及各精确提交报告解释：采集不是无损通道，缓冲溢出/暂停/调试下载可能丢失观测；多变量不是原子快照，不能保证任意时序上界。
- V3无屏幕、不支持HPM；V3.6.4原生Keil先运行再采集、暂停/单步/继续/退出和OpenOCD均通过。V4最终无诊断固件完整SES矩阵未完成。
- 后台最后会话释放约5秒租约，加排空和退出开销；不保证硬实时5秒。每个GUI客户端一个后台，同窗口切换固定PID/端口；一个物理探针在任一时刻仅由一个后台独占。打开已有URL的额外页面共享当前后台并跟随明确切换；独立操作应启动新客户端。
- 跨物理主机Agent、真实Modbus从站及全部芯片组合未完整认证，模拟测试不能替代实体。0.3.5最终独立Windows Site Agent已重新构建并通过两项实际包资格检查；macOS Intel/ARM和Linux原生CI包构建/冻结运行/载荷检查通过，但实体USB/MSC、原生GUI、签名升级未认证。Mac仅ad-hoc无Developer ID公证，Windows无Authenticode。Web真实文件句柄选择/跟踪未完成；新候选原生日志文件选择、回放和PNG已通过。
- nRF54L15 GUI保护闭环、全部物理擦除/拔插/休眠/断电场景、电源外部精度校准未全部认证。VCC每次改动必须确认具体电压，HPM已锁定OTP不得重放。 已知无可靠扇区表的26个FLM禁用扇区操作；重叠算法需要匹配Bank模式。 HPM5301组18/19永久锁定的历史状态及用户字先写/组锁最后、全部固件独立校验后才写OTP等边界见docs/ai/hpm-offline-otp-handoff.md；接手重新确认芯片，其他型号不继承验收。

## 延续协议

- 读取唯一工作区AGENTS.md、本交接及两份v036报告，validate并核对状态；PR46已推送1669348b及记忆，保留本分支。现有安装版窗口未操作，测试候选已结束；离线夹具不继承硬件结论，不重建旧工作区。
- V2 RBL更新见v035-v2-rbl-update.md，用户回退2.8后真实升级2.9已经通过；最终应用2f474f60与Skill已同步。V3.6.5/V4.6.9本轮仅发布原始UF2并验证公开文件，未再次刷入实体探针，不重复升级或回退。
- CDC 995根因仅保留待排查。恢复只允许同身份CDC故障5秒内；超时不自动接回或新建AI会话，主动断开立即生效，不重放未知写入。测试实例已经全部释放；见v035-transport-recovery.md，不寻找旧现场窗口。
- 客户启动故障仅确认PyInstaller解压ucrtbase.dll时Permission denied，重启后恢复；未定位权限/杀软/占用的具体来源，按用户意见暂不做推测性修复。若再现，结合新startup/runtime日志复查。
- 2026-10-18授权的验收与发布已完成，已知未解项交接保留；正式源2f474f60。发布后交接/正式Web通过独立PR保存，标签不动；敏感日志和本机硬件路径不提交。
