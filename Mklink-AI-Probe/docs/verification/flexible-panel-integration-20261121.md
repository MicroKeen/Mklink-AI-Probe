# 灵活面板集成复审与真机复测

2026-11-21，Windows，官方标准 GUI。远端基线为 `a38557b93ed0ec0efdb007ea72ebb06b4cff408b`。本地分支 `codex/workbench-integration-1121` 包含 #80 已有工作及当前 main 的下载、安装修复。应用代码及默认生产资源为 `cdd86ea4fa5b85f8767fb4efdd6dc1d88d5c9294`，公共 Skill 使用文档修订为 `9402d34112fc6d260a5dc99ab540da2ea7aecf30`。

远端 #80 草稿头仍为 `732562e4aa0d97c71cfdc30ae5816dcd673931ce`。另一个开发分支 `codex/v0.5.1-fixes` 的 `eb5e3d0c` 包含独立 CLI RTT 读取及安装变更，尚未合入 main。若该分支先合入，应在合并后的实现上复跑同通道双读者测试。

## 审查意见与回归入口

| 审查项 | 修复提交 | 可重复的用例和预期 |
| --- | --- | --- |
| #80 离线页面占满 32 个名额 | `d94f2ec1` | `test_runtime_frontend.py` 覆盖连续刷新、32 个同时在线窗口、设备代次切换和旧页重现。查询旧命令保留原回执，达到 500 条证据上限明确拒绝新命令。 |
| #80 同窗口无关请求的失败归入写操作 | `d94f2ec1`、`cdd86ea4` | `frontendControl.test.ts` 覆盖成功写入与独立保存/查询失败并发、当前写响应丢失、HTTP 500、损坏响应。额外覆盖保存当前及命名布局时丢失应答，结果为 unknown；读请求网络失败及保存的 409 冲突保留明确错误。 |
| #80 存储阻塞事件循环 | `d94f2ec1`、`cdd86ea4` | `test_frontend_concurrency.py` 给九种存储操作注入 400 ms 延迟，20 ms 后发心跳与另一窗口交换，要求在 250 ms 内完成。覆盖写入前后的目标和 revision 变化。 |
| 多进程同时覆盖布局 | `cdd86ea4` | `test_layout_library.py` 中四个独立进程持同一 revision 并发保存，当前布局、命名布局各自仅允许一个提交，其余三个返回冲突。 |
| 搜索无结果仍可加载或覆盖上一项 | `cdd86ea4` | `WorkbenchLayoutDialog.test.ts` 在保存、加载两种模式下选中条目再搜索空集，原选中项和版本均清除。覆盖作用域切换、只读预置、取消、查询与保存失败。 |
| 工程根恰为用户主目录 | `cdd86ea4` | `test_layout_library.py` 在临时主目录创建工程和全局同名布局，二者独立；其他工程能读到全局模板。原主目录布局文件继续作为全局库读取。 |
| 公共接入文档混入本地品牌及维护流程 | `9402d341` | `test_skill_context_boundaries.py` 对公共文档逐篇检查。使用文档只描述实际交付的行为。 |
| 生产资源检查将图表库中的环境名识别为脚本 | `2677496e` | ECharts 依赖用 `indexOf('Node.js')` 检查环境，浏览器不会请求此文件。资源检查区分预载路径、导入和 worker URL 与普通文本。实际资源图与包含缺失模块名的引用提取用例均通过。 |

## 实机与浏览器复测脚本单

前置条件为 MicroLink V4、STM32F411CEUx、匹配目标的 AXF、已输出 CH0 RTT 的运行中固件以及独立测试工程。通过探针身份、MCU 身份、AXF 可加载 Flash 段的首/中/尾各 16 字节确认目标。默认 GUI 从候选 `gui/dist` 提供，使用真实 Chromium，不设置外置资源目录。测试用的连接、原始内存、符号名、工程路径及一次性登录链接仅保留于本机。

