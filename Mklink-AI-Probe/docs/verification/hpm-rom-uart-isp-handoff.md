# HPM ROM USART ISP 上位机协作交接

2026-10-20：分支 `codex/hpm-usart-isp` 基于 `microkeen/main`（bdc63533），功能已实现并提交 PR47。原 RTT/SuperWatch PR46 和安装证据保留在原分支，未合并或改写。

范围：现有脱机下载页面新增 HPM USART ISP；独立参数模型、BIN 顺序/地址、自动轮次、完成蜂鸣及复位设置；统一预览/部署验证；由 V4 固件本地执行，不经 PC 转发 UART。仅 HPMLINK 固件开放；本会话不操作硬件。

已对齐固件 `hpm-rom-uart-isp-contract.md` v1：

- 仅 HPMLINK V4 / HPM5301，默认 115200，可选 2000000；部署和触发前无目标能力查询，不回退 JTAG。
- 1–8 BIN 按地址排序；文件范围、共享擦除扇区等在写 SD 前验证，固件再次预检。Flash 容量必须填写，8MiB 只是示例。
- 独立 NOR 参数与 RAM/容量/擦除单元字段，末尾 padding 为 0，不带入旧 JTAG 控制器地址。
- 完成蜂鸣及软件/硬件/断电复位，断电恢复电压显式填写。旧 HPM JTAG 内部复位保留。
- `load.offline` 进入固件纯 UART 引擎，无 JTAG IDCODE/初始化；最终结果只认匹配任务的结构化 `result`。

固件会话回复采用明确用户选择的 ISP 离线后重握手语义，上位机已调整：
`rearm_mode=isp_reconnect`，默认 1 轮，`count>1` 必须显式勾选
`confirm_reconnect_cycles`，界面说明此机制不能识别是否换板；后端同样拒绝未确认的多轮。
固件负责连续多次完整查询失联判定，协议错误不得算作离线。
已接入 v1 脚本、旧固件部署能力门控、真实文件范围/共享扇区预检和最终结果解析；
第一组 Python 171 项通过（离线夹具，非实机）。

## 当前进度（2026-10-20）

- GUI 全量 94 文件 986 项通过；TypeScript 与 Vite 生产构建通过。后端最终全量正在运行。
- v1 渲染使用 `path0`–`path7` 独立赋值；每个安全 ASCII BIN 名最长 240 字符，8 文件调用单行低于 512 字节。新增长度回归。
- 无目标能力探测命令为 `print("MKLINK_HPM_ISP_API", hpm.isp_supported())`，只接受独立行 `MKLINK_HPM_ISP_API 1`，已由固件会话实机核对。旧/非 HPMLINK 拒绝。
- 生成脚本首行 `# MKLINK_HPM_ISP_V1 {"job_id":"...","total":1}` 用于上位机读取任务元数据；正文只有 import、赋值、if 和 API 调用。没有 SWD 时钟/IDCODE/额外擦除回读。
- 触发时独占 Serial/Modbus 资源，并暂时阻止共享运行时独立 UART 请求；结构化 result 需匹配 job_id、总轮数、完成数、code=0、rom_status=0。缺少终态为 unknown，前端禁止重触发。
- 通用 debug 蜂鸣/原有硬件复位可选；旧 HPM JTAG 内部复位保留，UI 不提供假控制。ISP 按契约支持三种复位及显式恢复电压。
- 生产 Web + 真实后端 + 模拟固件/本地 SD 目录的浏览器检查通过。本会话没有操作下载器或目标；实体 UART 联调由固件会话完成，证据见后文。

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
- GUI 全量首次 985 通过、1 旧断言失败（trigger 新增可选协议参数）；断言补齐后 **94 文件、986 项全部通过**。后端最终全量正在复跑。

生产资源、断言及本交接已提交 `ff8b51dc` 并推送。上位机草稿 PR：https://github.com/MicroKeen/Mklink-AI-Probe/pull/47 。最终 Python 全量和后续实机证据完成后更新验证状态；原 PR46 与当前安装不受本分支变更。

## 固件会话提供的 HPM5301 首轮实机证据

