# Watch 1/2 字节批量协议与上位机验收 — 2026-11-03

上位机在 `codex/v0.4.3-fixes` 增加显式协商的 1/2 字节紧凑 Watch 帧支持，
配合独立固件会话的外设快速读取和 RAM 流水覆盖优化。**本轮只有离线验证，
没有连接设备、刷入候选、构建上位机或覆盖安装；尚不能判断候选硬件速度。**
产品版本仍为 0.4.2，已有正式资产不变。

固件会话为 `01a1a1a2-9adc-79e2-b30e-07c07d5f90c6`，固件代码位于
`codex/v4-arm-fast-sampling`，交付提交 `d4f7479b26e81102e4827647f7e85f1dec911169`。
它负责外设快读、超过前 64 KiB 的 RAM 及不同 ARM 内核覆盖；本次宿主修改
不证明这些固件行为已在实板通过。固件报告为其仓库的
`MicroLink/microlink_app/docs/arm-sampling-20261103.md`。

## 最终协议

- HELLO capability bit 10（`0x400`）声明 `WATCH_NARROW_BATCH`。
  仅当单区域为自然对齐的 1/2 字节时，宿主选择新 START `0x33`。
  其他情况在发目标命令前选择原 `0x32`，失败不重试为旧命令。
- `0x33` body 与 `0x32` 完全相同：`<IB period_us, region_count>`，随后
  每区 `<IB address, size>`。沿用 nonce、epoch、认证及去重；没有新增 flags。
  非法参数返回 status 2，固件应保留已有订阅。
- `0xB3` 成功应答的状态字节之后必须恰为 8 字节
  `<II accepted_period_us, timebase_hz>`。宿主核验周期一致、timebase 非零，
  才为当前订阅打开窄批量解码。最快模式仍要求 bit 9 的 timing-v2 能力。
  应答成功但格式错误时 STOP 一次；STOP 失败则使传输失败，保留未确认的
  capture 状态，不自动重放 START。样本时间戳仍以微秒为单位。
- status 9 payload 为 `[0, 9, count, sample_bytes]`，后跟 count 个
  `<I timestamp_us> + 原始值`。窄值恰为 1/2 字节，不填充为 4 字节。
  count 为 1..127，整帧 payload 不超过 1024 字节。
- 旧 `0x32` 不开启窄批量，新固件必须继续兼容旧上位机。宿主原有 4..64 字节、
  4 字节倍数的 compact 路径不变。STOP、新 START、新会话以及 DAP 失效或
  reset 恢复超时会清除窄批量许可；同一订阅的正常 reset 恢复保留配置。
- 新订阅也接受原 status 0 单样本及 status 5 读错事件。按固件侧确认的契约，
  合法 `0x33` 在 JTAG 下同样成功，但沿用 status 0，只有 SWD 使用窄批量引擎。

## 访问宽度与兼容

`superwatch.build_read_blocks` 原有优化保留：GUI 中来源为 RAM 且被已知
ELF/profile RAM 范围完整覆盖的 8/16 位变量，可以按对齐的 32 位块读取，
解码时再提取原值。这解释了某些历史 GUI 窄变量与 32 位变量速率接近。
本轮没有扩大这个优化的地址范围，也没有将外设寄存器访问自动扩为 32 位。

显式 `capture_dump` 的 region size 为 1/2 时仍保持实际读取宽度。
后续实测速率必须同时记录逻辑变量大小和实际 START region，不能用
GUI 的 4 字节读取代替真正的 8/16 位总线访问对照。

## 正确性验证

通过统一 `scripts/build_workspace.ps1`、`BuildRoot=F:/MKLink-Build`，使用
Windows PowerShell 7、Python 3.14.5 运行 15 个相关模块，最终 **608 passed**。
覆盖新旧协商、ACK 邻接首帧、CRC/raw-v2 字节分片、符号值、时间戳回绕、
packed 偏移、错误帧拒绝、无重放、STOP 失败、共享运行时 10000 样本逐值校验、
原有 RAM 对齐，以及 Watch/RTT/SystemView 共用传输和资源释放。

另将固件真实 `ml_mux_event/pack_watch_increment` 模型输出交给真实宿主
`MuxTransport`，每次按 7 字节分片输入。三份输出各有 254 帧，覆盖
1/2 字节 × count 1..127；plain/packed 两种解码共验证 **97536 个样本**，
值、时间戳回绕和计数全部一致。三份输入 SHA256 均为：

`4699996b1963c0240c7458a1df003ddb31c013a5b808fa6c4f9fdb8392eb4742`

其中 1/5/127 样本的六个原始帧固化在
`_maintainer/testing/tests/watch_narrow_batch_golden.json`，由新测试直接读取，
避免只用宿主自制编码器验证自己。JTAG 配置的 packer 模型输出仅验证公共
打包器，不能当作 JTAG 真机输出紧凑帧的证据。

## 现有解析路径性能对照

比较原提交 `02a64672` 与本轮源码，只测 `MuxWatchSession.read_frames`。
每种大小/解码模式先预热，再做六对交替顺序的前后运行，每轮约 40 万样本。
本轮把固定采样宽度与 word-batch 判定移到构造阶段，避免增加逐帧开销。

| 组大小 | 解码模式 | 原版，样本/s | 候选，样本/s | 中位吞吐变化 |
| ---: | --- | ---: | ---: | ---: |
| 4 B | plain | 1830774 | 1815477 | -0.84% |
| 4 B | packed | 2538884 | 2526930 | -0.47% |
| 16 B | plain | 1886915 | 1918767 | +1.69% |
| 16 B | packed | 2609178 | 2588229 | -0.80% |
| 64 B | plain | 1654976 | 1676213 | +1.28% |
| 64 B | packed | 2208271 | 2387809 | +8.13% |

这是存在系统调度波动的 CPU 离线比较，没有 USB、目标访问和 GUI 发布。
不把正变化解释为实机提速，不把微小负变化隐藏，也不据此保证 SuperWatch
端到端零退化。初次未预计算宽度、较短窗口的结果亦保留，未择优删除。

本机证据目录为 `F:/MKLink-Build/artifacts/v043-watch-narrow-batch-20261103`：
`pytest-final.xml`、`golden-check.json`、`check_golden.py`、`parser_compare.py`、
`mux_watch_before.py`、`parser-compare-first.json`、`parser-compare.json`。
测试创建的含链接临时目录由 wrapper 明确保留，未强制清理。

## 待实机验收

等待用户授权精确固件候选后，由固件会话协调占用，使用同探针、同目标映像、
同 SWD 时钟，比较实际 1/2/4 字节、已知 RAM GUI 对齐路径、跨 64 KiB RAM、
GPIO、RTT/SystemView 及 Keil 共存。记录数据完整性、间隔分布、P95、错误和
丢弃计数，不只给最快轮或中位数。普通 MCU 寄存器是否支持窄访问仍以目标
定义为准，不通过访问宽度转换掩盖错误。

既有 [最高流速基线](v043-stream-maximum.md)、[40 µs LED 波形](v043-h7-led-waveform.md)
分属不同目标映像；[普通内存读取 P95/间隔低于 1 ms](v043-tail-latency.md)
目标仍未达成，不能由本轮批量协议支持代替。
