# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-09-12T23:13:04+08:00`
- 分支：`codex/v0.2.1-development`
- HEAD：`最新提交以 Git 为准；应用发布标签 v0.2.0 = 911a70f。`
- 远端 HEAD：`从 microkeen/main 的 7b826c35b1bea146c9afae6f0054e7df5477f28c 创建 0.2.1 开发分支，已包含合并的 PR #1。`
- 工作树：持续开发分支增加 mem_dump 三档、CLI/MCP 周期测量、SuperWatch 档位入口及 Windows 独立串口接收；协作探针固件已更新并完成 HPM 三档测试。
- 当前任务：HPM GUI验收：连接准备失败回滚、HPM脱机无通用reset/run、数组index/元素数已修。SystemView parser live 20026事件0丢弃通过；二次启动收到原始同步头，探针Recorder状态复位补丁已构建待升级复测。
- 状态：`in_progress`

## 里程碑

- **已交付** — `complete`。应用 0.2.0、MicroLink V3.4.0/V4.4.0 已发布；最新源码与报障流程已同步 MicroKeen/main。

## 验证证据

- **正式版**：docs/verification/v0.2.0-release-qualification.md：Python 1913、GUI 682、Rust 19；安装/Skill/CLI/MCP 及下载校验通过。 docs/verification/v0.2.0-prerelease-hil-20260907.md、v0.2.0-superwatch-write-20260907.md；firmware-20260908.md 仅验证发布/格式/哈希，新固件未做 HIL。
- **报障流程**：docs/verification/issue-feedback-stage1.md：本地/CI 各 60 项通过；真实缺陷自动修复闭环未验证。
- **仓库权限**：GitHub API 回读四项 active 规则；release/firmware 与旧索引提交一致。仅 Aladdin-Wang 可绕过发布引用规则，main 审核/CI 无绕过者；未使用 su5176 身份执行写入测试。
- **外设三端统一**：docs/verification/v0.2.1-peripheral-unification.md：Python 190 通过/1 跳过；HPM 43 型号共 1226962 条目录项可加载；HPM5301 CLI/MCP stdio/Chrome 三通道约 1 kHz，CRC/帧丢失/固件丢样标记为零。ARM 未做实板验证。
- **选项字节/OTP 第一阶段**：docs/verification/v0.2.1-device-configuration-stage1.md：Python 103、GUI 24、正式构建通过；HPM5301 CLI/MCP/Chrome 8 个公开字段一致；Chrome ARM 配置及脚本预览通过，没有 ARM 实板读写或 OTP 编程。
- **STM32F103 选项字节第二阶段**：docs/verification/v0.2.1-stm32f103-options-stage2.md：Python 99、GUI 29、生产构建通过；CLI/MCP stdio/Chrome 10 字段一致，DATA、两项低功耗复位位及 WRP3 写入/复位/回读/恢复通过；组合下载通过，最终全部 512 KiB Flash 与原始备份一致。未测试 RDP 转换及看门狗/低功耗/WRP 拒写行为。
- **mem_dump 三档与 USB 暂停容忍**：docs/verification/v0.2.1-mem-dump-batch.md：新固件4/10/20MHz单变量33.40/60.22/88.24k；多变量/4KB矩阵、6组30秒、逐帧BIN比对、150ms GIL暂停、MCP stdio/Web REST通过；C模型含错误/背压。旧121 Python/29 GUI证据在profiles报告，浏览器点击仍被工具阻断。
- **SuperWatch 与 SystemView 文档实测修复**：docs/verification/v0.2.1-hpm-gui-acceptance.md：172+159+149 Python、95 GUI与构建通过，部署复测协调中。trigger-cursors报告：Chrome两轮201点及游标通过。systemview-freertos-framing报告：live 5秒20026事件105348B丢弃0/0。原生CSV/PNG保存未验证。

## 架构决策

