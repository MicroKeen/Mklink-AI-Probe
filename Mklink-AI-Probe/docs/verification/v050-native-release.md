# V0.5.0 原生包补充发布验收

## 范围与来源

维护者于 2026-11-15 明确要求补齐 Linux x64、macOS Apple Silicon / Intel 安装包与自动更新，发布到 MicroKeen GitHub 和腾讯云。当前没有 Linux/Mac 实物，维护者接受先完成 CI 原生验证，并将未验范围写入交接；产品版本保持 **0.5.0**。

首轮候选构建源是已发布的 `v0.5.0` / `1097f98eb9025b38b16cd32095bced7dd65ecdcd`。原生验收发现遗漏的同步枚举，因此补充源码修复后重建；最终原生清单需记录其实际提交，不能把新二进制误标为原标签源。本轮不移动正式标签，不替换此前 Windows、Skill、Site Agent 和四款固件文件。原发布证据见[正式发布交接](v050-release-handoff.md)。

## 构建、启动与 USB 回归

[原生构建 43661438434](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/43661438434) 三平台成功：

| 平台 | 产物 | 冻结后台健康耗时 |
| --- | --- | ---: |
| macOS ARM，runner 15.8.2 | DMG、app.tar.gz | 6.057 秒 |
| macOS Intel，runner 15.7.9 | DMG、app.tar.gz | 29.359 秒 |
| Ubuntu 22.04 x64 | AppImage、DEB | 5.184 秒 |

耗时属于共享 CI 环境，不等于用户机器启动承诺。每个平台 USB/卷关联与慢查询回归 73 项通过、1 项 Windows 专属跳过。冻结 CLI、MCP、内置算法、生产 Web 资源、后台健康与正常退出通过。Mac 包为 ad-hoc 签名，不启用 Hardened Runtime，DMG 内应用和 updater 归档的执行文件及模式一致。

这证明相关修复已进入新包；没有把客户 ioreg 3.7→0.15 秒或真实 USB 接口/卷枚举当作独立实测结果。

## 签名与更新验证

四种 updater payload 使用既有本地发布密钥签名；私钥没有上传 CI。独立验证了文件 SHA-256、大小及签名。CI 只接收公开签名。

原生验收使用真实 Tauri updater 2.10.1 库、真实安装包和原生 WebView。测试用的旧版本 AppHandle 是合成的 0.4.3，仅用于选择并执行更新；这不等于历史 0.4.3 客户端的端到端升级验证。测试回环 HTTP 配置只存在于测试程序，没有修改产品 TLS 或更新配置。

测试覆盖：首选端点 503 后使用备用端点、错误签名拒绝、有效签名替换安装、当前 0.5.0 不重复升级、安装后再次启动、MCP 操作真实窗口的四个主页面和八个仪表盘标签。

- [43663801545](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/43663801545)：ARM、Intel Mac 全部通过；Linux 页面操作遇到租约失效。
- [43664552055](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/43664552055)：Linux AppImage 签名更新与更新前后原生窗口通过；DEB 进入仪表盘耗时 5.317 秒，下一次 MCP 操作返回会话过期。
- [43665537966](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/43665537966)：原包加入外部堆栈采样后四次窗口及两种签名更新通过，但导航仍有 3.7～4.5 秒阻塞，不能将偶发通过视为修复。后台主线程采样定位 `online_flash_api.probes → control.presence → inventory → pyserial comports → glob /dev`；此前仅将后续 CMSIS-DAP 枚举放到线程，漏掉了前置串口身份扫描。

源码修复把上述身份扫描移到后台线程，保持租约时长和显式重连规则不变。查询前后核对连接身份/代次，枚举期间换设备时返回 409 要求刷新，避免将旧探针信息与新连接混合。新增阻塞枚举时心跳可响应和中途换设备的回归，两项均通过；相关在线烧录、共享安全、切换及慢枚举回归合计 220 项通过。最终原生重建和复验结果见下节。

原始构建、签名、运行日志和发布准备记录保存在构建根 `artifacts/v050-unix-20261115`；不提交临时鉴权 URL、私钥或本机诊断。

## 接受的设施边界

- 没有接下载器的 Linux / Mac 实物，未验真实 USB、串口权限、探针卷关联或查询性能。
- Mac 未做 Developer ID 公证、Gatekeeper 隔离属性首次启动或用户 Finder 覆盖安装。ad-hoc 签名验证不能替代这些验证。
- Linux DEB 更新测试使用 CI 既有免密 sudo；交互式管理员提示、发行版差异和用户权限仍需实物验收。AppImage 独立分发时 USB 规则需按安装说明配置；DEB 内置规则。
- 以上设施边界由维护者明确接受并记录；已观察到的软件失败必须单独处理，不能借此记为通过。

## 最终原生包与发布

