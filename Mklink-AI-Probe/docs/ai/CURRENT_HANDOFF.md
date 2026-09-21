# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-09-20T20:17:24.5820836+08:00`
- 分支：`codex/v0.2.2-development`
- HEAD：`0.2.2 shared light/dark/system themes, RTT transmit surround, canvas redraw and consistent package metadata.`
- 远端 HEAD：`codex/v0.2.2-development / PR #5; regression follow-up, no merge or release.`
- 工作树：Handoff includes offline OTP draft source and documentation; separate firmware and MicroBoot work remain outside this repository.
- 当前任务：HPM5301脱机OTP和真实断电保持验收完成，标准0.2.2 NSIS已生成并覆盖安装通过；开发分支待审阅，未正式签名/合并/发布。
- 状态：`in_progress`

## 里程碑

- **已交付** — `complete`。应用 0.2.1 已发布；HPMLink/MicroLink V4.5.0 独立固件发布，MicroLink V3.4.0 保留。

## 验证证据

- **报障流程**：正式版: docs/verification/v0.2.1-release-qualification.md：Python 2187 通过/2 可选依赖跳过，GUI 698，Rust 19；正式签名、本机覆盖安装、2460 Skill 文件/68 MCP 工具、7059 型号/2224 算法审计通过。三仓库资产与更新索引通过；真实 0.2.0 Skill 经旧公开入口升级后改用 MicroKeen。旧桌面应用内自动更新按钮未单独端到端验证，桌面已做 NSIS 覆盖和签名验证。 固件记录 docs/verification/firmware-20260915.md：发布/升级定向测试 25 通过，UF2 与公开下载尺寸/SHA-256、三端索引解析核验通过；没有新增硬件认证。应用正式验收报告由 PR #3 提供。 docs/verification/issue-feedback-stage1.md：本地/CI 各 60 项通过；真实缺陷自动修复闭环未验证。
- **仓库权限**：2026-09-15 最新授权：规则 22630535 审批人数为 0、关闭最后推送审批和附加审批。必需 feedback-contract、PR、讨论解决、禁止删除和强推保留，无新增绕过者；已通过 API 回读。此永久规则取代早前发布临时例外。
- **外设三端统一**：docs/verification/v0.2.1-peripheral-unification.md：Python 190 通过/1 跳过；HPM 43 型号共 1226962 条目录项可加载；HPM5301 CLI/MCP stdio/Chrome 三通道约 1 kHz，CRC/帧丢失/固件丢样标记为零。ARM 未做实板验证。
- **选项字节/OTP 第一阶段**：docs/verification/v0.2.1-device-configuration-stage1.md：Python 103、GUI 24、正式构建通过；HPM5301 CLI/MCP/Chrome 8 个公开字段一致；Chrome ARM 配置及脚本预览通过，没有 ARM 实板读写或 OTP 编程。
- **STM32F103 选项字节与 ARM mem_dump**：docs/verification/v0.2.1-stm32f103-options-stage2.md：Python 99、GUI 29、生产构建通过；CLI/MCP stdio/Chrome 10 字段一致，DATA、两项低功耗复位位及 WRP3 写入/复位/回读/恢复通过；组合下载通过，最终全部 512 KiB Flash 与原始备份一致。未测试 RDP 转换及看门狗/低功耗/WRP 拒写行为。 docs/verification/v0.2.1-stm32f103-mem-dump.md：27软件测试、14项稳定矩阵、LA3.904/10.549MHz测量、CLI/MCP/Chrome低中档通过；20/30电气试验失败保留。单RAM60s约603万点101.293kSa/s，4KB630.34KiB/s；GUI功能素材和RTT双消费者修复分别记录A/B演示构建，未做多小时认证。 docs/verification/v0.2.1-stm32-clock-calibration.md：117相关Python测试通过；Keil/在线/脱机频率实测、RTT/SystemView短时复测通过，20/30M不合格。GUI同一API改频与LA通过，RTT修复后14项mem_dump通过；最终Chrome截图尚未完成。 本轮更新（旧失败仅属旧板/旧固件）：docs/verification/v0.2.1-stm32-four-profile-freeze.md。pipe-r20四档20项完整矩阵通过，持续59.598/111.956/157.770/187.636kSa/s；20M60秒/30M120秒。Keil1/2/5/10M，Chrome配置四档和SuperWatch四档，在线/脱机各四档LA通过。USB暂停/启停20、CDC12、RTT/SV32次启动及功能/CLI/MCP通过。入口Python405、间隔66、GUI144/29（重叠）/95、生产构建与2460文件本地Skill安装审计通过。Chrome真图已交文档任务，发布渠道不变。
- **mem_dump 四档与 HPM 实板稳定性**：docs/verification/v0.2.1-mem-dump-four-speeds.md：143 Python、3 GUI、生产构建、72打包/更新/边界通过；CLI/MCP stdio及Chrome四档切换/曲线实板通过。旧7510单变量两档各30min，旧20M 4KB失败保留；新2927修复版48用例通过，20M 4KB600s/30M300s及小块、动态RAM、10轮四档重连。SBA忙冲突按报告计数恢复，不称零冲突。 HPM6E80独立记录v0.2.1-hpm6e80-mem-dump.md：21软件测试、304候选28矩阵/30长测重连、cbd最终28回归、CLI/MCP24和Chrome通过；共享ID不识别精确型号。
- **SuperWatch 与 SystemView 文档实测修复**：docs/verification/v0.2.1-hpm-gui-acceptance.md：172+159+158 Python、95 GUI/构建；HPM脱机78464B全回读、数组index0..15/16pts通过。新9a338046探针+Web codec两轮Chrome16449/16577事件、3任务、RuntimeDrop0，已断开。原生CSV/PNG保存未验证。 Web修复：docs/verification/v0.2.1-hex-preview.md，159 Python、121 GUI、生产构建；Chrome 无芯片 FLM+25.5MiB HEX、IAP越界提示与预览、默认折叠通过。
- **V2 narrow reads and shared RTT validation**：历史V2/V3/V4和四档实板资格见docs/verification各报告，不外推芯片。20260920 STM32F103在线6/脱机6、窄值/非对齐、UART/RTT/SystemView/CLI/MCP与Chrome通过；HPM6E80四档、在线3/脱机3及共享流通过，UART未接。主题与在线校验见v0.2.2-online-verify-theme-20260920.md：HPM校验约4.4倍提升，ARM三档BIN/HEX6次通过、Boot保留；带Verify导出FLM仅软件验证。本轮HPM5301脱机OTP详见v0.2.2-hpm-offline-otp-20260920.md：旧API/旧值/缺文件停止；真实Chrome写Word72=1、79=3和组18/19锁，完整BIN回读及UART通过，真正断电后值/锁、固件和UART/GUI复核通过。Python2294通过2跳过、12项符号链接权限失败经用户授权启用开发模式后补跑全通过（合计2306通过）；GUI720通过、生产构建通过。Rust测试缺Common Controls v6清单已修复，19项通过。BrowserAct Chrome恢复可用。标准NSIS87.6MiB已构建/覆盖安装，受限PATH启动、内置后端、7059/2224资产哈希、退出释放及安装后HPM OTP回读通过；无签名、未发布。

