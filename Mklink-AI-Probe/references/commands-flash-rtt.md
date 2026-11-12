# 烧录、RTT 与工程配置

> 触发词：flash、rtt、project-init、probes、version、Keil、IAR、copy-flm
> 返回索引：[SKILL.md](../SKILL.md)

## 命令说明

普通原生 ARM 烧录使用所选 Flash 算法。周期性 WFI 目标可在当前连接显式开启睡眠访问后烧录。支持原子睡眠访问的下载器由原生加载器控制编程，随后按镜像地址分段回读并比较。兼容旧下载器在显式模式下由上位机确认 Cortex-M 停核并校验。HPM 使用 ROM API。烧录结果区分编程失败和已编程但回读未通过。独立复位需要下载器的成功回执；回执为空、缺失或报告失败时结果未知。正在运行的 MUX 采集使用帧内复位接口。

在线烧录的“连接设置”和脱机烧录的时钟列表按目标接口切换。HPM 使用 JTAG，ARM 使用 SWD。选择下载器后优先显示该探针的已知档位；若 HPM 页面标为“配置候选”，连接该探针后刷新可核对其能力。当前值需要重新选择时，先选择有效档位再提交。

### RTT 通道预览与窗口适配

Web/桌面 RTT View 点击“自动搜索”后，若已连接并识别芯片 ID，会只读解析该地址的 RTT 控制块，立即显示有效上行通道的 CH 复选框，无需先开始采集。无效或尚未初始化的控制块会显示错误，不自动启动或重试。双击通道面板周围、标题栏或下方空白处恢复自适应布局；按钮、输入框和终端文本的双击保留原行为。

CLI 可调用 `runtime call rtt_inspect --arguments '{"address":"0x20000000"}'`（附上当前工程和探针选择），共享 MCP 可用 `gui_call` 的 `rtt_inspect` 能力查询同样的 `channels`、`up_buffers` 和 `down_buffers`。只读检查不消费 RTT 数据，地址须在目标已知 RAM 内且 4 字节对齐；旧固件采集占用时需显式停止后查询。

### 连接管理

#### `python -m mklink probes list`

被动列出下载器的 USB 身份、当前命令端口、本机别名及身份稳定性。
V2/V3/V4 的命令接口为 `MI_04`；枚举只读取 USB 元数据，不打开串口，
不会向 UART/RS485 发送身份命令，也不改写工程中的 `com_port`。
GUI 正在采集时仍可枚举。旧 `discover` 及其自动保存端口的行为已删除。

多只下载器须用 `--probe ID/别名` 选择各自共享后台；省略选择仅在只有一只时有效。
已选设备缺失或身份不唯一会失败，不转连另一只。序列号缺失或重复时仍分别枚举，
但不能保存持久别名；接口元数据缺失的旧设备不参加自动扫描。

底层 Device 自动连接也只接受唯一被动候选，不使用工程里保存的 COM 号选择设备，
不重试失败连接、不遍历其他设备；显式端口连接仍执行现有 Bridge 同步及接口检查。
没有接口元数据时，仅保留低层显式端口连接，不能据此宣称支持共享身份绑定。

```powershell
python -m mklink probes list
python -m mklink version --probe <probe-id>
```

#### `python -m mklink device-status --probe <ID/别名>`

通过所选共享后台连接目标并读取设备状态，包含端口、目标 IDCODE 和符号状态。
后台尚未连接时会建立目标会话；目标初始化尚未完成或未接目标时 IDCODE 可为 0。
CLI 退出仅解除自己的会话，不关闭 GUI 的连接，也不停止采集。
仅检查下载器自身通信可用 `version --probe <ID/别名>`，不会建立目标调试会话。

旧 `test`、顶层 `--test/--port/--baud` 兼容入口已删除。
端口参数放在具体命令后，例如 `device-status --port COM6`。

#### `python -m mklink version [--port COM6] [--all] [--raw]`
读取烧录器自身固件版本（内部调用 PikaScript `cmd.get_version()`）。注意：
- **这是烧录器固件版本，不是目标 MCU 固件版本**（目标 MCU 固件版本请用 `read-ram` 读固定地址或通过项目自定义的 dump 命令）。
- 默认仅显示当前版本号 + 近期 3 个版本 + 文档链接。
- `--all` 显示完整版本历史（按 V*.*.* 段切分）。
- `--raw` 直接打印设备原始响应（不解析）。
- 经共享后台查询；多设备使用 `--probe ID/别名`，不自动持久化 COM 号，采集中返回忙。

