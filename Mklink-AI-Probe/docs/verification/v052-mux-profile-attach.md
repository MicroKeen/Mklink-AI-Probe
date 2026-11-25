# S32K314 原生 MUX 连接与无 GUI 验收

上位机基线为 `11202db0`，开发分支为 `codex/v0.5.2-fixes`。正式版仍为 0.5.1。
桌面、Web、CLI 和共享 MCP 使用同一型号目录与物理连接。实板与下载器固件由固件会话操作。

## 联调入口

| 入口 | 操作 | 成功依据 |
| --- | --- | --- |
| 桌面 / Web | 配置页 → 本地设备，选下载器与 S32K314，连接 | 后台确认的型号与 MEM-AP 4 |
| Skill / MCP | `list_target_profiles()` → `connect(probe=…, mcu="s32k314", project_root=…)` | `target_attach: {"profile":"S32K314","mem_ap":4}` |
| CLI | `mklink target-profiles` → `mklink device-status --probe … --mcu s32k314` | 同一后台的 `target_attach` 回执 |

工程、CLI 和共享 MCP 可精确选择 `s32k314` 或目录声明的别名 `S32K314HMS`、`NXPS32K314HMS`。
型号匹配忽略大小写和空白，成功回执统一为 `S32K314`、AP4。在线烧录页面沿用 Pack 目录中的 `target_part=S32K314`。

首次无 GUI 连接应使用目标工程的绝对路径。读写和采集继续使用已附着的会话，示例见[共享后台](../../references/shared-runtime.md)。
V4.7.5 尚未发布。同版本开发固件的能力可能不同，主机用 HELLO bit 13 判断是否支持专用连接。缺能力时返回升级提示。

## 在线烧录与读回

桌面「在线烧录」页使用 CMSIS-DAP 和 pyOCD。选中 S32K314 后，下载和 Flash 读回会在各自的
pyOCD 会话中执行上表对应的三阶段配置，并核对所选 CPU 的 MEM-AP。内置 FLM 提供 Flash 几何信息。
标准连接模式可选 HALT 或 ATTACH。此配置要求释放复位，保持复位连接会在打开新探针前返回提示。
S32K314 的 `ConfigTargetSettings.flash_prepare` 声明为 `halt`。算法预备阶段保持 AP4，
要求核实内核停机及特权 Thread/MSP 状态。若主机观察到应用原先在运行，可在普通中断中短时恢复运行，
待其自然返回后重新停机。已由外部暂停的应用保留暂停状态。选择的 FLM 还须满足当时生效的 MPU 权限及缓存条件。
复位会结束旧的 AP 绑定，软件复位回执明确后在同一探针上新建非停机会话确认目标运行。
未声明 `flash_prepare` 的型号沿用原有算法前复位。

用户选择最终复位时，在线驱动先解析当前处理器的 Pack 复位定义。无外部 Pack 时，
主机型号资源 `mcu_profiles.json` 的 `ConfigTargetSettings.online_system_reset` 指定
`s32k314_functional` 处理器，用于默认、软件或系统复位。受信任的处理器按名称注册，
目录在打开探针前核对处理器适用的型号和 MEM-AP。连接阶段和 MUX 协议均不触发此动作。