- 用户 Skill 只含运行时，报障指南按需读取；主仓库 MicroKeen/main，现有 Release/更新索引仍在 Aladdin-Wang 与 Gitee。
- 任务 mklink-issues-pr 为 PAUSED，未经要求不恢复；手动流程见 docs/ai/issue-maintenance.md，修复只提交 PR，合并由用户决定。
- 构建/清理遵循 AGENTS.md 与 docs/ai/build-storage.md；保留正式包、唯一备份、依赖缓存及 HIL 证据。
- 协作权限见 docs/ai/repository-governance.md：Aladdin-Wang、su5176 保持 Admin/Owner 并处理 PR；更新分支和正式标签仅 Aladdin-Wang 可写，最高管理员仍可修改规则，Release 附件权限不由分支规则隔离。
- 2026-09-10 用户指定 codex/v0.2.1-development 为本轮持续开发分支；后续修复继续该分支并推送 microkeen，整合 main 仍走审核 PR，不自动发布。

## 真机环境

- **state**：探针保持9836a48e批量固件。全局Skill已安装b0eed36开发快照并验证38个HTTP资源/三档接口；文档任务已将目标更新为16路波形RTT扩展。当前本任务不占设备，由文档任务协调Chrome复测。
- **backups**：.build/reports/prerelease-hil-20260907、superwatch-write-20260907；保留其他芯片唯一备份。；本轮本地证据 .build/reports/peripheral-unification。；本轮 OTP 只读和浏览器证据 .build/reports/device-configuration。；STM32F103 唯一原始备份与本轮证据 .build/reports/stm32f103-options。
- **installer**：.build/artifacts/release-0.2.0-20260908/Mklink-AI-Probe-v0.2.0-x64-Setup.exe

## 下一动作

1. 文档任务完成HPM脱机/数组GUI复测后释放COM488；升级Recorder会话复位固件并做连续两轮SystemView开始停止。记录新UF2哈希，不将既有性能矩阵冒充新固件重测。
2. Chrome扩展browser3已可用；已完成三档显示及single/游标实板，ARM20M仍待板卡校准。
3. 审核 PR #2 的三端外设统一、OTP 读取与 STM32F103 选项配置；不自动合并或发布。
4. 后续以用户提供的 STM32F103 工程补充看门狗、STOP/STANDBY 和 WRP 拒写行为测试，再扩展其他 ARM 系列和容量板卡；当前验证报告区分配置加载与外设行为。
5. HPM 永久编程仍需专用固件及单独授权。全局Skill已更新开发快照，正式安装器未更新；不发布，定时任务保持暂停。

## 已知限制

- 高速 USB 识别异常暂缓；RTT 偶发启动失败及停止后 UART 残留未闭环。
- PY32F030 保护后恢复未闭环；未覆盖物理 Modbus、所有板卡、Mac/Linux 与跨主机 Agent。
- 外设轮询可漏短脉冲，缓冲有限；SystemView 启动可能丢弃少量数据。
- 共享外设目录目前只支持对齐 32 位、小端、无已知读取副作用的寄存器；真实 16 位 MMIO 需要探针协议/固件补齐和 ARM 实板验证。HPM 全型号目录加载不等同全外设 HIL。
- STM32F103 非 XL USER/DATA/WRP 配置已开放，实板为 V4 高容量组；WDG_SW 保持软件模式，未验证低功耗进入和 WRP 拒写行为。V3/其他容量仅描述与生成测试；其他 ARM 维持原有安全配方，G474/PY32 仍仅 V3。HPM OTP 永久写入未开放。
- 新批量路径限HPM5301白名单DLM/XIP对齐<=64B/16word、最多15区域，<50us请求沿用满速语义。批末验证、每样本末word响应时间戳，非原子多变量/硬实时。未达参考148K，4KB无收益；旧4.361ms根因仍未定位，冻结安装版无独立接收进程。

## 延续协议

- 先核对 Git、任务和设备状态；仅按需读相关验证报告，不加载历史流水账。
