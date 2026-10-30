# 共享 RTT / SystemView 与有界 MUX 传输

2026-10-31 更新：STM32H7 后续已完成限定实测和离线复核，见 [H7 control 验证](h7-rtt-control-20261031.md)。下文各轮的“H7 未测”是当时的边界，历史 HPM 非零丢失证据继续保留。

2026-10-30，`codex/v0.4.2-fixes`，产品提交 `70841886`、`a44128f9`、`4be6ab66`。
用户在指定固件会话授权加速、并行验收及取消 RTT/SystemView 独占原始流，随后要求新短帧连同头和 CRC 不超过 512 字节。
固件会话负责固件、目标程序和全部实机操作；本会话负责宿主、Skill、离线回归及不可变源码候选。
本轮没有重新构建安装包、覆盖安装、修改正式资产或发布版本。

## 行为

- RTT 和 SystemView 共用唯一 MUX 读线程和固件 RTT 引擎；同一控制块按消费者合并通道掩码，首次启动、增量调整、最后停止分别使用 `0x20/0x23/0x22`。不同控制块明确冲突。
- 相同通道只从固件读取一次，宿主分发至独立有界队列。停止一个消费者不停止其他消费者或 SuperWatch；最后一个通道观察者退出后才停止目标 SystemView recorder。
- 新消费者先注册再发启动命令，保留与 ACK 同次 USB 读取到达的首帧。队列溢出独立计数，DAP 失效和目标读错不因溢出消失。
- SystemView 经 RTT down 发送 START/STOP/TASKLIST，不再自动进入独占 raw recorder。缺少增量能力明确拒绝；旧实现仅保留为显式兼容类，不自动回退。
- SDK `RuntimeClient.rtt_subscribe_bytes()` 复用共享后台，通过持续 WebSocket 传递任意字节、会话、偏移及丢失信息；不使用文本解码或逐批短 HTTP 请求。采集 ready、订阅 ready 后再触发目标，是完整载荷验证的前提。
- Skill 增加二进制订阅、能力检查、并行及数据完整性边界；沿用普通物理下载器所有权锁，不另开串口绕过后台。

## 协议兼容

| 能力/命令 | 宿主规则 |
| --- | --- |
| `0x20` | 成功业务载荷为 up/down 两个 descriptor count，不能当作通道掩码或空回复。目标描述表每方向最多 64，订阅仍限通道 0..7。 |
| bit 7 / `0x23` | 增量掩码，失败保持原消费者；未知结果不重放。 |
| bit 8 / `0x25` | claim 后默认 128，仅支持方显式协商至 480；ACK 处理时立即更新解析上限，保留紧随 ACK 的首帧。 |
| `0x40` RTT | 480 字节数据加通道/状态/时间戳后，完整帧最大 506 字节。 |
| `0x11/0x12` | 普通内存读写按协商量子分块；最大写帧含 nonce/地址/CRC 为 512 字节。 |
| `0x24` | 1..480 字节 RTT down，返回 u16 accepted；只推进已接收部分，不重放整个写入。 |
| `0x21` | 旧 128 字节 down 与 u8 accepted 保持兼容。 |
| bit 6 / `0x16` | 原有独立 4096 字节整块读取不受新短帧量子限制。 |

## 离线与浏览器验证

- 最终 `4be6ab66`：996 项相关 Python 回归通过，覆盖 RTT/SystemView/MUX、共享资源、重置恢复、后台操作、WebSocket、Skill/包边界。
- 真实 loopback WebSocket 单连接传输 10 MiB，所有字节值和 SHA256 一致；验证心跳、序号/偏移间隙、会话替换和慢消费者有界丢弃。
- 覆盖 128/480 协商、ACK 与首帧同次读取、1/127/128/129/479/480/481/960/1001 字节边界、部分接受、非法回复、超限帧和旧固件。
- 描述表 33/64 的 Device 预检及启动通过，65 在读取表或启动消费前拒绝；固件 ACK 超限会终止未知状态，不自动重放。
- Skill quick_validate 通过；相关上下文/包边界测试包含在 996 项内。
- 使用真实源码 composable、真实冲突判断 API 和真实 stream router，在隔离浏览器确认：新能力下 RTT/Watch 不阻塞 SystemView；旧能力仍提示冲突；256 种字节原样到达浏览器。仅硬件返回值使用夹具，不作为实机证明。隔离服务与临时页已关闭。
- `git diff --check` 通过。构建/测试均使用 `scripts/build_workspace.ps1`，产物根为 `F:/MKLink-Build`；有链接的测试临时目录按规则保留，未强删。

