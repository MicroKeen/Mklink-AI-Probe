# Web GUI 重编译提醒和 SuperWatch 实时数值

0.5.2 客户验证构建的源码为 `f643032b`。回归在 Windows 11 上运行，构建、项目、日志和测试文件均位于 `F:/MKLink-Build`。

## ELF 与 AXF

在 Edge 中从 RTT 打开真实 Arm ELF，后台工程内放置一份同名、相同 SHA-256 的副本。旧版在浏览器刷新、链接器替换原 ELF 后继续显示旧符号。修复版持久保存用户选择的文件句柄和已解析版本的指纹，按 Web 入口和文件路径恢复跟踪。仅收到普通上传快照的浏览器可以在“配置 → 文件来源”使用后台可访问的原路径。

| 验收操作 | 检查结果 |
| --- | --- |
| 页面刷新，再用 Arm GCC 重新链接并原子替换 ELF | RTT 弹窗出现，确认前仍能查到第一次编译的变量 |
| RTT 选择“稍后”，再点重载按钮 | 新符号取代旧符号，RTT 地址从 `0x20000040` 更新为 `0x20000080` |
| 再次重编译，在 SuperWatch 确认 | 第三版变量进入共享符号表，第二版变量移除 |
| 在 SuperWatch 通过浏览器打开另一份 AXF，重编译后点“稍后”，再点重载 | 工具栏能重新解析选中的文件，查询返回新变量 |
| 从配置页输入后台 AXF 原路径，解析后原地替换 | RTT 再次提示，确认后能查到新的 AXF 变量 |

浏览器测试通过 Chromium 的文件拖放接口取得真实磁盘文件句柄，自动化替代系统文件选择对话框的选取动作。文件替换、IndexedDB、页面刷新、按钮、解析后端和符号查询均执行产品代码。

## 实时数值

共享后台保留最新一行原始精度。WebSocket 客户端可加 `latest64=1`；当最新行转为 Float32 会舍入时，服务端在原批次尾部附加每通道一个小端 Float64，同时置标志 `0x08`。旧订阅者继续收到原格式，绘图历史仍用 Float32。该改动覆盖实时变量读数，历史录制和回放保留既有精度。

回归使用 `0x24A75B19`、`UINT32_MAX` 和带符号负值检查共享最新值与传输兼容性。对于现场样本，实时显示期望 `614947609`，Float32 曲线点为 `614947584`。实板问题来源为固件会话的 S32K344 测试，原始日志见 `F:/MKLink-Build/runs/s32k344-field-flash-20261127/full-acceptance/debug-hil.json`。

## 构建与回归

- Windows x64 客户安装包为 `F:/MKLink-Build/artifacts/MKLink-0.5.2-f643032b/MKLink-AI-Probe-v0.5.2-f643032b-Windows-x64-Setup.exe`，SHA-256 为 `a8ff1de04486bd6f188e71b8ca053fad402d9124d564fcf99fbfa190ed791d27`。
- 相关 Python 测试 330 项、GUI 测试 461 项通过，生产 Web 构建通过。打包阶段重跑符号后端及实时数值组件回归。
- 安装包解包比对覆盖 3760 项。桌面 EXE 的三个差异字节与 Tauri 写入 NSIS 类型标记相符，其他文件均匹配构建清单。项目内同步 92 个成品 Web 文件。
- 从 NSIS 单独解包后，用包内 sidecar 在隔离目录启动共享后台，与包内 Web GUI 在 Edge 上重复验证两种格式、两个面板及重新打开页面。记录见 `edge-package.log`。源码后台模拟采样的真实 Edge 变量栏和 REST 亦显示相同数值，见 `edge-source.log`。
- 固件会话用同一安装包和 COM62 上的 S32K344 实板验证了 `74565` 与 `614947609`。两个变量的 MEM 读回、共享最新值、Edge 实际显示三者一致，原始数据和截图分别为 `F:/MKLink-Build/runs/s32k344-field-flash-20261127/full-acceptance-a8ff1de0/final-precision.log`、同目录 `superwatch-number-f643032b.png`。
- 原始记录和测试程序在 `F:/MKLink-Build/reports/web-symbol-precision-20261127/`。

## S32K344 实板验收

固件会话在 ROX R11、HPMLink V4.7.5、10 MHz SWD 上使用同一客户包完成验收。

- 在线烧录作业将两份不同的 1 MiB 镜像依次写入 128 个扇区。BIN 用时 14.88 秒，HEX 用时 14.91 秒。每次重新连接后逐字节读回全部镜像，主启动区及相邻保护扇区均通过比对。目标计算的镜像 B 数据段 CRC32 为 0x349A4372，与主机一致。
- RTT 和 25 ms SuperWatch 同时采集。按游标读取的 568 条 RTT 记录连续，文本及二进制下行读回通过。点击 MCU 复位后两路均收到新数据。GUI 和两个 MCP 客户端共用同一探针，全局断开和 GUI 重新连接通过。
- 证据保存在 F:/MKLink-Build/runs/s32k344-field-flash-20261127/full-acceptance-a8ff1de0/S32K344-最终验收.md。实测采用台架测试镜像，擦写范围由镜像覆盖的扇区确定。
