# SuperWatch 显式最快模式隔离SDK

2026-10-31，产品源码 `d08bf1dceea7cde21996656dc6fca85a9332d426`，共用 `codex/v0.4.2-fixes`。已直接核对用户在指定固件会话提出的最快采样、多点校准和禁止过短周期要求。固件会话要求先交付基于固定7843的最小SDK候选做对照，硬件仍由其独占。本会话无硬件操作，未构建或替换安装包、全局Skill、固件。

## 实现边界

- `MuxWatchSession`与`DumpMemoryStreamSession`新增独立关键字`fastest=True`，同时要求传入period=0；普通正周期保持秒参数。不带标志的旧period=0单次适配保持不变，未改CLI/high-level capture_dump接口。
- 以实际MUX HELLO capability bit9（0x200）协商`WATCH_TIMING=2`。最快模式线上period_us=0，周期模式仍是整数µs；旧固件无此能力时明确拒绝最快模式，不自动改成1µs或退回REPL。
- 新固件所有START成功应答必须有精确8B `<II accepted_period_us, timebase_hz>`，周期与线上请求相等且频率非零。timebase_hz是固件报告值，可为24MHz、360MHz等；样本timestamp仍按µs使用，不作二次缩放。
- `session.timing`仅记录已接受的线协议配置，旧固件为None，不表示实测达标。无效ACK对已启动的本次Watch只发送一次STOP，保留RTT；清理失败使传输失效并保留未知采集状态。没有自动重发START或写操作。
- 产品GUI仍使用原周期输入；动态最小周期策略、能力范围、校准结果失效规则待固件多点证据，不能宣称已限制到可达周期。后续接入见 `../ai/superwatch-period-contract-draft.md`。

## 离线验证

主源码和实际隔离候选imports分别通过相同227项回归，包含新增真实MUX帧/CRC/ACK旁首样本验证以及既有MUX、dump单次/停止、能力与复位回归。新测试覆盖普通周期1µs/0.5ms/1ms/60s、最快与旧单次语义隔离、不同timebase、拒绝能力不足/冲突参数、缺失/短长/错周期/零频率ACK、START拒绝、STOP失败与RTT保留。首轮新增测试误按16B拆nonce导致20项失败，按实际8B协议修正夹具后全部通过；未将该轮失败计为通过。

## 隔离导出

- 基线：`7843de8c3fc6e5d959de75997dd1b1ede4529269`。
- 仅覆盖两个生产文件：`mklink/mux_watch.py`、`mklink/dump_memory.py`；其余1260个Git blob与基线一致。原固定7843候选在测试前后均按全部1262个Git blob核对，不改写。
- 已验证目录：`F:/MKLink-Build/artifacts/superwatch-timing-20261031/candidate-7843-d08bf1dc-timing-v2-verified`，入口`enter-candidate.ps1`只隔离该shell的导入/后台目录，不连接硬件、不更改物理探针锁目录。
- ZIP：`source-7843-d08bf1dc-timing-v2.zip`，SHA256 `61d8a34b8fc1e8c07f43a569919ce046ee128871d7fc5b8471ce31b98f69715d`，CRC及全部载荷摘要通过。包含manifest、README和实际imports验证记录。
- 初次无`-verified`后缀的导出被Git自动CRLF转换影响，逐blob检查拒绝，保留为失败产物，未交给硬件测试。最终导出显式关闭该次Git archive的autocrlf，未改全局Git设置。

已将验证后的路径、哈希、接口和范围交给指定固件会话。它报告计划修正CPU PLL参考时钟初始化，同时保留高速计时与SWD实现；这是固件侧尚在验证的方案，本会话不声明已修复偏差。旧固件隐式最快基线与新固件显式最快应分别标注语义，不能称为相同线请求。Windows仍已装e29d候选，工作区按钮字体115ca0ce及本SDK改动都未打包；正式发布/合并无授权。
