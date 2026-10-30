# HPM 下载与调试

HPM / HPMLINK / RISC-V 任务先读本页，再按需读烧录、内存或采集参考页。
使用 `tools/list` 核对 MCP 工具，用 `ping.capabilities` 核对 `gui_call` 能力；
它们列出的是上位机入口，不代表每个目标架构都支持所有操作。

## 识别与连接

1. `discover_probes` 选择物理下载器；HPM 要求具备 HPM 能力的 V4，V2/V3 不支持。
   `runtime_status(probe=...)` 检查现有任务，`connect(probe=...)` 复用共享后台。
   GUI 已加载工程/ELF 时省略覆盖参数；否则使用用户实际 HPM 工程和对应 ELF。
   后台退出后重连须重新提供 ELF；没有可信 RAM 图时 RTT 的拒绝是缺少工程上下文，
   不能据此判定 HPM 不支持 RTT。先确认 ELF 与板上程序一致。
2. `gui_call("probe_version")` 核对固件/能力，`device_status()` 核对连接。
   `cmd.get_idcode()` 以及 `gui_call("probe_idcode")` 返回的 ID 可能来自缓存；
   `0x1000563D` 不能证明精确 HPM 型号、Flash 容量、当前在线状态或 SBA 已初始化。
   精确 `target_part`、板卡和存储配置取自工程/板级资料。
3. 新固件的原始 `hpm.read_idcode()` 是实时 JTAG 存在性检查，先查
   `hpm.jtag_presence_supported()`。这是固件接口，不是同名 MCP 工具；正常 AI
   使用共享入口，不另开串口执行。返回负数表示忙/不支持/错误，不能当作已拔板。
4. 首次内存访问报 `SBA unavailable` 时，记录固件版本、完整错误和调用入口。
   旧固件可能缺少冷启动初始化；反复 `cmd.get_idcode()` 不会修复它。不要通过
   ARM halt、通用复位、OTP 或反复重放写命令尝试恢复。共享 MUX 路径与原始 Pika
   路径不同，不能用前者成功宣称后者冷启动已修好。

## 调试速度：不要把 SWD 参数当成任意 JTAG 频率

AI 可以自行选择 `set_debug_speed(profile="low")` 或 `"medium"`，对应 4/10 MHz，
无需为普通调试的档位选择再次询问用户；新接线优先 low，已知稳定连接可用 medium。
`high`/`ultra` 对应 20/30 MHz，仅在目标和接线允许时选择。切档前按共享后台规则
处理正在运行的采集；不要抢停其他客户端。读取返回的 `interface`、
`profile_confirmed`、`qualification`，随后用已知有效地址验证通信。

固件的历史命令名 `cmd.set_swd_clock(Hz)` 同时包含 SWD 设置和 HPM JTAG DMI
档位选择。当前 HPM 私有 JTAG 后端只有 **4/10/20/30 MHz** 的 DMI 快路径。
`cmd.set_swd_clock(8000000)` 会返回 `JTAG profile=0`，回退到固定延时的通用
C 路径，**不是把 JTAG TCK 设为 8 MHz**。`set clock 8000000` 只是接受请求，
不是频率测量。1 MHz 同样不代表该 JTAG 路径真实降到 1 MHz。

烧录接口里的 `swd_clock`、脱机 `swd_clock_hz` 也是历史字段名；HPM JTAG 只填
`4000000/10000000/20000000/30000000`。遇到示例或旧配置中的 8 MHz，AI 可选择
受支持的 4/10 MHz 并报告实际选择；用户要求严格 8 MHz 时说明当前路径不能保证。
现有工程保存了其他频率时应显式修正配置，不能用原始命令绕过拒绝。

`JTAG profile=10000000` 只确认选择了内核；快路径还取决于扫描宽度、TAP 链及
探针 CPU 时钟。TAP 发现、通用扫描和 CMSIS-DAP/IDE 路径不等同于该 DMI 内核。
报告分别写明请求档位、固件应答、读写是否成功；没有示波器/逻辑分析仪实测时，
不要声称实测 TCK 或用采样率倒推 TCK。

## 能力和正确入口