```
[*] 连接 COM6 ...
[OK] 连接成功
[*] 发送 cmd.get_version()
[OK] 烧录器固件版本: V4.3.1
     近期版本: V4.3.0, V4.2.3, V4.2.1
     文档: https://microboot.readthedocs.io/zh-cn/latest/tools/microlink/microlink
[*] 已断开连接
```

`--all` 模式：

```
[*] 连接 COM6 ...
[OK] 连接成功
[*] 发送 cmd.get_version()
[OK] 烧录器固件版本: V4.3.1

=== 完整版本历史 ===
  V4.3.1
    1.增加flush_memroy api
  V4.3.0
    1.解决xxx.FLM.o文件导致的损坏文件系统的问题
    2.增加dump_memory的API
  ...
```

### 烧录操作

自动处理“下载固件”请求前，必须先读取 [firmware-download-priority.md](firmware-download-priority.md)。普通 MCU 的默认顺序是 IDE 原生编译并下载、pyOCD 在线烧录、MKLink 脱机下载 API。只有能力不可用/不适用时才能进入下一后端；执行中的后端失败必须停止并报告。

Keil 工程默认先调用 `UV4.exe -b <project> -t <target>` 编译，再调用 `UV4.exe -f <project> -t <target>` 下载。只有用户明确要求只下载并确认现有产物有效时才能跳过编译。IAR 先用 `IarBuild.exe` 编译，仅在项目已有可靠下载配置时使用 IDE 下载，否则进入 pyOCD。

#### `python -m mklink flash --probe <ID> --firmware <HEX/BIN> --target-part <型号>`
显式原生 MKLink 串口/FLM 烧录入口，用于用户指定、旧流程兼容或诊断，不是自动下载首选。通过共享后台提交任务；`load.hex()` / `load.bin()` 内部按扇区边擦边写，无需单独擦除（独立擦除命令为全片擦除）。

无需初始化工程即可烧录，包括普通 CMake/CLion 项目。例如在目标工程目录运行：

```powershell
python -m mklink flash --probe <ID> --firmware build/Debug/firmware.hex --target-part STM32G071GBU6
```

`--firmware` 与 `--hex` 等价，显式文件相对当前工作目录解析。省略文件参数时，使用所选工程 `.mklink/project_info.json` 中唯一的 `hex_path` 或 `bin_path`；保存的相对路径按项目根目录解析。两者指向不同文件时必须显式选择，不能猜测。型号可以由 `--target-part` 指定，或读取工程中保存的 `device`。可用 `--project-root <目录>` 明确选择工程；固件路径来自该工程时也绑定同一工程，不采用其他 GUI 工程的目标。

**烧录前提条件：**
1. 已选择可连接的探针和正确目标。
2. 明确固件路径与目标型号；`project-init` 可选。
3. HEX/BIN 已编译生成，所选后端需要的算法或 HPM ROM 能力可用。

自动解析 FLM 时依次使用发布包内置 Pack、发布包内置 DAPLink FLM、已安装 Pack、已登记的自定义 FLM。用户在命令或界面显式选择的算法覆盖自动顺序。HPM 目标始终使用 ROM API，禁止加载 FLM。

### RTT 调试

#### `python -m mklink rtt --probe <设备ID或别名> --duration 10`

通过共享后台捕获 RTT，GUI 已打开时仍可使用。已有采集仅订阅，省略 addr/channels
等重配参数；CLI 结束不停止 GUI 的采集。未运行时才指定目标实际地址及通道，例如：

```powershell
python -m mklink rtt --probe "电机板" --addr 0x20000e24 --channels 0 1 --duration 10
```

地址是示例，应从当前工程符号或配置取得。AI 的 MCP 流程使用共享 `rtt_start()`、
`rtt_read_channel`，不发送旧固件 RTTView 原始命令。详见[共享后台](shared-runtime.md)。

**RTT 前提条件：**
1. 固件已集成 SEGGER RTT（运行 `rtt-integrate` 可自动集成）
2. 固件已编译并烧录到芯片
3. `.mklink/rtt_config.json` 中有 `rtt_addr`

#### `python -m mklink rtt-integrate --project-root .`
集成 RTT 源码到项目（支持 Keil 和 IAR）。自动完成：
1. 复制 RTT 源文件到项目的 src/ 和头文件目录（自动检测）
2. 将文件添加到 Keil 或 IAR 工程
3. 在 main.c 中添加 USE_RTT 宏保护的 SEGGER_RTT_Init() 调用
4. 在工程中添加 `USE_RTT` 预处理器宏
5. 从 MAP 文件查找并保存 _SEGGER_RTT 地址

**初始化验证：** 集成后会自动验证 main.c 中的 RTT 代码是否正确写入。如果验证失败，会明确报告失败原因。

