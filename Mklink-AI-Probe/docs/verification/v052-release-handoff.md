# MKLink AI Probe 0.5.2 正式发布记录

2026-11-29 发布 Windows x64、macOS Apple Silicon 和 Intel、Linux x64、完整 Skill、Windows Site Agent，以及 MicroLink V3.7.1、MicroLink V4.7.5 和 HPMLink V4.7.5。上位机标签 `v0.5.2` 指向 `480743f065d2ae24bdbebd75b6f8c68c86a4e352`。客户可从[官方下载中心](https://download.microkeenai.com/)或 [GitHub Release](https://github.com/MicroKeen/Mklink-AI-Probe/releases/tag/v0.5.2) 下载。

## 安装与更新验证

| 平台 | 正式交付物 | 本轮验证 |
| --- | --- | --- |
| Windows x64 | NSIS 安装包、签名 | 从正式安装包启动桌面、打开仪表盘、隐藏到托盘、恢复及退出，确认后台释放端口。旧版 0.5.1-r20261125 下载新版、通过签名校验并显示可安装。|
| macOS Apple Silicon、Intel | 各一份 DMG、应用更新包及签名 | 两种架构各自在原生 CI 运行应用、测试签名更新。发布包为 ad-hoc 签名，未取得 Apple 公证。 |
| Linux x64 | AppImage、Debian 安装包及各自的签名 | 原生 Linux CI 构建，并实际验证安装、启动与签名更新。|
| 完整 Skill | 含 Web、离线算法和厂商 Pack 的 ZIP | 从已发布的 0.5.1 分别经腾讯云和 GitHub 后备源更新，校验 2,756 个文件、保留用户文件，复核 MCP、外设查询和二次检查。|
| Site Agent | Windows x64 便携 ZIP、清单 | 随版本提供，核对文件大小和 SHA-256。|

macOS、Linux 验收使用产品的 Tauri 更新库和合成旧版本标识，均测试了拒绝错误签名、安装有效更新、重新启动和再次检查已是最新版。Windows 及 Skill 的升级另用已正式发布的 0.5.1 验证。

两个下载渠道分别回读 17 个上位机附件和 3 个 UF2，核对 SHA-256、长度及分段下载。稳定通道覆盖 Windows、两种 macOS 架构及两种 Linux 格式。下载中心保留历史条目，两个渠道独立的 V2 固件索引保持逐字节一致。完整发布文件摘要见 [SHA256SUMS.txt](https://github.com/MicroKeen/Mklink-AI-Probe/releases/download/v0.5.2/SHA256SUMS.txt)。

[跨平台正式构建](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/46163135093) · [三平台签名升级资格测试](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/46165891257) · [开发与合入记录](https://github.com/MicroKeen/Mklink-AI-Probe/pull/98)

## 软件与实板范围

冻结 Windows 后台可枚举 60 个 MCP 工具，桌面与 Skill 的 92 个 Web 资源逐字节相同。分支回归覆盖 1,496 个前端用例。Windows V3.7.1 与 STM32F103RE 实测覆盖 RTT、SuperWatch 启停、多客户端订阅释放及 512 KiB Flash 完整回读。V4.7.5 的 STM32F103 和 S32K344 板级证据见开发报告，其中 S32K344 完成 1 MiB BIN/HEX 烧录后逐字节核验。V3 搭配 S32K3 有模型验证，实物冷启动和擦写仍待验。macOS 和 Linux 本轮使用 CI，未接物理探针。HPM6E80 的 OTP Word 72 永久写入继续暂停。

[V3 与 STM32F103 实测](v052-windows-v3-release.md) · [V4 与 STM32F103 实测](v052-f103-field-regression.md) · [S32K3 覆盖范围](v052-s32k3-family.md)

## 历史下载

上海节点的 17 个旧版上位机附件已验证历史下载回退并归档。3 个旧版 UF2 未通过历史路由检查，已恢复原文件。另保留 5 个缺少同哈希备用件的 0.5.1-r20261125 文件。下载页实查显示 0.5.2、V3.7.1 和两款 V4.7.5，V2 继续提供 V2.9.5。

## 常用交付物摘要

| 文件 | SHA-256 |
| --- | --- |
| `Mklink-AI-Probe-v0.5.2-x64-Setup.exe` | `e483d1a622e24561445a71a899d14df5cc964ac2443f773334372c75f5a2d59d` |
| `Mklink-AI-Probe-v0.5.2-Skill.zip` | `0f83bc6cfb3d40878ed6c69669fd0d2c72393d73abad1fbf62effbf6c778c5c8` |
| `HPMLink_V4.7.5.uf2` | `a87e39ccf6584ab99b4d2c3f0cbe00436444ef39e19d83de71cef412b5a7aee7` |
| `MicroLink_V3.7.1.uf2` | `95096e9420b7b3047310d55f36cb996b42f3f1333e9edc0bae18e856ea4eb04d` |
| `MicroLink_V4.7.5.uf2` | `3b20da792da9c72779ded64f88e9e1f7cf9bebcc43e335ac908607ebb77cf638` |
