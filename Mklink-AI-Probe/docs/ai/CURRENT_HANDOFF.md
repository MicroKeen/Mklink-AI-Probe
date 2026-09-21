# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-09-21T15:07:20.4759451+08:00`
- 分支：`codex/release-022-handoff`
- HEAD：`基于已发布 main 424f470；本分支整理交接并将MK-Firmware同步为已发布的四份新固件。`
- 远端 HEAD：`PR #5 已合并；v0.2.2 固定在 424f4700a4d9726db1e9e1a7cfbadaee68a737e6。`
- 工作树：正式发布附件与MK-Firmware四份新固件SHA-256一致。原主工作区及其他仓库修改保留。
- 当前任务：将已发布的四份固件同步到主线MK-Firmware目录，并按维护者授权核对检查后合并PR #6。
- 状态：`complete`

## 里程碑

- **正式发布** — `complete`。0.2.2 标准安装包、Skill、Site Agent 已同步新旧 GitHub 和 Gitee；四份探针固件已同步，UF2 三端索引通过。

## 验证证据

- **发布与安装**：docs/verification/v0.2.2-release-final.md：Python2306通过/2跳过，GUI720、Rust19通过；正式NSIS87.6MiB，覆盖安装、内置后端、7059型号/2224FLM哈希、退出释放、更新签名及三端公开索引通过。
- **STM32与HPM功能回归**：按目标和功能查阅 v0.2.2-v4-stm32-regression-20260920.md、v0.2.2-v4-hpm6e80-regression-20260920.md、v0.2.2-online-verify-theme-20260920.md（均位于docs/verification）。包含高速档、烧录、窄值/非对齐、共享流、CLI/MCP/GUI；HPM6E80本轮UART未接。
- **HPM5301用户OTP**：docs/verification/v0.2.2-hpm-offline-otp-20260920.md：独立Flash回读门槛、旧API/旧值/缺文件停止、用户字和组18/19永久锁、真实Chrome/UART及断电保持通过。不能外推其他型号或安全生命周期字段。
- **固件发布**：HPMLinkV4.5.1、MicroLinkV4.5.1/V3.5.0/V2.8.0已公开下载校验；25项发布/升级测试通过。V2 RBL头/体CRC、长度及程序版本验证，打包头V1.0.0保留原件。此发布轮未刷机，不新增硬件认证。
- **历史证据**：旧版测试保留在docs/verification，按需查阅；旧失败或曾经待测项目不再逐项重复载入当前交接。

## 架构决策

- 开发主仓库MicroKeen/main；后续修改从最新main创建codex分支，经PR及必需CI整合。审批人数0，发布和合并仍需明确授权；标签不可变。
- 应用主索引MicroKeen/release，旧GitHub/updates兼容，Gitee/updates备用。固件三个firmware索引保持兼容，客户端URL仍可指向旧GitHub。
- 现有自动固件更新仅支持UF2；V2 RBL作为手动升级附件，不写入严格UF2索引，避免破坏0.2.2解析。
- 按维护者授权，Gitee应用发布页仅保留最新0.2.2，固件渠道独立保留；GitHub历史版本不删除。
- 保留正式包、唯一备份、依赖缓存和必要HIL证据。原主工作区用户固件替换不得reset。mklink-issues-pr自动任务维持暂停。

## 真机环境

- **state**：HPMLink V4 + HPM5301。Word72=1、Word79=3、HARD_LOCK=0x304C0016；38,364字节固件独立回读一致，UART0心跳递增。组18/19已永久锁定，禁止重放原配方。实际断电后GUI/独立回读和UART复核通过，不进行安全生命周期操作。
- **backups**：本地.build/reports保留原始HIL证据；Gitee历史备份与清理记录在.build/artifacts/gitee-historical-backup-20260921。
- **installer**：.build/artifacts/v0.2.2-official/Mklink-AI-Probe-v0.2.2-x64-Setup.exe（正式签名更新包，已覆盖安装）。

## 下一动作

1. 先读取本交接与docs/verification/v0.2.2-release-final.md；根据用户新任务选取具体历史报告，不重复已完成发布。
2. PR #6包含精简交接和已发布固件目录同步；从主工作区更新源码前核对用户修改，勿reset/stash未知修改。
3. 如需V2自动升级，单独实现RBL类型、校验与升级路径并回归；当前只提供手动RBL下载。
4. Cargo debug/release生成物已清理，后续构建自动重建；STM32测试.mklink历史capture.csv已转为相邻capture.csv.gz，旧分析脚本使用前按需解压。审计见.build/reports/disk-cleanup-20260921；其他E:/PHDZ由维护者处理。
5. MicroBoot文档及固件源码各有独立修改，接手先检查各仓库状态；硬件操作先枚举当前连接，勿重复OTP烧写。

## 已知限制

- 有限缓冲不保证无限暂停/物理断线无损；外设轮询可能漏短脉冲，多变量不是原子快照。
- 客户原始ELF/程序不可用，不能宣称复现其毛刺根因；odd-address packed halfword不保证原子性。
- HPM OTP仅按报告限定型号和字段；当前HPM5301组18/19永久锁定，禁止重放配方。其他安全GUI写入口未开放。
- PY32F030保护后恢复、物理Modbus、所有板卡、Mac/Linux与跨主机Agent未完整认证；STM32看门狗、STOP/STANDBY、WRP拒写仍待专测。
- Windows安装器无Authenticode签名（未知发布者），自动更新签名已验证；标准包不含离线WebView2。原生桌面本轮无新增视觉截图，Chrome截图不替代桌面视觉验收。
- HPM6E80回归有限时长且无UART；本次用户更新的四份固件只做格式/CRC/公开发布验证，不把历史实测外推到新二进制。

## 延续协议

- 先核对 Git、任务和设备状态；仅按需读相关验证报告，不加载历史流水账。