S32K314 处理器采用 Keil S32K3xx DFP 1.0.1 的 `ResetSystem → FunctionalReset`。
发送前重新读取 AP6 IDR，须完整匹配 `0x001C0030`。四次 MDM-AP 控制写各自提交并等待确认；
其中一次置位 SYSFUNCRST。回执不明时停止，错误详情保留 AP6 IDR、当前步骤和已确认步数。
确认复位命令后，新绑定报告处理器运行状态。台架另从应用启动状态和独立读回验证实际复位。
[Keil S32K3xx DFP 版本记录](https://www.keil.arm.com/packs/s32k3xx_dfp-keil/versions/)

下表的路径均位于所选本机后台的 `/api/online-flash` 下。桌面先通过
`POST /api/runtime/select` 选择 CMSIS-DAP 探针，并沿用后台的探针标识和设备代次。

| 操作 | 接口 | 如何核对 |
| --- | --- | --- |
| 选型号与算法 | `GET /targets?q=S32K314`、`GET /targets/S32K314/algorithms` | 按镜像地址选择 Code 或 Data FLM，使用当前目录返回的 `algorithm_id`；旧镜像重新检查 |
| 检查镜像 | `POST /images/inspect` | multipart 传 `file`、`part_number=S32K314`、`algorithm_ids`，BIN 还需 `base_address`。核对返回的 `image_id`、算法和扇区 |
| 执行已选操作 | `POST /jobs`、`GET /jobs/{job_id}` | 传 `target_part=S32K314`、所选 `probe_id`、时钟、连接模式、镜像、算法、动作及扇区。以任务终态和校验结果为准 |
| 读回 Flash | `POST /memory/read` 或 `POST /memory/read-stream` | 传同一型号和探针、`address`、`size`，与原镜像逐字节比对 |

内置 DAPLink 算法的在线读回按 Flash 地址范围选算法。RAM、RTT 和 SuperWatch 使用共享 MUX 会话的 AP4。
切换传输时先释放当前探针占用。

| S32K314 算法 | 可编程地址（含末地址） | Keil S32K3xx DFP 1.0.1 与内置文件的 SHA-256 |
| --- | --- | --- |
| `S32K3x4_Code.FLM` | `0x00400000–0x007DFFFF` | `ec68ecfee2740100df26150537e4e63ae4f3ce20f93bb4006b8f84e05c0ec1b7` |
| `S32K3x4_Data.FLM` | `0x10000000–0x1001FFFF` | `05a67d4697187c87b42e72de41ef17cf38239d3b358ee683d24c87d57c1c6b80` |

两项 FLM 的工作区均为 `0x20400000–0x2040FFFF`，保留整机 SRAM 映射。
旧目录将 Code 文件同时指向 Data 地址。新主机按 SHA-256 验证目录中已有的 Data 文件，旧算法 ID 失效。
缺少 Data 文件或其校验失败时，Code 条目仍可使用。Data 的算法选择、地址边界、编程及读回已做软件验证。
该板 DFlash 的实际擦写、校验和读回仍待实测。

在 S32K314 上，Keil 1.0.1 的 `S32K3x4_Code.FLM` 可写范围为 `0x00400000` 至
`0x007DFFFF`。驱动按算法文件 SHA-256 识别这一限制。使用内置算法、导入 FLM 或加载 DFP 时，
扇区擦除和编程都须落在该范围内，自定义区域也须满足此条件。如果整片擦除将调用这个
Code FLM 的无地址 `EraseChip`，请改为选择需要擦除的扇区。Data FLM 使用自己的几何信息。
独立内存读取继续使用已绑定的 AP4。

## 配置和传输

`mklink/mcu_profiles.json` 的 `mux_attach.version=1` 指定配置格式。型号只能从主机目录解析。
阶段名称参照 [SEGGER 的 Customizable actions](https://kb.segger.com/J-Link_script_files)。目录在
`hook_support` 中公布全部 44 个名称。当前的 3 个可用阶段如下。

| 阶段 | S32K314 的配置 | 校验规则 |
| --- | --- | --- |
| ConfigTargetSettings | 选用 MEM-AP 4，要求释放复位 | 仅主机配置，无目标访问 |
| InitTarget | 依次核对 AP4/6/7 IDR、应用调试授权和功能复位状态，按掩码更新 AP7 调试使能 | AP 更新前必须验证该 AP 的完整 IDR |
| SetupTarget | 在 AP4 读 Cortex-M7 CPUID 和 SIUL2 MIDR1 | 两项掩码签名均须匹配 |

阶段顺序由编译器决定。保留阶段可省略或声明空列表。有非空保留阶段或未知阶段时返回
`unsupported_hook` 和具体名称，错阶段或不支持的版本也在打开探针前被拒绝。
其余 41 个名称供后续扩展，本版只执行上述连接配置。

主机在同一 CLAIM 下发送 `0x18`。最大 16 步，含 8 字节 nonce 的载荷上限为 268 字节。
错误回执保留 status、step、reason、actual。缺能力、型号签名不符及绑定失效均不会转入通用 attach。
绑定失效需显式重连，写入结果不确定时停止。普通芯片继续原有连接和共享逻辑。

## 软件验证

- 真实 stdio MCP 子进程通过回环 HTTP/WebSocket 调用共享后台，生产 Device、Bridge、MUX 对接模拟串口。验证旧 HELLO 缺能力、错误型号的第 7 步诊断、成功的 AP4 回执、读写、双样本采集及写失败后的无重放。
- 桌面/Web 的生产资源在真实 Edge 中连接隔离的模拟 API。验证选探针与型号、失败只发送一次请求、切换探针不继承型号，以及无 IDCODE 时展示已确认型号。
- 线帧回归覆盖最大载荷、阶段顺序、诊断和默认芯片通用 attach。共享后台回归覆盖多客户端、工程默认型号和探针隔离。专项测试位于 `_maintainer/testing/tests/test_*profile_attach*.py` 和 `test_target_profile_catalog.py`。
- 在线烧录使用真实 HTTP 路由与任务管理器，在模拟驱动上分别运行 Code Flash 和 Data Flash 的检查、选定扇区擦除、编程、校验和独立读回。驱动测试另行覆盖 AP4、选错 AP、诊断透传和标准芯片。pyOCD 初始化顺序使用真实 0.44.1 库和模拟 DAP 验证。
- 真实 Edge 还在生产「在线烧录」页选中 S32K314，向模拟 Code Flash 写入 10 字节并另行读回，结果与原文件一致。
- 最终本机回归中，共享主机与 MUX 组通过 1086 项，在线烧录与算法组通过 922 项，灵活面板能力清单及路由组通过 481 项。部分测试文件重叠。GUI 全套 139 个文件的 1478 项通过。
- 实际 Keil DFP 和内置算法文件经 pyOCD 解析，确认 Code、Data 地址和工作区。模型覆盖末端合法字节、跨界镜像、越界扇区，以及上传 BIN 的摘要或后缀与检查结果不一致时的处理。

## 固件会话实板联调

- 冷上电的 S32K314 通过无 GUI MCP 连接，返回 MEM-AP 4。CPUID 为 `0x411FC272`，SIUL2 MIDR1 为 `0x2D3A0000`。两组 8 字节数据读回一致，原值已恢复。连接前后另行读取 AP7，DBGENCTRL 从 0 变为 `0x300000F0`。
- 固件会话也用原始料号 `NXPS32K314HMS` 从真实 MCP 连接，回执为 `S32K314`、MEM-AP 4，再读 CPUID 和 MIDR1 均匹配。
- 同一台架将最后一步的预期型号签名改为 `0x2D3B0000`，设备返回 `status=5, step=7, reason=8, actual=0x2D3A0000`。随后普通读返回 5，显式用正确型号重新绑定后恢复 AP4 访问。见 `bench/profile-negative-live.log`。
- 在线驱动加载 Keil S32K3xx DFP 1.0.1 后在 AP4 读回 `0x00602000` 起的 8 KiB 空白扇区。旧的算法准备随后复位目标并收到 SWD No ACK，未进入扇区擦除。独立复查发现 DBGENCTRL 已清零，扇区仍为空白。
- 固件台架先用独立的受控 FLM 流程写入 1592 字节测试程序，核对完整 8192 字节。随后在此程序运行、MPU 关闭且 I-cache 开启的状态下，从生产在线烧录后端重新开始。它通过 Keil DFP 擦除指定扇区、执行一次 ProgramPage，校验并另行读回全部 8192 字节。整扇区 SHA-256 为 `2820c4a50dcdec3aec233a6f2aa47c4795ceb2da496cbbe52a596fc3c203a4fc`。此项为真实驱动实测，界面截图所用的内置 FLM 另记。
- 在线驱动还通过实际 Keil DFP 执行了用户选择的软件复位。复位后新会话在 AP4 确认应用运行，第三次独立连接读回同一 8 KiB，摘要一致。
- 原应用运行时，固件会话按截图参数在生产驱动上使用 10 MHz SWD、HALT 和软件复位。FLM Init 前在 AP4 确认特权 Thread/MSP，`CONTROL=4`、`PRIMASK=1`、`CCR=0x60200`，应用的 `MPU_CTRL=3` 保持启用。Keil DFP 执行一次 EraseSector、一次 8192 字节 ProgramPage。独立校验全页一致，软件复位后新建 AP4 会话再次读回一致。
- 随后独立验证了截图中的内置 Code FLM。目标从原应用开始，在线烧录产品接口 `/images/inspect`、`/jobs` 通过 CMSIS-DAP 以 10 MHz、HALT、软件复位运行，使用 64 KiB FLM 工作区，未加载外部 Pack。Init、EraseSector、UnInit、Init、ProgramPage、UnInit 的返回值均为 0；只擦写 `0x00602000` 的一个 8192 字节扇区。任务成功后经 `/memory/read-stream` 新建 AP4 会话，全页逐字节匹配。台架日志为 `bench/ui-builtin-product-job.log`。Data Flash 实板擦写待验。
- 用生产驱动所写镜像再次运行后，同一 stdio MCP 会话读到 RTT 连续序号 0–169，缺失 0 条，下行 4 字节由目标确认。SuperWatch 计数为 54622、55547、56402，MEM 邮箱回显 `0xadba12ab`。最终软件复位后原应用运行，`VTOR=0x20000000`、`MPU_CTRL=3`，测试镜像保留在指定扇区。
- 内置算法写入的镜像也用原始料号从无 GUI MCP 复测，RTT 收齐 170 条、下行 4 字节，SuperWatch 计数为 57099、58023、58879，MEM 邮箱回显一致。随后从正在运行的测试程序执行一次内置驱动软件复位。`VTOR` 由 `0x00602000` 变为原应用的 `0x20000000`，`MPU_CTRL` 从 0 变为 3。新会话回报 RUNNING、AP4，全页 8192 字节读回一致。见 `bench/builtin-mcp-streams.log` 和 `bench/builtin-reset-proof.log`。
- Code FLM 按实际范围收窄后，台架重新查询算法 ID，以 `0x007E0000` 为 Flash 结束地址、`0x20410000` 为 RAM 结束地址（均不含）。同一指定扇区再次通过在线任务，全部 FLM 调用返回 0，复位后的独立整页读回一致。见 `bench/ui-final-builtin-job.log`。
- 真实 Edge 的在线烧录页在台架选中物理探针、S32K314、内置 Code FLM、10 MHz 和 ATTACH，从读回对话框读取 `0x00602000–0x00602637`，并点击「保存文件」。浏览器下载的 1592 字节与输入镜像逐字节一致，SHA-256 为 `1d862944b0cf1c8f3398148aba2777a99f1d08e9e86fec9f4d10613c34628000`。台架证据为 `bench/gui-readonly-20261125-235506-909790/verified.png` 和 `downloads/readback.bin`。实板擦写和复位通过上文的生产任务接口验收。

同板普通读写的 P95、采集长尾及 RTT 共存需按[上位机性能基线](v043-host-baseline.md)另做同条件测量。
