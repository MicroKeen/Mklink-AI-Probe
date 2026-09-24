# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-09-24T16:56:10.8635427+08:00`
- 分支：`codex/0.2.3-dev`
- HEAD：`ca00001；在线 nRF54L15 安全操作已提交，真机闭环待授权`
- 远端 HEAD：`microkeen/codex/0.2.3-dev=ae0aae2；本轮远端已获取并核对`
- 工作树：在线安全代码、测试、生产 Web 资源和验证记录已提交；当前仅维护记忆待提交。主工作区固件改动保留，未触碰固件仓库。
- 当前任务：接续 0.2.3 开发：在线 nRF54L15 GUI 加锁/CTRL-AP 解锁已接入并完成静态、组件和真实浏览器入口验证；真机破坏性闭环待用户明确授权。脱机下载后加锁仍待开发，当前安装候选包不含本轮代码。
- 状态：`active`

## 里程碑

- **正式发布** — `complete`。0.2.2 标准安装包、Skill、Site Agent 已同步新旧 GitHub 和 Gitee；四份探针固件已同步，UF2 三端索引通过。

## 验证证据

- **发布与安装**：docs/verification/v0.2.2-release-final.md：Python2306通过/2跳过，GUI720、Rust19通过；正式NSIS87.6MiB，覆盖安装、内置后端、7059型号/2224FLM哈希、退出释放、更新签名及三端公开索引通过。
- **STM32与HPM功能回归**：按目标和功能查阅 v0.2.2-v4-stm32-regression-20260920.md、v0.2.2-v4-hpm6e80-regression-20260920.md、v0.2.2-online-verify-theme-20260920.md（均位于docs/verification）。包含高速档、烧录、窄值/非对齐、共享流、CLI/MCP/GUI；HPM6E80本轮UART未接。
- **HPM5301用户OTP**：docs/verification/v0.2.2-hpm-offline-otp-20260920.md：独立Flash回读门槛、旧API/旧值/缺文件停止、用户字和组18/19永久锁、真实Chrome/UART及断电保持通过。不能外推其他型号或安全生命周期字段。
- **固件发布**：HPMLinkV4.5.1、MicroLinkV4.5.1/V3.5.0/V2.8.0已公开下载校验；25项发布/升级测试通过。V2 RBL头/体CRC、长度及程序版本验证，打包头V1.0.0保留原件。此发布轮未刷机，不新增硬件认证。 PR #6同步四份固件至源码目录，合并前Python2306/2跳过、GUI720及生产构建通过。
- **nRF54L15保护**：Python真机 APPROTECT/SECUREAPPROTECT 写入、复位保护状态3、AHB关闭、CTRL-AP恢复0.923秒、1560576字节全空检查、客户HEX恢复校验通过。原始证据保存在用户测试目录 .mklink/security_roundtrip_20260924.json。别名与算法目录回归19项通过。
- **0.2.3本地安装交接**：标准builder成功，覆盖安装退出0；Skill升级至0.2.3，插件版本及安装清单核对完成。收尾再次核对安装包SHA256及D盘程序ProductVersion=0.2.3。安装后启动、health与退出验收见下一项，无待补启动检查。
- **0.2.3安装后验收**：用户启动D盘安装版后，8765 health=ok，探针枚举接口正常；nrf54l/V4 unlock_supported=true、lock_supported=false。sidecar SHA256=925C353519384C6EADE1D8C9467218D212C69A6904B4C42CCF6AA8B1E62221DF，与构建产物一致。进程树无Python回退。CloseMainWindow正常退出后主进程及两层sidecar均退出，8765监听数0。
- **0.2.3在线nRF54L安全操作阶段验证**：docs/verification/v0.2.3-nrf54l-online-security.md：新配方9项、在线API/CLI相关155项、GUI相关101项通过；生产前端构建成功。全量Python2320通过/2跳过、GUI721通过，各有1项既有版本断言失效，修正后单项复测通过。真实Chrome的V4探针/目标选择和两项确认弹窗通过，弹窗取消；未执行真机安全写入。

## 架构决策

