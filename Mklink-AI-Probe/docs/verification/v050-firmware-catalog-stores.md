# V0.5.0 桌面固件检查与淘宝店铺菜单

2026-11-23，修复分支 `codex/v0.5.1-fixes`，候选安装包源码 `e8334000`。上位机版本为 V0.5.0。

## 截图中的版本从哪里来

用户的 Mac 显示 MicroLink V4.7.3，构建时间为 11 月 7 日 16:04:46。页面列出的 V4.7.2 和 11 月 1 日 21:06:26 与旧安装包内置目录完全吻合。此前手动检查会合并在线目录和内置目录，界面无法说明选中了哪一份。只要已安装版本更高，即使两个在线目录都不可达，也会提示当前固件已满足要求。截图不足以确定该台 Mac 的网络或证书错误。

新版在验证固件索引和文件的 HTTPS 连接时同时支持系统信任及安装包内的公共根证书，并尊重用户显式设置的 OpenSSL 证书路径。默认先查腾讯云，失败再查官方 GitHub。手动检查显示选中的在线或本地目录；使用本地目录时提示尚未核实云端最新版本。已安装构建较新时保留现有固件。检查、下载和升级按下载器系列及型号选择文件。

当天两个官方索引的文件名、构建时间、大小和 SHA-256 一致。逐一下载校验通过，内置目录同步为 MicroLink V2.9.5、V3.7.0、V4.7.4 和 HPMLink V4.7.4。V2 使用独立 RBL 通道。[腾讯云 V3/V4 目录](https://download.microkeenai.com/mklink/firmware/latest.json) · [V2 目录](https://download.microkeenai.com/mklink/firmware/latest-v2.json)

## Windows

- 使用截图中的版本和时间制作只读识别样本，检查返回 `upgrade_required`，候选 MicroLink V4.7.4。用独立临时目录模拟升级盘及重启后的版本读回，升级流程复制的 UF2 与官方 SHA-256 一致。
- 让本地测试代理拒绝两个官方 HTTPS 地址。分别用已安装 V4.7.3、V4.7.4 和较新 V4.7.5 的样本检查，均先请求腾讯云再请求 GitHub，均标识为内置目录。较新版本识别为 `installed_newer`。
- 对本机已连接 MicroLink 的实际 U 盘单独只读核对。当前和腾讯云均为 V4.7.4，构建时间均为 11 月 14 日 11:33:15，结果为 `ok`。本轮无探针刷写。
- 从候选 NSIS 包解出后台及前端，启动桌面代理，从实际固件下载接口取得腾讯云 MicroLink V4.7.4，1,649,664 字节，SHA-256 为 `82d86c9f5de1611ee101f8ccd349deb8ee73b065340cb3a4958ac4c69f886917`。
- 使用 Microsoft Edge 操作安装包内的生产页面，点击菜单外、移出键盘焦点、按 Esc、分别选择两家店铺均收起。Esc 返回菜单按钮，两家店铺各自打开原链接。测试拦截外部店铺的页面内容。
- 启动包内原生桌面程序，在实际 WebView2 配置页重复点击菜单外、按 Esc 和选择两项店铺测试，菜单均关闭，Esc 后焦点回到菜单按钮。
- GUI 全量 1,305 项、固件/代理/卷识别相关 Python 回归 237 项通过，生产前端构建通过。Windows x64 NSIS 的 SHA-256 为 `5c2c4dbb33a6a4bf295f0c83566131c1a88620c1f361878cf6e1898d82ae8663`。

## macOS

两台原生运行器均挂载候选 DMG，使用包内后台查询在线目录，经桌面代理下载 MicroLink V4.7.4。两份报告记录的目录来源和文件来源均为腾讯云，UF2 长度与 SHA-256 均与 Windows 匹配。系统 WKWebView 加载包内生产页面，验证菜单外点击、选择店铺、Esc 收起及焦点恢复。CLI、MCP、后台启动及正常退出均通过。

| 原生环境 | DMG SHA-256 | 构建与验收 |
| --- | --- | --- |
| Apple Silicon，macOS 15.8.2 | `cbd2d4c2473a928ac28e470c3d249a3601f55afb618b00baf1b0ba6567b5d083` | [运行记录](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/45124959362) |
| Intel，macOS 15.7.9 | `3cc72aca2f67d01777e262f42b0efde3b1660ab5a388e2653cf1c2b1b2546306` | [运行记录](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/45124963237) |

两个 DMG 均使用 ad-hoc 签名，未经 Apple 公证。客户 Mac 的网络环境、Gatekeeper 首次打开及 V4.7.3 探针经 USB 刷写后的回读仍待实机确认。
