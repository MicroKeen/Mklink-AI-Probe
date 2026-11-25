# MKLink AI Probe 0.5.1 正式发布

2026-11-25，正式标签为 `v0.5.1`，源码提交为 `595544d958a42f9c170de3429c26db046a444fa3`。[腾讯云下载中心](https://download.microkeenai.com/)为主下载入口，备用入口为 [GitHub Release](https://github.com/MicroKeen/Mklink-AI-Probe/releases/tag/v0.5.1)。

| 用户安装包 | 交付形式 |
| --- | --- |
| Windows x64 | NSIS 安装器 |
| macOS Apple Silicon、Intel | 独立架构 DMG，另含签名更新包 |
| Linux x64 | AppImage、DEB |
| AI 工具与远端现场代理 | 完整 Skill ZIP、Windows x64 Site Agent 便携包 |

本次共发布 17 个文件、5 个桌面更新目标。腾讯云和 GitHub 均通过匿名完整下载、大小及 SHA-256 核验，校验清单随版本提供。腾讯云支持分段下载，移走一份签名时 GET 与 HEAD 均回退到对应 GitHub 附件，还原后恢复本地直供。双渠道稳定索引、下载中心的三个栏目以及原有两份下载器固件索引均已回读核验。

上一版在上海下载服务器的 20 个文件已逐项核对归档摘要并验证历史链接回退，释放 1,477,087,753 字节。GitHub 的历史附件继续保留。

## 发布验收

- Python 7,989 项通过，2 项跳过。GUI 1,474 项、Rust 23 项通过。
- Windows 在受限 PATH 下启动签名包内的桌面端，识别到 1 只探针。Web 仪表盘、托盘隐藏、恢复及退出释放端口通过。随包 CLI、59 个 MCP 工具的枚举、离线器件和外设查询通过。
- 正式 0.5.0 Windows 客户端下载签名的 0.5.1，安装后重新启动并回读版本，再查更新显示为当前版本。
- 两个干净的 0.5.0 Skill 副本分别通过腾讯云主站和 GitHub 回退更新。逐项核对了更新后的 2,738 个文件，用户自建文件保留，MCP 查询通过。GitHub 回退首次下载遇到连接关闭，在另一份干净副本上重试通过。
- Apple Silicon、Intel、Linux x64 原生环境验证包启动、错误签名拒绝、有效签名安装及同版本检查。见[原生构建](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/45567781554)、[签名安装验收](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/45572438851)。
- Mac 包使用 ad-hoc 签名。Apple Developer ID 公证、Mac/Linux 现场 USB 探针和交互式提权仍需在相应用户环境验证。HPM6E80 永久 OTP 写入保持暂停。

Windows 当前发布文件 SHA-256 为 `6dbd3da007ce0d2f27fc0753ded29fef836c0c0019bedddbfed6dcb5b549dd00`。完整证据保存在维护机 `F:/MKLink-Build/artifacts/v051-formal-595544d9`。