## 候选与实机证据边界

- 初始 `70841886` 候选把旧 `0x20` 的两字节 count 回复误认为非法；真实启动失败，目标未触发。失败候选保持不变。`a44128f9` 修正该错误并加入 480 协商。
- 更早 128 量子尝试收到 10 MiB 减 128 字节，不能计作有效性能成绩。其 harness 未等待 streaming-ready；发现的 ACK 后 drain 窗口已有专门回归，但不能仅凭该次运行证明缺帧根因。
- 指定固件会话实测：宿主 `a44128f9` 配合固件 `7d7a6480`、能力 `0x1ff`，1024/2048 两种目标块长各完整收到 10 MiB，量子 480，gap/drop 为 0。目标约 127.24 KiB/s，宿主约 127.04 KiB/s；相对该会话保存的约 41.60 KiB/s 基线约 3.06 倍。本会话随后只读复核保存的完整载荷：逐字节模式、每块递增序号、总长度和 SHA256 全部一致；并核对报告的量子、丢弃统计及按时间计算的吞吐。不是本会话新做的硬件实验。独立复核记录为本机 `shared480-independent-review.json`。
- 最新 `4be6ab66` 追加 descriptor count 上限兼容及测试；指定固件会话随后使用已核对的源码候选完成下述控制共存实测。吞吐的两轮 10 MiB 仍属于 `a44128f9`，不混为同一实验。
- 首次 `4be6ab66` 导出在嵌套源码目录执行，受 Git 路径前缀影响生成仅 22 字节的空 ZIP。协作会话的导入路径断言在硬件操作前阻止了回落至已安装 Skill；这是源码交付失败，不是固件故障。更正候选固定为 `candidate-4be6ab66-verified`：从 Git 根目录关闭 CRLF 转换导出，7,733,541 字节、1255 文件，全部路径及每一文件 Git blob hash 与提交一致；另在非源码目录实际导入确认模块来源和 count64。旧空目录及中间检查失败目录保留，不得使用。
- `4be6ab66` 的并行控制与 RTT 载荷通过，但饱和负载下 SystemView 目标端丢事件；不能宣称全采集无损。按用户后续明确要求，并行溢出保留为容量边界，验收以 SystemView 独立运行无丢失为准，另测 30 MHz RTT 吞吐。历史 USB 995、SDK socket 10048 和完整 SES 组合仍未定因或未覆盖；本轮速度提升不代表这些问题关闭。
- 采集暂停或有界队列溢出可能丢观测；不承诺任意时序、永久无损或全部客户端调试操作并行。现有宿主 debug 控制的停采集要求保留。

## 最终共存报告独立复核

固件会话提供 `coexist-final.json`，宿主为 `4be6ab66-verified`，配套固件 `7d7a6480`。
本会话只读核对该报告、两份原始载荷、测试脚本和 OpenOCD 日志，没有连接硬件。
报告 SHA256 为 `c227f02592256fb3c15d833bb16e86279b0639cba7e7a089d7931da0b72351f4`；本机复核记录为 `coexist-final-independent-review.json`。

| 检查 | 复核结果 |
| --- | --- |
| 三路负载 | 262144 字节，256 个 1024 字节块，序号 1431..1686、全部模式字节和 SHA 一致。 |
| DAP 期间 RTT 负载 | 1263616 字节，1234 个块，序号 1687..2920、全部模式字节和 SHA 一致。 |
| 启停与共享 | 两种启动顺序；SV 停止/暂停/恢复；同 CH1 观察者在 SV 停止后继续接收及 SV 重加入；分别停止 RTT/Watch 后其他采集继续，共 12 个阶段状态及进度检查通过。 |
| DAP | 50 次 64 字节物理内存读取及写入恢复通过；日志确认显式 halt/step/resume，退出后采集继续。 |
| 内存/下行 | 报告记录 480 字节内存写读恢复、256 字节 RTT 二进制下行回显通过。 |
| MUX/宿主解码/Watch | 所核对阶段 MUX gap/drop、SV parser drop、Watch read error/drop 均为 0。 |
| SV 目标端丢事件 | **未通过无损条件**：DAP 负载阶段 overflow 123→580，退出后累计 768；`target_dropped_packets_since_baseline` 达 17371。 |

