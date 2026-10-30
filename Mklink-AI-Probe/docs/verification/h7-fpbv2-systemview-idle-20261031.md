# H7 FPBv2 与 SystemView 调试暂停兼容

用户在指定固件会话明确要求由上位机会话修复 FPBv2，再用 H7 验证设置、命中、查询、清除及 Keil 仿真与采集共存。宿主修复分别为 `e4d5fc4f`（FPBv2）和 `7843de8c`（SystemView 静默）。实板及 Keil 由指定固件会话操作；本会话只修改宿主、运行离线回归并独立核对保存证据。没有重新构建或安装安装包，也没有修改全局 Skill 或发布资产。

## FPB 版本与共享操作

按 FP_CTRL.REV 区分 FPBv1（0）和 FPBv2（1），使用目标报告的比较器数量，包括高位计数。未知版本在访问比较器或写入前拒绝。

- FPBv1 保留代码区低于 `0x20000000` 的限制及 REPLACE 半字选择。
- FPBv2 使用完整 32 位半字地址，比较器值为 `address | 1`，读取地址清除 bit 0；不沿用 v1 的 REPLACE 位。
- 状态/列表新增 `fpb_version` 和 `fpb_enabled`。设置、清除与清除全部保留槽位检查、占用保护、共享资源串行化；设置后校验比较器、版本和全局使能。
- 未知写入结果不重放，不用回滚覆盖其他客户端状态。设置比较器本身不隐式 halt 或使能 DHCSR.C_DEBUGEN；调试使能与实际命中是独立条件，Skill 已说明。

