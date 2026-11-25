# S32K314 原生 MUX 连接与无 GUI 验收

上位机基线为 `11202db0`，开发分支为 `codex/v0.5.2-fixes`。正式版仍为 0.5.1。
桌面、Web、CLI 和共享 MCP 使用同一型号目录与物理连接。实板与下载器固件由固件会话操作。

## 联调入口

| 入口 | 操作 | 成功依据 |
| --- | --- | --- |
| 桌面 / Web | 配置页 → 本地设备，选下载器与 S32K314，连接 | 后台确认的型号与 MEM-AP 4 |
| Skill / MCP | `list_target_profiles()` → `connect(probe=…, mcu="s32k314", project_root=…)` | `target_attach: {"profile":"S32K314","mem_ap":4}` |
| CLI | `mklink target-profiles` → `mklink device-status --probe … --mcu s32k314` | 同一后台的 `target_attach` 回执 |

首次无 GUI 连接应使用目标工程的绝对路径。读写和采集继续使用已附着的会话，示例见[共享后台](../../references/shared-runtime.md)。
V4.7.5 尚未发布。同版本开发固件的能力可能不同，主机用 HELLO bit 13 判断是否支持专用连接。缺能力时返回升级提示。

## 在线烧录与读回

桌面「在线烧录」页使用 CMSIS-DAP 和 pyOCD。选中 S32K314 后，下载和 Flash 读回会在各自的
pyOCD 会话中执行上表对应的三阶段配置，并核对所选 CPU 的 MEM-AP。内置 FLM 提供 Flash 几何信息。
标准连接模式可选 HALT 或 ATTACH。此配置要求释放复位，保持复位连接会在打开新探针前返回提示。

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

同板普通读写的 P95、采集长尾及 RTT 共存需按[上位机性能基线](v043-host-baseline.md)另做同条件测量。