两份载荷 SHA256 分别为 `a6b75333c418d9beef4d7377f437e2320092e027fb5be1e01690aa4cfb6bd39b`、`2b6408f6f2894578fc9496a3424bbef52c2ef60872f05ccfd024c4e1ef184842`。

原测试脚本的 `passed=true` 只检查功能和事件增长，没有断言目标 overflow。固件会话最初“target overflow 为零”的消息与详细状态不符；本会话的独立无损断言也在该字段失败。保留原报告，明确区分完整 RTT 传输与 SV 目标事件丢失，不能用宿主 parser/MUX 为零覆盖目标溢出。后续测试补充对应断言，当前不据此修改准确上报该状态的宿主。

该轮目标/SV 时钟均为 250 MHz；记录的收尾为所有采集停止、`device_closed=true`、负载使能为 0、JTAG 恢复 10 MHz。后续独立 SV 和 30 MHz RTT 的结果见下文；再次操作前仍须核对实际占用。未重新构建或覆盖上位机安装。

## 后续验收范围

2026-10-30，用户在指定固件会话明确调整为：“SystemView只要独立运行不丢数据就可以，另外测一下30M下RTT的最大速度”。
因此不再要求修到并行饱和场景全无损，也不抹去上面的溢出记录。
固件会话使用同一 `4be6ab66-verified` 宿主完成了下述 SV 独立检查和 JTAG 30 MHz RTT 双 10 MiB 测量；本会话分别完成状态证据及完整 RTT 载荷的独立复核。
“最大速度”只报告该条件下完整性通过的实测吞吐，不推断理论上限。本会话没有连接硬件、改动候选、重新打包或覆盖安装。

## SystemView 独立运行验收

`sv-standalone-60s.json` 的 13 个连续状态样本与脚本已独立离线核对通过，报告 SHA256 为 `c6bd4e997d8cee62d4881c80ed3992e02ead49896e19ac5685a05ad048deab58`。
本机复核记录为 `sv-standalone-independent-review.json`。

- 宿主 `4be6ab66-verified`，配套 480 量子固件，JTAG 配置 20 MHz、目标/SV 时钟 250 MHz；未启动 RTT 或 SuperWatch，目标 RTT 压力负载关闭。
- 持续 62.837 秒，同一采集 session 的 13 个样本事件/字节计数持续增长。最终累计 847588 个解析事件、3723652 原始字节；首尾样本间新增 847098 个事件。
- 全部样本的 target overflow、baseline 后 target drop、parser drop、MUX event gap/RTT drop/Watch drop 均为 0，无暂停或自动重启。
- 报告记录采集正常停止、JTAG 恢复 10 MHz、`device_closed=true`，该轮收尾通过。

这满足本次限定时长、目标程序和配置下的独立运行零丢失计数要求。复核依据为状态计数及测试脚本，未对完整 SystemView 原始事件文件作逐字节对照；滚动历史容量和并行饱和溢出边界保持原说明。

## JTAG 30 MHz RTT 实测

`rtt30m-max.json`、测试脚本和两份原始 10 MiB 载荷已独立核对通过。
报告 SHA256 为 `42c286164ed9b9407f71b2485c835a6df2f76763e3e1b8d0e68e5b89e2700b56`；本机复核记录为 `rtt30m-independent-review.json`。
配置为宿主 `4be6ab66-verified`、480 量子固件、JTAG 30 MHz 档位确认、目标 250 MHz、16 KiB 环形缓冲，仅订阅 CH1。

| 目标块长 | 完整载荷 | 目标耗时 | 主机耗时 | 目标吞吐 | 主机吞吐 |
| --- | --- | --- | --- | --- | --- |
| 1024 B | 10485760 B | 60.408418 s | 60.516088 s | 169.512799 KiB/s | 169.211203 KiB/s |
| 2048 B | 10485760 B | 60.421452 s | 60.529762 s | 169.476231 KiB/s | 169.172976 KiB/s |