实现对照 [Arm Cortex-M7 TRM](https://documentation-service.arm.com/static/5e906d72c8052b1608760d63) 的 FPBv2 定义及 [pyOCD FPB 实现](https://raw.githubusercontent.com/pyocd/pyOCD/main/pyocd/coresight/fpb.py) 的版本、地址和编码规则。不是仅删除原 FPBv1 guard。

`test_fpb_revisions.py` 通过实际寄存器命令编码/解析和共享 HTTP 接口覆盖两个半字、高地址、0/8/17 个比较器、非法参数、未知 REV、无空闲槽、请求期间槽位被占、读回不符、全局使能失败、应答丢失及清除中途失败。旧 FPBv1 回归保留。

## SystemView 等待目标事件

Keil 首轮实测中，目标暂停后 RTT 和 Watch 保持，而 SystemView 在连续 5 秒没有事件时被宿主停止。`keil-baseline.json` 的终态是 `running=false`、`progress_state=error`，事件数停在 140124，继续运行后未增长。原脚本仅凭其他采集及丢包指标给出的 passed 不代表 SystemView 恢复通过。

共享 MUX 已有独立心跳、请求时限、帧校验和目标读取状态。空读只能说明没有事件，无法区分 CPU 暂停和运行中的合法空闲。因此修复为：

- 共享 MUX 连续 5 秒健康空读后进入 `progress_state=waiting`，保留解析器的半包、历史游标、计数、Recorder 和订阅。目标恢复产出后继续同一会话，不重发 START 或复位目标。
- 首包未到达也可等待，GUI 不再因此触发准备超时；界面说明等待并提示目标已运行时检查录制配置和通道。等待不代表已经生成有效跟踪，也不声称探测到了 CPU halt。
- 保留心跳超时、CRC/epoch/claim 错误、目标读取失败和持续无法解码的退出路径，错误不变为无限重试。会话 duration 与显式停止仍有效，旧非 MUX 看门狗和有界重试不变。
- 不增加 DHCSR 轮询、目标 resume 或设备枚举；HPM 不会因此收到 ARM 寄存器访问。

## 离线和浏览器验证

- `7843de8c`：616 项相关 Python 测试通过，覆盖 FPB、共享运行时、MUX/RTT、SystemView 生命周期、解析、历史、CLI 及 Skill 边界。日志 `run-20261031-004931-a5ab7b5d.log`。
- 新的 10 项 MUX 静默测试使用真实帧传输、SystemViewSession 和解析器：暂停跨越半包后继续原时间轴、初始空闲、时长结束、心跳/CRC/目标状态 5/7/8、无法解码以及启动校验失败。
- 27 项 SystemView GUI 测试、TypeScript 检查通过；含 65 秒模拟静默不会停止、恢复清除提示和真实错误展示。
- 内置浏览器加载真实源码组件的独立生产资源，模拟采集状态验证等待、恢复、错误三种状态。浏览器证据在本机构建根的 `artifacts/sv-idle-20261031/webcheck/`；这些是界面夹具，不是实板证据。未改跟踪的 `gui/dist`。
- 从导出目录真实导入并运行 113 项 FPB/共享断点/静默回归通过。测试环境提示 anyio 已导入及关闭缓存后的 cache_dir 选项告警；无失败。Vite 配置打包有可选 esbuild 解析告警，产物构建及浏览器验证成功。

## 不可变候选

`F:/MKLink-Build/artifacts/rtt-shared-20261030/candidate-7843de8c-verified/`：

- Commit：`7843de8c3fc6e5d959de75997dd1b1ede4529269`。
- `source.zip`：7766036 字节，SHA256 `9ea57f92ba65de4b8023d7f385821b75d3c94cdb37ecef46a43fbc6e348599c7`。
- 1262 个文件与 Git 树、所有 blob 哈希一致；`manifest.json` 记录关键模块哈希，`source/` 是固定解包目录。
- `enter-candidate.ps1` 仅供指定会话启用隔离源码运行环境；没有覆盖旧 `e4d5fc4f` / `4be6ab66` 候选。归档中的历史构建 Web 资源不代表本轮 GUI 已打包，GUI 修复在源码中。

## H7 首轮断点实证

`e4d5fc4f` 候选、HPMLink control 固件、STM32H743IITx、SWD 10 MHz。保存报告 `fpbv2-e4-debug-enabled.json` SHA256 `11a9cd6d1b11947e86d7ec967e66edcf165a0747612b2b8331622047d78cd4ba`，本会话离线重新核对了原始返回数据：

| 项目 | 结果 |
| --- | --- |
| 识别 | CPUID `0x411fc271`、FPBv2、8 个比较器 |
| 函数地址 `0x0802b9e8` | 比较器 `0x0802b9e9`，PC 精确命中，DFSR 含 BKPT |
| 下一条指令 `0x0802b9ea` | 比较器 `0x0802b9eb`，PC 精确命中，DFSR 含 BKPT |
| list / 占用保护 | 地址及 halt 状态正确；占用槽拒绝后前后 40 字节寄存器完全相同 |
| clear / resume | 比较器回读零；两次恢复后的目标计数均增长 |
| 内存与收尾 | 4..4096 字节长度/hex/base64 一致；480 字节写入与回读一致，恢复后完整 4096 字节等于原快照；最终运行、无断点、设备已关闭 |

独立核对脚本及结果：本机构建根 `artifacts/rtt-shared-20261030/verify_fpbv2_hits.py` 与 `fpbv2-e4-debug-enabled-independent-review.json`。仅读取保存的 JSON，没有运行实板脚本。

最初 IDE 退出后没有使能 halting debug 的未命中记录仍保留；通过显式授权的 halt/resume 建立调试状态后才完成上述命中测试。此修复没有修改共享 `step` 的实现；Keil 单步不能代替该 API 的独立验收。

## 最终共存验收状态

`7843de8c` 的真实 Keil CMSIS-DAP 与 MUX RTT/SystemView/Watch 共存复测通过。独立核对 `keil-7843-acceptance.json`（SHA256 `0f46533a36abd6eac69740a4477a5eebfdda3f74cedc83a15a2ef364b856a868`）全部 161 个样本、保存的 RTT 原始数据和历史游标：

| 阶段 | 采样跨度 | 实测结果 |
| --- | --- | --- |
| Keil 暂停 | 23.480 秒 | SV 等待；RTT、目标计数均不增长，Watch 增长 23401 周期 |
| Keil 单步后 | 36.495 秒 | 目标保持暂停，产生 2 个 SV 事件；Watch 增长 36317 周期 |
| Keil 断点命中保持 | 95.160 秒 | 命中截图停在 `0x0802b9e8`；SV 等待不退出，Watch 增长 94951 周期 |
| 继续运行 | 24.536 秒 | RTT 增加 784384 字节、SV 增加 122815 事件/589512 字节、Watch 增加 24434 周期 |

完整 RTT 为 1902592 字节，1024 字节块序号 974..2831，每块所有数据和总 SHA256 `33f0867edcf364620bceaf9a638d9ad59b47e6473e7df5a6578b84494ce92a67` 独立核对通过。样本及历史状态递归 4369 处丢失/读取错误计数均为零；无心跳超时。此结论依赖当前 H7 镜像、HPMLink control 固件及有限测试配置，不是所有工作负载无损保证。

`history-halted.json` / `history-resumed.json` 的历史 session 一致，next_seq 从 162188 增至 228171；旧游标增量首条为 162189，连续 10 条且 dropped=0。SystemView 的连接/采集代次保持 1、auto_retry_count=0；RTT session 同样不变。对应 SHA256 为 `6828fafaed3a6bcc4c5d42e396b501e9b52da4051c5053a6a1dcb021f54561ee` / `b08d267c1f182dc7afe050d9d68f06ba63b2df55561cf074831cb355658bc4d3`。

共存报告收尾记录目标运行、比较器恢复且 device_closed=true。本机独立核对脚本 `verify_keil_idle.py` 和 `keil-7843-acceptance-independent-review.json` 位于上述 F 盘证据目录；没有访问在线后端。首次启动就已暂停的情形及真实故障退出由离线回归覆盖，本轮真机只验证先采集再暂停。

同一最终候选的独立共享断点复测也通过：`fpbv2-7843-acceptance.json` SHA256 `346c3a485935819fa21d140815088aedb84efe4000e5cc71b45fc8e85c13129f`。独立重新核对了与 e4 首轮相同的两个半字地址、精确 PC/DFSR、比较器编码、占用拒绝后 40 字节不变、清除读回零、恢复运行计数、480 字节写入及完整 4096 字节恢复。最终目标运行、无断点且 device_closed=true；结果文件 `fpbv2-7843-acceptance-independent-review.json` 同在 F 盘证据目录。

补充回归 `fpbv2-7843-other-regression.json` SHA256 `1c85a67dcef5f8acf94755cfc1cf0ca3b5b9b66fefc2751ca5e5dd1fe4fd68d2`：内存 10/30 MHz 读写恢复、两组 D-cache 脏行与 CPU 参照一致、RTT 下行 256 字节的目标计数和滚动哈希、12 阶段采集启停/暂停/反序启动及同 SystemView 通道观察者均通过。保存的并行 RTT 333824 字节全部数据/序号/SHA 独立核对；递归 34 份 SV、59 份 MUX、24 份 Watch 状态的相关丢失/读取错误为零。独立 DAP 的 50 次读取、写入恢复及 halt/step/resume 由报告记录通过，不替代共享 `step` 验收。对应 `verify_fpbv2_other.py` / `fpbv2-other-independent-review.json` 同在 F 盘目录。

指定会话报告收尾已恢复 Keil 原 0..8 号断点的启用状态、删除本次 9 号测试断点并退出调试，窗口保留；最终流已停止、目标运行、恢复 10 MHz、设备释放。原断点恢复列表保存在本机 `keil-restored-breakpoints.txt`，不提交用户工程或截图。

额外调用共享 `breakpoints status` 的中途试验因既有准入返回 409，报告 `keil-7843-final.json` 按失败保留。`runtime_api.py` 仅豁免受支持 MUX 内存操作及复位，断点 status/list/set/clear 都要求先停止采集；本轮未修改此边界。最终应分别报告共享断点独立验收和 Keil CMSIS-DAP 与 MUX 采集共存，不能将后者解读为共享 debug API 可在采集中调用。

已装 0.4.2 Windows 源 `dce17d3e`、Skill 归档源 `0d680d90` 不包含本轮修复；正式 0.4.1 和旧 Linux/macOS 包不变。先前 HPM/H7 速率、丢包、单次 API 延迟及失败试验边界仍见 [H7 control 验证](h7-rtt-control-20261031.md)，不因断点通过而关闭。