## 架构决策

- 用户 Skill 只含运行时；开发主仓库 MicroKeen/main，0.2.1 起默认更新源 MicroKeen/release；旧 GitHub/updates 提供桥接版，Gitee/updates 保持原址。 固件资产仍使用旧 GitHub firmware-assets 与 Gitee 后备，MicroKeen/firmware 同步兼容索引，未迁移客户端固件 URL。
- 任务 mklink-issues-pr 为 PAUSED，未经要求不恢复；手动流程见 docs/ai/issue-maintenance.md，修复只提交 PR，合并由用户决定。
- 构建/清理遵循 AGENTS.md 与 docs/ai/build-storage.md；保留正式包、唯一备份、依赖缓存及 HIL 证据。
- 协作权限见 docs/ai/repository-governance.md：Aladdin-Wang、su5176 保持 Admin/Owner 并处理 PR；更新分支和正式标签仅 Aladdin-Wang 可写，最高管理员仍可修改规则，Release 附件权限不由分支规则隔离。
- 所有 PR 不再强制第二人审批；核对差异及相关验证、必需 CI 后，按明确合并授权和确切头提交整合。不得恢复旧审批门槛；发布仍需独立授权，其他保护保留。

## 真机环境

- **state**：HPMLink V4 + HPM5301。Word72=1、Word79=3、HARD_LOCK=0x304C0016；38,364字节固件独立回读一致，UART0心跳递增。组18/19已永久锁定，禁止重放原配方。实际断电后GUI/独立回读和UART复核通过，不进行安全生命周期操作。
- **backups**：.build/reports/prerelease-hil-20260907、superwatch-write-20260907；保留其他芯片唯一备份。；本轮本地证据 .build/reports/peripheral-unification。；本轮 OTP 只读和浏览器证据 .build/reports/device-configuration。；STM32F103 唯一原始备份与本轮证据 .build/reports/stm32f103-options。
- **installer**：.build/artifacts/v0.2.2-hpm-otp-20260920/Mklink-AI-Probe-v0.2.2-fdf24c0-x64-Setup.exe