每份载荷的所有模式字节及递增序号一致，SHA256 分别为 `ed1679b3a5144f6603d9cee2b85c27006f3193f1b7163513093412dbac7dead6`、`5ca77de447608f4a7477f9c347a2528110ccb7b690fb52f3b543578c01007b74`。
独立复核还从目标周期计数和 250 MHz 时钟重算目标耗时，并按总字节数重算两端吞吐；完成状态、接受字节数和块数一致。
两个运行均保持同一 streaming 会话，量子 480、仅 CH1，MUX gap/drop 为 0，无超时记录。

本组观察到的最高主机吞吐为 **169.211203 KiB/s**，目标为 **169.512799 KiB/s**。
此前 20 MHz 测量订阅 CH0+CH1，本组只订阅 CH1，轮询范围也发生变化；不能把全部增幅归因于时钟，也不能推断物理最大速度或其他芯片/固件组合的保证值。JTAG 数字来自档位确认，未做仪器测频。
报告记录 RTT 正常停止、JTAG 恢复 10 MHz、`device_closed=true`。本轮按用户更新后的验收范围完成；并行饱和 SV 溢出、历史 995/10048 仍保留，正式发布与安装包构建没有发生。

## 固件读取流水线后续优化

上述限定验收完成后，用户继续要求优化 RTT/SystemView，并提供 J-Link 15 MHz 约 820 KB/s 作为比较线索；该数字未在本会话独立复现，不能与 KiB/s 结果直接作严格对比。
指定固件会话报告共享 RTT 的 `io.read` 原先仍走普通 sysbus，现候选已接入已有 `riscv_debug_sysbus_read_mem_stream` 读取流水线；分离 1..3 字节首尾和对齐主体，适配范围为共享 RTT/SystemView，保持 480 量子、普通内存/Watch 路径、写指针提交和 DAP 仲裁。
固件会话提供的候选标识为编译时间 `2026-10-30 23:15:39`，UF2 SHA256 `8ff28361456dcf54e4a5f26bb876bb5f4e8ecb35ce601b079adcb324de05ef2a`；来源仍是未提交的固件工作区，不能归为之前的 `7d7a6480` 提交。本会话独立核对提供的 UF2 文件及源码快照哈希，没有重新构建固件或读取设备自身的固件哈希。
源码快照 `mux_runtime.c` SHA256 为 `d3783c9da715af4902ef609c8fc20507ded046a03b37d6d81abac400259d5266`，对应测试文件 SHA256 为 `92afaf9ae750b8a3c0596644f47143be0804d468d6a14fdbb50c2a4764a2901c`；与候选 audit 记录一致。差异快照显示增加 RTT 读适配，原普通读和写路径不变。固件审计记录 Flash 分配增加 154 字节，AHB/DLM 分配无增加。
宿主继续使用不可变 `4be6ab66-verified`，本会话只核对报告及保存载荷，没有连接硬件。新 RTT、SV 独立及共存结果如下；之前约 169 KiB/s、SV 独立和饱和溢出记录仍属于前一固件候选。

### 流水线候选 RTT 证据

`pipeline30m.json` 的 SHA256 为 `60900538c029525f98df9de2b5053f8b2d46be17163e5f49cf308c4ee79fabf3`；本机独立复核记录为 `pipeline30m-independent-review.json`。
两份各 10485760 字节载荷逐字节模式、每块递增序号及 SHA 全部一致，载荷 SHA 与前一 30 MHz 表中相同。

| 目标块长 | 目标耗时 | 主机耗时 | 目标吞吐 | 主机吞吐 | 对上一相同配置主机实测比值 |
| --- | --- | --- | --- | --- | --- |
| 1024 B | 17.701149 s | 17.745925 s | 578.493532 KiB/s | 577.033895 KiB/s | 3.41014 |
| 2048 B | 17.685276 s | 17.730440 s | 579.012727 KiB/s | 577.537826 KiB/s | 3.41389 |

本次与 `rtt30m-max` 的宿主源码、目标镜像 SHA、JTAG 30 MHz 档位、仅 CH1、目标 250 MHz、16 KiB 环形缓冲和 480 量子均一致。独立复核还从周期计数重算目标耗时，并按完整载荷重算两端吞吐。
两组完成状态、字节数、块数一致，保持同一 streaming session；MUX gap/drop 为 0，无超时记录。报告记录 RTT 停止、JTAG 恢复 10 MHz、`device_closed=true`。
因此当前 RTT 实测最高主机吞吐为 **577.537826 KiB/s**；这仍是该配置下的观测值，不是通用上限。

