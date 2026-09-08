# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-09-08T21:14:34+08:00`
- 分支：`main`
- HEAD：`最新提交以 Git 为准；应用发布标签 v0.2.0 = 911a70f。`
- 远端 HEAD：`microkeen/main 为开发主线；origin/master 保留旧发布基线。`
- 工作树：旧候选包/缓存已清理约 1.08 GB，用户随后清空 .build/runs，已核实。其余保留项见 .build/reports/workspace-cleanup-20260908/cleanup-summary.md。
- 当前任务：发布与仓库迁移完成；定时任务暂停，等待用户手动指定 Issue。
- 状态：`ready`

## 里程碑

- **已交付** — `complete`。应用 0.2.0、MicroLink V3.4.0/V4.4.0 已发布；最新源码与报障流程已同步 MicroKeen/main。

## 验证证据

- **正式版**：docs/verification/v0.2.0-release-qualification.md：Python 1913、GUI 682、Rust 19；安装/Skill/CLI/MCP 及下载校验通过。
- **报障流程**：docs/verification/issue-feedback-stage1.md：本地/CI 各 60 项通过；真实缺陷自动修复闭环未验证。
- **硬件与固件**：docs/verification/v0.2.0-prerelease-hil-20260907.md、v0.2.0-superwatch-write-20260907.md；firmware-20260908.md 仅验证发布/格式/哈希，新固件未做 HIL。

## 架构决策

- 用户 Skill 只含运行时，报障指南按需读取；主仓库 MicroKeen/main，现有 Release/更新索引仍在 Aladdin-Wang 与 Gitee。
- 任务 mklink-issues-pr 为 PAUSED，未经要求不恢复；手动流程见 docs/ai/issue-maintenance.md，修复只提交 PR，合并由用户决定。
- 构建/清理遵循 AGENTS.md 与 docs/ai/build-storage.md；保留正式包、唯一备份、依赖缓存及 HIL 证据。

## 真机环境

- **state**：本轮仅清理与交接，不操作硬件；以重新发现设备为准，旧测试的写入/供电授权不自动延续。
- **backups**：.build/reports/prerelease-hil-20260907、superwatch-write-20260907；保留其他芯片唯一备份。
- **installer**：.build/artifacts/release-0.2.0-20260908/Mklink-AI-Probe-v0.2.0-x64-Setup.exe

## 下一动作

1. 等待用户指定 Issue：先分析或按要求修复、验证、提交 PR；不自动合并/发布/恢复定时任务。
2. 上游 su5176 PR #17 仍 OPEN 且冲突；仅按用户后续要求整合。迁移新仓库 Release/更新服务也尚未进行。

## 已知限制

- 高速 USB 识别异常暂缓；RTT 偶发启动失败及停止后 UART 残留未闭环。
- PY32F030 保护后恢复未闭环；未覆盖物理 Modbus、所有板卡、Mac/Linux 与跨主机 Agent。
- 外设轮询可漏短脉冲，缓冲有限；SystemView 启动可能丢弃少量数据。

## 延续协议

- 先核对 Git、任务和设备状态；仅按需读相关验证报告，不加载历史流水账。
