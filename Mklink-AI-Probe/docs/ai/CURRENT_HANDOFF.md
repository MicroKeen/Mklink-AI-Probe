# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-11-10T10:20:56+08:00`
- 分支：`codex/v0.5.0-fixes`
- HEAD：`8d895328`
- 远端 HEAD：`8d895328`
- 工作树：以上为此次记录前已推送的源码与生产 Web 快照。开发基线为 cf034fe1。
- 当前任务：SuperWatch 拔插 SWCLK 后的状态提示已提交 [PR #79](https://github.com/MicroKeen/Mklink-AI-Probe/pull/79)。MicroLink V4 的 SWD 重连由固件项目跟进。
- 状态：`上位机已验证，待固件联测`

## 里程碑

- **0.5.0 上位机开发基线** — `已合入 main`。2026-11-09，[PR #78](https://github.com/MicroKeen/Mklink-AI-Probe/pull/78) 以 `2861d7a6` 合入，新增 CLI 显式重载 AXF/ELF 符号，[Issue #77](https://github.com/MicroKeen/Mklink-AI-Probe/issues/77) 已关闭（Completed）。随后 [PR #76](https://github.com/MicroKeen/Mklink-AI-Probe/pull/76) 以 `cf034fe1` 合入，修复 Windows 普通用户因 jobs.json 访问受限而无法连接探针的问题，[Issue #75](https://github.com/MicroKeen/Mklink-AI-Probe/issues/75) 已关闭（Completed）。
- **MKLink 0.4.3** — `正式`。`v0.4.3` 指向 `3905a68b`。Windows 上位机、完整 Skill、Site Agent、MicroLink V3.6.9、MicroLink V4.7.3 和 HPMLink V4.7.3 已发布。MicroLink V2 沿用 V2.9.3。

## 验证证据

- **SuperWatch 读取中断**：现场旧版错误计数、普通采样恢复、Edge 双语提示和待验的固件联测见[验证记录](../verification/v050-superwatch-swclk.md)。
- **合并回归**：集成提交 `0b80e790` 与主线合并提交 `cf034fe1` 的文件树一致。Python 全量 6846 项通过，2 项因缺少 `hil_core.observe` 跳过。GUI 全量 1203 项通过，生产 Web 构建通过。
- **普通权限连接**：原分支 1015 项回归覆盖只读日志、权限恢复和不重放。与 PR #78 集成后，在 Windows 普通权限进程中拒绝读取临时 jobs.json，GUI 使用的选择并连接接口成功连接 V4.7.3 真机。任务查询返回 503；恢复权限后，同一后台找回原 request_id，日志字节未变。
- **发布与验收**：正式包哈希、安装、Skill 更新、分发渠道及真机记录见[发布报告](../verification/v043-release-handoff.md)。
- **工作区清理**：C/E/F 清理回执、人工检查清单和恢复资料位置见[清理报告](../verification/v043-postrelease-cleanup-20261108.md)。
- **CLI 符号重载**：238 项回归通过。V4.7.3 与 STM32F103 真机读回 116736 字节，与 Keil 工程映像一致。同路径重链后 watch 返回 409，显式重载使目录从 1 升到 2，新变量名与系统 tick 读取成功。另以 GCC ELF 和模拟内存验证了变量换址。与 PR #76 集成后，在同一探针和 STM32F103 上重复验证了映像一致、过期拒读、显式重载和 SDK 重新附着。

## 架构决策

- 采集或调试改动须按[上位机基线](../verification/v043-host-baseline.md)同条件复测 SuperWatch、RTT 和调试共存，核对数据完整性。
- 默认仅构建 Windows。用 PowerShell 7、UTF-8 和 `scripts/build_workspace.ps1`，构建根为 `F:/MKLink-Build`。
- 上海轻量服务器直供最新版，历史文件由 COS 和 Git 保存。COS 累计 189 GiB 告警、207.9 GiB 停止，已取消日期截止。账本和停止锁按[下载策略](tencent-updates.md)维护。

## 真机环境

- **操作前**：重新核对下载器型号、目标和占用。固件变更由指定会话协调，升降级按本次授权执行。VCC、OTP 操作分别确认。

## 下一动作

1. 使用固件候选和本分支上位机在同一板卡上完成 SWCLK 拔插与基线复测，记录自动续采、原始数据和性能。
2. 下一项上位机任务沿用现有 `codex/v0.5.0-fixes` 工作树。接手时执行 `git fetch microkeen`，核对本地分支、远端跟踪分支和工作树状态。

## 已知限制

- 普通读取 P95 和间隔读取稳定低于 1 ms、最大采样间隔 20 µs、40 µs 翻转零漏采仍是未达目标。
- 公网远程中继继续延期。独立 [S3 PR #65](https://github.com/MicroKeen/Mklink-AI-Probe/pull/65) 仍开放。其他硬件的[历史未验范围](known-limits-20261030.md)按需查阅。

## 延续协议

- 后续合并、签名或正式发布须有新的明确指令。