| 任务 | 当前入口和边界 |
|---|---|
| BIN / HEX 在线烧录 | 共享 `start_job(action="flash", ...)` 或在线烧录页的 HPM ROM 后端；不是 ARM pyOCD/FLM。BIN 要真实基址，HEX 用文件内地址；精确目标加 `board` 或四字 `hpm_flash_cfg`。 |
| 脱机部署、换板循环 | `/api/offline-download` 的 preview/deploy/trigger；实时存在性检查由生成脚本负责。部署成功不等于已烧写，保存并查询匹配任务结果。 |
| UART ROM ISP | 用户明确选择时走 [USART ISP](hpm-usart-isp.md)；独立的 NOR 参数、波特率与 ROM 启动条件，不隐式从 JTAG 切换。 |
| RAM / Flash 快照 | `read_memory`、`read_memory_regions`；使用工程已知地址。Flash 读取不需要 FLM；RAM 局部/全局映射、总线可访问性和缓存一致性以实际 HPM 工程为准。 |
| RAM / 变量写入 | `write_memory` / `flush_memory` / 共享类型化写入；先确定用户允许修改的对象和范围。RAM 写命令不是 Flash 编程器。未知结果不重放。 |
| ELF、符号、源码行、变量 | 使用 RISC-V 构建产物，通过 `search_symbols`、`gui_call("symbol_status")`、内存/变量接口。仅解析 ELF 不等于具备 CPU 调试控制。 |
| 外设寄存器 | 先 `peripheral_targets(query="HPM...")`，选择 HPM 系列或匹配 SVD，再 `read_register` / `capture_peripherals`。内置系列共用目录，支持手动导入厂家 `*_svd.xml`；不使用 SCB/NVIC/CoreDebug 名称。 |
| RTT、SuperWatch、VOFA | 使用共享采集接口；地址来自当前 ELF 或板级 RAM，不套用 STM32 的 `0x20000000`。已有采集先订阅，连续曲线不用循环 `read_ram` 替代。 |
| SystemView | 目标须有适配 HPM/RISC-V 的 RTT/RTOS 跟踪实现；上位机可接收解析，自动移植模板并不因此支持 HPM。时间基准取目标真实时钟，不能套用 Cortex-M DWT。 |
| 目标复位 | 显式 `start_job(action="reset", ...)` 由后端路由；运行采集时受固件复位能力约束。烧录 ROM API 自带复位/运行，不额外补 ARM SWD reset。 |
| halt / resume / step / 断点 / CPU 寄存器 | 配套上位机的 `hpm_debug` 经 HPM_DEBUG v1 固件接口操作 RV32 hart 0，先查 capabilities。旧固件/旧工具缺少此入口时明确说明接口缺失；可协调释放探针后使用工程已有 HPM IDE/OpenOCD/GDB。不能据旧 ARM API 的拒绝判定 HPM 硬件不支持。 |
| 异常分析 | 使用 HPM 异常现场和对应 ELF；配套 `hpm_debug` 可在已暂停 hart 上读 PC、mepc、mcause、mtval、mstatus。Cortex-M HardFault / CFSR / HFSR / MSP / PSP 不适用，当前没有自动 RISC-V 异常报告，不能把 ARM 检测结果称为 HPM“无异常”。 |
| OTP、保护、供电 | `configuration_description` / `read_configuration` 只限声明支持的字段。OTP 写入/锁定使用专用受控流程，VCC 每次单独确认具体电压；不以通用 ARM `security_lock/unlock` 替代 HPM OTP。 |

## HPM 外设 XML 与 SuperWatch

内置 HPM SDK 1.13.0 的九个系列：HPM5100、HPM5300、HPM5E00、HPM6200、
HPM6300、HPM6700、HPM6800、HPM6E00、HPM6P00。无需本机安装 SDK 或精确到型号。
例如 `select_peripherals(chip="HPM5300")` 可直接加载；输入 HPM5301、HPM5361、
HPM53M1 也会匹配 HPM5300。若已安装精确型号的 Pack，优先选择该 Pack；有多个版本时
使用 `peripheral_targets` 返回的 `target_id` 明确选择。

SuperWatch 的外设面板可输入系列或型号，点击“加载外设”。“加载 SVD / XML 文件”
支持厂家 `soc/<系列>/<型号>/*_svd.xml`，桌面和浏览器均可手动添加；MCP 使用
`select_peripherals(svd="<后台可访问的XML绝对路径>")`。它是标准 CMSIS-SVD，
不是 `hpm_ses_riscv_cpu_regs.xml`，后者不能用于外设目录。

