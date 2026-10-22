# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-10-22T11:52:34.477618+08:00`
- 分支：`codex/hpm-isp-deployment-ux`
- HEAD：`自动烧录次数侧栏/等待时间启用规则与生产Web已提交，具体HEAD见Git。`
- 远端 HEAD：`本轮源与Web随PR48任务分支推送；已安装组合仍203dfe51。`
- 工作树：唯一工作区E:/software/HPM5300/Mklink-AI-Probe，源码子目录Mklink-AI-Probe；当前codex/hpm-isp-deployment-ux。已安装组合源在codex/v036-isp-ux-local。
- 当前任务：自动烧录次数移至左侧目标连接/换板等待时间之前；每次打开默认1，不恢复历史次数；只有次数>1允许编辑等待时间。脚本文件名占满原区域。51离线GUI、TS/Vite、真实浏览器1→2→1及刷新恢复1、零控制台错误通过。源码和生产Web已更新，本轮没有重新打包或覆盖安装。
- 状态：`offline_count_ui_verified`

## 里程碑

- **0.3.5正式版** — `complete`。PR43合并源2f474f60372e。Windows/Skill/三平台/SiteAgent与17附件、5签名、3渠道通过；全局Skill同步、原生退出资源释放。V3.6.5/V4.6.9独立发布。详见v035-release-handoff.md和v035-probe-firmware.md。
- **0.3.4正式版** — `complete`。不可变源a8fd3fab0403，PR40正式发布；PR41已保存正式Web/交接，合并提交185678c59623。17附件、5份验签、3渠道及实装/Skill通过。07846c1a记录后续清理完成，本次补入0.3.5；见v034-release-handoff.md及v034-workspace-cleanup.md。
- **0.3.3正式版** — `complete`。源11616f80，PR38；Windows/ARM/Linux/Intel包、五份签名、三渠道核对和本地Skill更新完成。正式归档已回原工作空间；见v033-release-handoff.md。
- **0.3.2正式版** — `complete`。源3d511e94，PR35/36；三平台原生构建38028928283。Windows实装、五份更新验签、三个渠道已核对，见v032-release-handoff.md。
- **0.3.1正式版** — `complete`。PR33合并，源1d61159d；签名NSIS/Skill/SiteAgent与三端索引完成，最终提取包检查通过。见v031-release-handoff.md。
- **0.3.0及2026-10-09固件归档** — `complete`。0.3.0发布及2026-10-09固件记录见历史交接和固件归档；不继承其硬件验收结论。

## 验证证据