- 开发主仓库MicroKeen/main；后续修改从最新main创建codex分支，经PR及必需CI整合。审批人数0，发布和合并仍需明确授权；标签不可变。
- 应用主索引MicroKeen/release，旧GitHub/updates兼容，Gitee/updates备用。固件三个firmware索引保持兼容，客户端URL仍可指向旧GitHub。
- 现有自动固件更新仅支持UF2；V2 RBL作为手动升级附件，不写入严格UF2索引，避免破坏0.2.2解析。
- 按维护者授权，Gitee应用发布页仅保留最新0.2.2，固件渠道独立保留；GitHub历史版本不删除。
- 保留正式包、唯一备份、依赖缓存和必要HIL证据。原主工作区用户固件替换不得reset。mklink-issues-pr自动任务维持暂停。

## 真机环境

- **state**：2026-09-24：MKLink V4 + nRF54L15，Python 真机加锁/CTRL-AP 解锁闭环通过。已恢复客户 HEX，460524 字节回读一致；复位运行 5 秒后未加锁。未启用 ERASEPROTECT。
- **backups**：本地.build/reports保留原始HIL证据；Gitee历史备份与清理记录在.build/artifacts/gitee-historical-backup-20260921。
- **installer**：.build/artifacts/v0.2.3-local-20260924/Mklink-AI-Probe-v0.2.3-x64-Setup.exe；SHA256 552EB646504C162AE4E5738280A054063704A88DA97F9EEC8202C69017BDD6D0。标准NSIS，自带后端与7059型号/2224算法，安装/S退出0；未正式发布，无更新签名。 实际安装目录 D:/Program Files/Mklink AI Probe，ProductVersion=0.2.3。

## 下一动作

1. 用户若明确授权，按当前目标与已验证客户HEX执行在线GUI加锁、复位核对、CTRL-AP解锁、重烧和全量回读；记录证据。未经授权不执行擦除或安全写入。
2. 后续补齐nRF54L脱机GUI下载后加锁，使用Python配方，不在下载器固件中硬编码型号。完成两条GUI真机验证后重新打包，不能沿用当前安装包验收结论。
3. 手动清理移交：旧候选.build/artifacts/v0.2.3-dev和v0.2.3-nrf54l-offline此前删除被自动审批拦截，路径已给用户；未核实用户是否删除，不重试绕过。保留v0.2.3-local-20260924、正式0.2.2及唯一真机证据。
4. 新会话继续codex/0.2.3-dev，先读取本文件并重新加载本地0.2.3 Skill。用户安装版位于D:/Program Files/Mklink AI Probe；开发WebGUI此前使用8785，操作前重新核对进程、设备和端口。0.2.3尚未正式发布。

## 已知限制

- 有限缓冲不保证无限暂停/物理断线无损；外设轮询可能漏短脉冲，多变量不是原子快照。
- 客户原始ELF/程序不可用，不能宣称复现其毛刺根因；odd-address packed halfword不保证原子性。
- HPM OTP仅按报告限定型号和字段；当前HPM5301组18/19永久锁定，禁止重放配方。其他安全GUI写入口未开放。
- PY32F030保护后恢复、物理Modbus、所有板卡、Mac/Linux与跨主机Agent未完整认证；STM32看门狗、STOP/STANDBY、WRP拒写仍待专测。
- Windows安装器无Authenticode签名（未知发布者），自动更新签名已验证；标准包不含离线WebView2。原生桌面本轮无新增视觉截图，Chrome截图不替代桌面视觉验收。
- HPM6E80回归有限时长且无UART；本次用户更新的四份固件只做格式/CRC/公开发布验证，不把历史实测外推到新二进制。
- nRF54L15 CTRL-AP 解锁已在 V4.5.1 真机验证：脚本恢复后客户 HEX 脱机烧录、全量回读和运行后保护状态通过；未在固件中写入 nRF54L15 型号。
- 在线GUI已接入nRF54L安全操作，但尚未做本轮真机加锁/CTRL-AP解锁闭环；脱机GUI仍仅解锁配方。此前Python真机配方通过不能外推为本轮GUI验收。

## 延续协议

- 先核对 Git、任务和设备状态；仅按需读相关验证报告，不加载历史流水账。