**USE_RTT 宏：** 所有 RTT 代码被 `#ifdef USE_RTT` 宏保护。生产固件时只需从工程定义中移除 `USE_RTT` 即可禁用所有 RTT 输出，无需修改代码。
- Keil: Options → C/C++ → Preprocessor Symbols → Define 中管理 `USE_RTT`
- IAR: Project → Options → C/C++ Compiler → Preprocessor → Defined symbols 中管理 `USE_RTT`

**头文件目录自动检测：** 自动从 Keil（IncludePath）或 IAR（CCIncludePath2）工程配置中提取头文件搜索路径，将 RTT 头文件放到正确的位置。

**运行后需重新编译项目。**

#### `python -m mklink rtt-find <map_path>`
从 .map 文件解析 RTT 地址。

```bash
python -m mklink rtt-find "path/to/build/Project.map"
# [OK] _SEGGER_RTT 地址: 0x20000e24
```

### RTT View（Web 仪表盘）

#### `python -m mklink rtt --visualize [选项]`
启动 Web 仪表盘，在浏览器中实时显示 RTT 数据的趋势图表。自动解析 RTT 输出中的数值数据，以 Chart.js 折线图展示。

```
python -m mklink rtt --visualize
```

自动完成：发现端口 → 连接 → 启动 RTT → 启动 Web 服务器 → 打开浏览器 → 实时绘图

**RTT View 选项：**

| 选项 | 说明 |
|------|------|
| `--host 127.0.0.1` | HTTP 服务器绑定地址（默认 127.0.0.1） |
| `--port-http 0` | HTTP 端口（默认 0 = 随机可用端口） |
| `--no-browser` | 不自动打开浏览器 |
| `--max-points 500` | 浏览器最大数据点数（默认 500） |
| `--parser auto` | 解析策略：`auto`、`kv`、`csv`、`regex` |
| `--regex-pattern "..."` | 正则解析模式（含命名分组） |
| `--csv-headers "col1,col2"` | CSV 列名，逗号分隔 |
| `--duration 30` | 运行时长（秒，默认 10） |

**解析策略说明：**
- `kv`（键值对）：自动解析 `name: value | name2: value2` 格式，也支持 `key=value` 格式
- `csv`：解析逗号/制表符/空格分隔的有限十进制数值（支持正负号、科学计数法和括号）；整行须为数值。HEX 日志、混合文本及单位后缀不作为 CSV 曲线数据；带单位的数据可使用 `kv` 或明确的 `regex` 提取。
- `regex`：使用自定义正则表达式（含 Python 命名分组 `(?P<name>...)`）
- `auto`（默认）：自动检测前几行输出来选择策略

Web RTT 终端模式只订阅终端文本，不运行收发视图的行/曲线解析；切换到收发模式后才按需解析。各通道及共享窗口按订阅独立处理，切换视图不重启设备采集。无法解析的数值行不影响原始 RTT 文本或后续采集，CLI、MCP 与 Web 共用数值解析规则。

桌面/Web 的 RTT View 通道中，打开 **日志 → 开始记录** 可保存原始 RX/TX JSONL。
停止记录后，后台以较低进程优先级在同一目录生成同名 UTF-8 TXT，界面显示生成状态。
每行带主机收发日期、时区、通道、RX/TX 和会话，例如：
`[2026-11-12 10:20:30.123456+08:00] channel=0 RX session=... temperature=25`。
跨数据块的 UTF-8 字符和文本行会拼接，时间取该行首块接收时间；分段间未完行会出现在后续分段。
缺失字节和会话切换会保留标记，二进制、控制字节或无法按 UTF-8 解码的字节以转义形式保留。
TXT 供直接阅读，JSONL 保留原始字节供回放；TXT 转换失败不改变 JSONL 的保存结果。
采集期间不转换 TXT；若立即开始下一轮采集，上一轮转换仍会占用少量 CPU 和磁盘资源。

**仪表盘功能：**
- 实时折线图，每个变量独立曲线
- 变量选择芯片，点击切换显示/隐藏
- 统计面板：当前值、最小值、最大值、平均值
- 按 `Space` 暂停/恢复更新
- 按 `L` 显示/隐藏原始日志面板
- 支持多个浏览器标签页同时连接

**RTT 仪表盘 HTML 加载优先级（由高到低）：**

1. `.mklink/rtt_viewer.html` — **完全自定义 HTML**（需自行通过 SSE `/stream` 端点获取数据）
2. `.mklink/rtt_viewer_template.html` — **用户模板**（保留 `__MAX_POINTS__` 占位符，服务器自动注入，其余可自由修改）
3. 内置模板 `_rtt_viewer_template.html`（默认）

