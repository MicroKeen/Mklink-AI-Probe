# 灵活面板：页面生命周期、请求归属与异步存储回归

本轮针对评审核对的 `732562e4aa0d97c71cfdc30ae5816dcd673931ce`。
仅本地修改、构建与验收，不更新 PR、不推送、不请求审查、不发布；正式版本号及发布资源不变。
此前 RAM、记录回放与固件恢复证据继续保留，见[功能覆盖矩阵](v050-flexible-panel-gui-coverage.md)。

## 三项修复

| 问题 | 修复行为 | 回归 |
|---|---|---|
| 离线页面永久占用 32 个名额 | 新报告注册前回收离线/旧目标报告；先冻结在途命令为 unknown。命令结果独立保留，旧页回来不恢复 queued；含历史命令的页面 ID 不得用于另一目标 | 第 33 页、100 次刷新、32 个在线窗口、连续目标切换、旧页重连/迟到结果、500 条结果与重复 ID |
| 无关请求失败污染当前操作 | 不再替换 window.fetch；语义操作显式携带请求上下文。异步调用链传递同一上下文；同步 GUI 控件分发只给本次调用栈的请求归属。队列保存、轮询和其他操作不会继承它 | 后台 PUT 500/网络错误/查询失败与成功写入并发；自己的响应丢失、500、损坏 JSON 仍为 unknown；绑定嵌套、设备代次、真实组件请求链 |
| 同步文件 I/O 阻塞事件循环 | 文件读取、存储锁、flush/fsync/replace 在线程池执行；目标/页面检查仍在事件循环。请求固定项目目录，写入前及返回前重新核对目标；intent 提交前再次检查页版本；存储锁下继续做版本 CAS | 六种读写接口注入 400 ms 延迟，20 ms 心跳及另一窗口交换在 250 ms 内完成；慢 fsync 期间目标/页版本改变不落盘；并发布局/回复仅一个版本胜出 |

回收页面不回收命令证据。命令记录达到 500 条仍明确拒绝新命令，既有 ID 的原结果仍可查询；
不会以删除证据来伪装无限运行。unknown 不能自动重试，只有真实的迟到终态能解除该页的不确定状态。
`view.control.*` 继续报告“已分发”，用户/Agent 需查看原组件状态、确认框或任务终态；不能把它当作硬件完成回执。

## 复现与自动验证

旧代码负向对照通过 `git show` 读取上述精确提交：页面回收和慢存储回归失败；
成功写入期间独立 workspace PUT 500 将命令误标 unknown，前端回归失败。
这些是离线注入结果，不是真机证据。

使用仓库 `scripts/build_workspace.ps1 -Action run` 执行：

```text
python -m pytest -q _maintainer/testing/tests/test_runtime_frontend.py _maintainer/testing/tests/test_frontend_storage.py _maintainer/testing/tests/test_frontend_concurrency.py
npm run test -- src/lib/frontendControl.test.ts src/composables/useSymbolCatalog.test.ts src/components/dash/SymbolVariablePanel.test.ts
npm run test -- src/lib/superwatchReplayControls.test.ts src/components/dash/WaveformViewer.test.ts src/lib/trackedSymbolSource.test.ts src/lib/frontendControl.test.ts
python -m pytest -q
npm run test
npm run build
```

当前定向后端 140 项通过；回放/波形/跟踪源/请求上下文 166 项通过；TypeScript 与生产构建通过。
完整 Python、GUI、最终 SHA、交付与实界面结果在最终验收后补记，不能用定向通过数代替全量结果。

## 交付与验收边界

生产构建写入受跟踪 `gui/dist`，默认 GUI、Skill ZIP 与冻结 sidecar 使用同一资源树；
验收不依赖 `MKLINK_GUI_DIST`。本地 NSIS 使用 `--local-bundle`，不签名更新或上传。
本机立芯版是独立发行版，本轮本地候选不能覆盖其运行目录或修改它的 MCP 配置。

原生窗口、覆盖安装、实际 Skill/MCP 包、多消费者采集和性能需要各自的现场证据。
Computer Use 主连接目前不可用；备用原生窗口入口可枚举，Playwright CLI 可用，验收尚在进行。
所有原始日志、运行会话、截图和设备身份存放在仓库外，不提交私有令牌或设备记录。
