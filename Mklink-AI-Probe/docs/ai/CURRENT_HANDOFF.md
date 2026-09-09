# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-09-09T18:12:12+08:00`
- 分支：`codex/repository-governance`
- HEAD：`最新提交以 Git 为准；应用发布标签 v0.2.0 = 911a70f。`
- 远端 HEAD：`开发主线 microkeen/main；本次基线 04f1f7b，已包含上游 PR #15/#17 的合并历史。`
- 工作树：权限配置与协作文档使用独立工作树；主工作区原 main 未切换。
- 当前任务：MicroKeen 更新分支与主线保护已配置，协作文档提交 PR 待另一维护者审核；未迁移正式发布服务。
- 状态：`ready`

## 里程碑

- **已交付** — `complete`。应用 0.2.0、MicroLink V3.4.0/V4.4.0 已发布；最新源码与报障流程已同步 MicroKeen/main。

## 验证证据

- **正式版**：docs/verification/v0.2.0-release-qualification.md：Python 1913、GUI 682、Rust 19；安装/Skill/CLI/MCP 及下载校验通过。
- **报障流程**：docs/verification/issue-feedback-stage1.md：本地/CI 各 60 项通过；真实缺陷自动修复闭环未验证。
- **硬件与固件**：docs/verification/v0.2.0-prerelease-hil-20260907.md、v0.2.0-superwatch-write-20260907.md；firmware-20260908.md 仅验证发布/格式/哈希，新固件未做 HIL。
- **仓库权限**：GitHub API 回读四项 active 规则；updates/firmware 与旧索引提交一致。仅 Aladdin-Wang 可绕过发布引用规则，main 审核/CI 无绕过者；未使用 su5176 身份执行写入测试。

## 架构决策

- 用户 Skill 只含运行时，报障指南按需读取；主仓库 MicroKeen/main，现有 Release/更新索引仍在 Aladdin-Wang 与 Gitee。
- 任务 mklink-issues-pr 为 PAUSED，未经要求不恢复；手动流程见 docs/ai/issue-maintenance.md，修复只提交 PR，合并由用户决定。
- 构建/清理遵循 AGENTS.md 与 docs/ai/build-storage.md；保留正式包、唯一备份、依赖缓存及 HIL 证据。
- 协作权限见 docs/ai/repository-governance.md：Aladdin-Wang、su5176 保持 Admin/Owner 并处理 PR；更新分支和正式标签仅 Aladdin-Wang 可写，最高管理员仍可修改规则，Release 附件权限不由分支规则隔离。

## 真机环境

- **state**：本次只配置仓库权限、复制已发布索引并更新维护文档，未操作硬件。
- **backups**：.build/reports/prerelease-hil-20260907、superwatch-write-20260907；保留其他芯片唯一备份。
- **installer**：.build/artifacts/release-0.2.0-20260908/Mklink-AI-Probe-v0.2.0-x64-Setup.exe

## 下一动作

1. 由另一位维护者审核 codex/repository-governance 的文档 PR，CI 通过后由两名指定维护者之一合并；AI 不自动合并。
2. 后续缺陷/功能从最新 microkeen/main 创建独立任务分支并提交 PR；定时任务保持暂停。
3. 正式发布仍使用原 Aladdin-Wang/Gitee 渠道。新 updates/firmware 不自动同步；切换前另行适配发布脚本并验证资产、签名与旧客户端兼容。

## 已知限制

- 高速 USB 识别异常暂缓；RTT 偶发启动失败及停止后 UART 残留未闭环。
- PY32F030 保护后恢复未闭环；未覆盖物理 Modbus、所有板卡、Mac/Linux 与跨主机 Agent。
- 外设轮询可漏短脉冲，缓冲有限；SystemView 启动可能丢弃少量数据。

## 延续协议

- 先核对 Git、任务和设备状态；仅按需读相关验证报告，不加载历史流水账。
