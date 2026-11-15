# v0.5.0 自由面板能力与调试场景矩阵

2026-11-15。隔离分支 `codex/agent-ui-workbench` / [PR #80](https://github.com/MicroKeen/Mklink-AI-Probe/pull/80)，合入 `microkeen/main` 的 `7610ab20`，合并提交 `c14c30fe`。基于 v0.5.0 正式源码及后续维护修复；本扩展仍是候选，未替换已安装程序、正式标签、固件、更新索引或受跟踪的 `gui/dist`。上游原生发布是[独立证据](v050-native-release.md)，不代表本扩展已完成原生安装验收。

## 盘点结论与交付边界

[逐项入口矩阵](v050-capability-matrix.md)由真实共享表、FastMCP 工具注册、主 CLI/remote parser 和完整挂载 OpenAPI 生成，包含参数 schema 与 CLI choices 的原始 JSON 留在本地构建输出。计数包含别名和不同协议入口，不能相加当作独立业务功能数。

| 范围 | 数量 | 接入与验证结论 |
| --- | ---: | --- |
| 共享调用 | 155 | 原 154 项加能力目录发现；全部进入面板目录 |
| 面板直接操作 | 234 | 155 共享项、76 个原 GUI JSON 操作、3 个原离线工具；全部真实路由/工具解析及非法参数拒绝通过 |
| MCP 工具 | 59 | 全部盘点并建立业务映射；包装参数需转换，未逐项做硬件调用 |
| CLI 命令节点 | 124 | 含分组、别名、remote 子命令；业务能力映射到面板，宿主/工程/远程工作流由当前 Agent 调用原 CLI |
| HTTP 操作 | 291 | 审计含认证、代理、任务、文件和流；文件上传下载与连续流保留原控件/协议 |

**不能把当前结果称为“所有能力都已独立面板化并完成真机验收”。** 直接能力面板现在覆盖共享业务及新增 GUI 操作；文件传输、宿主安装配置、工程源码集成、远程站点等仍走原页面或 Agent 请求/回复工作流，尚不是全部可直接绑定的子面板动作。自动盘点清单让后续新增入口和剩余范围可见。

新增 `capability` 面板可搜索、选择能力、查看实际参数、执行并显示/保存该次结果；按钮/表单可以绑定公布的动作。鼠标与 Agent 共用 `execute` 和原业务处理器。布局只存选择，恢复不执行。大结果摘要显示，完整 JSON 保留供显式导出；单次参数仍受面板和原能力大小上限约束。

## 调试场景证据

| 场景 | 自动化 | 真实 Web / CLI | 真机 |
| --- | --- | --- | --- |
| 全目录、路由、方法、参数、固定路径 | 234 项逐项解析；234 项非对象拒绝；路径注入、Origin、缺少会话/确认拒绝 | CLI 读出 234 项可用目录，页面实际加载 | 不涉及 |
| 内存、寄存器、变量、HardFault、断点、HPM debug | 原共享/HardFault 套件及目标换代拒绝；设备处理器使用明确 fixture | 未连接内存读取返回失败，无自动连接 | 待目标身份与授权范围 |
| SystemView 离线解码/分析、配置描述/脚本 | 复用原离线函数；非法十六进制、非事件对象、额外字段、RDP 与布尔值伪装整数拒绝 | 页面按钮解码 2 字节，独立 CLI 观察结果；Agent 再解码 10 字节，分析空事件返回 no_data；HPM5301 配置描述只读成功 | 未采集 RTOS 真机数据 |
| 原始波形记录、文件关闭、Excel 转换 | 真实记录器进程接收 1,200 组合成样本；原 API 启停/转换/回放链路通过 | 独立原记录器保存 12,000 组、24,000 个合成数值；Excel 全部时间/数值与 JSONL 对照、1 个 discontinuity 保留；原文件 SHA-256 不变 | 未验持续实物采集 |
| 大文件路径回放与显示隔离 | 解析器、路径校验、大小、编码、链接、目标换代相关回归通过 | 12,000 行 JSONL 通过后端路径载入；播放/暂停、4 倍速、3.25s 定位、双面板隔离、返回实时通过；原文件不改写 | 回放不向设备发送数据 |
| 保存图像与结果 | 新面板完整结果导出不重跑操作的组件断言通过 | 实际 PNG 按钮生成 45,586 字节图像；Excel 与原始 JSONL 已落盘 | 不涉及 |
| 软件故障注入 | 丢响应、500、坏 JSON → unknown 且禁止自动重放；过期命令、旧 revision、旧目标、页面重连、重复 ID；记录队列溢出/磁盘错误/工作进程退出及 HardFault fixture 回归通过 | 非法离线字节、越界定位、截断 JSONL、缺失日志均明确失败；另一波形保持；原命令 ID 返回 duplicate 且 operation ID 不变 | 未写故障变量、未触发复位/HardFault |
| 未绑定探针时开始记录 | 原守卫保留 | 返回 unselected；不创建 JSONL、不影响回放。没有为演示放宽身份检查 | 不涉及 |
| 烧录、擦除、安全、OTP、供电、固件 | 原任务守卫/任务回执与参数检查；稳定 request_id 透传，任务状态不当作完成 | 未执行 | 待专门确认；永久 OTP/锁定未验 |
| RTT、串口、Modbus、VOFA | 原记录器/共享/串口录制回归；RTT 停止记录通道 query/body 兼容测试 | 界面未发送数据，也未绑定串口 | 未验 TX/RX、RS485、外部故障注入 |
| 后台重启、新会话发现、恢复 | 原 Broker/存储套件及能力面板只恢复选择通过 | 按项目重新发现后台与窗口，page ID 更新；恢复后面板 idle、无 operation ID、无自动回放；再显式加载原文件成功 | 不涉及 |
| 当前 Agent 连续会话 | 原 intent/reply、幂等与目标校验套件通过 | 页面提交带对象上下文的请求；当前会话通过独立 CLI 读取真实上下文，查询目录并核对文件后回写；页面显示 replied | 没有实际语音输入；依赖宿主提供语音 |

浏览器最终错误日志为空。HTTP 结果、命令与回执、PNG、截图、合成记录和逐行核对结果仅保存在主检出忽略的 `.build/agent-ui-matrix`；不提交凭据、会话 URL 或设备标识。只保留供用户继续测试的示例后台；中途用于重载的后台通过自己的控制接口正常结束，测试中的记录器和临时服务已关闭。

## 发现并修正的问题

1. 新能力路由最初排在 SPA 兜底之后，真实浏览器收到 HTML。调整至兜底之前，回归改为经真实 HTTP 获取目录，不能只检查 OpenAPI。
2. RTT 停止记录的 `channel` 不能放入普通 JSON。共享适配层正确分开 query 和已有 `channel_body`，DELETE 的 query 参数也原样保留。
3. 新面板中的异步任务必须显示原任务 ID 与原 state；提交不等于成功，unknown 不自动重放。输入草稿不进入公共状态或布局。
4. 目录消除已固化路径参数（如 RTT 的 kind、OTP 的 action），脱机部署/任务提交公布实际适配参数；配置生成严格验证类型，避免 bool 被转换为整数而绕过原验证。

## 运行结果与复现

Windows，既有源码虚拟环境，Node/npm 使用已安装依赖；全部运行通过 `scripts/build_workspace.ps1`，产物在非系统盘忽略目录。

- 最终 Python 15 个相关套件 **919 通过**，包含新增能力测试 **475 项**。范围为 frontend_capabilities、frontend_replay、runtime_frontend、frontend_storage、shared_runtime、runtime_jobs、runtime_uart、runtime_cli、runtime_mcp、superwatch_recording、traffic_recording、serial_recording、hardfault、skill_context_boundaries、recording_text。
- GUI 全量 **127 文件 / 1363 项通过**；`vue-tsc -b` 与 Vite 生产构建通过。保留既有 Dashboard 大分块提示。
- 持续集成清单已加入能力路由回归、能力矩阵自检及 8 个自由面板/会话测试文件；工作流 YAML 与 207 个测试路径检查通过。CI 结果以对应 PR 提交的检查为准。
- 首轮导出失败来自旧验证虚拟环境缺少正式版声明的 XlsxWriter；补齐已声明依赖后重跑。另将一处录制测试的默认编码改为 UTF-8，消除中文 Windows 默认 GBK 的误失败。未增加产品依赖。
- 现存依赖弃用与 OpenAPI 重复 operation ID 警告保留，没有隐藏或据此放宽断言。

生成清单（输出目录须在构建根，不能提交原始运行文件）：

```powershell
./scripts/build_workspace.ps1 -Action run -BuildRoot <构建根> -Executable <项目Python> -ArgumentList @('_maintainer/testing/frontend_capability_matrix.py','--output','<构建根>/capability-inventory')
```

公共使用入口见[接入说明](../../references/agent-ui.md)。本轮未跑全仓 Python、Rust、NSIS 安装、原生桌面或物理探针矩阵；不把上游的安装/真机数据计入本扩展结果。已发现一只探针但目标板、可注入地址/变量和允许复位操作尚未确认，因此不做推测性真机注入。
