# MKLink 0.4.3 正式发布交接

Windows 上位机、完整 Skill、Windows Site Agent 和三款下载器固件已正式发布。北京时间 2026-11-07 创建正式附件，11-08 00:06 完成上海稳定索引切换。GitHub 与 Gitee 上的注解标签 `v0.4.3` 均指向 `3905a68bceaf6d863b9159de2a390e161788af48`。[下载中心](https://download.microkeenai.com/) · [GitHub Release](https://github.com/MicroKeen/Mklink-AI-Probe/releases/tag/v0.4.3) · [Gitee Release](https://gitee.com/Aladdin-Wang/Mklink-AI-Probe/releases/tag/v0.4.3)

## 源码与本机验收

- [PR #72](https://github.com/MicroKeen/Mklink-AI-Probe/pull/72) 的头提交为 `0da56450`。合并提交的源码树与之相同。PR 和合并提交的三个 CI 检查均通过。本地通过 6,837 项 Python、1,203 项 GUI 和 23 项 Rust 测试，另有 2 项 Python 跳过。
- 候选覆盖安装保留 7 份设置。从安装目录启动三次，窗口可见至识别出标志和进度条分别为 389、259、370 ms，三轮均未采到纯色空白帧。[首帧前后对照](v043-desktop-startup.md)
- 从干净的合并提交重建正式包，并用随应用分发的公钥验证更新签名。正式覆盖安装后，3,671 个受管文件与安装包逐一匹配。原生桌面启动、隐藏后重载、恢复工作区及退出均通过。正式桌面和 Skill 的 42 个 Web 文件逐字节相同。Windows 使用 Tauri 更新签名，本次没有 Authenticode 签名。
- 本地完整 Skill 的 2,663 个受管文件与正式 ZIP 匹配，保留 5,340 个用户文件。原版 0.4.2 Skill 分别通过上海默认入口、模拟主源不可达时的真实 Gitee 备用入口升级至 0.4.3。两轮均保留用户文件、逐一匹配全部归档文件，复查无需再次更新，MCP 与 SVD 查询均通过。
- 硬件与性能资格沿用对应实测。本次发布回测没有重刷目标板或下载器。[V4/F103、USB 与性能对照](v043-s3-integration.md) · [睡眠与固件实刷记录](v043-f103-wake-data.md)

## 正式原件

| 发布件 | 字节 | SHA-256 |
| --- | ---: | --- |
| Windows 安装包 | 186,759,560 | `45786abdfac3ad49671988ac5a8b6fcb5054259964a8dca961090a8a92d90342` |
| 完整 Skill | 100,333,143 | `9fd2d80cd85be2f8e6189524f16fce650bb4d9914ead7480c7fd2f94df92fc78` |
| Windows Site Agent | 67,944,588 | `329ca667f7beabf4daa33b5e099c1ec815bacbf3d8fb628d7ef78204267556fe` |
| MicroLink V3.6.9 | 846,336 | `0b6866c0d305eb9ef14d6b97a379883a8c5d1a4b91e28ceef96bfa445b646d05` |
| MicroLink V4.7.3 | 1,640,960 | `7b62337faaf54cacb8ea63011046444d3f1b99ed073d06b3e94971603e3d67dc` |
| HPMLink V4.7.3 | 1,640,960 | `074a6fd36ac268ee9a71279407a55b78ac4e20aaa1a3dd777be0402805ae988a` |

三个 UF2 的构建时间分别为 11 月 7 日 16:03:03、16:04:46 和 16:03:37，与验收原件一致。MicroLink V2 保持 V2.9.3。三渠道 V2 索引的 SHA-256 仍为 `db1148d961f749bd3a37741708aea12bc7c46700402fea9e51805b366ab2a200`。[固件索引](https://download.microkeenai.com/mklink/firmware/latest.json) · [V2 索引](https://download.microkeenai.com/mklink/firmware/latest-v2.json)

## 分发与历史归档

上海直供的全部 10 个新文件均通过匿名 HEAD、Range、完整下载与哈希校验。上海、GitHub、Gitee 的上位机索引和固件索引均已回读。Gitee 实际托管完整 Skill 和三个 UF2；其 100 MB 附件限制拒绝 Windows 安装包，Gitee 的安装包链接使用已验证的 GitHub 正式附件。下载中心保留所有历史条目。[稳定索引](https://download.microkeenai.com/mklink/stable/latest.json)

上海内网完整校验旧版 COS 原件，并匹配 GitHub 历史附件哈希后，清退 10 份被替代的本地文件，共 357,550,001 字节。十个旧地址均已复核为指向 COS 的重定向，仍为最新版的 V2 文件继续由上海直供。流量告警、停用阈值和累计记录沿用原策略。[腾讯云下载策略](../ai/tencent-updates.md)

原始证据位于构建根 `artifacts/v043-official-20261107`。其中 `install`、`formal-install` 保存覆盖安装回执，`channels-after.json`、`host-cloud-verified.json`、`firmware-cloud-verified.json`、`old-archive-routes.json` 和两份 `skill-upgrade-*-report.json` 记录公开渠道回读和升级结果。
