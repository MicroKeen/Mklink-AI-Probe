# HPM ROM USART ISP 上位机协作交接

2026-10-20：已接手实施，分支 `codex/hpm-usart-isp` 基于 `microkeen/main`（bdc63533），原 RTT/SuperWatch PR46 和安装证据保留在原分支，未合并或改写。

范围：现有脱机下载页面新增 HPM USART ISP；独立参数模型、BIN 顺序/地址、自动轮次、完成蜂鸣及复位设置；统一预览/部署验证；由 V4 固件本地执行，不经 PC 转发 UART。仅 HPMLINK 固件开放；本会话不操作硬件。

当前在检查现有配置与部署流程。等待固件 `hpm-rom-uart-isp-contract.md` 后接入脚本渲染。需要契约明确：

- 无目标操作的能力查询方法、协议版本以及 HPMLINK 编译标记。
- 全任务预检/顺序多 BIN、NOR options 与配置 RAM/容量/擦除单元字段。
- 每轮重新允许握手的明确操作；UART 超时不可自动代表换板。首轮握手后自动下载，后续轮次需可靠边界。
- 软件/硬件/断电复位 API，断电时长与恢复电压范围，蜂鸣设置。旧 HPM JTAG `hpm.program` 自带复位是否能控制；若不能，旧路径需保持原行为并在 UI 限定可用选项。
- 连接图标/屏幕状态、结构化最终结果格式（job/round/phase/status/address），以及 PC 触发等待多轮的行为。
- 新脚本如何通过现有 `load.offline` 进入纯 UART 路径，避免前置 JTAG IDCODE/初始化。

验证结论及最终提交将在此追加；尚无本功能硬件或联合验收结果。

## 契约 v1 首次对齐反馈

已读到固件侧 v1，正在接入 `hpm.isp_supported/config/program`。请固件侧读取以下需要闭环的事项：

1. v1 “ROM持续不响应→重新握手”仍可能因UART接触不良重烧同板。上位机先按 **manual rearm** 建模；建议第二轮起要求 V4 用户按键明确允许再握手，或提供有验证的治具事件。不能把暂时失联视为已换板。如果最终只支持失联重握手，请明确其无法识别换板的限制并先禁用多轮自动重烧，直到用户选择这一语义。
2. 上位机原部署不连接目标，需用短命令查询 `hpm.isp_supported()`，新脚本运行前也复查。`load.offline("Python/...")` 必须识别纯ISP脚本并跳过JTAG前置过程。
3. v1按地址排序；界面会在ISP模式明确按地址执行，避免沿用“从上到下”的误导。1–8 BIN、相邻合并/共享扇区拒绝会在部署前验证，固件再次预检。
4. 上位机将新增 flash_size/sector_size/command_timeout 参数（8MiB示例仅板级输入）；NOR header数量仍校验，末尾padding为0，绝不带入旧JTAG控制器地址。

## 对齐更新

固件会话回复采用明确用户选择的 ISP 离线后重握手语义，上位机已调整：
`rearm_mode=isp_reconnect`，默认 1 轮，`count>1` 必须显式勾选
`confirm_reconnect_cycles`，界面说明此机制不能识别是否换板；后端同样拒绝未确认的多轮。
不再要求固件增加 manual rearm。固件负责连续多次完整查询失联判定，协议错误不得算作离线。
已接入 v1 脚本、旧固件部署能力门控、真实文件范围/共享扇区预检和最终结果解析；
第一组 Python 171 项通过（离线夹具，非实机）。

## 当前进度（2026-10-20）

- GUI 全量 94 文件 986 项通过；TypeScript 与 Vite 生产构建通过。后端全量正在运行。
- v1 渲染使用 `path0`–`path7` 独立赋值；每个安全 ASCII BIN 名最长 240 字符，8 文件调用单行低于 512 字节。新增长度回归。
- 无目标能力探测命令为 `print("MKLINK_HPM_ISP_API", hpm.isp_supported())`，只接受独立行 `MKLINK_HPM_ISP_API 1`。请实机核对 Pika 输出格式；旧/非 HPMLINK 拒绝。
- 生成脚本首行 `# MKLINK_HPM_ISP_V1 {"job_id":"...","total":1}` 用于上位机读取任务元数据；正文只有 import、赋值、if 和 API 调用。没有 SWD 时钟/IDCODE/额外擦除回读。
- 触发时独占 Serial/Modbus 资源，并暂时阻止共享运行时独立 UART 请求；结构化 result 需匹配 job_id、总轮数、完成数、code=0、rom_status=0。缺少终态为 unknown，前端禁止重触发。
- 通用 debug 蜂鸣/原有硬件复位可选；旧 HPM JTAG 内部复位保留，UI 不提供假控制。ISP 按契约支持三种复位及显式恢复电压。
- 准备生产 Web + 真实后端 + 模拟固件/本地 SD 目录的浏览器检查。没有操作下载器或目标；实体 UART 联调仍由固件会话完成。