**自定义样式推荐方式：** 拷贝内置模板到项目目录后修改 CSS 即可：

```bash
cp <mklink安装目录>/mklink/_rtt_viewer_template.html .mklink/rtt_viewer_template.html
```

模板中必须保留的占位符（服务器启动时自动替换为实际值）：
- `__MAX_POINTS__` — 图表最大数据点数（注入到 `var MAX_POINTS = ...`）

> **Agent 行为指引：** 当用户要求"RTT View"且未指定自定义方式时，直接使用默认内置模板启动即可。如果用户提到"自定义样式"或"调整布局"，告知用户可拷贝模板到 `.mklink/` 下修改。

**使用示例：**

```bash
# RTT View（自动检测格式）
python -m mklink rtt --visualize

# 指定解析器和时长
python -m mklink rtt --visualize --parser kv --duration 60

# 自定义正则解析（命名分组对应曲线名）
python -m mklink rtt --visualize --regex-pattern "counter:\s*(?P<counter>\d+).*adc:\s*(?P<adc>\d+)"

# CSV 格式，指定列名
python -m mklink rtt --visualize --parser csv --csv-headers "counter,adc,sensor"

# 固定端口，不打开浏览器（用于远程查看）
python -m mklink rtt --visualize --port-http 8888 --no-browser
```

### HPMicro BIN / HEX 下载

HPM 任务先读 [HPM 下载与调试](hpm.md)，区分 JTAG、UART ISP 和 ARM 调试接口。

HPM SDK 工程会走设备端 `hpm.program()` 下载路径。HPM 型号不使用 FLM，也不需要 Pack；算法发现必须直接返回空。`project-init` 识别到 HPM board 后，会把 `hpm_flash_cfg` 写入 `project_info.json`；手动配置时必须使用 4 个参数：

HPM5301 也可以在脱机界面显式选择 [USART ISP](hpm-usart-isp.md)，由支持该能力的 HPMLINK V4 固件使用独立 UART 执行。该协议使用单独的 NOR 配置，不沿用下述 JTAG 四字参数，也不自动改变现有下载路径。

```json
"hpm_flash_cfg": ["0xfcf90002U", "0x00000005U", "0x00001000U", "0xf3000000U"]
```

这 4 个参数依次对应 `hpm.flash_cfg(header,opt0,opt1,xpi_base_addr)`。不要再使用旧的 3 参数写法，因为下载算法里的 XPI 基址不应固定。

MCP/AI 调用示例：

```text
start_job(
  action="flash", request_id="<本次唯一请求ID>", confirm=true,
  arguments={"firmware": "<固件绝对路径.bin>", "target_part": "HPM5301",
             "base_address": "0x80000400", "board": "hpm5301evklite",
             "swd_clock": 10000000, "verify": true, "reset_after": true}
)
job_status(job_id="<返回的job_id>")
```

BIN 未提供工程配置时必须显式传 `base_address`。新版 V4 固件支持 HEX：把 `firmware` 改为 HEX 文件，省略 `base_address`，数据使用文件内绝对地址。工具复用解析器校验并规范化文件，使用独立 `hpm.program_hex` 入口；旧固件拒绝，不得改用原始 `hpm.program` 绕过检查。`board` 未知时改传四字 `hpm_flash_cfg`。成功结果包含 `algorithm_source: "hpm-rom-api"`，不得安装 Pack 或加载 FLM。

HEX 保留未覆盖的完整扇区；被覆盖扇区内未指定的字节会被擦除，不承诺保留这些空隙。HPM BIN/HEX 烧录期间不要写入下载器 U 盘，固件会拒绝并发磁盘写入。脱机 HEX 同样要求新版 V4，脚本会在整组烧录前检查能力。

XPI 基址按芯片族选择：
- `0xf3000000U`: HPM5300/HPM5301/HPM5E/HPM6E/HPM6P/HPM6800
- `0xf3040000U`: HPM6200/HPM6300/HPM6750

### MICROKEEN 磁盘管理

#### `python -m mklink mcu-detect [--device STM32H723ZETx] [--flm <算法ID或唯一文件名>] [--json]`
只读检查工程或显式精确器件名对应的统一算法目录，与实际烧录复用同一个发现实现。