- **自动烧录次数与等待时间**：51离线GUI及TS/Vite通过；真实生产Web模拟后台验证默认1且等待时间禁用，2时启用，改回1禁用，5后刷新恢复1；左侧相邻对齐、右侧脚本名满宽，控制台无错。未部署/触发/接触设备，未重新打包安装。
- **ARM每板完成复位和蜂鸣**：源eca8b0b0/Web7c5dea72，305相关Python/51离线GUI/TS/Vite通过；IAB模拟双镜像3轮与最终实时查询脚本3轮均通过，无控制台错。组合203dfe51管理员覆盖exit0，解包/实装205Python/41Web/四载荷、冻结CLI/MCP/SVD/HTTP/无宿主Python/后台正常退出通过。配套固件2435484双SES/38CI通过且已升级；软件/硬件/3300mV断电复位各一次通过。恢复遥测3480mV非外部校准。原生已打开，实装Web三模式/电压/等待标签核对通过，无控制台错。完整实际Flash多板循环尚未验证。见v036-arm-completion-reset.md。
- **蜂鸣时长与预览输出并排**：e700f579/5244c274/Web def4d105：236Python、80GUI、TS/Vite；IAB模拟100ms部署触发，两列442px等宽/349.333px等高、标题28px、无控制台错误。组合9b8c9009管理员覆盖exit0，解包/实装205Python/41Web/四载荷与冻结CLI/MCP/SVD/HTTP/退出通过。固件8705f753双SES/37CI通过，原下载器单次升级，13参数100ms与旧12参数均rc0后清配置释放。原生已重开，实际声长/完整换板待用户测。见v036-beep-layout.md。
- **自适应布局与拔板断开显示**：主机5c979720/373b44e9/Web f6ca3925，79GUI/TS/Vite及IAB对齐通过；组合a821be6d覆盖和冻结资格保持。8845cab实物失败；cd790707查询诊断捕获154 FRAME/0 TIMEOUT，证明无效帧清空静默计数。8d5d294独立presence修复：37回归、50/250ms各29场景、双SES/SWD地址/UF2通过并升级。实物115200拔开时disconnected+用户确认LCD已断开，19.834秒后重接connected，code0/close。200–225ms仅模型，无精确拔开时间戳；高速多轮未重测。报告v036-isp-disconnect-layout.md。
- **多镜像ISP阶段与右侧输出布局**：cc043fd1/Web4433456e；79GUI、TS/Vite、20条生产C序列化事件交叉解析通过。IAB模拟后台确认右侧布局且零控制台错误，文件选择事件超时未上传。固件d2452d2报告20轮×双BIN×5M回归40写/20复位/19掉线，文件间无重连且进度单调；36CI及双版SES通过。组合ea606a48于2026-10-22 00:32:07+08覆盖exit0，解包/实装205Python/41Web/四载荷、冻结CLI/MCP/SVD/HTTP/无宿主Python/正常退出通过。原身份重接后UF2仅写一次，版本/编译时间及三项能力通过；原生已打开，安装版IAB右侧预览/零控制台错。详见docs/verification/v036-multifile-isp-display.md。
- **镜像与UART OTP联合脱机任务**：功能a3d55b76/bea39ab5/f576a68d，Web bc23b878；274Python/132GUI，最终针对模块166Python/17面板/28输出复验及TS/Vite通过。真实浏览器模拟部署和安装版连续输入/HPM6200入口通过，零控制台错。组合8d2ed5a3覆盖exit0，205Python/41Web/四载荷、冻结CLI/MCP/SVD/HTTP/无宿主Python/正常退出通过。固件313ab4e生产C结果交叉解析通过并升级。实际V4 BIN@0x80023000+Word69 1→3联合部署，仅触发一次code0/ROM0/1/1、otp_verified1；128字回读唯一69=3，锁/生命周期/VCC未改。报告docs/verification/v036-joint-offline-otp.md。
- **共享脱机工作区与八系列UART OTP**：源c59a6f30/2f681cad：179相关Python、209GUI、36目录测试；组合373Python、TS/Vite通过。IAB生产Web+真实API模拟CDC验证跨HPM系列/ARM、模板预览/模拟写入、旧确认失效，零控制台错误；固件生产C read/plan/program交叉解析通过。组合a2599b21管理员覆盖exit0；解包及实装204Python/41Web/四载荷一致，冻结CLI/MCP/SVD/HTTP/无宿主Python/正常退出通过。原生启动和IAB安装后网页通过，原生窗口留给用户；未关闭本轮用户窗口。报告v036-offline-workspace.md。此前73fccac2安装见v036-uart-otp-settings.md。 2026-10-21按用户授权升级3d96dbb，安装版profile_v1实机128字全读、Word69 0→1预检/真实单次写入/全读回通过，唯一该字变化；锁/VCC未改。
- **0.3.6 ISP错误原因**：2506e93c/9b056ed1：102Python、72GUI，扩展90GUI通过；修正App旧哈希断言a8250c25，CI重跑以GitHub为准。Chrome临时SD和模拟固件显示timeout/Cancelled，脚本/JSON过滤。组合9c80b12a管理员覆盖退出0，199Python/40Web/四载荷、冻结CLI/MCP/SVD/HTTP、原生/浏览器与退出零进程/监听/端点通过。见v036-isp-readable-errors.md。

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

