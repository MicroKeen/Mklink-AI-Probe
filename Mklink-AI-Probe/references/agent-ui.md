# 自由面板与连续对话接入

新会话从本页开始，无需上次聊天的端口、令牌或私有会话文件。此入口适用于基于
v0.5.0 的自由面板扩展；原版 v0.5.0 仅有通用 GUI 控制，不包含本扩展。
必须核对运行时公布了 `gui_frontend_pages/read/call/receipt`，不能只看版本号。

可复制的激活语句：

> 使用 MKLink skill 的 Agent UI 接入说明，找到我指定项目的运行后台与窗口，打开自由面板。后续在当前会话中连续接收文字或宿主语音请求，执行已授权能力，并把真实结果更新到同一界面。

## 发现、选择、接入

1. `ping` 核对版本及能力；只读 `runtime_status` 或 CLI `python -m mklink runtime status`
   列出后台，按实际项目与用户目标选择 `runtime_id`，多实例不得默认取第一项。
2. 用户要求显示界面时，`gui_open(runtime_id=...)` 复用该后台；没有实例时按
   [安装说明](install.md)使用实际运行目录的解释器，以
   `python -m mklink gui --project-root <项目绝对目录> --no-browser` 启动。
   打开启动返回的本地入口；私有登录链接不放入公开文档或提交。
   `gui_open` 不连接设备，当前 MCP 持有 GUI 附着直到 `detach`。
3. `gui_control(action="windows")` 获取窗口，明确选择 `window_id`，确认
   `gui_protocol=2`。用 `gui_control(action="navigate", window_id=..., page="dashboard", tab="workbench")`
   打开组合工作台，再 `snapshot`，读取 `panels.workbench` 中的
   `connected/protocol/session_id/page_id/target`，把选定窗口与语义页面对应起来。
4. `gui_call("gui_frontend_pages")` 检查该页面在线且目标一致，再
   `gui_call("gui_frontend_read", {"page_id":"..."})` 读取实际目录和当前 revision。
   `connected=false`、窗口关闭、页面刷新、后台重启、切换项目或探针后重新发现；不复用旧 ID。
   能力缺失说明正在使用旧后台或原版 GUI，应报告版本/能力缺口，不能猜测调用。

CLI 复用同一发现与认证机制，使用所选运行时的解释器；这些调用只附着已有后台，
不会为了操作界面而连接探针，也不会自动选择另一个后台：

```powershell
python -m mklink runtime status
python -m mklink runtime call gui_windows --runtime-id <后台ID>
python -m mklink runtime call gui_action --runtime-id <后台ID> --arguments '{"window_id":"窗口ID","action":"navigate","page":"dashboard","tab":"workbench"}'
python -m mklink runtime call gui_snapshot --runtime-id <后台ID> --arguments '{"window_id":"窗口ID"}'
python -m mklink runtime call gui_frontend_pages --runtime-id <后台ID>
python -m mklink runtime call gui_frontend_read --runtime-id <后台ID> --arguments '{"page_id":"页面ID"}'
```

## 每轮操作

从 read 中的 `catalog.panels` 和 `actions` 找实际动作 ID、参数 schema 与 effect。
不要从名称推算哈希 ID。用 `gui_frontend_call` 提交包含 `protocol`、`session_id`、
`page_id`、唯一 `command_id`、`expect_revision`、未来 30 秒内的 Unix 毫秒 `deadline`、
`action`、`args` 的命令；查询 `gui_frontend_receipt({command_id})`，再回读页面状态。
`queued/accepted` 不是完成；`unknown` 只查原命令，不能换 ID 重做。
通用 `gui_control` 仍可操作原控件；指定子面板优先使用语义目录中的稳定 panel ID。

创建面板、组件、设置参数与执行动作分开。调用真实 CLI/skill 后，记录原任务及结果，
使用目录中已提供的展示能力回写；缺少展示动作时按 Agent UI 开发技能补齐实现，
不能伪造设备结果。设备读写、采集、发送、文件及供电仍走原业务权限与本次用户授权。
GUI 附着不表示自动连接或授权硬件操作，前端回执也不代替后台任务终态。

宿主直接对话无需先在页面发问；页面 Agent 请求用 `gui_frontend_intents/intent`
读取可信上下文，再按原 `request_id/revision` 用 `gui_frontend_reply` 回复。
语音识别与工具调用由宿主提供，本产品不负责唤醒已结束的 Agent。

显示配置按面板隔离，保存/恢复布局不启动采集或执行绑定动作。结束时 `detach`
只释放本 Agent 附着；关闭视图不会停止其他窗口采集。后台停止按
[控制权与恢复](runtime-recovery.md)显式执行，不根据旧 PID 或端口猜测服务身份。