## 下一动作

1. 标准NSIS候选已完成，源fdf24c0，见HPM脱机OTP验收报告及本地artifacts/v0.2.2-hpm-otp-20260920。正式渠道未发布；按用户下一步指示审阅合并/签名发布。开发人员模式已按授权开启。
2. 原生桌面视觉新一轮截图尚未补，本轮真实Chrome验证暗黑主题、OTP流程和更新记录。其他芯片OTP、带Verify导出FLM仍按报告限定资格。
3. 官网文档任务已收到四档Chrome真图和技术附件；保留公众号风格及技术附件分层，不自动发布。继续优化前先拆分批间组帧/调度开销；慢浏览器订阅需按队列背压评估，勿与USB字节故障混同。
4. 后续补STM32F103看门狗、STOP/STANDBY、WRP拒写及其他ARM实板。HPM用户OTP开放限定型号，安全字段仍为实验路径；其他系列按报告OTP基址和EXIP长度分别适配。
5. 本机桌面已覆盖安装本地0.2.2离线包；正式发布渠道和Skill仍为0.2.1，定时任务维持暂停。

## 已知限制

- 本轮已复现的USB停读后32B缺失由独立对齐DMA槽修复，并修复RTT回执/描述符并发。有限缓存仍不保证无限暂停或物理断线无损；历史枚举异常未做全部场景认证。
- PY32F030 保护后恢复未闭环；未覆盖物理 Modbus、所有板卡、Mac/Linux 与跨主机 Agent。
- 外设轮询可漏短脉冲，缓冲有限；SystemView 启动可能丢弃少量数据。
- 共享外设目录目前只支持对齐 32 位、小端、无已知读取副作用的寄存器；真实 16 位 MMIO 需要探针协议/固件补齐和 ARM 实板验证。HPM 全型号目录加载不等同全外设 HIL。
- STM32F103 非 XL USER/DATA/WRP 配置已开放，实板为 V4 高容量组；WDG_SW 保持软件模式，未验证低功耗进入和 WRP 拒写行为。V3/其他容量仅描述与生成测试；其他 ARM 维持原有安全配方，G474/PY32 仍仅 V3。HPM用户区与组19永久锁有实测；其他安全GUI写入口尚未开放。
- 批量路径覆盖已列明HPM5301 DLM/XIP和新增HPM6E80 AXI SRAM、最多15区域；shared JTAG ID不识别精确型号，也不证明接线稳定。<50us请求沿用满速语义，非原子多变量/硬实时。XIP有界块忙冲突恢复不适用于RAM/MMIO或真实总线错误。历史HPM资格按对应固件保留；本轮HPM6E80有限时长批时间戳/USB回归通过，见20260920报告；不代表无限暂停或多小时认证。ARM高速本轮按专门报告验证。
- 客户原始 ELF/程序不可用，不能认定其8位毛刺根因已复现；odd-address packed halfword 不保证原子性。远程文件测试12项受Windows symlink权限限制。

## 延续协议

- 先核对 Git、任务和设备状态；仅按需读相关验证报告，不加载历史流水账。