### 流水线候选 SystemView 与共存证据

`pipeline-sv-60s.json` 的 13 个状态样本独立复核通过：63.129936 秒，最终累计 852087 个事件、3743416 原始字节，首尾样本间新增 851397 个事件。全部样本的 target overflow/drop、parser 和 MUX 丢失计数均为 0。配置仍为 JTAG 20 MHz、目标 250 MHz，只启动 SV、目标 RTT 压力负载关闭；报告记录正常停止、10 MHz 恢复及设备关闭。这满足用户本轮独立 SV 零丢失计数要求，不据此承诺任意负载或无限时长无损。

对 `pipeline-coexist.json` 做了全报告递归审查，包含 79 个 SV、124 个 MUX、46 个 Watch 状态对象，而不是只看会因重启归零的末次状态：

- 目标压力任务周期为 **32 ms**，Wave 任务为 1 kHz、Watch 请求间隔 1 ms。虽然脚本沿用 `After saturated channel2` 标签，不能据该名字把本轮描述为饱和测试。
- 两份 RTT 原始载荷分别为 102400 字节（序号 0..99）和 264192 字节（序号 100..357），所有模式字节、连续序号及 SHA 一致，且与目标接受计数吻合。
- 12 个启停/共享阶段、50 次 DAP 64 字节读取、写入恢复、halt/step/resume、480 字节内存写读恢复、256 字节 RTT 二进制回显及退出恢复通过。
- MUX、SV parser、Watch read error/drop 为 0；但 session generation 2 的中间状态出现 target overflow **28**、baseline 后 target dropped packets **1330**。最后状态为零不抹去该事实：控制共存及 RTT 完整性通过，**并行 SV 无损未通过**，按用户范围保留容量边界。
- 两个新报告均记录正常停止、恢复 10 MHz、`device_closed=true`；固件会话最终说明目标保留 SV fixture、压力负载关闭且运行实例已释放。本会话没有连接硬件作额外验证。

新报告 SHA256：

| 报告 | SHA256 |
| --- | --- |
| `pipeline-sv-60s.json` | `5af9b135dbbe3db0829a4074c70924b85d438c0fd720faec80f50dcafa05d230` |
| `pipeline-coexist.json` | `ea92cf5812ffd01df1a39836a9261cc16950381b776a6b4583f901276c6a8e73` |

两份共存载荷 SHA256 为 `26bd57c9af96eeb28dc19e9200a7263833ed9be6c2c786e96672ac2487609b4a`、`cf4ccd9d74873d468cc55bbd54abb08f24d96a0ef0cc54fbbeb2664055cd8536`。本机完整复核记录为 `pipeline-sv-independent-review.json` 和 `pipeline-coexist-independent-review.json`。
本轮按更新后的用户范围完成；宿主源码候选及已安装包保持不变，固件源码快照未提交，正式发布仍未获本轮指令。

### 后续 DMI burst 候选

上述流水线候选完成后，指定固件会话继续用户授权的 RTT/SystemView 优化，新增仅 RTT/SV 启用的 DMI read burst。差异快照显示每块只进行一次资格判断及扫描函数选择，仍逐扫描检查 DMI ACK，以 NOP 收尾；最后一个字仍由原 SBA 路径关闭 autoread 后读取。普通 stream 包装保留原路径，普通内存/Watch 不启用 burst。宿主保持 `4be6ab66-verified`，本会话仅离线核对，硬件操作仍由指定会话完成。

最终候选编译时间为 `2026-10-30 23:29:38`，UF2 SHA256 为 `5396eedb0c777e2ba15f6e30e2dce8ca219e1e3846e689044f3c218745637232`；对应 BIN SHA256 为 `30ee8f3fbe1535e5fb99d309b065c677854765eaf4bdeb21e8feea06e9cb0262`。本会话独立核对 UF2 全部块头、地址边界、载荷与 BIN 一致，并核对保存的升级记录与 BIN 编译时间一致且早于测试开始；没有读取设备自身哈希或重新构建固件。此前 `burst30m` 试跑因增量编译时间戳未更新、升级身份断言失败，不计入最终验收；只采信全量重编译、身份通过后的 `burst-final30m`。