| 场景 | 操作与断言 | V4.7.3 实测 |
| --- | --- | --- |
| 人和 Agent 共用布局 | 进入最右侧灵活面板，读取所选窗口页面和 revision。选择真实变量，增加两个 CH0 RTT 实例，保存命名工程布局，搜索并加载。读取完成回执与面板数量。 | 搜索命中，回读 4 个面板。 |
| 同通道实例独立 | 同时采集 RTT CH0 及 20 ms SuperWatch；暂停 A、检查 B 仍在运行，再清空 A、移除 A，独立读取 CH0 游标。 | 两个实例暂停状态相互独立；移除 A 后流仍运行。独立读者观测到的累计丢字节为 0。 |
| 当前记录可播放 | 分别开始和结束真实记录；在面板加载 SuperWatch 文件并定位到 0.1 秒，返回实时。通过 RTT 文件选择器导入自己的记录，10 倍速播放到结尾并关闭回放。 | 波形记录 13.460 秒，定位成功。RTT 记录 13 帧、1196 字节载荷，播放到第 13 帧。 |
| 双窗口共同采集 | 两个窗口打开同工程，各自观察每个流 worker 的序号及其传输/后台丢弃计数，观察 8 秒。关闭第二个窗口后再观察第一个窗口 4 秒。 | 两窗口 RTT 分别从 67、68 前进至 76，波形序号均前进；关闭后 RTT 至 80，三个波形读者分别至 3015/3017/3020。观测窗口各项丢弃最大值为 0。 |
| 响应与开销 | 从本地打点健康端点并采样后端进程 CPU（100% 为一个核心）。同时记录操作周期、样本数及窗口数。 | 单窗口操作段 18 次，最大 57.03 ms，CPU 平均 42.59%。含打开和关闭双窗口的整个会话 105 次，最近秩 P95 71.40 ms，最大 126.22 ms，平均 45.99%。 |
| 运行时和 Skill 交付 | 按发布白名单提取受跟踪公共文件，在独立目录用既有官方 Python 环境运行 `.mcp.json` 配置的 stdio 命令。移除 PYTHONPATH 和外置 GUI 资源变量，核对实际导入目录。MCP 发现窗口，读取目录并实际执行全局布局搜索。 | 433 个公共文件、59 个 MCP 工具。ping、显式附着、快照、命令回执、3 个只读模板和 detach 均通过。 |

三轴/心率等具体固件变量通过通用组件绑定。数值、仪表、条形表、统计图、菜单和配置弹窗的自动化使用实际组件。PR 历史上的[能力与证据矩阵](v050-flexible-panel-gui-coverage.md)保留了 RAM 写入后恢复、裸机 SystemView、虚拟 UART/Modbus 等结果。上述 V4 测试没有刷写、复位或更改供电。真机采集先于本轮最后的布局写请求归属修改；最终前端重新构建并在默认 GUI 中完成了 MCP 搜索。

## 可复跑的自动验证

从源码目录通过 `scripts/build_workspace.ps1 -Action run` 执行下列命令，GUI 命令的工作目录为 `gui`。

| 检查 | 命令或入口 | 结果 |
| --- | --- | --- |
| 全量 GUI | `npm ci`、`npm test` | 138 个文件、1,438 项通过。 |
| 默认资源及类型检查 | `npm run build`，包含 `vue-tsc -b` | 通过，受跟踪的 `gui/dist` 随应用提交。 |
| 后端、回放与公共接入 | `python -m pytest -q` 加下列七个文件 | 758 项通过。 |
| 真实浏览器布局弹窗 | 在独立工程另存布局，选中它，再输入无匹配搜索词；切到全局查看预置，按 Esc 关闭。 | 1280×800、390×800 两种视口均禁止加载旧条目，对话框未水平裁切，焦点返回原按钮，页面运行错误 0。 |
| 重新盘点接口 | `python _maintainer/testing/frontend_capability_matrix.py --output <临时目录>` | [生成矩阵](v050-capability-matrix.md)列出 234 个面板操作、59 个 MCP 工具、124 个 CLI 节点、294 项 HTTP 操作。 |

定向测试文件均位于 `_maintainer/testing/tests`：

```text
test_frontend_capabilities.py   test_frontend_replay.py
test_runtime_frontend.py        test_frontend_concurrency.py
test_frontend_storage.py        test_layout_library.py
test_skill_context_boundaries.py
```

第一次全量运行使用现有 Python 3.11.3 环境，`python -m pytest -q` 得到 7,840 通过、7 跳过、39 失败、4 个准备阶段错误。逐组复核如下。

