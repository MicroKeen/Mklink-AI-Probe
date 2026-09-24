# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-09-24T15:40:58.4590517+08:00`
- 分支：`codex/0.2.3-dev`
- HEAD：`197ea28：修复 nrf54l 别名导致脱机解锁置灰；含 0.2.3 版本信息和算法发现修复。`
- 远端 HEAD：`推送前远端 99e302c；本轮提交修复与交接，不发布正式版本。`
- 工作树：正式发布附件与MK-Firmware四份新固件SHA-256一致。原主工作区及其他仓库修改保留。
- 当前任务：0.2.3 开发交接及分支推送；安装包重建、覆盖安装、本地 Skill 更新和临时文件清理尚待完成。
- 状态：`active`

## 里程碑

- **正式发布** — `complete`。0.2.2 标准安装包、Skill、Site Agent 已同步新旧 GitHub 和 Gitee；四份探针固件已同步，UF2 三端索引通过。

## 验证证据

- **发布与安装**：docs/verification/v0.2.2-release-final.md：Python2306通过/2跳过，GUI720、Rust19通过；正式NSIS87.6MiB，覆盖安装、内置后端、7059型号/2224FLM哈希、退出释放、更新签名及三端公开索引通过。
- **STM32与HPM功能回归**：按目标和功能查阅 v0.2.2-v4-stm32-regression-20260920.md、v0.2.2-v4-hpm6e80-regression-20260920.md、v0.2.2-online-verify-theme-20260920.md（均位于docs/verification）。包含高速档、烧录、窄值/非对齐、共享流、CLI/MCP/GUI；HPM6E80本轮UART未接。
- **HPM5301用户OTP**：docs/verification/v0.2.2-hpm-offline-otp-20260920.md：独立Flash回读门槛、旧API/旧值/缺文件停止、用户字和组18/19永久锁、真实Chrome/UART及断电保持通过。不能外推其他型号或安全生命周期字段。
- **固件发布**：HPMLinkV4.5.1、MicroLinkV4.5.1/V3.5.0/V2.8.0已公开下载校验；25项发布/升级测试通过。V2 RBL头/体CRC、长度及程序版本验证，打包头V1.0.0保留原件。此发布轮未刷机，不新增硬件认证。 PR #6同步四份固件至源码目录，合并前Python2306/2跳过、GUI720及生产构建通过。
- **历史证据**：旧版测试保留在docs/verification，按需查阅；旧失败或曾经待测项目不再逐项重复载入当前交接。
- **nRF54L15保护**：Python真机 APPROTECT/SECUREAPPROTECT 写入、复位保护状态3、AHB关闭、CTRL-AP恢复0.923秒、1560576字节全空检查、客户HEX恢复校验通过。原始证据保存在用户测试目录 .mklink/security_roundtrip_20260924.json。别名与算法目录回归19项通过。

## 架构决策

- 开发主仓库MicroKeen/main；后续修改从最新main创建codex分支，经PR及必需CI整合。审批人数0，发布和合并仍需明确授权；标签不可变。
- 应用主索引MicroKeen/release，旧GitHub/updates兼容，Gitee/updates备用。固件三个firmware索引保持兼容，客户端URL仍可指向旧GitHub。
- 现有自动固件更新仅支持UF2；V2 RBL作为手动升级附件，不写入严格UF2索引，避免破坏0.2.2解析。
- 按维护者授权，Gitee应用发布页仅保留最新0.2.2，固件渠道独立保留；GitHub历史版本不删除。
- 保留正式包、唯一备份、依赖缓存和必要HIL证据。原主工作区用户固件替换不得reset。mklink-issues-pr自动任务维持暂停。

## 真机环境

- **state**：2026-09-24：MKLink V4 + nRF54L15，Python 真机加锁/CTRL-AP 解锁闭环通过。已恢复客户 HEX，460524 字节回读一致；复位运行 5 秒后未加锁。未启用 ERASEPROTECT。
- **backups**：本地.build/reports保留原始HIL证据；Gitee历史备份与清理记录在.build/artifacts/gitee-historical-backup-20260921。
- **installer**：.build/artifacts/v0.2.3-nrf54l-offline/Mklink-AI-Probe-v0.2.3-x64-Setup.exe：旧候选不包含 197ea28 别名修复，不能作为最终修复安装包。

## 下一动作

1. 按用户更正保持0.2.3，重建标准NSIS并覆盖安装，更新本地运行时Skill，清理可确认临时产物。
2. 在线安全操作与脱机加锁仍需实现与GUI真机回归，不可仅放开复选框。

## 已知限制

- 有限缓冲不保证无限暂停/物理断线无损；外设轮询可能漏短脉冲，多变量不是原子快照。
- 客户原始ELF/程序不可用，不能宣称复现其毛刺根因；odd-address packed halfword不保证原子性。
- HPM OTP仅按报告限定型号和字段；当前HPM5301组18/19永久锁定，禁止重放配方。其他安全GUI写入口未开放。
- PY32F030保护后恢复、物理Modbus、所有板卡、Mac/Linux与跨主机Agent未完整认证；STM32看门狗、STOP/STANDBY、WRP拒写仍待专测。
- Windows安装器无Authenticode签名（未知发布者），自动更新签名已验证；标准包不含离线WebView2。原生桌面本轮无新增视觉截图，Chrome截图不替代桌面视觉验收。
- HPM6E80回归有限时长且无UART；本次用户更新的四份固件只做格式/CRC/公开发布验证，不把历史实测外推到新二进制。
- nRF54L15 CTRL-AP 解锁已在 V4.5.1 真机验证：脚本恢复后客户 HEX 脱机烧录、全量回读和运行后保护状态通过；未在固件中写入 nRF54L15 型号。
- 在线GUI尚未接入nRF54L安全操作，脱机GUI仅解锁配方；加锁Python真机通过不等于GUI验收通过。

## 延续协议

- 先核对 Git、任务和设备状态；仅按需读相关验证报告，不加载历史流水账。