候选仍来自未提交工作区。最初归档用文本读写转换换行，导致两个测试脚本原始哈希不符；本会话严格检查发现后，固件会话改用原始字节保存，产品源码及 UF2 均未改变。重新核对全部 9 份产品/测试源码快照与修正清单一致，其中 SBA 测试另补 24/480 字节模型用例；该测试补充不改变固件。最终 audit SHA256 为 `4df7cf38229603e331466a2846f24d801533c3411096e41fbccfec4418f0cf69`，记录相对流水线候选 Flash 分配 +428 B、ILM 代码 +402 B、AHB/DLM 分配不变。

#### Burst RTT 完整载荷核对

两份各 10 MiB 数据所有字节、块序号及 SHA 均通过，载荷 SHA 与前两轮一致；目标周期计时、两端吞吐重算、完成字节/块数、同一 streaming session、零 MUX gap/drop 及正常停止/10 MHz 恢复/设备关闭记录均通过。

| 目标块长 | 目标耗时 | 主机耗时 | 目标吞吐 | 主机吞吐 | 相对上一流水线同配置主机实测 |
| --- | --- | --- | --- | --- | --- |
| 1024 B | 16.408666 s | 16.463591 s | 624.060476 KiB/s | 621.978526 KiB/s | +7.7889% |
| 2048 B | 16.417518 s | 16.449609 s | 623.724009 KiB/s | 622.507201 KiB/s | +7.7864% |

宿主、目标镜像 SHA、JTAG 30 MHz 档位、仅 CH1、250 MHz 目标、16 KiB 环形缓冲和 480 量子均与上一流水线轮相同。**622.507201 KiB/s** 是当前受测配置的主机最高观测值，不能称为通用极限，也未复现用户提供的 J-Link 对比值。

#### Burst SystemView 与并行边界

- 独立 SV：62.964688 秒，13 个同会话样本，最终累计 850153 事件/3734919 原始字节，首尾新增 849772 事件；target、parser、MUX 的全部丢失计数为 0。JTAG 20 MHz、目标 250 MHz、RTT 压力关闭、不运行 Watch，与前轮独立条件相同；正常停止/恢复 10 MHz/设备关闭记录通过。此为计数器验收，没有完整原始 SV 归档逐字节比较。
- 并行：32 ms RTT 负载、1 kHz Wave、Watch 请求 1 ms；两份 103424/256000 字节 RTT 数据（序号 0..100 / 101..350）逐字节及 SHA 通过。12 个控制阶段、50 次 DAP 64 字节读、写回恢复、halt/step/resume、480 字节内存及 256 字节 RTT 回显记录通过。
- 全报告递归核对 81 个 SV、126 个 MUX、46 个 Watch 状态：中间 SV 会话 target overflow **26**、baseline 后 dropped packets **1164**，parser/MUX/Watch 错误及丢失为 0。最终重启后的零值不抹去中间溢出；仅认定控制共存和 RTT 完整性通过，仍不宣称并行 SV 无损。

| 最终报告 | SHA256 |
| --- | --- |
| `burst-final30m.json` | `6a2c383c0718eae917c021ab8e65ed799453fa9a5d171bcada869df1e8df4e3d` |
| `burst-sv-60s.json` | `973a41c41d50d3630e297b43df46367a11c924b017fb3ff1193db29f04d87405` |
| `burst-coexist.json` | `dca3577a38706c9ce74f4b71cc4ac1ec1cd79475050f6e96d23435e08542fa38` |

两份并行载荷 SHA256 为 `08a7ac6bef88ed0c8f337a4adf8a204a708428c7e529826e5557be75c85e9469`、`c0ea5e9ac6f7f4f1ac8d0419d5a4aa03883a83ee1a37e1824dda212b7b8b63d8`。完整本机复核记录为 `burst-final30m-independent-review.json`、`burst-sv-independent-review.json`、`burst-coexist-independent-review.json`。各轮报告的设备释放只证明对应收尾，后续操作仍先与指定会话协调。已装宿主及 Skill 均未重建或覆盖，未正式发布。

