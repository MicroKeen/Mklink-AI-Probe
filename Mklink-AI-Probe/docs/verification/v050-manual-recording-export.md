# 手动日志转换与普通用户覆盖安装

2026-11-12，产品提交 `c66523b80c0863b82c93fd30feda28da059ef0c5`，
继续 `codex/v0.5.0-fixes` / PR #79。根据用户的新选择，替代此前停止后自动生成 TXT 的行为。

## 当前行为

- SuperWatch 和 RTT 停止记录只排空并关闭 JSONL，不启动转换。
- 在对应日志区域手动点击：SuperWatch 转为 Excel，RTT 转为带时间戳的 TXT。
  本次记录的全部分段参与转换；当前入口针对后台最近一次记录。
- Excel 使用独立低优先级进程和 XlsxWriter 按行写入。`Info` 页说明时间和完整性；
  数据页包含采样相对时间、变量列和中断事件，提供表头冻结与筛选。
  每页最多 1,048,576 行（含表头），超限或新增变量列继续到下一页。
- 转换状态独立于记录状态；原始 JSONL 不变，已有同名结果不覆盖。
  请求带当前日志路径，拒绝仍在记录或已切换记录的旧请求；重复请求共用同一个任务。
- Web、共享 CLI/SDK、MCP 使用相同的 export 能力与 `export_*` 状态。
  RTT 停止接口同时接受既有 query channel 和 CLI/MCP 的 JSON channel。
  转换属于主机文件操作，不占用或停止正在运行的探针采集。

