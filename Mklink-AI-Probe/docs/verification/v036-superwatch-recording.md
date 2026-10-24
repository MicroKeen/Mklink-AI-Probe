# 0.3.6 SuperWatch 日志入口改进

2026-10-19，基线 `cdb7307e1e03`，继续分支 `codex/0.3.6-fixes` / PR46。维护者要求改用用户电脑的系统文件夹选择器，并取消“必须先采集才能记录”的限制。

## 行为

- 桌面本机窗口的“日志 → 开始记录”直接调用 Tauri 原生文件夹选择器，默认进入上次成功保存的目录。确认目录即开启记录；取消不调用记录接口、不创建文件；选择器错误显示并允许重试。
- 浏览器、远程窗口继续浏览后台电脑目录。浏览器文件句柄和远程窗口本机路径不能直接作为后台写入路径。
- 后台允许在采集前启用记录，零样本时界面显示“等待数据”。后续采集沿用同一个记录器，第一条样本和停止时的尾批次正常写入。没有数据时也可以停止并再次开启。
- 采集旧线程正在退出时拒绝创建新记录，避免新记录被旧线程的退出流程关闭。重复开启、目录有效性、自动分段、磁盘/队列失败与停止排空行为保留。
- 生产 Web 资源、公开使用说明和 shared-runtime/shared-gui CI 的记录回归清单同步更新。

## 本地验证

Windows、PowerShell 7、UTF-8、Python 3.14；构建与测试均经 `scripts/build_workspace.ps1`，使用 F 盘专用构建根。

| 检查 | 结果 |
| --- | --- |
| SuperWatch recording、RTT/SuperWatch streaming、live write | 222 passed |
| SuperWatchRecording、filePicker、SuperWatchTab、WaveformViewer | 4 文件 138 passed |
| Skill 边界与记忆预算 | 59 passed |
| Tauri builder 默认开发构建 | TypeScript、Vite、Rust release executable 全部通过；未生成或安装 NSIS |

新增采集生命周期测试调用真实 `SuperWatchStreamManager.start/stop` 和记录器，以受控 DumpMemory session 输入首个浮点样本，验证预先创建的同一文件得到 `{"a":42.0,"_t":0.0}`。HTTP 从未采集且无 metadata 的状态开始记录；取消原生选择、选择失败重试、中文目录、browser/remote 回退分别由前端回归覆盖。

新增生命周期测试首轮仅因遗漏测试局部 `json` 导入而失败（221 passed / 1 failed），补齐后原组三文件 222 passed；没有为通过测试修改产品实现。含测试联接的临时运行目录由入口保留，不绕过清理保护。

## 原生窗口检查

使用本次构建的独立 exe 和源码 Python 后台，独立 WebView profile；现有安装版保持原样，未连接硬件。
Windows 实际弹出标题为“选择 SuperWatch 日志保存文件夹”的系统目录窗口，包含桌面、此电脑、系统导航及新建文件夹。取消后真实 recording/status 为 `idle/active=false`。
第二次打开后，目录输入验证受到桌面的 QMCapture64 截图覆盖层阻挡；自动化报告点击点属于 `CCaptureMainWnd`。尝试重新激活测试窗口后仍受遮挡，未操作或结束截图工具。原生“选择目录 → 等待数据 → 停止”完整点击链未完成，不能把自动化测试视为该原生链路已验收。检查测试记录器仍 idle 后仅结束本轮独立测试进程，既有安装窗口未操作。

启动脚本第一次沿用构建入口的临时 TEMP，父命令退出清理后后台日志目录消失；测试脚本改用构建根持久目录后正常启动。这是本地测试启动环境问题，不改产品代码。

## 边界

此记录是源码功能验证，不是发布或安装验收。采集数据来自离线 session 夹具，不代表实体板连续采样验收。未覆盖 Mac/Linux 原生选择器；未合并、发布、更新安装版或全局 Skill，未刷固件。
