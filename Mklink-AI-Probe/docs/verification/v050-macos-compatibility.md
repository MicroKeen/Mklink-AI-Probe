# macOS 兼容性修复与候选包验证

日期：2026-11-12。任务分支 `codex/v0.5.0-fixes`，继续在 PR #79 审阅。
产品修复为 `494ddfef`、`e1e8e24f`；`de2dd98e` 只替换已退役的 CI runner，源码子树与 `e1e8e24f` 相同。
本轮未合并、发布、更新正式下载索引或覆盖 Windows 已安装应用。

## 反馈与归因边界

桌面 v0.4.1 截图和对应日志来自同一案例；另一段 macOS Skill 0.4.3 的文字反馈来自不同用户。
前者的 dyld 日志明确显示 onefile 解包的 Python 库与启动程序 Team ID 不一致，后端尚未发布 endpoint 就退出。
截图中的更新错误是另一条独立路径：更新索引缺少 Darwin 平台。文字案例中的 USB 身份、会话与 STOP 错误不能归因于桌面签名。

在正式 `v0.4.3` 和本任务修复前源码上构造带重复 VID/PID 的 IORegistry 树，可复现 CDC 命令接口及磁盘身份关联丢失。
客户报告的 ioreg 3.7 秒到 0.15 秒为客户测量，本机没有该 Mac，未独立复现这两个耗时。

## 实现

- macOS 候选构建明确采用 ad-hoc 签名且不启用 Hardened Runtime，避免无 Team ID 的 PyInstaller onefile 内嵌库被同团队验证拒绝。只改 Unix builder 的 Darwin 配置，Windows 安装模式不变。正式 Developer ID 构建仍须在冻结时为内嵌库签名，不能仅在外层重新签名。
- USB 遍历依据设备类、设备描述符和接口属性识别设备边界。接口、驱动和磁盘后代可以继承相同 VID/PID；真实嵌套设备仍是边界，VID/PID/序列号冲突仍拒绝关联。串口和探针卷使用相同规则。
- 优先运行 `ioreg -a -l -p IOService -r -c IOUSBHostDevice`，错误、空树或无效输出才退回全 IOService 查询。每次枚举获得新快照，没有跨调用保存静态 USB 缓存。
- 操作准入的 OS 枚举移到工作线程，返回后重查连接代际、端口和连接状态。持续持有连接时的 250 ms 内存身份缓存仍保留；采样数据没有改为缓存值。
- 心跳共享单个未完成的被动枚举，每次最多等待 0.5 秒；慢查询期间可续约。实际操作仍独立检查身份，完成的失联结果撤销租约；过期连接观察被丢弃，detach 后不会复活会话。异步准入后重新检查任务去重和占用，未知结果不重放。
- 更新检查只有“响应缺少平台”转为中英文普通提示和重新检查按钮；网络、签名、下载和安装错误仍保留错误状态。安装说明区分更新索引与后端启动，并保留更新后重载 MCP 的要求。
- 根据固件会话核查，通用 status 6 改为“目标忙或访问准备未完成”，保留 opcode，避免把旧固件的重连失败断言为 debugger 预约。status 5 原核心状态未确认和写入不重放语义不变。
- 全量回归发现 Windows 状态轮询可能短暂阻止转换状态文件原子替换；仅在 Windows 错误 5/32/33 下最多重试 10 次、每次 20 ms。只重试状态发布，不重新转换或读写目标，永久权限错误仍报告失败。

## 软件与浏览器验证

- Windows Python 3.14 全量：6929 项通过、2 项因缺少 `hil_core.observe` 跳过，剩余 1 项为独立包审计夹具读取了旧 DLL 路径。隔离包实际构建和运行已成功。修正夹具记录并核对实际构建所用 DLL 后，独立包完整 6 项通过。没有把首次全量的 1 项失败记作通过，也没有跳过原审计；后一次只复跑相关范围。
- GUI 全量：105 个文件、1219 项通过。TypeScript 和生产构建通过，更新的生产 Web 已提交；GUI 源码在后续产品修正中未变化。
- 最终相关回归 280 项通过；此前 USB、共享会话、作业、边界、构建配置和流性能专项分别 126、51、434、112 项通过（范围有重叠，不累加为独立总数）。
- 两种 macOS 原生环境各 73 项 USB 回归通过，1 项 Windows 卷枚举用例按平台跳过。
- 核心日志：`run-20261112-191522-11de561a.log`（Python 全量）、`run-20261112-193109-c9ff6bb4.log`（独立包复测）、`run-20261112-191322-2d9a050f.log`（GUI 全量）、`run-20261112-191013-0a956bb8.log`（280 项）、`run-20261112-185243-647bef51.log`（生产构建）。
- `1aa0b671` 只完善测试夹具的 DLL 路径证据，不改产品运行文件。与两种 Mac 包相比，`mklink`、GUI、用户参考和 builder 源码相同。

新增用例覆盖同 VID/PID 接口继承、真实设备边界、身份冲突、USB 子树查询及回退、磁盘身份、慢枚举期间续约、单次在途查询、detach/代际变化、任务去重、失联结果不被缓存覆盖、平台缺失提示以及临时/永久文件占用。

