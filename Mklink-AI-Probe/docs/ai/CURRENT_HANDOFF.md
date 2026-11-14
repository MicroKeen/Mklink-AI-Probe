# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-11-14T13:27:26+08:00`
- 分支：`codex/agent-ui-workbench`
- HEAD：`6cb1364d87e8ad4ed1f835ea82e672f75844948f`
- 远端 HEAD：`cf034fe1cf11ee39c3bc7e40d38d6811a019e1d0`
- 工作树：head 记录动态组件与停靠扩展实现提交；本记忆单独提交。remote_head 为收尾再次获取且未变化的 microkeen/main 基线。功能分支及草稿 PR #80 按流程更新，未合并；其他工作树未提交修改已保留。接手时重新核对远端。
- 当前任务：基于当前主线完成 SuperWatch 19 组语义动作、多波形/变量/RTT/串口子面板，并扩展 controls 动态组件、真实接口绑定、跨窗口移动、停靠标签与 v2 布局。用户与 Agent 共用业务及显示操作。入口见[工作台说明](../frontend-workbench.md)、[组件开发](../frontend-components.md)和[验证报告](../verification/agent-ui-workbench.md)。
- 状态：`语义组态工作台完成，草稿 PR #80 待审查与授权真机验收`

## 里程碑

- **MKLink 0.4.3** — `正式`。`v0.4.3` 指向 `3905a68b`。Windows 上位机、完整 Skill、Site Agent、MicroLink V3.6.9、MicroLink V4.7.3 和 HPMLink V4.7.3 已发布。MicroLink V2 沿用 V2.9.3。

## 验证证据

- **Agent 语义工作台**：最终 GUI 全量 1265、后台相关 272、公共 Skill 边界 78 项通过，类型与生产构建通过。真实认证后台/浏览器完成原多面板回放/PNG/意图往返，以及组件注册绑定、UI/Agent 同动作、原生跨窗拖动/停靠、草稿保持、v2 保存恢复和明暗/窄屏检查。unknown、改绑恢复、显式空字符串、结果身份与并发保护均有回归。详见[验证报告](../verification/agent-ui-workbench.md)。
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

1. 接手时核对任务分支、[草稿 PR #80](https://github.com/MicroKeen/Mklink-AI-Probe/pull/80)、CI 和工作树并执行 git fetch microkeen；不要覆盖其他工作树未提交变更。
2. 按工作台验证报告和 0.4.3 基线完成获授权的真机采集/写入、多端点和持续性能验收；确认需要后再开展精确选区。合并、安装或发布仍需明确指令。

## 已知限制

- 工作台未做真机写入、多端点持续采集和资源性能验收；32 面板为数量上限。动态类型需源码 manifest/renderer 注册及构建，运行时组合已注册能力；当前为页内网格和停靠标签，无独立系统窗口、跨屏同步或任意热加载。意图为面板级，未实现精确采样点/日志选区；未构建安装包。
- 普通读取 P95 和间隔读取稳定低于 1 ms、最大采样间隔 20 µs、40 µs 翻转零漏采仍是未达目标。
- 公网远程中继继续延期。独立 [S3 PR #65](https://github.com/MicroKeen/Mklink-AI-Probe/pull/65) 仍开放。其他硬件的[历史未验范围](known-limits-20261030.md)按需查阅。

## 延续协议

- 后续合并、签名或正式发布须有新的明确指令。