- 21 个脱机下载用例缺正式 FLM 资源。用官方 Skill 的算法库设置 `MKLINK_BUILTIN_FLM_ROOT` 后，`python -m pytest -q _maintainer/testing/tests/test_offline_download.py` 全部 115 项通过。
- 4 个 Site Agent 准备阶段错误缺本地 STCP 桥接库。第二轮向忽略目录提供原有原生桥接库和算法资源。
- 12 个 Windows 链接文件夹用例报 WinError 1314。当前运行账户缺创建符号链接权限。
- 在干净的远端 main 单独运行 5 个失败用例，两个子进程退出码用例、MCP schema 快照、包管理器进程和端口锁进程用例也均失败。
- 余下 1 项为上述资源图误报，修复后的 `test_remote_api.py -k "asset_graph or asset_references"` 两项通过。未修改运行时以迎合测试。

第二轮使用与 CI 一致的 Python 3.12、pytest 8.4.2，在独立虚拟环境安装项目 `mcp,s3,test` 依赖并启用 UTF-8。全量 `python -m pytest -q --tb=line -r fE` 的原始结果为 **7,859 通过、7 跳过、20 失败、4 个准备阶段错误**，耗时 26 分 39 秒。该轮开始时应用代码及使用文档位于 `9402d341`。资源图用例在收集后修订，未计入该轮的通过数。应用源码与生产资源从 `cdd86ea4` 起相同。

| 本轮失败项 | 同环境对照与最终状态 |
| --- | --- |
| 12 项 Windows 符号链接 | 账户缺少创建目录符号链接权限，测试明确报告此前提。需要在有此权限的 Windows 环境执行。 |
| 4 项 Site Agent 安装载荷准备 | 已识别原生桥接库。测试复制的干净源码没有 FLM manifest，冻结 Site Agent 及其载荷验收仍未通过。未制作本候选正式安装包。 |
| 4 项子进程/锁 | 在远端 main `a38557b9` 同环境定向对照均失败，两个子进程退出码、包管理器子进程和端口锁共四项。3.11 的额外 MCP schema 快照在 3.12 对照通过。 |
| 1 项 HPM OTP 测试 | 测试枚举 FastAPI 路由时访问不存在的 `_IncludedRouter.path`，在候选和干净 main 上均复现。 |
| 1 项静态资源图 | 3.12 全量已载入修改前测试。针对 `2677496e8d68b5e866fee2f2515b449339072142` 复跑实际生产资源图与引用提取用例，两项在 Python 3.11、3.12 各自均通过。 |
| 2 项计时 | 模拟远端烧录等待、下载后 RTT 查找超时，在候选单独复跑均通过。main 单独复跑时 RTT 超时用例失败。保留原始全量失败记录。 |

同一 Python 3.12 环境运行本地 `feedback-contract` 对应的 `test_issue_queue.py` 和 `test_skill_context_boundaries.py` 共 84 项通过。合并门禁尚未全绿，不能用定向通过数抵消全量失败。

## 覆盖边界与复测顺序

后续已完成[同板 V4.7.4 实测对照](flexible-panel-v474-20261121.md)，包含首次非零的主机分发丢弃及从零计数开始的两轮复跑。

- 这次两个窗口各观测到五个流 worker。原仪表盘隐藏的 RTT/SuperWatch 标签仍挂载，性能数据包含这些消费者。短时零丢弃不能推导出长时或饱和采集的保证。
- 新固件使用同一目标、同一 AXF、相同的采样周期重复上表，并先读取实际固件版本。重新枚举后按稳定身份选择探针。本轮设备报告家族 microlink、型号 V4。[官方固件清单](https://github.com/MicroKeen/Mklink-AI-Probe/blob/83c650a2ddd67b3aa6b5e18c95a9a9bbbd3d9873/latest.json)中 `MicroLink_V4.7.4.uf2` 为 1,649,664 字节，SHA-256 为 `82d86c9f5de1611ee101f8ccd349deb8ee73b065340cb3a4958ac4c69f886917`。本地文件与清单一致。
- 本轮没有新做原生 WebView、安装器覆盖、物理 RS485、RTOS 调度、受控 HardFault、刷写/OTP 或其他平台验收。源码白名单目录验证覆盖公共 Skill 运行入口，安装器行为需要独立验收。
