# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-10-24T20:09:18.2128716+08:00`
- 分支：`codex/tencent-update-preview`
- HEAD：`基于main 303a2667开发腾讯云独立测试更新；精确源码见Git HEAD。`
- 远端 HEAD：`PR42/46/48/49均已合并；main 303a2667，正式release/firmware引用未变。`
- 工作树：唯一原工作区及源码子目录保留；测试/构建证据位于F盘。
- 当前任务：用户要求启动画面取消勾选及阶段文字：改为30/60/90/100进度条，按并行前置任务完成及首屏绘制推进，延迟不虚增；失败仍显示错误与重试，切换下载器提示保留。7项启动回归、TS/Vite生产构建、浏览器60%视觉预览通过，gui/dist已同步。本轮仅UI源码/Web资源，未重新打包或覆盖安装；当前实装仍为86f9a75d，既有性能与冻结资格见v036-desktop-startup.md。
- 状态：`complete`

## 里程碑

- **0.3.5正式版** — `complete`。PR43合并源2f474f60372e。Windows/Skill/三平台/SiteAgent与17附件、5签名、3渠道通过；全局Skill同步、原生退出资源释放。V3.6.5/V4.6.9独立发布。详见v035-release-handoff.md和v035-probe-firmware.md。
- **0.3.4正式版** — `complete`。不可变源a8fd3fab0403，PR40正式发布；PR41已保存正式Web/交接，合并提交185678c59623。17附件、5份验签、3渠道及实装/Skill通过。07846c1a记录后续清理完成，本次补入0.3.5；见v034-release-handoff.md及v034-workspace-cleanup.md。
- **0.3.3正式版** — `complete`。源11616f80，PR38；Windows/ARM/Linux/Intel包、五份签名、三渠道核对和本地Skill更新完成。正式归档已回原工作空间；见v033-release-handoff.md。
- **0.3.2正式版** — `complete`。源3d511e94，PR35/36；三平台原生构建38028928283。Windows实装、五份更新验签、三个渠道已核对，见v032-release-handoff.md。
- **0.3.1正式版** — `complete`。PR33合并，源1d61159d；签名NSIS/Skill/SiteAgent与三端索引完成，最终提取包检查通过。见v031-release-handoff.md。
- **0.3.0及2026-10-09固件归档** — `complete`。0.3.0发布及2026-10-09固件记录见历史交接和固件归档；不继承其硬件验收结论。

## 验证证据

