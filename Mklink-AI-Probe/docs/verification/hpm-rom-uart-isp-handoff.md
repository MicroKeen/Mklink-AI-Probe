# HPM ROM USART ISP 上位机协作交接

2026-10-20：分支 `codex/hpm-usart-isp` 基于 `microkeen/main`（bdc63533），功能已实现并提交 PR47。原 RTT/SuperWatch PR46 和安装证据保留在原分支，未合并或改写。

范围：现有脱机下载页面新增 HPM USART ISP；独立参数模型、BIN 顺序/地址、自动轮次、完成蜂鸣及复位设置；统一预览/部署验证；由 V4 固件本地执行，不经 PC 转发 UART。仅 HPMLINK 固件开放；本会话不操作硬件。

已对齐固件 `hpm-rom-uart-isp-contract.md` v1：

- 仅 HPMLINK V4 / HPM5301；最终要求为按时钟分频和目标兼容性提供固定档位、默认 2M，见末节。部署和触发前无目标能力查询，不回退 JTAG。
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

- GUI 全量 94 文件 986 项通过；TypeScript 与 Vite 生产构建通过。后端最终全量结果与最终提交 CI 见 [PR47](https://github.com/MicroKeen/Mklink-AI-Probe/pull/47)。
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

生产资源、断言及本交接已提交 `ff8b51dc` 并推送。上位机 PR：https://github.com/MicroKeen/Mklink-AI-Probe/pull/47 。最终全量测试及合并状态以 PR47 为准；原 PR46 与当前安装不受本分支变更。

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

2M 源码 `6c298e47` 已推送，生产资源及报告提交 `3927a27f`。237 项相关 Python 回归通过，TypeScript/Vite 生产构建通过。Chrome 加载生产构建 `6c298e47dc0c`，确认默认 115200；选择 2M 后显示恢复提示，实际部署及触发的 `isp_config` 首参为 2000000，路径为 `/first.bin`，匹配部署任务的终态显示完成，控制台无 error。夹具证据为 `reports/hpm-isp-browser/result-2m.json` 和 `result-2m.png`，没有操作物理下载器。含 2M 的全量 GUI **94 文件、986 项通过**；最终 Python 全量结果与最终提交 CI 在 [PR47](https://github.com/MicroKeen/Mklink-AI-Probe/pull/47) 汇总。

固件提交 `6801f0b` / [固件 PR6](https://github.com/Aladdin-Wang/MicroLink_Plus/pull/6) 提供后续重复验证：2M 共 4 次成功；追加 3 次写入时长 1.14857472 / 1.14963942 / 1.14564028 秒，609 个载荷 CRC 通过、双向帧错/跳过字节均为 0，三次重组与原 BIN 完全一致。35 项固件原生回归通过。最终上位机生成脚本的实体下载器联测由固件会话执行，结果见下文。

### 最终真实生成脚本联合验收

固件会话原样复制本节 2M 脚本到 SD 并执行，本会话只读核对证据：脚本 SHA256 与上文一致，`job_id=305c851ac58f4cb282ab6585098b2dc4` 的最终 JSON 为 `code=0,rom_status=0,completed=1,total=1`。50MHz 波形重组 95180 字节与原 BIN SHA256 一致，写入至最终响应 **1.15065468 秒**。证据为构建根 `reports/hpm-isp-20261020/host-2m-final.log`、`host-2m-final/verified-writes.json` 及同名原始捕获文件。最终联合脚本验收通过，未改变上述 RST 电气验证/电压精度边界。

## 2026-10-21 自定义波特率追加要求

用户要求“速度应该可以通过上位机设置，固件不应该限制”，并要求继续实测 4M/10M。上位机源码 `ecc65d6d` 已推送：

- 取消两档白名单，输入自定义正整数；仅保留脚本 API 的 uint32 范围（1–4294967295）。是否能实现由下载器时钟/驱动和目标 ROM 判断，配置失败不回退。
- 默认改为已验证的 2M；提供 115200/2M/4M/10M 输入快捷值，界面不把快捷值描述为已认证。
- 本机保存并恢复最后有效速率；清空、负值、非整数等编辑中间态不会覆盖已保存的有效值。前后端都拒绝非法值。
- 247 项 Python 定点、42 项离线页面/API GUI 回归通过，含任意非快捷值渲染、非法边界、默认值与重新挂载后的保存恢复。
- 上一版固定两档版本最终完整 Python **4981 通过、2 项可选 hil_core.observe 依赖测试跳过**；GUI **986 通过**。这些只记录上一版，不能替代自定义速率的最终全量。

已用真实生成器生成以下单轮、无蜂鸣/复位的 `/MicroLink.bin` @ `0x80000400` 联调脚本（原 115200/2M 脚本未覆盖）：

| 文件（构建根 reports/） | job_id | SHA256 |
| --- | --- | --- |
| `hpm-isp-hpm5301-4m.py` | `c6fef9aa14d4443d9439a62248389396` | `4f8a610c218ab20667afc0a6c55fcca289ae58c0bab30fac86144d7b4d9488a3` |
| `hpm-isp-hpm5301-10m.py` | `e503f72099f347529c78546d5d97c75a` | `146c0d872d146d68c9933ba0eb8b092999e75a0714375c1978e1c5799a1df579` |

4M/10M 实机结果由固件会话提供，当前未写为已验证。自定义速率最终浏览器/全量/CI/合并结果在 PR47 汇总。

TypeScript/Vite 生产构建通过。Chrome 实际加载 `ecc65d6d73ae`：默认 2M，输入非快捷值 3456789 后刷新并重新进入 ISP 页面，值正确恢复；输入 0 时部署禁用；恢复有效值后生成/部署/触发成功，实际调用 `isp_config` 首参为 3456789、路径 `/first.bin`，最终结果匹配部署任务。控制台无 error，测试页面/夹具正常退出。证据 `reports/hpm-isp-browser/result-custom.json`、`result-custom.png`。这是上位机任意速率传递和保存恢复证据，不声称该任意速率在实体目标上可用。

## 中间版本：六档时钟分频档位（已被下节替代）

用户随后明确要求“根据下载器固件的时钟和分配，固定上位机可以设置的波特率，只设置可以满足分频系数的档位”。该要求替代上一节自由输入方案：

- GUI 改为固定下拉，当前列表为 115200、1M、2M、4M、5M、10M，默认 2M；前后端使用一致的列表。
- 继续保存和恢复所选档位。此前保存的自由输入值若不在列表内，恢复为 2M，不生成未显示的隐藏速率。
- 固件仍接收通用数值参数并检查硬件能力；上位机不修改共享 PLL。下载器 UART 通常使用 PLL1 800MHz /8 得到 100MHz，4M 时本 UART 可用 /10 得到 80MHz，释放后恢复。
- 1M/2M/5M/10M 对应 100MHz、10 倍采样、分频 10/5/2/1；4M 对应 80MHz、10 倍采样、分频 2。115200 保留为 ROM 基础速率。
- 12.5M 虽可在下载器端整除生成，但固件会话实测 HPM5301 切速后查询超时（code -3），没有写入。因此已从界面和后端列表删除；不能把下载器分频可行等同于端到端兼容。
- 固件会话报告最终 4M 已 3/3 成功约 0.78 秒，10M 两版共 6/6 成功约 0.66 秒；最终版两档均 3/3 波形逐字节验证通过。1M、5M 后续也各 3/3 实测通过，并由 200MHz 波形逐字节核对；CRC/停止位/跳过字节错误均为 0，ROM status=0。

自由输入中间版本 GUI 全量 993 通过；其 Python 全量在用户修改需求后约 4% 时结束，不计完整通过。固定档位版本须完成自己的回归、生产浏览器及最终全量。

最终固定档位源码 `6b013fdc`：250 项相关 Python、44 项页面/API GUI 回归及 TypeScript/Vite 生产构建通过。Chrome 加载 `6b013fdc5b8b`，确认 SELECT 恰好六档、旧任意值回退 2M、10M 选择刷新后恢复、实际部署脚本首参 10000000 及最终匹配结果成功；无控制台 error，页面/夹具已退出。证据为 `reports/hpm-isp-browser/result-presets.json` 与 `result-presets.png`。最终完整 GUI/Python 及精确提交 CI 在 [PR47](https://github.com/MicroKeen/Mklink-AI-Probe/pull/47) 汇总。

## 最终五档与固定 100MHz（2026-10-21）

用户最终要求移除 4M，省去备用 80MHz 时钟切换。源码 `43a5cb5d` 的唯一可选列表为 **115200、1M、2M、5M、10M，默认 2M**。前后端同时拒绝 4M、12.5M 和其他任意输入；旧保存值不在五档内时恢复 2M。此前生成的 4M 脚本仅为历史证据，不应继续使用。

156 项 ISP/脱机 Python 定点测试、45 项 GUI 页面/API 测试、TypeScript 与 Vite 生产构建通过。Chrome 真实生产页面确认五档列表、5M 刷新恢复、实际部署脚本首参 5000000、SD 根路径和匹配终态成功，无控制台 error。浏览器使用真实上位机与模拟固件，本会话没有操作物理目标；页面与夹具已退出。证据为本地 `reports/hpm-isp-browser/result-five-presets.json` 和同名 PNG。最终完整 Python/GUI 与精确提交 CI 在 PR47 汇总。

固件会话最终版本已合并 [PR7](https://github.com/Aladdin-Wang/MicroLink_Plus/pull/7)，合并提交 `c350e4a542a5764fa417d4ca8170013baedbee67`。已安装 UF2 SHA256 `cc949152471a6b020810013038b327f9052a851dec48a8012cb15ede469ef351`；上位机会话只读核对了文件哈希及 `reports/hpm-isp-20261021/manifest.json`：

- UART 始终使用原 100MHz 时钟，没有 4M 的 80MHz 切换逻辑；35 项 native 测试通过。
- 最终固件 115200、1M、2M 各一轮通过，写入分别约 9.049、1.530、1.151 秒。
- 5M 三轮分别 0.77730851、0.777405675、0.777286275 秒；10M 同哈希固件三轮 0.659939145–0.66595199 秒。
- 五档均由波形逐字节确认写入内容一致，CRC、停止位、跳过字节错误均为 0；固件会话确认 USB-UART 查询恢复 115200。
- 旧 `test-*` 六档实验不代表最终配置；最终证据以 manifest 对应捕获为准。此前 RST 未接线、电压未外部校准的范围限制保留。

## 本地安装验收追加范围

用户要求将本地安装版改为 0.3.6，并增加可见版本信息；源码 422cc533 已同步 Python/runtime、Tauri/Cargo 版本和中英文 USART ISP 更新说明。用户同时要求覆盖现有安装后检查界面及功能。PR47 保持独立功能集；本地安装须额外组合已安装 2b3d5528 的 RTT/SuperWatch 修复，避免回退已有功能，不因此合并 PR46。实际本地集成提交、覆盖安装、原生与安装后浏览器、5M 单轮实机结果另行记录。此前六档/五档测试在版本信息变更后不作为最终完整检查，0.3.6 重新执行全量。

用户随后明确允许本次跳过管理员权限安装测试。按该授权不弹 UAC、不执行需要提权的本地覆盖安装；仍构建 0.3.6 NSIS，并验证其解包程序、原生界面/生产 Web 与已授权目标功能。解包验证不能写成已安装；本地现有安装保持原版本，安装后检查列为本次授权跳过。

## 0.3.6 最终检查与本地包（2026-10-21）

- PR47 功能版本 GUI 全量 94 文件 / 996 项通过。Python 全量 4993 项通过、2 项可选依赖跳过，1 项隐藏插件清单版本不一致已修正为 0.3.6；随后版本/更新及包元数据 17 项复验通过。未将中断的历史测试计为全量通过。
- 用户既有 RTT 终端解析隔离与 SuperWatch 原生目录选择/采集前记录保存在 PR46。为本地升级不回退功能，单独的 `codex/v036-local-integration` 源码 `0673490b502a9fd656aeba569969e83b693bb5af` 组合这些已安装修复与 PR47；组合版 496 项相关 Python、94 文件 / 1002 项 GUI 及 TypeScript/Vite、NSIS 构建通过。PR46 不因此合并。
- 本地包 `MKLINK_BUILD_ROOT/artifacts/v036-local-isp-0673490b/Mklink-AI-Probe-0.3.6-local-0673490b-Setup.exe`，SHA256 `c2be4e2297b7d3f82f6bae9cfb38524bea6ae5ed2dfe1256728f1ae011b9faae`。标准 NSIS，无签名，不是公开更新发布。组合版生产 Web 保存在 `3eac4a6d`。
- 解包逐项核对 199 Python 文件、40 Web 资源；内置算法 7059 型号 / 2224 blobs、外设 4800 型号。仅 Windows 系统 PATH 下冻结 CLI/SVD/MCP、HTTP/生产资源、无宿主 Python 和正常退出通过。
- 原生程序显示 `v0.3.6 · 0673490b502a`，中英文更新说明包含 USART ISP、RTT 和 SuperWatch。浏览器连接该冻结后台，实际确认五档、默认 2M、5M 刷新恢复，双 BIN 逆序添加后生成脚本按地址排序，完成动作设为无蜂鸣、不复位，执行 1 轮。
- 实际从该打包程序部署至下载器 SD 并触发。两段 BIN 合计 95180 字节，重新合并 SHA256 与授权原 BIN 一致。最终任务 `60b9729462554632a1f8d6b10a165e86` 与已部署脚本一致，`code=0, rom_status=0, completed=1, total=1`。浏览器无控制台 error；本轮未另外测量波形耗时，不将之前约 0.7773 秒的测量冒充本轮计时。
- 浏览器及原生程序正常关闭，候选进程与监听端口释放。现有安装的三个主要载荷哈希前后一致。按用户明确豁免未执行管理员覆盖安装，不能称为安装后验收；用户配置未清除，全局 Skill 未替换。
- 测试隔离 Windows 用户目录最初导致原生 WebView2 启动失败；保留系统已安装 WebView2 的用户目录定位，仅隔离浏览器数据和任务目录后正常启动。不是靠宿主 Python 回退。
- 本地证据：上述 artifact 目录内 `manifest.json`、`extracted-qualification.json`、`native-hardware-qualification.json`、`sd-deployment.json`、`actual-5m-result.log`、`native-version.png`、`actual-5m-result.png`。测试产生的联接 run 按存储规则保留，不强制清理。最终精确提交 CI 与合并状态见 PR47；未签名、未打标签或公开发版。