指定会话最终报告本轮硬件均已释放，目标保留 SystemView fixture、压力负载关闭。其交付 ZIP `HPMLink_RTT_SystemView_latest.zip`（1327623 字节）已独立核对：SHA256 `79cee1e7ae79d831739868ff6ca5325ae58668a9318b6a2e9919afb71f326283`；43 个载荷文件加一份 manifest，所有大小/哈希匹配，manifest SHA256 为 `e17c7737e5f1822c4e7fbe3f948d5b47fa1214b8cc81d18a80afb63b2ab61022`。9 份源码快照、3 份报告、5 份原始载荷/DAP 日志与已核对文件一致，RTT 目标 BIN 与报告镜像 SHA 一致，最新数据摘要和非零并行溢出均正确；不含旧轮/身份失败试跑报告或 runtime 认证/所有权文件。该包是本地固件复测交付资料，含本机复测路径，未公开发布；不是宿主安装包或正式 Skill。核对记录为 `burst-delivery-independent-review.json`。

### 描述符与 SBA 复用候选（HPM 已核对，H7 待实板）

指定固件会话随后报告用户继续要求优化描述符、读指针及 SBA 复用，并兼顾 ARM；当前仍用 HPMLink，后续将换接 STM32H7。其正在完整编译的新改动包括：共享描述符只读取 buffer/size/Wr/Rd 的 16 字节，保留双快照校验；HPM 仅复用已验证 quiet 状态，普通 DMI/所有权变化使其失效，读指针写前仍实时核验 SBCS；ARM 仅在同一 RTT 锁范围复用 prepared 状态，下一服务冷启动，保留 CSW/TAR/DRW/drain 路径。所谓读指针正常 6 次扫描对旧 11 次，是固件会话的扫描次数模型，不是本会话测得的耗时或性能结果。

固件会话后续明确把复用边界命名为 `rtt_memory_scope`；本会话从原字节快照生成统一行尾的可读差异，核对每次 poll 进出及失败出口均清除状态，非 scope 命令不复用 HPM quiet 缓存，ARM prepared 仅限锁内。固件会话报告生产模型覆盖相关故障及 ARM 一致性/上下文；其日志中完整 480 B 正常调用为 22+136+20+6=184 次扫描，对旧轮 197 次减少约 6.6%。该次数模型不代表实测耗时分布。本会话未重新执行固件构建或硬件测试。

新候选编译时间 `2026-10-30 23:46:18`，UF2 SHA256 `c995a6ea2a3ec708f22add355ca33fc897f4e80f01f40ebdc133cbcac24c1699`，BIN SHA256 `a1de025766029be2fd5698f382938183c34894d9a7c6f024acc822bfcbee1d94`。UF2 块头/地址边界/载荷与 BIN 一致、保存的升级身份与测试时序、10 份源码/测试快照哈希均独立核对通过。该版本仍来自未提交固件工作区；audit SHA256 为 `8af2c624fd47fee9067a8fb911e6f5a7ee8a9ab06c0f84c358a39bf6f5091fd8`，相对 burst 候选记录 Flash +1750 B、AHB +8 B、DLM +1 B、ILM +26 B，不再表述为数据 RAM 无增量。

#### HPM control 结果

两份各 10 MiB RTT 载荷的完整模式字节、块序号、SHA、目标周期计时和两端吞吐重算均通过；保持相同目标镜像及宿主、30 MHz 仅 CH1、250 MHz 目标、16 KiB ring、480 量子，零 MUX gap/drop。载荷 SHA 与前两轮相同。

| 目标块长 | 目标耗时 | 主机耗时 | 目标吞吐 | 主机吞吐 | 相对 burst 同块长主机实测 |
| --- | --- | --- | --- | --- | --- |
| 1024 B | 15.445134 s | 15.486803 s | 662.992002 KiB/s | 661.208148 KiB/s | +6.3072% |
| 2048 B | 15.444629 s | 15.489375 s | 663.013675 KiB/s | 661.098325 KiB/s | +6.1993% |

最高主机观测值为 **661.208148 KiB/s**，仍不是通用极限。独立 SystemView 在相同 20 MHz/250 MHz、无额外 RTT 压力及 Watch 条件下运行 **62.679469 秒**，13 个同会话样本累计 **846407 事件/3718463 字节**，首尾新增 845517 事件；所有样本 target、parser、MUX 丢失计数均为 0。该结论来自记录及计数器核对，不是原始 SV 事件逐条真值比较。