- **腾讯云下载与更新通道接入**：源码5920c5c5；全Python5412通过2跳过、GUI1090和96项定点通过，CI三项通过；Windows签名、完整FLM/Packs、解包与实装206Python/41Web冻结资格通过。公网安装包8.17秒21.87MiB/s，Skill3.93秒23.94MiB/s；完整SHA/Range通过。Skill真实0.3.5到0.3.6升级2617文件一致、用户文件保留、二次无更新、MCP模糊搜索20候选。GitHub/Gitee实际索引及Gitee完整包通过，无降级。首次UAC未完成；用户要求重试后原生较低版本下载/验签/安装/自动重启成功，启动检查无重复更新或错误提示。临时SSH撤销并验证拒绝，stable404，正式引用未变。详见docs/verification/v036-tencent-preview-20261024.md。
- **0.3.6四PR整合与发布前资格**：源码f20fe781；5404Python/2skip、1090GUI、生产构建；Windows覆盖exit0、206Python/41Web/4载荷、离线完整Skill7059目标/2224FLM/4800外设通过。实机Flash全回读/RTT8/Watch/UART5/TTLModbus/VOFA/SystemView/HardFault/共享MCP及浏览器和原生文件选择通过。30MHz一顺序1读错，10MHz0。详见docs/verification/v036-prerelease-20261024.md。
- **SuperWatch离线文件与公式颜色**：SuperWatch离线解析/重载先停采集、断开保留变量与数组选择；增加单曲线公式/颜色与快捷合并。源870471b6，组合e7c49b04/Web bcdc8474，188Python、1083全GUI及末次189GUI/TS/Vite通过。真实浏览器离线1480变量、公式x/1000、颜色与合并通过；0.3.6安装包SHA256 818035c005e02978b0729facd7cafcfba91babc659aa209e6bbc6409495b202b。首次UAC取消，用户要求重试后管理员覆盖exit0，解包/实装206Python/41Web与公式静态模块、冻结MCP/SVD/HTTP/离线功能及原生Web/退出通过。未操作硬件或更新固件/全局Skill。见v036-superwatch-formulas.md。
- **新连接RTT搜索与采集顺序**：修复刚连接RTT搜索未准备MUX的问题，搜索/启动统一通道且保留旧ARM文本读取。462Python、70GUI、TS/Vite通过；原V4+HPM5301源码及实装新连接、两启动顺序、活动搜索和独立重启通过，四组实装读错/丢样0。0.3.6 ef51d4d3/Web5aeb2da2管理员覆盖exit0、冻结/原生/真实网页验收通过，已重新打开。V2/V3及ARM仅协议回归，未换板实测。见v036-rtt-discovery.md。
- **HPM JTAG实时换板与单次配置**：c963982c/9442e5b5，332定点Python、53GUI、TS/Vite及真实网页通过。固件7d21040的44回归/Pika/双构建通过并升级一次；只读拔插及时报告且用户确认LCD，第二轮240秒858次0/1522有效ID。首次断开后-4导致采集断言退出，主机补有限重试并保留证据。最终d0b662b9包SHA256 72274ecca51ea790beac8e15a06c24042a42faefb60a5875d41a2c59b99fdc1a，覆盖exit0、解包/实装206Python/41Web/四载荷/冻结MCP-SVD-HTTP/无宿主Python/正常退出通过；解包首次HTTP超时原包重跑通过。原生与安装网页正常。完整实体连续Flash未做。见v036-hpm-jtag-cycles.md。 用户后续要求本地Skill同步：已由0.3.5更新为与安装包一致的d0b662b9/0.3.6，2615文件逐字节/生产Web一致、5339本地配置缓存保留、离线CLI/SVD和实际stdio MCP通过；备份与报告在构建根artifacts/v036-local-skill-d0b662b9，无硬件操作。
- **RTT与SuperWatch启动顺序及覆盖安装**：77f0f004缓存能力查询，445Python/TS/Vite通过；组合a8a5dfad/Web f579b0c4，NSIS SHA256 90361fe45063167cad76cba2b3b46e574b1390f600aaabb0de3d7834924c6395。管理员覆盖exit0，解包/实装206Python/41Web/四载荷及冻结CLI/MCP/SVD/HTTP/后台正常退出通过。原V4+HPM5301在30MHz、RTT0/1+Watch10ms，两顺序各新连接及逐项停止重开通过；安装观察265/283组、无读错/丢样，网页约88Hz与RTT文本正常。详见v036-capture-start-order.md。
- **合并HEX及0.3.6安装包**：6c2095c7自定义FLM几何修复；388Python/5GUI/真实浏览器通过。两种算法组合均正确映射外部4MiB+内部4588B，1027扇区；实体N32未写。集成f4221d96（Web d7d2db3d）NSIS SHA256 82f95c6310507fbe832b6749f3752e26be7af07384034f0f66ab80765e404cf7，管理员覆盖exit0、解包与实装冻结运行通过；两条简短版本说明已验证。见v036-combined-hex-fix.md。
- **在线烧录100%停顿诊断**：35f7da59：391测试含真实pyOCD构建器模拟目标、多Bank稀疏HEX/单双缓冲/失败清理；唯一授权源JobManager实烧通过，写入阶段7.892→5.595s，PROGRAM100%仅一次到完成0.796ms，完整回读通过。初始UnInit推断已纠正。详见v036-online-program-progress-diagnosis.md；已包含f4221d96安装包并覆盖验证。

## 架构决策