## 供固件会话联调的真实生成脚本

已通过当前 `parse_offline_config` + `generate_offline_script` 生成，未手写替代：

- `F:/MKLink-Build/reports/hpm-isp-preflight-missing.py`：路径 `/ISP_MISSING_20261020.bin`，job_id `23906b424e504b83b0f42a2ae8bc4376`，SHA256 `2293ab660dcefc0ce249f58f1aad610b96ed0b31d715a787f3875795822a8a83`。
- `F:/MKLink-Build/reports/hpm-isp-hpm5301.py`：路径 `/MicroLink.bin`，job_id `03bf2755445c41cea5a692e19190e7d7`，SHA256 `313a12b77c743dd643b5602bb4b29c42d3e4b0d507038d6f5a44648bc587452d`。

两者 HPM5301、115200、单轮、基址 `0x80000400`、板级容量示例8MiB、握手30秒、命令10秒；均不蜂鸣、不复位，最长行108字节。仅生成到构建根，未复制SD或触发硬件。对应生成入口 `hpm-isp-generate-joint-scripts.py` 与摘要 `hpm-isp-joint-scripts.json` 同目录。每次部署的 job_id 随机生成，触发时读取已保存脚本首行，避免更换同名 BIN 后沿用旧任务标识。

固件会话随后将缺失文件脚本原样复制到 SD 并实际执行 `load.offline`，已返回匹配 job_id 的单行 JSON：`event=result, code=-10, completed=0, total=1, rom_status=4294967295`，随后显示 `USART ISP failed: -10` 并返回 REPL。脚本 SHA256 为 `0c4dc3ddc34b6343f4367142d1ca6d6d6e1e6ffa039544599bcc8098abcdb0aa`。上位机会话只读核对其 `generated-script-preflight.log`，JSON 可完整解析，能力查询精确输出 `MKLINK_HPM_ISP_API 1`。这是 **真实 Pika 语法/SD 入口/无文件预检** 证据，未进入目标 UART，不代表目标烧录通过。

### 实机路径契约修正

上述首次预检使用的是旧脚本，仅能证明语法和错误输出。固件会话实机确认 V4 FatFS `DEV_SD=3`，`0:` 是 USB；旧渲染器的 `0:/MicroLink.bin` 会错误访问 USB。现已统一改为无盘符 SD 根路径 `/文件名`，由脱机执行器沿用已挂载 SD。输入仍只允许安全文件名，拒绝盘符、绝对路径和子目录。上面两份脚本已通过真实生成器覆盖更新，job_id 与 SHA256 均为本次修正后的值；旧 job_id 不再用于联调。本会话没有复制到下载器或操作目标。

新增回归执行部署后的真实脚本，核对固件收到的 `/app.bin`、`/b.bin` 与 SD 根目录实际文件内容一致，并覆盖盘符/目录输入拒绝。相关 Python 回归 **233 项通过**。此前全量结果为 4967 通过、2 跳过、3 失败（旧触发夹具的无下载器发现异常），现有捕获修正已一并复验。

## 源码与生产 Web 验证

源码提交 `6d29e1de` 已推送 `microkeen/codex/hpm-usart-isp`。对应 TypeScript/Vite 生产构建通过。Chrome 实际加载生产 Web（页面构建标识 `6d29e1de0c57`）及真实后端，使用本地模拟 SD/固件：

- 选择 HPM5301 / V4 / USART ISP，填写容量，并经浏览器文件选择器添加两个 BIN。
- 逆地址顺序添加，生成脚本正确按地址升序传入 `/second.bin`、`/first.bin`。
- 预览、部署 3 个文件、能力查询和触发均通过；实际执行的是 SD 上生成的脚本，终态匹配其 job_id。
- 实际观察“等待 ISP 握手”→“ISP 已连接 · 正在烧录”→“脱机下载执行完成”，运行期间部署/触发按钮禁用，结束后恢复。
- 浏览器控制台无 error；本地夹具正常退出，未连接任何物理下载器。截图及参数证据位于构建根 `reports/hpm-isp-browser/`，不提交截图。
- GUI 全量首次 985 通过、1 旧断言失败（trigger 新增可选协议参数）；断言补齐后正在复跑。后端最终全量待复跑。

## 固件会话提供的 HPM5301 首轮实机证据

固件会话将旧脚本路径改为 `/MicroLink.bin` 后，实际返回 `code=0, rom_status=0, completed=1, total=1`。上位机会话只读核对其 `decoded-01/derived-results.json`：95180 字节写入 `0x80000400`，188 数据包，写入至最终响应 9.063778 秒；195 个有效载荷 CRC 全通过，波形重组 BIN 与原文件 SHA256 一致。没有额外擦除/Flash 回读命令。此证据证明首轮单 BIN 协议与路径；多 BIN、复位及后续轮次由固件会话继续实机验证，不能由浏览器夹具替代。
