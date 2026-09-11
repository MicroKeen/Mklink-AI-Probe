# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-09-11T14:24:44+08:00`
- 分支：`codex/v0.2.1-development`
- HEAD：`最新提交以 Git 为准；应用发布标签 v0.2.0 = 911a70f。`
- 远端 HEAD：`从 microkeen/main 的 7b826c35b1bea146c9afae6f0054e7df5477f28c 创建 0.2.1 开发分支，已包含合并的 PR #1。`
- 工作树：本轮在既有 codex/v0.2.1-development 修改上位机源码；协作固件项目仅审计，未修改或更新探针固件。
- 当前任务：已完成外设三端统一和 ARM 读取审计；190 通过/1 跳过，43 个 HPM 型号可加载，最终 HPM5301 CLI/MCP/Chrome 三通道约 1 kHz 通过。提交指定开发分支供审核。
- 状态：`ready_for_review`

## 里程碑

- **已交付** — `complete`。应用 0.2.0、MicroLink V3.4.0/V4.4.0 已发布；最新源码与报障流程已同步 MicroKeen/main。

## 验证证据

- **正式版**：docs/verification/v0.2.0-release-qualification.md：Python 1913、GUI 682、Rust 19；安装/Skill/CLI/MCP 及下载校验通过。
- **报障流程**：docs/verification/issue-feedback-stage1.md：本地/CI 各 60 项通过；真实缺陷自动修复闭环未验证。
- **硬件与固件**：docs/verification/v0.2.0-prerelease-hil-20260907.md、v0.2.0-superwatch-write-20260907.md；firmware-20260908.md 仅验证发布/格式/哈希，新固件未做 HIL。
- **仓库权限**：GitHub API 回读四项 active 规则；release/firmware 与旧索引提交一致。仅 Aladdin-Wang 可绕过发布引用规则，main 审核/CI 无绕过者；未使用 su5176 身份执行写入测试。
- **外设三端统一**：docs/verification/v0.2.1-peripheral-unification.md：Python 190 通过/1 跳过；HPM 43 型号共 1226962 条目录项可加载；HPM5301 CLI/MCP stdio/Chrome 三通道约 1 kHz，CRC/帧丢失/固件丢样标记为零。ARM 未做实板验证。

## 架构决策

- 用户 Skill 只含运行时，报障指南按需读取；主仓库 MicroKeen/main，现有 Release/更新索引仍在 Aladdin-Wang 与 Gitee。
- 任务 mklink-issues-pr 为 PAUSED，未经要求不恢复；手动流程见 docs/ai/issue-maintenance.md，修复只提交 PR，合并由用户决定。
- 构建/清理遵循 AGENTS.md 与 docs/ai/build-storage.md；保留正式包、唯一备份、依赖缓存及 HIL 证据。
- 协作权限见 docs/ai/repository-governance.md：Aladdin-Wang、su5176 保持 Admin/Owner 并处理 PR；更新分支和正式标签仅 Aladdin-Wang 可写，最高管理员仍可修改规则，Release 附件权限不由分支规则隔离。
- 2026-09-10 用户指定 codex/v0.2.1-development 为本轮持续开发分支；后续修复继续该分支并推送 microkeen，整合 main 仍走审核 PR，不自动发布。

## 真机环境

- **state**：HPM5301 已完成 GPIO 位、UART GPR 字段和 GPTMR1 三通道 CLI/MCP/Web 采集；源码服务保留，采集停止。全局已安装 Skill 与正式安装器未升级。
- **backups**：.build/reports/prerelease-hil-20260907、superwatch-write-20260907；保留其他芯片唯一备份。；本轮本地证据 .build/reports/peripheral-unification。
- **installer**：.build/artifacts/release-0.2.0-20260908/Mklink-AI-Probe-v0.2.0-x64-Setup.exe

## 下一动作

1. 审核 codex/v0.2.1-development 的外设统一 PR；不自动合并或发布。
2. 若后续需要 8/16 位 MMIO，先补齐明确访问宽度协议和固件实现，再连接 ARM 实板验证。
3. 正式安装器/全局 Skill 未更新；发布仍需单独授权，既有定时任务保持暂停。

## 已知限制

- 高速 USB 识别异常暂缓；RTT 偶发启动失败及停止后 UART 残留未闭环。
- PY32F030 保护后恢复未闭环；未覆盖物理 Modbus、所有板卡、Mac/Linux 与跨主机 Agent。
- 外设轮询可漏短脉冲，缓冲有限；SystemView 启动可能丢弃少量数据。
- 共享外设目录目前只支持对齐 32 位、小端、无已知读取副作用的寄存器；真实 16 位 MMIO 需要探针协议/固件补齐和 ARM 实板验证。HPM 全型号目录加载不等同全外设 HIL。

## 延续协议

- 先核对 Git、任务和设备状态；仅按需读相关验证报告，不加载历史流水账。