首轮全量发现 8 个失败和 4 个环境错误：两项异步身份夹具未更新、两项旧日志转换协议夹具、两项符号重载夹具未模拟先加载配置的正常流程、一项文档入口被新段落后移、一项真实 Windows 状态发布竞争；四项独立包测试缺少工作树之外的 STCP DLL。相应夹具、文档和竞争已修正，隔离包测试允许显式指定已验证 DLL，不跳过原测试。
GUI 首轮 1218 项通过、1 项因隔离副本缺少独立 RTT 模板而失败；补齐真实源码模板后全量通过，不修改测试断言。

浏览器使用产品 `AppUpdateBanner` 和 `useAppUpdater`，只模拟桌面更新 IPC 返回值，实际点击重新检查、切换网络错误和中英文。确认平台缺失显示普通信息，网络失败仍显示错误，缺少平台时不提供安装按钮。
这是实际浏览器中的组件行为验证，不是原生 macOS GUI 或真实更新下载/安装验收。截图及脚本保存在本地构建证据目录，不提交截图到源码。

## macOS 原生构建与最终包检查

| 架构 | 构建系统 | 源提交 | 冻结后端启动 | 证据 |
| --- | --- | --- | ---: | --- |
| Apple Silicon | `macOS-15.8.2-arm64-arm-64bit` | `de2dd98e` | 5.593 s | [原生构建与自检](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/43207226586) |
| Intel | `macOS-15.7.9-x86_64-i386-64bit` | `e1e8e24f` | 11.6 s | [原生构建与自检](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/43206999516) |

以下候选均已下载到本地并核对 SHA-256：

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| `MKLink-0.4.3-de2dd98e-macos-arm64-candidate.dmg` | 167763118 | `6a5e366b490cd4cf044d844ca04a8416de52f9269c49c40ecf425ecf51cb48da` |
| `MKLink-0.4.3-e1e8e24f-macos-x64-candidate.dmg` | 168173449 | `ca24a0ca42852e646fd5be32f858eb0a48c77a7664e53cc62657fefb94a534f0` |
| `MKLink-Skill-0.4.3-1aa0b671.zip` | 99790063 | `d504e26f973f81b03553befb6aef5db5814af16e75980b91bf355744497c88dd` |

完整 Skill 使用同一产品源码，包含 7059 个算法目标、2224 个算法 blob 和 4800 个外设目标；运行文件逐项核对 Git 对象，归档排除维护文档、测试和维护者 Skill。没有更新用户已安装的 Skill 或发布渠道。两个 DMG 的构建清单、资格报告与 `SHA256SUMS.txt` 随本地证据保存。

首两次 Apple Silicon 任务未执行步骤便取消；旧工作流使用的 macOS 14 runner 已于 2026-11-02 退役，现使用 `macos-15` ARM runner。旧 Intel 提交的任务在新的产品修复后主动取消，以最新候选为交付依据。CI 使用分平台并发组且不取消已运行构建。

验证脚本挂载 DMG、复制最终 `.app`，验证 `codesign --verify --deep --strict`；核对主程序和 sidecar 为 ad-hoc、无 hardened runtime，再运行最终包内 sidecar。仅使用系统 PATH 检查冻结 CLI、stdio MCP、内置算法、desktop-proxy endpoint、健康接口、生产 Web 资源和正常退出；同时核对 `.app.tar.gz` 的可执行权限及两个可执行文件与 DMG 相同。

候选不带 Developer ID、公证或 updater 签名。没有向正式更新索引增加 Mac 平台，也未验证 Gatekeeper 首次启动、Finder 拖放/覆盖安装、原生窗口操作或 macOS 27 实物探针。CI 最终包自检不替代这些验收。

## STOP 固件联动

固件会话在普通 V4.7.4 源码审计中确认：MUX 0x17 的 `restore_target()` 失败会误用默认 status 6。独立补丁将其归为 status 5，保留真实调试会话占用的 6；原分支缺陷可复现，隔离 C harness 与清理边界测试通过。补丁未应用到固件主源码，未生成/刷写 UF2，未发布。

0x17 只能在调试域可访问或有足够唤醒窗口时进行有时限的 Halt/访问/恢复，不能保证解除持续 STOP。status 5 也可能包含原核心状态恢复未确认，不能据此保证 MCU 已恢复运行。仅关闭调试器 USB 句柄而不发送 DAP_Disconnect/HostStatus=false 时，逻辑预约可能仍保留；不自动抢占或按空闲清理。

客户下载器固件版本、MCU 完整丝印、VTref/供电和 IDE 使用历史均未齐备。手动唤醒后成功不能排他定位先前故障。后续应保留 opcode/status/耗时的连续日志，并确认 STOP 的唤醒条件；本轮没有进行目标寄存器写入或设备刷写。

## 验收范围与后续

Windows 已安装实例仍为此前 `c66523b8` 候选，详见[手动转换与安装报告](v050-manual-recording-export.md)。本轮的软件全量、包内运行和浏览器测试不构成新的 Windows 覆盖安装或硬件吞吐/P95/调试共存 A/B 结论。
后续实物验证仍按[0.4.3 上位机基线](v043-host-baseline.md)执行；本轮未改变其未达性能目标。

本地原始证据目录：`v050-macos-fixes-20261112`；首轮重现见 `v050-macos-review-20261112`。带链接的 pytest 临时目录按构建包装器规则保留待安全检查，没有强制递归清理。

参考：[PyInstaller macOS 签名](https://pyinstaller.org/en/v6.18.0/feature-notes.html#macos-binary-code-signing)、[Apple 库验证](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.disable-library-validation)、[GitHub macOS 14 退役说明](https://github.com/actions/runner-images/issues/13518)。