- 0.3.5已经完成正式发布，源2f474f60372e及标签不可变；发布后正式Web/交接另经PR合入。新修改从最新microkeen/main创建codex/任务分支，保留必需CI、精确PR头和指定整合者边界；本轮授权不自动延伸到新版本发布。
- 后台协议 52：一个 GUI 客户端持有一个固定后台，同窗口切换只改下载器，RTT/Watch/Trace 跟随当前设备并清空旧目标状态；另开客户端才建独立后台。已有 URL 的额外页面共享该后台。工程上下文固定，换工程须停止原后台后重开。
- 物理探针唯一 OS 所有权、USB 身份核对和 epoch 隔离保留。GUI/AI 明确断开或切换自动停止采集、排空在途操作并释放端口；旧会话不得跨设备，未知结果不得自动重放，不偷取其他后台占用。MCP disconnect 物理断开，detach 仅退出自身；独立 UART 保留。
- SuperWatch 变量写入只认写应答，不做自动回读；烧录/显式内存校验仍保留，真实写错误不得吞掉或重放。外设 ID 基于 Pack 版本/芯片/SVD 相对路径；失效选择不得阻断物理连接，无法迁移时重选。 在线型号提供脱机/外设默认值，各页可独立修改；Pack操作完成自动刷新。下载先预留唯一物理身份，不要求先连接目标；自身预留不重建下载表单，其他设备切换仍清理。
- 用户2026-10-24要求腾讯云download.microkeenai.com优先，GitHub release与Gitee updates备用。本次仅/mklink/preview/latest.json测试发布，/mklink/stable/latest.json及GitHub/Gitee正式索引不得更新，不创建正式标签。桌面--preview-updates显式构建；Skill进程MKLINK_UPDATE_CHANNEL=preview，缓存按有序URL隔离。固件索引独立不迁移。
- 测试直接使用用户原工程及 build/keil/Obj ELF，允许修改且无需备份还原，不复制工程；硬件路径只留本地。HPM 使用 ROM API，不使用 FLM/第二次通用 SWD reset；VCC 每次改动需确认具体电压，固件修改另开会话。
- 用户2026-10-24明确长期规则：默认只构建Windows安装包；仅在用户明确要求Linux/macOS时才构建对应安装包或触发原生CI，一般构建、全功能验收及发布请求不包含它们。用户Skill仍需完整FLM/Pack资格检查。历史Linux/macOS本地构建包已按用户要求清理，保留日志与验收证据；用户明确保留GitHub已正式发布附件。 构建使用scripts/build_workspace.ps1与F:/MKLink-Build，保留正式包、独有证据和依赖。用户明确清理授权下可删除过时可再生编译输出，链接/不可访问目录交人工处理，不强删。唯一原工作区保持；清理不接管硬件、不重复发布。
- 工程上下文固定于后台生命周期；被动MI_04枚举不遍历占用设备，底层自动连接只接受唯一候选；本机别名不写固件。未知结果不重放，worker实际退出后才发布串口关闭，取消前保留缓冲寿命，背压错误不隐瞒。
- 原MK-Firmware及用户固件工程改动保留，不自动恢复旧备份。2026-10-18授权的0.3.5、V3.6.5/V4.6.9发布已完成；未知操作不重放。用户要求未解决项保留交接，未扩大验收或宣称客户故障已闭环。
- 编译完成不代表目标已下载：文件变化仅发待重载提示，不后台解析。用户明确加载/重载文件时自动停止目标采集，确认worker退出后原子换表，保持停止；失败保留旧目录/选择。不要求连接下载器；断开保留文件和选中变量但清空旧采样。公式只改变可视化，原始记录不变；不恢复旧地址采集或重放写操作。

## 真机环境