Excel 数值约有 15 位有效数字；JSONL 仍是无损数据源。
原理依据：[XlsxWriter 内存说明](https://xlsxwriter.readthedocs.io/working_with_memory.html)、
[数值与工作表限制](https://xlsxwriter.readthedocs.io/worksheet.html#worksheet-write-number)。

## 软件验证

PowerShell 7 / UTF-8，所有构建与测试经 `scripts/build_workspace.ps1`，
BuildRoot 为 `F:/MKLink-Build`。

| 检查 | 结果 | 日志 |
|---|---|---|
| 转换、记录器、HTTP、MCP | 56 passed | `run-20261112-163527-be98649c.log` |
| 共享后台、CLI、流性能、RTT/SuperWatch、用户内容边界 | 296 passed | `run-20261112-163811-7c6a6e11.log` |
| Recording、SuperWatchTab、WaveformViewer | 152 passed | `run-20261112-163642-cd64b5cd.log` |
| TypeScript 与生产 Web | 通过 | artifacts 中 source/gui/dist |
| 全新冻结 sidecar、Tauri、NSIS | 通过 | `run-20261112-164114-d6a1045d.log` |
| 记忆、Skill 边界、桌面资源、安装元数据/文件检查 | 96 passed | `run-20261112-170036-d6b75fdc.log` |

专项覆盖：停止无转换、运行中拒绝、路径过期、重复请求、文件冲突、中文与公式形式变量名、
相对时间、有效前缀与中断标记、行数分页和列变化、RTT UTF-8 分片/跨段/丢字节/会话边界、
源码父进程退出续转、冻结进程参数与普通优先级以下的独立进程。
既有十秒流性能门禁通过，不等于新的实物性能 A/B 结论。

## 安装验收

- 候选：`MKLink-0.4.3-c66523b8-current-user-x64.exe`。
- SHA-256：`20250ee2c59343a9394f6771c61ac2704c43fc0934fa66475f18b5b449ea6553`。
- 标准 Windows x64 NSIS，`--local-bundle`，未签名、没有 `.sig`，未发布。
- 安装器 `asInvoker`、RID 8192，覆盖退出码 0；3,675 个安装文件与包逐一匹配，
  包含完整 `_internal`。6 份原有 JSON 配置、USB 显示名称和旧 HKLM 登记未改变。
- 桌面 RID 8192；仅 Windows 目录的 PATH 下运行，无 Python/Node/Rust/Keil 依赖。
  健康检查、探针枚举、通用 CMake project-init、58 个实际 stdio MCP 工具初始化通过，
  实际调用 inspect_mcu、security_status、peripheral_targets 成功。
- 冻结包算法校验：7,059 个目标、2,224 个 FLM blob；Pack 校验：5,065 个目标、
  4,800 个 SVD 目标。安装桌面和真实浏览器载入生产资源，浏览器无 error/warn。
- 正常退出后应用和后台进程消失。测试时未修改用户原 AXF；使用其 F 盘副本。

## 实物与文件核对

沿用用户原下载器和 STM32F10x，核对目标身份，SWD 30 MHz，未刷写或修改目标固件。
实际解析 AXF 得到 6,718 个变量，保存 4 个波形变量、500000 缓存与 1 µs 配置。

记录得到 1,114,032 组 SuperWatch 样本、6 个 JSONL 分段；RTT 通道记录 19,190 字节。
记录结束后检查没有 XLSX、TXT 或转换任务文件。随后在真实浏览器分别点击两个转换按钮。
CLI 与实际冻结 MCP 再次请求同一路径，复用 GUI 任务；采集仍运行，直到显式停止。

逐行读取 Excel XML 与原始 JSONL 对照：两张数据页分别包含 1,048,575 与 65,457 组，
合计 1,114,032 组、4,456,128 个变量值；时间单调，时间与数值在 Excel 精度内一致。
RTT 的 505 行 TXT 与原始内容、首分片主机时间对应。7 个原始 JSONL 文件 SHA-256 未变。
采集结束前状态快照中的读取错误、二进制丢弃、流队列丢弃及固件/解析完整性错误均为 0。

最终复核 6 份原配置哈希仍匹配，MKLink 进程为 0，8765/8766 端口已释放。
当前 Excel 转换在应用正常退出后首次检查时已完成，因此没有直接观察到它在父进程
退出后仍运行的时间窗口；不把本轮结果表述为冻结 Excel 退出续转专项验收。

配套用户 Skill：`MKLink-Skill-0.4.3-c66523b8.zip`，SHA-256
`2e642cd7936e648ee266c75d28683b4319c3794a843efaf6e7b3fadf10acca0b`。
完整资源校验通过，2,225 个 FLM 目录文件、74 个 Pack 文件及 43 个 Web 文件与安装版
逐一相同。包内包含当前手动转换与符号旁配置参考；没有更改全局 Skill 或 editable 入口。

## 范围与保留项

这次验证安装升级、功能与文件正确性，没有重新宣称普通读 P95、吞吐或 SWD/RTT/调试
共存性能无退化。继续执行 [0.4.3 基线](v043-host-baseline.md)，合并/发布前仍需全量门禁。
转换仍消耗 CPU/磁盘，当前没有全局转换并发上限。最近一次记录被新记录替换后，当前
日志按钮不再提供旧记录的转换入口；此边界已写入用户参考。

安装依旧保留旧 HKLM 登记，不改受保护目录 ACL；缺少 WebView2 的机器未测。
测试创建链接的临时目录按规则保留，没有强制删除：
`runs/run-20261112-163403-4eb0031c`、`runs/run-20261112-163527-be98649c`、
`runs/run-20261112-163811-7c6a6e11`、`runs/run-20261112-170036-d6b75fdc`，
均在 BuildRoot 下，供维护者检查。
构建保留既有大 chunk、无 Git 快照元数据和链接器提示；构建退出码为 0。

本地原始记录、检查脚本、截图、进程证据、安装包位于 artifacts 中
`v050-manual-export-20261112`，不提交仓库。此前 `4b0a483f` 候选的覆盖安装、
真实符号重启恢复、1,144 万组 TXT 核对及冻结 TXT 父进程退出续转证据仍保留在
`v050-overwrite-20261112`；它已被当前手动转换候选替代。
