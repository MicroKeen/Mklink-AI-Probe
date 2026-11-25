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

下表的路径均位于所选本机后台的 `/api/online-flash` 下。桌面先通过
`POST /api/runtime/select` 选择 CMSIS-DAP 探针，并沿用后台的探针标识和设备代次。

| 操作 | 接口 | 如何核对 |
| --- | --- | --- |
| 选型号与算法 | `GET /targets?q=S32K314`、`GET /targets/S32K314/algorithms` | 按镜像地址选返回的 `algorithm_id`。两个内置条目可显示同一 FLM 文件名 |
| 检查镜像 | `POST /images/inspect` | multipart 传 `file`、`part_number=S32K314`、`algorithm_ids`，BIN 还需 `base_address`。核对返回的 `image_id`、算法和扇区 |
| 执行已选操作 | `POST /jobs`、`GET /jobs/{job_id}` | 传 `target_part=S32K314`、所选 `probe_id`、时钟、连接模式、镜像、算法、动作及扇区。以任务终态和校验结果为准 |
| 读回 Flash | `POST /memory/read` 或 `POST /memory/read-stream` | 传同一型号和探针、`address`、`size`，与原镜像逐字节比对 |

内置 DAPLink 算法的在线读回按 Flash 地址范围选算法。RAM、RTT 和 SuperWatch 使用共享 MUX 会话的 AP4。
切换传输时先释放当前探针占用。

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

## 固件会话实板联调

- 冷上电的 S32K314 通过无 GUI MCP 连接，返回 MEM-AP 4。CPUID 为 `0x411FC272`，SIUL2 MIDR1 为 `0x2D3A0000`。两组 8 字节数据读回一致，原值已恢复。连接前后另行读取 AP7，DBGENCTRL 从 0 变为 `0x300000F0`。
- 固件会话也用原始料号 `NXPS32K314HMS` 从真实 MCP 连接，回执为 `S32K314`、MEM-AP 4，再读 CPUID 和 MIDR1 均匹配。
- 在线驱动加载 Keil S32K3xx DFP 1.0.1 后在 AP4 读回 `0x00602000` 起的 8 KiB 空白扇区。旧的算法准备随后复位目标并收到 SWD No ACK，未进入扇区擦除。独立复查发现 DBGENCTRL 已清零，扇区仍为空白。
- 固件台架先用独立的受控 FLM 流程写入 1592 字节测试程序，核对完整 8192 字节。随后在此程序运行、MPU 关闭且 I-cache 开启的状态下，从生产在线烧录后端重新开始。它通过 Keil DFP 擦除指定扇区、执行一次 ProgramPage，校验并另行读回全部 8192 字节。整扇区 SHA-256 为 `2820c4a50dcdec3aec233a6f2aa47c4795ceb2da496cbbe52a596fc3c203a4fc`。此项为真实驱动实测，界面截图所用的内置 FLM 另记。
- 在线驱动还通过实际 Keil DFP 执行了用户选择的软件复位。复位后新会话在 AP4 确认应用运行，第三次独立连接读回同一 8 KiB，摘要一致。
- 原应用运行时，固件会话按截图参数在生产驱动上使用 10 MHz SWD、HALT 和软件复位。FLM Init 前在 AP4 确认特权 Thread/MSP，`CONTROL=4`、`PRIMASK=1`、`CCR=0x60200`，应用的 `MPU_CTRL=3` 保持启用。目标实际收到一次 EraseSector、一次 8192 字节 ProgramPage。独立校验全页一致，软件复位后新建 AP4 会话再次读回一致。两次实板编程均使用 Keil DFP 和 Code Flash；真实浏览器的内置 FLM 流程为软件验证。Data Flash 的实板擦写待验。
- 用生产驱动所写镜像再次运行后，同一 stdio MCP 会话读到 RTT 连续序号 0–169，缺失 0 条，下行 4 字节由目标确认。SuperWatch 计数为 54622、55547、56402，MEM 邮箱回显 `0xadba12ab`。最终软件复位后原应用运行，`VTOR=0x20000000`、`MPU_CTRL=3`，测试镜像保留在指定扇区。

同板普通读写的 P95、采集长尾及 RTT 共存需按[上位机性能基线](v043-host-baseline.md)另做同条件测量。
