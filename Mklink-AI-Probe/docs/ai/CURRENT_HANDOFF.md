# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-11-10T14:26:23+08:00`
- 分支：`codex/v0.5.0-fixes`
- HEAD：`1888fd10`
- 远端 HEAD：`1888fd10`
- 工作树：以上为 V3.6.10 固件验收同步前的分支快照。已安装上位机产品代码为 8f8709a4，生产 Web 同步为 61d46690。
- 当前任务：普通用户安装和 SuperWatch 状态提示见 [PR #79](https://github.com/MicroKeen/Mklink-AI-Probe/pull/79)。上位机本地包已覆盖安装；固件会话完成 V4.7.4 升级和 V3.6.10 实物拔插恢复，验证范围见[记录](../verification/v050-superwatch-swclk.md)。
- 状态：`普通用户安装完成，V3/V4 本地修复固件已升级`

## 里程碑

- **0.5.0 上位机开发基线** — `已合入 main`。2026-11-09，[PR #78](https://github.com/MicroKeen/Mklink-AI-Probe/pull/78) 以 `2861d7a6` 合入，新增 CLI 显式重载 AXF/ELF 符号，[Issue #77](https://github.com/MicroKeen/Mklink-AI-Probe/issues/77) 已关闭（Completed）。随后 [PR #76](https://github.com/MicroKeen/Mklink-AI-Probe/pull/76) 以 `cf034fe1` 合入，修复 Windows 普通用户因 jobs.json 访问受限而无法连接探针的问题，[Issue #75](https://github.com/MicroKeen/Mklink-AI-Probe/issues/75) 已关闭（Completed）。
- **MKLink 0.4.3** — `正式`。`v0.4.3` 指向 `3905a68b`。Windows 上位机、完整 Skill、Site Agent、MicroLink V3.6.9、MicroLink V4.7.3 和 HPMLink V4.7.3 已发布。MicroLink V2 沿用 V2.9.3。

## 验证证据

- **Windows 普通用户安装**：安装与卸载均以 RID 8192 运行。最终候选覆盖后 3,672 个文件匹配、6 份用户配置及端口名称保持不变，桌面/Web/CLI/MCP、内置资源和正常退出通过。安装相关 66 项、配置页 47 项通过。候选哈希、旧 HKLM 登记及遗留文件边界见[安装验证记录](../verification/v050-user-installer.md)。
- **V4 SuperWatch 恢复**：V4.7.3 修复候选在用户实物拔插后，原订阅跨过 12.637 秒缺口自动续采。普通 V4 随后升至 V4.7.4，健康检查收到 223,728 组、零读错及队列丢弃，中位 43,486.6 组/秒。本轮未重做拔插，沿用相同恢复代码的上午证据。版本、哈希和验收边界见[验证记录](../verification/v050-superwatch-swclk.md)。
- **V3 SuperWatch 恢复**：V3.6.10 实刷回读通过，用户拔插 SWCLK 后同一订阅自动恢复，中断期间样本计数冻结。最终 1,484,544 组，零队列丢弃、序号异常和时间倒退，恢复后中位 43,056.7 组/秒。旧 V3.6.8 缺采样能力，无同条件旧版基线；有日志负载的 RTT 拔插、Keil/IAR 实机并行仍未验，详见[记录](../verification/v050-superwatch-swclk.md)。
- **合并回归**：集成提交 `0b80e790` 与主线合并提交 `cf034fe1` 的文件树一致。Python 全量 6846 项通过，2 项因缺少 `hil_core.observe` 跳过。GUI 全量 1203 项通过，生产 Web 构建通过。
- **普通权限连接**：原分支 1015 项回归覆盖只读日志、权限恢复和不重放。与 PR #78 集成后，在 Windows 普通权限进程中拒绝读取临时 jobs.json，GUI 使用的选择并连接接口成功连接 V4.7.3 真机。任务查询返回 503；恢复权限后，同一后台找回原 request_id，日志字节未变。
- **发布与验收**：正式包哈希、安装、Skill 更新、分发渠道及真机记录见[发布报告](../verification/v043-release-handoff.md)。
- **工作区清理**：C/E/F 清理回执、人工检查清单和恢复资料位置见[清理报告](../verification/v043-postrelease-cleanup-20261108.md)。
- **CLI 符号重载**：238 项回归通过。V4.7.3 与 STM32F103 真机读回 116736 字节，与 Keil 工程映像一致。同路径重链后 watch 返回 409，显式重载使目录从 1 升到 2，新变量名与系统 tick 读取成功。另以 GCC ELF 和模拟内存验证了变量换址。与 PR #76 集成后，在同一探针和 STM32F103 上重复验证了映像一致、过期拒读、显式重载和 SDK 重新附着。

## 架构决策

- 采集或调试改动须按[上位机基线](../verification/v043-host-baseline.md)同条件复测 SuperWatch、RTT 和调试共存，核对数据完整性。
- 默认仅构建 Windows。用 PowerShell 7、UTF-8 和 `scripts/build_workspace.ps1`，构建根为 `F:/MKLink-Build`。
- Windows NSIS 默认 currentUser；安装不自动命名 USB 端口。只有用户确认修改或恢复端口显示名称时，才调用独立 UAC 助手。旧机器级登记与受保护目录不自动迁移。
- 上海轻量服务器直供最新版，历史文件由 COS 和 Git 保存。COS 累计 189 GiB 告警、207.9 GiB 停止，已取消日期截止。账本和停止锁按[下载策略](tencent-updates.md)维护。
- 跨会话固件联测固定上位机提交并核对 mklink/runtime 模块导入路径；主工作区和全局 editable 入口不自动代表当前任务版本。

## 真机环境

- **操作前**：重新核对下载器型号、目标和占用。固件变更由指定会话协调，升降级按本次授权执行。VCC、OTP 操作分别确认。
- **普通 V4**：固件会话已回读 V4.7.4 / 2026-11-10T13:55:55，原 STM32F103 健康采样通过；测试结束时专用后台退出并释放探针。下次操作仍需重新核对占用。
- **普通 V3**：固件会话已回读 V3.6.10 / 2026-11-10T14:14:14，原 STM32F103 的一次 SWCLK 拔插恢复通过；测试结束时后台退出、设备释放。下次仍需重新核对占用。

## 下一动作

1. 审阅上位机 PR #79。V4.7.4 与 V3.6.10 均为本地已验包，正式发布及其他目标的验证由固件项目维护。
2. 下一项上位机任务沿用现有 `codex/v0.5.0-fixes` 工作树。接手时执行 `git fetch microkeen`，核对本地分支、远端跟踪分支和工作树状态。

## 已知限制

- 普通读取 P95 和间隔读取稳定低于 1 ms、最大采样间隔 20 µs、40 µs 翻转零漏采仍是未达目标。
- 公网远程中继继续延期。独立 [S3 PR #65](https://github.com/MicroKeen/Mklink-AI-Probe/pull/65) 仍开放。其他硬件的[历史未验范围](known-limits-20261030.md)按需查阅。

## 延续协议

- 后续合并、签名或正式发布须有新的明确指令。