- **state**：当前目标STM32F103；原V4固件2435484已升级，三种授权复位各一次通过并释放端口；无本轮Flash/OTP写入。原生上位机已打开供用户测试。
- **installer**：已安装0.3.6组合203dfe51，管理员覆盖与冻结资格通过；SHA256 22d8be1bbbd99b44f31ecf742a6380f88ba602b4d136370a327f8b923ca4a193。次数侧栏的后续纯UI改动尚未打包覆盖。
- **backups**：0.3.4正式包/安装/渠道/Skill/HIL在MKLINK_BUILD_ROOT/artifacts/v034-official，相邻v034-official-native保存完整原生CI ZIP；0.3.5本机包见上述构建根。原Git根.build/artifacts/v033-official、v032-official及用户备份保持；清理前快照/删除清单在构建根reports/v034-cleanup-*.json、v034-deleted-branches.json、v034-memory-before-cleanup.json。不能再把F盘仅视为可删缓存。

## 下一动作

1. 次数侧栏与等待时间规则已完成源码/生产Web验证，尚未打包覆盖；当前已安装203dfe51且原生窗口为用户保留，若继续安装先确认测试已结束。无需为本次纯UI改动更新固件或重复复位。
2. 每板多镜像完成次数与换板去抖已有脚本执行/真实浏览器模拟，尚未实测完整STM32多板Flash流程。当前目标已从HPM换成STM32F103，不继承历史HPM镜像或OTP写入授权，不能重放旧unknown任务。
3. PR48未合并发布。此前联合镜像+OTP实机证据保留，当前Word69=3；本轮未追加目标烧录/OTP/VCC。其他HPM型号继续由用户测试，固件交会话01a15977-1aef-7430-aa11-6e39725f0465。
4. 未知MKLINK_V2任务不得重放。当前接入若为烧好固件的目标板或另一V2.9.0设备，不能误当原下载器升级。
5. 其他维护边界：继续排查 30MHz 并行目标读错/Flash 偶发 status5，区分固件目标访问与主机队列；本次低负载 F103 结果不关闭该限制，需要固件改动另开会话。；保持Gitee真实Skill回退：0.3.5已验证；Windows超过100MB被拒使用GitHub链接，其余平台仅GitHub。保留唯一发布/验收证据和Skill备份，联接run仅人工处理，不强删。；收集 Mac/Linux USB/MSC 和原地升级反馈、外置 Flash 多算法实物验证；完整 SES/芯片/拔插断电组合仍待补充。供电每次确认具体电压，长期验证仍暂停。

## 已知限制

