# MKLink V0.5.0 正式发布与交接

维护者于 2026-11-14 明确授权 V0.5.0 与四款新固件正式发布；双渠道发布及回读于 2026-11-15 完成。发布目标仅为 MicroKeen GitHub 与腾讯云，历史 Gitee 和旧 GitHub 未改动。

## 正式基线与渠道

- [PR #79](https://github.com/MicroKeen/Mklink-AI-Probe/pull/79) 已合并；正式源提交及 `v0.5.0` 为 `1097f98eb9025b38b16cd32095bced7dd65ecdcd`。合并树与已审核任务分支一致，正式包从干净源码构建。
- [GitHub V0.5.0](https://github.com/MicroKeen/Mklink-AI-Probe/releases/tag/v0.5.0) 包含 Windows x64 NSIS、完整 Skill、Windows Site Agent、签名和校验文件，共 7 个附件。腾讯云[下载中心](https://download.microkeenai.com/)与 stable 更新索引已同步，默认腾讯云、不可用时回退 canonical GitHub。
- 应用 `release` 分支索引提交 `36397bad`；四款固件发布到既有 [firmware-assets](https://github.com/MicroKeen/Mklink-AI-Probe/releases/tag/firmware-assets)，`firmware` 分支最终索引提交 `0a0819624b745aca5ec7a9dbe98c753a295965a9`。先切换应用/Skill，再切换固件索引。
- 新版 Windows 已在本机覆盖安装。实际 0.4.3 原生自动更新完成下载、签名校验、安装与重启至 0.5.0；再次检查无更新。测试窗口正常退出，本轮没有刷写下载器或目标应用。
- 本轮没有新发布 macOS/Linux 原生安装包；之前的 Mac 候选不进入正式更新索引。

## 软件、安装与升级验收

- 最终 Python 全量 **7173 通过、2 跳过**（已有硬件观察跳过），GUI **114 文件 / 1291 测试通过**，Rust **23 通过**，生产构建通过。PR 必需 CI 已通过。
- 发布索引改为保留现有历史、快进更新并拒绝并发覆盖；真实本地远端验证重复发布幂等。受限 Job Object 环境的测试替身适配通过，仍验证产品使用 breakaway 和 DEVNULL；发布/日志导出相关 34 项及受限环境复测通过。首轮遗漏显式 STCP DLL 路径造成的 4 项包测试失败，在补齐已验证依赖后由上述完整回归覆盖。
- 更新包使用既有 Tauri 签名密钥；NSIS `currentUser` / `asInvoker`。普通用户 RID 8192 的新安装、卸载、覆盖安装均 exit 0；3686 个载荷文件逐项一致，6 项用户配置保留，USB 端口名称和机器级登记不变。旧机器级登记仍保留，不自动提权。Tauri 签名不等于 Windows Authenticode。
- 冻结 CLI、通用 `project-init`、59 个 MCP 工具、7059 个内置算法目标 / 2224 个算法文件、5065 个 Pack 目标 / 4800 个 SVD 通过离线检查。
- 实际安装版原生与 Web GUI 验证 4 个主工作页、8 个仪表盘标签、显式多窗口选择、SystemView JSONL 加载/回放/缩放、RTT RX/TX 回放、SuperWatch CSV 回放及串口回放；本轮回放不访问硬件、不重发历史 TX。
- 原始 0.4.3 完整 Skill 分别沿腾讯云主源和隔离腾讯云后的 GitHub 备用源升级；2680 个分发文件一致，用户笔记保留，二次检查无更新，MCP 与 SVD 检查通过。
- 原始 0.4.3 原生客户端在仅限该进程的测试代理中模拟腾讯云不可达，实际走 GitHub 下载正式安装器并校验签名、覆盖、重启；实际重启版本 0.5.0，二次检查无更新。测试代理与测试应用已退出，没有改动系统代理。

功能和实物验收沿用产品代码一致的 [GUI 控制最终验收](v050-gui-control.md)、[强制覆盖验收](v050-installer-force-acceptance.md)、[HPM/USB 验收](v050-usb-hpm-overwrite.md)及各专项报告。本轮发版验证没有重做目标刷写或改变电源。

## 应用附件

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| Mklink-AI-Probe-v0.5.0-x64-Setup.exe | 187243644 | `c209018a4f29eae196148b8f628f215a41a65b42ccfb2f8782d7fcd995ef75af` |
| Mklink-AI-Probe-v0.5.0-x64-Setup.exe.sig | 428 | `5d4fd06520d06048f0228fae4436b56064e468326521ab0f04e726bbeac1b602` |
| Mklink-AI-Probe-v0.5.0-Skill.zip | 100412821 | `60544de4d2cb0c05d40252f09d3c74b09032149d3fa733ad2593099ff900956f` |
| MKLink-Site-Agent-v0.5.0-windows-x86_64-portable.zip | 67813011 | `293c3a64a9795ef6ebdaa2a25fbbca5cd08ec953626388ec23942d5b1bf03f81` |
| MKLink-Site-Agent-v0.5.0-windows-x86_64-portable.manifest.json | 2391 | `03e6374c72d63f3fd9e0b9596b06aa84e896eeb89eebb053664b371e0858e686` |
| release-manifest.json | 1276 | `458344c7fc9caf254d84956a37398247ae3b9f9639bdabe301de5345440cefb3` |
| SHA256SUMS.txt | 562 | `0552f90682a5a32df08f6d42c8aa56eab2edc9a41878552c503ea0b0f407b997` |

## 四款正式固件

固件会话确认以下为已合入固件主线的最终原件，本轮按公开文件名复制，没有重新编译或刷写。两个 V4 均支持 Arm SWD/HPM JTAG，仍须按下载器型号选择，不能互刷。

| 公开文件名 | 构建时间 | 字节 | SHA-256 |
| --- | --- | ---: | --- |
| MicroLink_V2.9.4.rbl | 2026-11-13T16:05:31 | 368944 | `3751d7f3ca9438c40f2002ebb3a91cc596fc1b7c7d8b66a8ea5a53689d3c9ead` |
| MicroLink_V3.7.0.uf2 | 2026-11-13T15:18:58 | 851968 | `c41cdb180f2365d6a5929b1ee595de80aa3ed3a1759d20aa2bafc32c35e723f3` |
| MicroLink_V4.7.4.uf2 | 2026-11-14T11:33:15 | 1649664 | `82d86c9f5de1611ee101f8ccd349deb8ee73b065340cb3a4958ac4c69f886917` |
| HPMLink_V4.7.4.uf2 | 2026-11-14T11:35:00 | 1650176 | `a3c6f34c4179d54a46f28bc3e28b30a4da8d0622903d424ec3831a9d873f136b` |

V2 使用独立 `latest-v2.json`，其他三款使用 `latest.json`。GitHub 与腾讯云的型号、版本、构建时间、字节和摘要一致。

## 腾讯云与历史归档

- 上海服务器直接提供最新版 7 个应用附件及 4 个固件，共 **359994885 字节**。公网 11 个文件完整 SHA-256、HEAD 与 Range 回读通过。
- 下载中心保留版本历史；应用和固件索引 `no-store`，未列入的下载路径返回 404。新索引仅含腾讯云和 canonical GitHub，没有新增 Gitee 地址。
- 旧 0.4.3 应用 7 文件、三款旧 UF2 和 V2.9.3 共 11 文件，完整 COS 副本与 GitHub 原件摘要一致后，移除上海服务器的重复本地文件 **359536472 字节**。历史入口仍经 COS 提供；公网 11 条历史入口 HEAD/Range 和小文件完整摘要复验通过。
- resolver 增加新版和归档文件后覆盖 60 个允许路径；44 个新旧文件 GET/HEAD 解析检查通过。暂移新版签名文件测试真实缺文件路径，GET/HEAD 均回退 COS，完整签名摘要一致，随后恢复本地直供。
- 首次重启后探测碰到短暂未监听；有界重试确认服务正常。验收脚本另有 Python urllib 在 HEAD 跳转时变成 GET 的问题，导致签名 403；修正脚本保留方法后通过，不是发布文件或 resolver 故障。
- SCF 只扩展允许签名的公开附件键；角色策略仅增加对应公开文件的 GetObject/HeadObject 精确资源，没有新凭据、通配权限或公开桶。预算状态和计量周期保留，189 GiB 告警 / 207.9 GiB 停止，未恢复日期截止。

原始证据在构建根 `artifacts/v050-official-20261114`，包括测试日志、`install-result.json`、`native-upgrade-result.json`、两份 Skill 升级报告、`gui-check-result.json`、`tencent-assets-verified.json`、`published-indexes-verified.json`、`archive-final-verified.json`、云端执行输出与下载中心截图。签名私钥、临时签名 URL、原始本机诊断不进入仓库。

## 更新顺序与保留限制

先更新上位机 / 完整 Skill，重新加载旧 MCP，再重连检查并按型号更新固件。覆盖安装按维护者最终要求结束当前用户旧 MKLink 与 Skill/MCP，活动任务会中断；普通用户不能结束管理员进程或突破目录权限。

原有 1 µs 三路极限采集溢出、10 Mbps RS485 大帧、客户 STOP、Mac 原生/Gatekeeper/实物 USB 等未验或未达范围保留，见[项目交接](../ai/CURRENT_HANDOFF.md)。正式发布不意味着这些边界已解决。