- **state**：V4.7.0+STM32F103RE512KiB/UART5实测；当前DAP缺GUID经用户批准定点修复后Keil/pyOCD枚举正常。测试固件保留SystemView CH2/UART5/RTT0和1/PID；无OTP、供电或探针固件变更。全部测试进程正常退出，30MHz1读错保留。
- **installer**：本地preview源86f9a75d覆盖exit0，SHA256 a8805b05aa38ca4cc405b5529baf71cf14447970919dacba5b0f4c740ec1d514；3623文件一致，冻结MCP/FLM/SVD/健康/ZIP/Web/正常退出通过。原生ZIP含2条正常启动记录；真实阶段提示、首屏计时及端口释放已验收。原生健康2.746s、首屏2.582s；后台三次中位数1.441s。见v036-desktop-startup.md；腾讯云线上仍为5920c5c5。
- **backups**：正式release、原安装包、CI ZIP、唯一硬件证据、Skill备份和当前F盘缓存保留。删除61个可再生旧编译/解压目录；218个含链接测试目录未删。完整人工清单和删除结果在F:/MKLink-Build/reports/cleanup-20261023，见v036-storage-cleanup-20261023.md。 2026-10-24另按明确授权删除896个本地Linux/macOS包/签名/归档/分片，释放16072740412字节；归档证据另存unix-package-cleanup，线上正式附件保留。

## 下一动作

1. 进度条UI已完成并同步生产Web，本轮未重打包安装，当前实装仍86f9a75d（勾选版）；如需实装新UI需生成新Windows本地包并验收。86f9a75d阶段优化覆盖安装及实装验收已通过，见v036-desktop-startup.md。等待V3再次掉线后先导出诊断ZIP再拔插，当前新版已安装且未连接，需用户连接并开启RTT；历史USB移除混有手动操作，根因未定。PR50待审，正式发布须明确授权，重新跑合并源码完整门禁并构建stable包，不能把preview候选当正式包；保留GitHub/Gitee，线上包及stable/release/firmware/标签未变，临时SSH已撤销。
2. 收集客户N32WB452内外Flash组合实际烧写/回读反馈；本轮主机解析准入及安装包通过，不代替外置SPI硬件验证。不重复使用已消耗的F103单次烧录授权；不主动烧写或改OTP/供电。
3. 用户需重新生成并部署U盘脚本再测完整HPM JTAG连续烧录；旧脚本不会自动更新。实时拔插/LCD已验证，完整多板Flash/蜂鸣次数仍待实测；不重复历史一次性写入授权。
4. HPM联合镜像/OTP历史证据保留，Word69=3；本轮使用F103，未写HPM OTP或调整VCC。其他HPM型号继续由用户测试，未知MKLINK_V2任务不得重放，勿将目标板误作下载器升级。
5. 继续排查30MHz并行读错/Flash偶发status5，客户及Mac/Linux实物矩阵仍待补充；低负载测试不关闭限制。人工清理只按reports/cleanup-20261023/manual-cleanup.csv核对临时目录，不沿链接删除目标，最新安装包必须保留。长期验证仍暂停。

## 已知限制

