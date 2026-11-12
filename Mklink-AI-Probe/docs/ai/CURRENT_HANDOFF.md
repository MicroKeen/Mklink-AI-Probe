# 当前 AI 交接

> 本文件由 `python scripts/ai_memory.py render` 根据 `project-memory.json` 生成。

## 当前断点

- 更新时间：`2026-11-12T15:10:04+08:00`
- 分支：`codex/v0.5.0-fixes`
- HEAD：`c60af890`
- 远端 HEAD：`c60af890`
- 工作树：以上为随 AXF/ELF 保存 SuperWatch 配置的产品代码提交，已推送。当前安装包仍为 8f8709a4、安装 Web 为 61d46690；不含通用工程初始化、TXT 日志和符号旁配置，本轮未重建或覆盖安装。
- 当前任务：首次加载 AXF/ELF 创建同目录追加 .superwatch.json 的配置，自动保存并恢复变量、数组范围、间隔和显示设置。Web GUI、Skill/CLI、MCP 共用后台；按当前符号解析地址，恢复不自动采集。见[配置验证记录](../verification/v050-superwatch-profile.md)。继续在 [PR #79](https://github.com/MicroKeen/Mklink-AI-Probe/pull/79) 审阅，未合并或发布。
- 状态：`SuperWatch 符号旁配置已完成并推送，等待 PR 审阅`

## 里程碑

- **0.5.0 上位机开发基线** — `已合入 main`。2026-11-09，[PR #78](https://github.com/MicroKeen/Mklink-AI-Probe/pull/78) 以 `2861d7a6` 合入，新增 CLI 显式重载 AXF/ELF 符号，[Issue #77](https://github.com/MicroKeen/Mklink-AI-Probe/issues/77) 已关闭（Completed）。随后 [PR #76](https://github.com/MicroKeen/Mklink-AI-Probe/pull/76) 以 `cf034fe1` 合入，修复 Windows 普通用户因 jobs.json 访问受限而无法连接探针的问题，[Issue #75](https://github.com/MicroKeen/Mklink-AI-Probe/issues/75) 已关闭（Completed）。
- **MKLink 0.4.3** — `正式`。`v0.4.3` 指向 `3905a68b`。Windows 上位机、完整 Skill、Site Agent、MicroLink V3.6.9、MicroLink V4.7.3 和 HPMLink V4.7.3 已发布。MicroLink V2 沿用 V2.9.3。

## 验证证据

- **SuperWatch 配置与可读日志**：配置最终 Python 207 项、GUI 266 项、流与文档边界 218 项通过，TypeScript/生产构建通过。真实浏览器验证创建、修改、后台重启、两文件隔离和恢复；使用离线符号夹具，未做新真机或安装验收。见[配置报告](../verification/v050-superwatch-profile.md)。此前 TXT 的 43 项 Python、103 项 GUI、69 项边界及软件对照/真实浏览器记录保留在[日志报告](../verification/v050-recording-text.md)，冻结包退出续转待验。
- **通用工程配置与直接烧录**：424 项相关回归通过，覆盖通用/IDE 导入、配置保留、共享烧录、目标提示、HPM/API 和 Skill 边界。真实 CLI 子进程完成离线 CMake 初始化、重复初始化及错误退出校验。显式目标冲突或旧 profile 阻止覆盖，多个固件候选要求显式选择。本轮未操作硬件、未更新安装包，详见[验证记录](../verification/v050-project-init.md)。
- **Windows 普通用户安装**：安装与卸载均以 RID 8192 运行。最终候选覆盖后 3,672 个文件匹配、6 份用户配置及端口名称保持不变，桌面/Web/CLI/MCP、内置资源和正常退出通过。安装相关 66 项、配置页 47 项通过。候选哈希、旧 HKLM 登记及遗留文件边界见[安装验证记录](../verification/v050-user-installer.md)。
- **V3 / V4 SuperWatch 恢复**：普通 V4 修复候选实物拔插跨 12.637 秒缺口原订阅恢复，V4.7.4 健康检查通过，223,728 组、零读错及队列丢弃，中位 43,486.6 组/秒。V3.6.10 实刷及拔插恢复通过，1,484,544 组，零队列丢弃、序号异常和时间倒退，恢复后中位 43,056.7 组/秒。旧 V3.6.8 缺采样能力，无同条件旧版基线。版本及未验范围见[恢复验证记录](../verification/v050-superwatch-swclk.md)。
- **合并回归**：集成提交 `0b80e790` 与主线合并提交 `cf034fe1` 的文件树一致。Python 全量 6846 项通过，2 项因缺少 `hil_core.observe` 跳过。GUI 全量 1203 项通过，生产 Web 构建通过。
- **普通权限连接**：原分支 1015 项回归覆盖只读日志、权限恢复和不重放。与 PR #78 集成后，在 Windows 普通权限进程中拒绝读取临时 jobs.json，GUI 使用的选择并连接接口成功连接 V4.7.3 真机。任务查询返回 503；恢复权限后，同一后台找回原 request_id，日志字节未变。
- **发布、验收与清理**：正式包哈希、安装、Skill 更新、分发渠道及真机记录见[发布报告](../verification/v043-release-handoff.md)。 C/E/F 清理回执、人工检查清单和恢复资料位置见[清理报告](../verification/v043-postrelease-cleanup-20261108.md)。
- **CLI 符号重载**：238 项回归通过。V4.7.3 与 STM32F103 真机读回 116736 字节，与 Keil 工程映像一致。同路径重链后 watch 返回 409，显式重载使目录从 1 升到 2，新变量名与系统 tick 读取成功。另以 GCC ELF 和模拟内存验证了变量换址。与 PR #76 集成后，在同一探针和 STM32F103 上重复验证了映像一致、过期拒读、显式重载和 SDK 重新附着。

## 架构决策

- 采集或调试改动须按[上位机基线](../verification/v043-host-baseline.md)同条件复测 SuperWatch、RTT 和调试共存，核对数据完整性。
- 默认仅构建 Windows。用 PowerShell 7、UTF-8 和 `scripts/build_workspace.ps1`，构建根为 `F:/MKLink-Build`。
- Windows NSIS 默认 currentUser；安装不自动命名 USB 端口。只有用户确认修改或恢复端口显示名称时，才调用独立 UAC 助手。旧机器级登记与受保护目录不自动迁移。
- 上海轻量服务器直供最新版，历史文件由 COS 和 Git 保存。COS 累计 189 GiB 告警、207.9 GiB 停止，已取消日期截止。账本和停止锁按[下载策略](tencent-updates.md)维护。
- 跨会话固件联测固定上位机提交并核对 mklink/runtime 模块导入路径；主工作区和全局 editable 入口不自动代表当前任务版本。
- project-init 是可选离线配置工具；通用工程可显式传型号和文件，直接烧录不依赖初始化。型号或镜像不明确时要求补充输入，不猜测，也不自动迁移已有芯片配置。
- RTT / SuperWatch 继续实时记录 JSONL，停止后自动后台生成同名 UTF-8 TXT。RTT 使用主机收发时间，SuperWatch 保留采样相对时间并在头部记录开始日期；TXT 供阅读，JSONL 供回放。
- SuperWatch 配置由共享后台保存在 AXF/ELF 旁，名称为原文件名加 .superwatch.json；三端共用名称与修订协议，不存变量地址、不自动开始采集。显示修改防抖，样本接收不写配置；浏览器上传只能保存到后台副本旁。

## 真机环境

- **操作前**：重新核对下载器型号、目标和占用。固件变更由指定会话协调，升降级按本次授权执行。VCC、OTP 操作分别确认。
- **普通 V4**：固件会话已回读 V4.7.4 / 2026-11-10T13:55:55，原 STM32F103 健康采样通过；测试结束时专用后台退出并释放探针。下次操作仍需重新核对占用。
- **普通 V3**：固件会话已回读 V3.6.10 / 2026-11-10T14:14:14，原 STM32F103 的一次 SWCLK 拔插恢复通过；测试结束时后台退出、设备释放。下次仍需重新核对占用。

## 下一动作

1. 审阅 PR #79 的普通用户安装、SuperWatch 状态提示、通用工程配置、可读日志及符号旁配置；合并和发布仍需明确指令，执行全量及受影响实际环境门禁。
2. 当前安装版不含通用工程配置、TXT 日志和 SuperWatch 符号旁配置。下次构建安装包时补测冻结包退出后 TXT 续转及真实符号配置恢复，按受影响范围执行真机/发布门禁。V3.6.10/V4.7.4 固件继续由固件项目维护。
3. 后续沿用 codex/v0.5.0-fixes 工作树；接手时 fetch microkeen 并核对实际分支、远端和已有改动。

## 已知限制

- 普通读取 P95 和间隔读取稳定低于 1 ms、最大采样间隔 20 µs、40 µs 翻转零漏采仍是未达目标。
- 公网远程中继继续延期。独立 [S3 PR #65](https://github.com/MicroKeen/Mklink-AI-Probe/pull/65) 仍开放。其他硬件的[历史未验范围](known-limits-20261030.md)按需查阅。
- TXT 转换的源码退出续转已测，实际冻结安装包退出续转待验；转换仍使用 CPU/磁盘且没有全局并发上限，软件对照不代表真机性能结论。

## 延续协议

- 后续合并、签名或正式发布须有新的明确指令。
