# V0.5.0 r20261115 与 MicroLink V2.9.5 发布

日期：2026-11-15。维护者明确授权本会话统一发布上位机修订包、完整 Skill 和 V2
最终固件到腾讯云；官方 MicroKeen GitHub 同步作备用源。没有更新 Gitee、旧 GitHub、
V3/V4 固件、Site Agent 或 Linux/macOS 包，也没有移动既有标签或覆盖既有附件。

## 原件与安装验收

PR #84 经维护者授权，核对确切头 `c54995c7` 的三项 CI 后合入 main
`ed5d55aa191c4bbd36e7b0b9c37b4371257cdd74`。从干净主线重新构建并覆盖安装，
版本维持 **0.5.0**，文件名加 `r20261115`，详见[专项报告](v050-install-path-offline-refresh.md)。

| 文件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| Mklink-AI-Probe-v0.5.0-r20261115-x64-Setup.exe | 187248429 | `78cc0df092d5012758e45ced0e5957501e07cd77461090f62ceee0e359aa1854` |
| Mklink-AI-Probe-v0.5.0-r20261115-Skill.zip | 99839461 | `b307e373294755013328d995545187d3b8c4ba2d9664948d159c5281033577cc` |
| MicroLink_V2.9.5.rbl | 370124 | `45dc34fc9dff29ed7904d33c74ae2fe850284d2c1624c176e18738004fbf1241` |

同批发布安装器 `.sig`、`release-manifest-r20261115.json` 和
`SHA256SUMS-r20261115.txt`。Updater 签名及 trusted-comment 校验通过；不称为
Authenticode 签名。7190 项 Python/2 跳过、1294 项 GUI 和生产构建已通过；最终
主线包重新完成普通用户无 `/D` 覆盖、3687 文件匹配、设置保留和原生/Web 脱机页检查。
本机完整 Skill 仅完成包内独立验证，全局安装未替换。

V2 原件由固件会话交付，测试源码 `56f5fdf5`，PR #9 合并 main `866fc5ff`，固件
源码无差异，没有再编译。build_id 为 `2026-11-15T21:39:19`，RBL payload
370028 字节。本轮 47/49 项命令实机通过；YMODEM 对端传输、真实 Modbus 从站、
USB 12 Mbps、H7 双核、深度低功耗及 SWD 拔插未完整验收。原目标 512 KiB 程序已
恢复且独立回读一致，连接释放。未发布本地完整证据 ZIP 或用户工程文件。

## 发布顺序与结果

1. 六个新文件先上传官方 GitHub，并逐个匿名完整下载核对大小、SHA-256。
2. GitHub `release/latest.json` 快进至 `ff005bff6ec4ab382b82671e8cf15f5a2302f456`。
3. 腾讯云暂存、逐文件哈希核对、正式下载路径部署后，完整 HTTPS GET、HEAD、
   `Range: bytes=0-99` 全部通过；不可变资源含 immutable 缓存头。
4. 模拟新签名文件暂时缺失，GET/HEAD 均 302 回退到官方 GitHub，下载内容一致；
   随即恢复原件。未知文件路径 404，JSON 索引保持 no-store。
5. 腾讯云应用/Skill 索引先切换；再快进 GitHub `firmware/latest-v2.json` 至
   `83c650a2ddd67b3aa6b5e18c95a9a9bbbd3d9873`，最后切换腾讯云 V2 索引。
6. 公开回读三个腾讯索引、两个 GitHub 索引和下载目录，大小、SHA、版本、build_id
   均匹配。macOS/Linux 条目、V3/V4 索引、Site Agent、历史目录和原 GitHub 附件
   保留；`v0.5.0` 仍指向 `1097f98e`。两个渠道分支保留原父提交，无 force push。

GitHub 发布使用指定维护者 Aladdin-Wang 的渠道写入权限，未修改仓库保护规则。
部分 GitHub API 请求 EOF；无索引覆盖重试，改走正常 Git 快进推送并回读确切提交。

腾讯云服务器直接拉取 GitHub 的首次传输在 600 秒仅得到约 6 MiB，超时前未改索引。
随后经现有 HTTPS 域名直接传入非公开暂存目录：临时接收器仅绑定 loopback，使用
随机凭据摘要认证，仅允许六个文件且强制长度/哈希，20 分钟自动到期。上传用时约
61 秒，完成后移除临时 Nginx 路由、结束接收器并删除本地临时凭据；已验证端口关闭、
临时 URL 404。没有新增 SSH/API 永久凭据、开放服务器端口或改变 TLS、COS 预算和权限。

原 Windows/Skill、签名、两份完整性清单及 V2.9.4 共六个旧文件，先从同区 COS
完整回读并核对 GET/HEAD 与解析器路由，再精确移除 Lighthouse 副本，释放
**288027675 字节**。旧路径仍通过 COS/Git 归档可下载；其他本地正式包未删除。
新文件由 Lighthouse 直供，缺失时回退 GitHub；本轮没有把新文件加入 COS 租约清单。

本地证据保存在 `artifacts/v050-refresh-20261115/final/`：
`public-github-readback.json`、`public-tencent-readback.json`、
`published-index-checks.json`、两份 `*-published.json`、
`direct-transfer-result.json`、`tencent-finalize-output.txt` 和安装验收记录。

## 用户升级说明

下载中心：<https://download.microkeenai.com/>。先安装 V0.5.0 修订版上位机/完整 Skill，
重载被结束的 MCP 进程，再为 **MicroLink V2** 更新 V2.9.5，勿跨型号刷写。

已经安装 0.5.0 的客户端不会因同版本修订自动弹出升级，需手动下载带
`r20261115` 的安装器覆盖；旧版本自动更新会取得新修订包。安装前保存数据，覆盖安装
按维护者要求结束旧程序及活动后台。普通用户仍无法写入受保护的旧目录或结束管理员
进程，安装器明确报错，不通过静默新建第二份绕过权限。