- 不写包内或工程 profile，不复制 FLM，不修改下次烧录配置。已删除旧自动生成/固化流程；内置 profile 只作为既有默认值保留。
- 返回算法 ID、来源、Flash/RAM 范围和目录提供的页/扇区信息；不填入猜测的几何参数或 SWD 时钟。
- 多候选返回 `needs_selection`；`--flm` 可按算法 ID 唯一选择，同名多来源仍需选择 ID。交互选择只用于本次检查。
- `--port` 可附加通过共享后台读取的 IDCODE，作为诊断信息；它不能证明精确器件或算法兼容性。
- 缺少算法时，在应用统一目录安装对应 Pack 或配置自定义算法。HPM 返回 ROM API 提示，不搜索 FLM。

不要把未知芯片改成 `custom` 绕过匹配。实际烧录仍须给出工程精确器件/镜像，并由现有目录核对算法覆盖；需要部署目录中的算法时使用 GUI 脱机部署，需要单独复制本地文件时使用下方 `copy-flm`。

#### `python -m mklink copy-flm --probe <ID或别名> [--flm <本地算法.FLM>] [--request-id <请求ID>]`
通过选定探针的共享后台，将本地算法校验部署到身份绑定磁盘的 FLM 目录。省略 `--flm` 时从旧项目/profile 配置解析 Keil 算法；多探针必须指定 `--probe`。同名内容不同的目标由既有脱机事务备份后替换，失败时回滚；不会触发烧录。

命令先输出请求 ID，结果记录在共享任务日志。响应丢失时用 `python -m mklink runtime jobs --probe <ID或别名>` 查询并匹配 `request_id`，不要重新提交未知结果。日志只保留最近64项，缺失不代表未执行。同一请求 ID 及相同内容不会重复复制；更改内容或目标文件名必须使用新 ID。

新工程无需生成 profile；可用 `mcu-detect` 检查目录，用 `--flm` 明确单独复制的本地文件。

`project-init` 不再复制 FLM；烧录时优先按精确器件和镜像范围从统一算法目录选择并部署。

### 配置管理

#### `python -m mklink project-init`
可选的工程配置工具。无显式型号时离线导入 Keil/IAR/HPM 工程；普通 CMake/CLion、Makefile 或只有编译产物的目录可直接保存输入：

```powershell
python -m mklink project-init --project-root D:/Projects/Blinky --target-part STM32G071GBU6 --firmware build/Debug/firmware.hex --elf build/Debug/firmware.elf
python -m mklink flash --project-root D:/Projects/Blinky --probe <ID>
```

`--firmware`（别名 `--hex`）支持 HEX/BIN，`--elf`（别名 `--axf`）支持 ELF/AXF/OUT。初始化的相对文件路径以项目根目录为基准，保存为绝对路径；允许在编译前保存尚未生成的产物路径。项目目录必须已存在。已有通用配置可只更新文件路径，未传入的设置保留。

只保存精确器件、工程目标、固件/符号路径和内存布局等必要信息。新配置不写入猜测的 `mcu_key`、COM 口或 FLM 路径，不连接探针、不下载 Pack，不创建 RTT/工具链模板；重复初始化保留已有连接、RTT 和工具链设置。无可导入工程且缺少型号时，提示补充 `--target-part` 并返回非零退出码；已有 JSON 损坏时不覆盖。算法是否支持在实际烧录时校验，不以初始化成功代表可安全烧录。

显式型号与已保存型号不同，或旧 `config.json` 仍含 `mcu_key` 时，初始化会拒绝覆盖并保留原文件。先核对所选项目及旧目标设置；此命令不自动迁移另一个芯片的算法、内存布局或 RTT 地址。

端口默认连接时自动发现，可显式指定 Windows `COM6`、macOS `/dev/cu.*` 或 Linux `/dev/ttyACM*`。移动工程后重新指定本机产物路径；不会把 Windows 绝对盘符猜测成 Mac 挂载目录。Mac + Parallels 使用与排障见 [macos-linux.md](macos-linux.md)。

#### `python -m mklink project-info`
显示当前项目配置状态（COM 口、MCU、IDE 类型、HEX/MAP 路径、RTT 配置等）。

#### `python -m mklink iar-parse`
解析并显示 IAR .ewp 工程详细信息。

#### `python -m mklink keil-parse`
解析并显示 Keil .uvprojx 工程详细信息。

---

## 按操作检查输入

`.mklink/` 用于保存可复用的默认值，不是所有硬件操作的统一前置条件：
- `config.json` — 可选连接覆盖（新工程只保存 SWD 时钟）。
- `project_info.json` — 精确型号、固件和符号路径等工程信息。
- `rtt_config.json` — 可选 RTT 配置，地址可由当前符号或显式参数提供。

烧录缺型号时补充 `--target-part`，缺文件或有多个候选时补充 `--firmware`。初始化无法识别某种工程不表示不支持其 MCU；CMake/CLion 可使用上述显式通用配置。