并行报告的 106496/271360 字节 RTT 载荷（序号 0..103 / 104..368）全部字节/序号/SHA 通过；12 个控制阶段、50 次 DAP 读取、写回恢复、halt/step/resume、480 字节内存与 256 字节 RTT 回显记录通过。全报告递归 75 个 SV、120 个 MUX、46 个 Watch 状态仍出现 SV 目标 overflow **15**、baseline 后 dropped packets **1442**，其他层计数为 0；有限并行控制及 RTT 数据完整，仍不认定并行 SV 无损。三项报告均记录停止/恢复 10 MHz/设备关闭。

| HPM control 报告 | SHA256 |
| --- | --- |
| `control30m.json` | `df03810f6180a1e7601b53ce22b83f211e2dd0d743f14dc8e6dace43efa3b5aa` |
| `control-sv-60s.json` | `b87061826fa1f83af28feaf7a9d38dab3c2fa10581bb243d73967a87f15a448f` |
| `control-coexist.json` | `eb9b751e3e3bfa8d0486639f3530a28448895a7fc59756c923fae56c3d1cf84c` |

并行载荷 SHA256 分别为 `0051521ae248947344a8a21f8cf8538b3b5c4b0f11089ac2f0be25a12a55a0d8`、`8e715b72cc5d376311f2766da2914aec5730033fc82a033bd999db0b54cddf7a`。本机独立核对记录为 `control30m-independent-review.json`、`control-sv-independent-review.json`、`control-coexist-independent-review.json`。

HPM 本轮限定证据已通过；STM32H7 尚未接入，模型及 HPM 结果不证明 ARM/H7 实板通过。H7 接线通知由指定固件会话统一发出，后续硬件状态先协调。前一 `5396eedb…` 及其交付 ZIP 保留为历史证据，不当作新候选交付；宿主仍为 `4be6ab66-verified`，本会话不占硬件、不构建或覆盖安装。

新 control 交付 ZIP 已独立核对：`HPMLink_RTT_SystemView_latest.zip` 为 **1343637 字节**，SHA256 `43b44dae23f36d139e0824a6cc201db8561ba120ba98de2070d2381e8036db12`，manifest SHA256 `fb5f739b5568176878810a822e9610145891478ce0cc7f6b6cd3635a6f03a213`。46 个载荷文件加 manifest 共 47 项，全部大小/哈希一致；10 份源快照、三份 control 报告及五份原始载荷/DAP 日志与已核对证据一致，UF2/BIN/目标镜像和最新摘要吻合。摘要最高吞吐比值 1.062169 是本轮最高值相对前轮最高值；与上述按相同块长比较的两个比值口径不同。包内仅包含本候选报告，保留非零并行 SV 计数及 `stm32h7_hardware_verified=false`；H7 文档是待执行计划，不能当作实测证据。审阅 diff 已统一行尾，原始源码字节和 audit 未变。指定会话确认三项测试停止、10 MHz、设备关闭；本会话未触碰硬件。复核结果为 `control-delivery-independent-review.json`。此包是本地固件复测资料，未公开发布。

本机证据目录为 `F:/MKLink-Build/artifacts/rtt-shared-20261030`；候选 ZIP 为源码导出，不是安装包或完整发行 Skill：

| 源码候选 | ZIP SHA256 |
| --- | --- |
| `70841886`（失败保留） | `f7bfe645f70ca41fd70543653b18bcb3b88ae23d44663f606b13e35995817f83` |
| `a44128f9`（双 10 MiB 吞吐验收） | `cdc1b411d06699fe755f4ca33d7269bc4cefa19237dd532aec9a2cb41c79013a` |
| `4be6ab66` 首次空 ZIP（失败保留，不可使用） | `8739c76e681f900923b900c9df0ef75cf421d39cabb54650c4b9ad19b6a76d85` |
| `4be6ab66-verified`（1255 文件/全部 blob 核对及实际导入通过） | `cb3c43fcec693cddcdcf101379fe35c66fc863a1fffeb1759ae3a3283fe0996e` |

已安装 Windows/完整 Skill 仍为 `dce17d3e/0d680d90` 的 0.4.2 本地测试包；未包含本报告改动，也未包含后续 `6ce79923` 读取提示和 `4551687d` HTTP 发现修复。正式 0.4.1 不变。