内置目录采用系列共用定义。HPM5361/53M1 的扩展外设需手动加载对应型号 XML。
更换目录前停止 SuperWatch；选择保存在项目中，重连会恢复。仅做只读寄存器/字段采集，
沿用只写与读取副作用过滤。系列目录覆盖不代表所有外设都已在每种芯片上实测；
实际外设是否存在、是否开启时钟仍以目标工程为准。

## 可执行的共享 MCP 烧录流程

当前默认共享 MCP 不提供旧版独立 `flash(...)` 工具。保留唯一 `request_id`，
使用实际 schema 调用，例如用户已授权烧录时：

```text
start_job(
  action="flash", request_id="<本次唯一请求ID>", confirm=true,
  arguments={
    "firmware": "<后台机器上的固件绝对路径.bin>",
    "target_part": "HPM5301", "board": "hpm5301evklite",
    "base_address": "0x80000400", "swd_clock": 10000000,
    "verify": true, "reset_after": true
  }
)
job_status(job_id="<返回的job_id>")
```

地址、型号和板名仅为示例；HEX 不填 BIN 基址。没有已验证板卡配置时传四字
`hpm_flash_cfg`，不要猜 Flash 容量或将其他板卡的参数原样套用。
轮询直到终态，确认 `algorithm_source="hpm-rom-api"` 和校验结果。
响应丢失先按 request_id 查原任务，不重复提交。结束后 `detach()`。

HPM ROM 每个文件的调用都可能复位目标并运行应用；`reset_after=false` 不能
禁止其内部复位。多镜像不是原子事务，也不能保证中间镜像不运行。独立扇区擦除、
全片擦除和“禁止复位”不能从 ARM 选项推断为 HPM 已支持。

## HPM CPU 调试

先检查 `tools/list` 是否有 `hpm_debug`，再调用 `hpm_debug(action="capabilities")`。
这是配套新接口，旧 V4.7.2 镜像不能仅凭同一版本号视为支持；返回能力缺失时停止，
不回退 `cmd.cpu_halt/cpu_run`（SWD）、`cmd.read_cpu_reg`（实际是内存读取）或 ARM FPB。
同时需要包含该接口的共享后台；只更新 Skill 文档或 MCP 客户端不能给旧上位机增加
接口。后台报告未知 capability 时核对其构建，不绕过共享后台直开串口。

用户要求指令调试时，先记录 `hpm_debug(action="status")` 的实时状态；
`state=1` 为运行、`2` 为暂停、`0` 为不可用/其他。需要暂停才显式 halt：

```text
hpm_debug(action="halt", timeout_ms=500)
hpm_debug(action="read-register", register="pc")
hpm_debug(action="read-register", register="sp")
hpm_debug(action="read-register", register="mcause")
hpm_debug(action="step", timeout_ms=500)
hpm_debug(action="breakpoint-query", slot=0)
hpm_debug(action="breakpoint-set", slot=0, address=<ELF解析的2字节对齐执行地址>)
hpm_debug(action="resume", timeout_ms=500)
```

不要无条件执行整个示例。单步、寄存器和断点访问要求 hart 已暂停，接口不代为暂停。
PC/x0..x31 与 CSR 是核心状态，外设仍用所选 SVD 的 `read_register`。
可读 CSR 包括 `mepc/mcause/mtval/mstatus/dcsr`；写入仅支持 x1..x31 和 PC，
不提供任意 CSR 写入。`max_slot=7` 是探测上限，不代表实际有八个硬件断点。
先 query 实际槽位，拒绝占用槽；clear 必须同时传 slot 与原 expected address
（参数名 `address`），不得覆盖其他调试器的断点或改写 Flash 模拟软件断点。

调试期间停止自己拥有的采集并遵守共享占用边界。只有确认本次是 AI 将运行目标暂停，
且所有修改结果已知、用户未要求保持暂停时，结束才恢复原运行状态；用户原先已暂停
的目标保持暂停。失败时保留 `rc/issued/cleanup/outcome_unknown`，不重放单步、
继续、写寄存器或断点操作，也不以复位恢复。可用显式只读 status 核对状态。

## 验证与报告

分别报告固件具备的底层能力、当前 MCP/GUI 可调用的接口、以及本次实际验证结果。
“有工具名称”“命令返回 0”“源码存在实现”都不能替代目标验证。
普通使用只验证用户任务相关能力；全面评估也不默认授权覆盖程序、任意 RAM 写入、
OTP 或 VCC 改动。采集以实际活动通道和已知信号校验，未观测到数据不等于协议不支持。