[PR #82](https://github.com/MicroKeen/Mklink-AI-Probe/pull/82) 以 `8d532019ffff55f2f9e93387c205b3feb1df78a4` 合入 main；本轮原生包由这个清洁、已审查提交构建，版本仍为 0.5.0。

- Windows 全量回归核对为 7,175 通过、2 项既有跳过；首轮五个测试替身补齐身份快照，四个隔离打包用例补入既有 STCP DLL 后，相关 26 项复验通过。未放宽产品校验。GUI 全量 1,291 项和生产构建通过；精确 PR head 的三个 CI 检查通过。
- [最终构建 43668900995](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/43668900995) 三平台成功；[最终原生签名验收 43671117920](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/43671117920) 三平台全部通过。上述设施边界仍适用。
- GitHub 和腾讯云追加 13 个原生文件/签名/规则/校验附件，更新索引共 5 个平台项。两渠道完整下载哈希通过，腾讯云 HEAD/Range、实际本地缺文件时 COS 回退及还原通过；未知文件返回 404。版本、发布日期、旧 Windows/Skill 索引和四款固件保留。
- 腾讯云目录保留既有软件来源，新增文件逐一记录实际 sourceCommit；`desktop-manifest.json` 记录原生构建提交与运行号，未重写 v0.5.0 标签。

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| `Mklink-AI-Probe-v0.5.0-aarch64-apple-darwin.dmg` | 167894311 | `30c3200724ddd8fe795901a8f15c936744789a38b782490361db0916f13bb9cb` |
| `Mklink-AI-Probe-v0.5.0-aarch64-apple-darwin.app.tar.gz` | 167602841 | `ac6554f108fd5a901a425b7e144f738cb919e83efd2d84ef031511ded3c9ba9b` |
| `Mklink-AI-Probe-v0.5.0-x86_64-apple-darwin.dmg` | 168247906 | `44c0411b2c8bb018b6dfa01f47c41231cca6b48db1395ef7e6fc899dd69f5c95` |
| `Mklink-AI-Probe-v0.5.0-x86_64-apple-darwin.app.tar.gz` | 168025804 | `9a133b7a3335f1aab97bbf259f1d39ffe67a3a3328a376627ebe6bc6803ffd5d` |
| `Mklink-AI-Probe-v0.5.0-x86_64-unknown-linux-gnu.deb` | 186267876 | `640987225579545152875770387f60234acab9f16898261b920cef572a02da1c` |
| `Mklink-AI-Probe-v0.5.0-x86_64-unknown-linux-gnu.AppImage` | 264137208 | `7ee57037ac9ec1f42dbe958fe45f9cbf22d8bb611ce6493dde5c303a5d8519b8` |

## 发布后的磁盘清理

发布回读通过后清理了 F 盘旧 Debug 缓存、历史重复解包、测试浏览器缓存及已结束测试副本，磁盘可用空间增加约 11.83 GiB；E 盘过期实验缓存增加约 0.20 GiB。正式安装包、原始真机记录、源码工作树、可复用 Release 缓存和当前 AXF 引用的目标快照保留。33 个清理目标全部成功，清除了 7,195 个测试链接，无权限或占用失败遗留。链接只移除自身，不递归进入目标；逐项结果保存在本地 `cleanup-result.json` / `cleanup-e-result.json`。

## 最终原生操作与发布核对

最终三平台冻结后台健康耗时为 ARM 4.313 秒、Intel 16.264 秒、Linux 3.002 秒。八个更新前后窗口共执行 136 次 GUI/MCP 操作，全部成功；每个窗口覆盖 17 次状态/导航操作，没有再次出现会话失效。最长单次操作如下，包含 CI 调度和 WebView 开销，不代表实物性能承诺。

| 安装格式 | 更新前最长操作 | 更新后最长操作 |
| --- | ---: | ---: |
| Mac ARM | 0.526 秒 | 2.575 秒 |
| Mac Intel | 2.311 秒 | 1.982 秒 |
| Linux AppImage | 0.647 秒 | 0.986 秒 |
| Linux DEB | 1.292 秒 | 1.212 秒 |

四份 Linux 20 秒外部堆栈采样中，修复的在线烧录 `control.presence` 路径在事件循环中的样本数均为 0，工作线程中分别为 170 / 200 / 198 / 78。这里只证明该路径已迁移；`/api/ports`、`/api/config` 仍有较短的同步枚举样本，不声称所有设备发现都已移出事件循环，也不将本轮无租约失效等同所有硬件的耗时上界。

腾讯云新增 13 个精确对象的只读策略 `MKLinkShanghaiGuard050NativeAssets`，仅关联现有下载守卫角色；旧 32 对象策略保持不变，未放宽为通配符。SCF/回退清单共 73 项，189 GiB 告警、207.9 GiB 停止与 180 秒签名期限保持不变。公开下载页已显示两个 Mac 架构及 Linux DEB/AppImage，静态说明同步更新。GitHub 最终附件共 20 个，原有 7 个的 ID、大小、摘要及 v0.5.0 标签核对不变。

## 已完成分支整理

已确认 PR #70、#76、#78 为 MERGED，三个分支 head 均已包含于 main，工作树无待提交或未跟踪改动；删除了其本地及 microkeen 远端的 `codex/s3-main-regression`、`codex/job-journal-access`、`codex/cli-symbol-reload`。旧工作树切为原提交的 detached HEAD，目录和忽略文件保留。合并记录保留，不删除 PR 历史。

PR #65（共享远程调试）、#80（Agent 工作台草稿）仍开放，分支未改动。`codex/v0.5.0-fixes` 保留，完成本次文档合入并同步 main 后继续后续上位机开发。