固件会话将旧脚本路径改为 `/MicroLink.bin` 后，实际返回 `code=0, rom_status=0, completed=1, total=1`。上位机会话只读核对其 `decoded-01/derived-results.json`：95180 字节写入 `0x80000400`，188 数据包，写入至最终响应 9.063778 秒；195 个有效载荷 CRC 全通过，波形重组 BIN 与原文件 SHA256 一致。没有额外擦除/Flash 回读命令。此证据证明首轮单 BIN 协议与路径；多 BIN、复位及后续轮次由固件会话继续实机验证，不能由浏览器夹具替代。

固件后续提交 `9d6b45e` 的实施记录及会话反馈补充：

- 逆序配置两个相邻 BIN，实际排序后合并写入，重组内容与原镜像一致；ROM 软件复位成功。
- 断电 1000ms、配置恢复 3300mV 后任务成功，后续任务能再次握手。固件 ADC 报告与设定值有偏差，未用外部仪表证明精确 3.3V。
- 第二轮等待时取消返回 `code=-8, completed=1, total=2`，随后独立 USB-UART 查询成功，所有权恢复。
- 用户从下载器屏幕选择脚本，首轮后断开 TVCC 两秒再接回，最终 `completed=2,total=2,code=0,rom_status=0`；两轮波形重组均匹配原镜像，用户确认两次蜂鸣。固件正在单独改进 LCD 的简洁状态/任务计数，CDC JSON 契约保持不变。
- RST 未连接，硬件复位电气行为未实测；完全断开 PC USB 的运行未在上位机会话验证。这些限制不以离线测试替代。

## 用户追加 2M 支持

固件会话转交用户“试试设置 2M 波特率能否下载”的要求，并报告实机成功后，上位机新增 2000000 选项，默认仍 115200；后端只允许这两个值，脚本按所选值传入 `isp_config`。页面和说明增加高速中断后的目标重新上电提示；旧 v1 固件拒绝 2M 配置时停止，不自动回退。固件负责每轮以 115200 握手、协商 2M、写入后切回 115200 查询确认，再执行完成动作。

通过生产解析器/生成器新建 `F:/MKLink-Build/reports/hpm-isp-hpm5301-2m.py`：

- job_id：`305c851ac58f4cb282ab6585098b2dc4`
- SHA256：`2eeb7b4edeaf659433d0838997bec2ef85491b9cf054d24181e59034efdc4d1c`
- 路径 `/MicroLink.bin`、地址 `0x80000400`、单轮、无蜂鸣/复位，最长行 109 字节。原 115200 正例/负例未改动。

固件报告 95180 字节、188 包在 2M 下写入至最终响应 1.14759604 秒，50MHz 逻辑分析重组匹配原 BIN，ROM status=0，回 115200 后透传查询正常；重复验证由固件会话继续。

追加需求到达时，旧配置的第二次 Python 全量到约 47% 无失败；为让最终验证覆盖新功能，已结束该轮，不计作全量通过。2M 定点及最终全量重新运行。

2M 源码 `6c298e47` 已推送。237 项相关 Python 回归通过，TypeScript/Vite 生产构建通过。Chrome 加载生产构建 `6c298e47dc0c`，确认默认 115200；选择 2M 后显示恢复提示，实际部署及触发的 `isp_config` 首参为 2000000，路径为 `/first.bin`，匹配部署任务的终态显示完成，控制台无 error。夹具证据为 `reports/hpm-isp-browser/result-2m.json` 和 `result-2m.png`，没有操作物理下载器。含 2M 的全量 GUI/Python 正在运行。

固件提交 `6801f0b` / [固件 PR6](https://github.com/Aladdin-Wang/MicroLink_Plus/pull/6) 提供后续重复验证：2M 共 4 次成功；追加 3 次写入时长 1.14857472 / 1.14963942 / 1.14564028 秒，609 个载荷 CRC 通过、双向帧错/跳过字节均为 0，三次重组与原 BIN 完全一致。35 项固件原生回归通过。最终上位机生成脚本的实体下载器联测由固件会话执行，结果待补。