- 0.3.5时钟修复已通过偏差注入及本地Windows3.11/3.14实机短测；客户3.11.9原电脑仍待升级确认。原始CDC首次离线/F405 PROGRAM100%后退出、受限AI/GD32及RTT客户后续MUX超时仍未闭环；不宣称同一根因或任意负载无损。历史unknown操作不得重放。 位域当前仅little-endian、只读；曲线Float32对大整数有舍入。真实ELF只离线回放，F103使用专门测试固件；未把客户固件烧到该板。 原0.3.2故障链见docs/verification/v032-postrelease-incidents.md；CDC传输错误、目标status5与本次DLL解压拒绝不混为同一根因，不靠清空用户配置或全杀后台掩盖原因。 本轮后台HEX下载2% Failed to write file,addr:0x2000，unknown未重放；用户Keil下载后仅重载验证成功，下载故障仍待另案排查。
- V4.6.8 30MHz RTT8/Watch4/UART并行目标读错1kHz +1、最大+273；10MHz0。旧V4.6.6原始+1/+224，报告此前漏记已更正。采集不停止、不误断、UART完整；用户明确继续发布，限制交接下版处理，不写公开发布说明。
- HPM/SES退出未发送DAP_Disconnect时可遗留占用，后续legacy握手等待；明确退出后正常OpenOCD init/resume/shutdown可恢复，用户可重插USB。禁止任意超时偷取调试所有权。完整SES矩阵和RTT下行未全部覆盖；V3.6.4/V4.6.8仿真中新启采集及负载读回通过，V4.6.8已完成Keil及相关矩阵。详见release handoff；长期目标暂停。 2026-10-17新增RTT status6截图仅证下载器忙返回；用户不清楚IDE占用/固件版本，不能认定与历史问题同因，待现场时序和显式重试结果。
- 性能和功能证据按docs/verification/v030-release-handoff.md及各精确提交报告解释：采集不是无损通道，缓冲溢出/暂停/调试下载可能丢失观测；多变量不是原子快照，不能保证任意时序上界。
- V3无屏幕、不支持HPM；V3.6.4原生Keil先运行再采集、暂停/单步/继续/退出和OpenOCD均通过。V4最终无诊断固件完整SES矩阵未完成。
- 后台最后会话释放约5秒租约，加排空和退出开销；不保证硬实时5秒。每个GUI客户端一个后台，同窗口切换固定PID/端口；一个物理探针在任一时刻仅由一个后台独占。打开已有URL的额外页面共享当前后台并跟随明确切换；独立操作应启动新客户端。
- 跨物理主机Agent、真实Modbus从站及全部芯片组合未完整认证，模拟测试不能替代实体。0.3.5最终独立Windows Site Agent已重新构建并通过两项实际包资格检查；macOS Intel/ARM和Linux原生CI包构建/冻结运行/载荷检查通过，但实体USB/MSC、原生GUI、签名升级未认证。Mac仅ad-hoc无Developer ID公证，Windows无Authenticode。Web真实文件句柄选择/跟踪未完成；新候选原生日志文件选择、回放和PNG已通过。
- nRF54L15 GUI保护闭环、全部物理擦除/拔插/休眠/断电场景、电源外部精度校准未全部认证。VCC每次改动必须确认具体电压，HPM已锁定OTP不得重放。 已知无可靠扇区表的26个FLM禁用扇区操作；重叠算法需要匹配Bank模式。 HPM5301组18/19永久锁定的历史状态及用户字先写/组锁最后、全部固件独立校验后才写OTP等边界见docs/ai/hpm-offline-otp-handoff.md；接手重新确认芯片，其他型号不继承验收。 UART OTP已实现ROM write-memory APIv2，独立熔丝/影子/临时锁读语义仍未知并如实显示；以ROM写入状态及回读为准。配套3d96dbb已实机验证HPM5301全部128字读取和用户批准的Word69 0→1单次写入回读；其余型号/区域未实写，新数据须具体授权。多Word顺序执行不可回滚。CSV原生选择器自动化未完成。

## 延续协议

- 当前STM32F103；ARM三种复位验证已完成，不重复硬件操作。最新纯UI改动（次数左移、默认1、>1启用等待）已验证，尚未覆盖安装。
- V2 RBL更新见v035-v2-rbl-update.md，用户回退2.8后真实升级2.9已经通过；最终应用2f474f60与Skill已同步。V3.6.5/V4.6.9本轮仅发布原始UF2并验证公开文件，未再次刷入实体探针，不重复升级或回退。
- CDC 995根因仅保留待排查。恢复只允许同身份CDC故障5秒内；超时不自动接回或新建AI会话，主动断开立即生效，不重放未知写入。测试实例已经全部释放；见v035-transport-recovery.md，不寻找旧现场窗口。
- 客户启动故障仅确认PyInstaller解压ucrtbase.dll时Permission denied，重启后恢复；未定位权限/杀软/占用的具体来源，按用户意见暂不做推测性修复。若再现，结合新startup/runtime日志复查。
- 2026-10-18授权的验收与发布已完成，已知未解项交接保留；正式源2f474f60。发布后交接/正式Web通过独立PR保存，标签不动；敏感日志和本机硬件路径不提交。