- 0.3.5时钟修复已通过偏差注入及本地Windows3.11/3.14实机短测；客户3.11.9原电脑仍待升级确认。原始CDC首次离线/F405 PROGRAM100%后退出、受限AI/GD32及RTT客户后续MUX超时仍未闭环；不宣称同一根因或任意负载无损。历史unknown操作不得重放。 位域当前仅little-endian、只读；曲线Float32对大整数有舍入。真实ELF只离线回放，F103使用专门测试固件；未把客户固件烧到该板。 原0.3.2故障链见docs/verification/v032-postrelease-incidents.md；CDC传输错误、目标status5与本次DLL解压拒绝不混为同一根因，不靠清空用户配置或全杀后台掩盖原因。 本轮后台HEX下载2% Failed to write file,addr:0x2000，unknown未重放；用户Keil下载后仅重载验证成功，下载故障仍待另案排查。
- V4.6.8 30MHz RTT8/Watch4/UART并行目标读错1kHz +1、最大+273；10MHz0。旧V4.6.6原始+1/+224，报告此前漏记已更正。采集不停止、不误断、UART完整；用户明确继续发布，限制交接下版处理，不写公开发布说明。 2026-10-24 V4.7.0+F103最终安装测试：30MHz RTT先Watch后11762周期1错，反顺序12297周期0；10MHz两顺序0，限制未关闭。
- HPM/SES退出未发送DAP_Disconnect时可遗留占用，后续legacy握手等待；明确退出后正常OpenOCD init/resume/shutdown可恢复，用户可重插USB。禁止任意超时偷取调试所有权。完整SES矩阵和RTT下行未全部覆盖；V3.6.4/V4.6.8仿真中新启采集及负载读回通过，V4.6.8已完成Keil及相关矩阵。详见release handoff；长期目标暂停。 2026-10-17新增RTT status6截图仅证下载器忙返回；用户不清楚IDE占用/固件版本，不能认定与历史问题同因，待现场时序和显式重试结果。
- 性能和功能证据按docs/verification/v030-release-handoff.md及各精确提交报告解释：采集不是无损通道，缓冲溢出/暂停/调试下载可能丢失观测；多变量不是原子快照，不能保证任意时序上界。
- V3无屏幕、不支持HPM；V3.6.4原生Keil先运行再采集、暂停/单步/继续/退出和OpenOCD均通过。V4最终无诊断固件完整SES矩阵未完成。
- 后台最后会话释放约5秒租约，加排空和退出开销；不保证硬实时5秒。每个GUI客户端一个后台，同窗口切换固定PID/端口；一个物理探针在任一时刻仅由一个后台独占。打开已有URL的额外页面共享当前后台并跟随明确切换；独立操作应启动新客户端。
- 本轮UART5 TTL实体Modbus RTU读写通过，RS485电气层未测；跨物理主机Agent、全部芯片组合未完整认证，模拟测试不能替代实体。0.3.5最终独立Windows Site Agent已重新构建并通过两项实际包资格检查；macOS Intel/ARM和Linux原生CI包构建/冻结运行/载荷检查通过，但实体USB/MSC、原生GUI、签名升级未认证。Mac仅ad-hoc无Developer ID公证，Windows无Authenticode。Web真实文件句柄选择/跟踪未完成；新候选原生日志文件选择、回放和PNG已通过。
- nRF54L15 GUI保护闭环、全部物理擦除/拔插/休眠/断电场景、电源外部精度校准未全部认证。VCC每次改动必须确认具体电压，HPM已锁定OTP不得重放。 已知无可靠扇区表的26个FLM禁用扇区操作；重叠算法需要匹配Bank模式。 HPM5301组18/19永久锁定的历史状态及用户字先写/组锁最后、全部固件独立校验后才写OTP等边界见docs/ai/hpm-offline-otp-handoff.md；接手重新确认芯片，其他型号不继承验收。 UART OTP已实现ROM write-memory APIv2，独立熔丝/影子/临时锁读语义仍未知并如实显示；以ROM写入状态及回读为准。配套3d96dbb已实机验证HPM5301全部128字读取和用户批准的Word69 0→1单次写入回读；其余型号/区域未实写，新数据须具体授权。多Word顺序执行不可回滚。CSV原生选择器自动化未完成。

## 延续协议

- 本轮最终Windows候选f20fe781和完整Skill位于artifacts/v036-prerelease-20261024；冻结、覆盖、原生、真实Web及F103实机通过，测试进程正常退出。用户授权原测试工程改编译烧录无需备份，但不包含OTP/供电或探针固件变化。客户旧MCP导入故障仍缺现场证据，不能认定已闭环。
- V2 RBL更新见v035-v2-rbl-update.md，用户回退2.8后真实升级2.9已经通过；最终应用2f474f60与Skill已同步。V3.6.5/V4.6.9本轮仅发布原始UF2并验证公开文件，未再次刷入实体探针，不重复升级或回退。
- CDC 995根因仅保留待排查。恢复只允许同身份CDC故障5秒内；超时不自动接回或新建AI会话，主动断开立即生效，不重放未知写入。测试实例已经全部释放；见v035-transport-recovery.md，不寻找旧现场窗口。
- 客户启动故障仅确认PyInstaller解压ucrtbase.dll时Permission denied，重启后恢复；未定位权限/杀软/占用的具体来源，按用户意见暂不做推测性修复。若再现，结合新startup/runtime日志复查。
- 2026-10-18授权的验收与发布已完成，已知未解项交接保留；正式源2f474f60。发布后交接/正式Web通过独立PR保存，标签不动；敏感日志和本机硬件路径不提交。
