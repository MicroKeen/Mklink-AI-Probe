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

源码修复把上述身份扫描移到后台线程，保持租约时长和显式重连规则不变。查询前后核对连接身份/代次，枚举期间换设备时返回 409 要求刷新，避免将旧探针信息与新连接混合。新增阻塞枚举时心跳可响应和中途换设备的回归，两项均通过；相关在线烧录、共享安全、切换及慢枚举回归合计 220 项通过。最终原生重建和复验待完成。

原始构建、签名、运行日志和发布准备记录保存在构建根 `artifacts/v050-unix-20261115`；不提交临时鉴权 URL、私钥或本机诊断。

## 接受的设施边界

- 没有接下载器的 Linux / Mac 实物，未验真实 USB、串口权限、探针卷关联或查询性能。
- Mac 未做 Developer ID 公证、Gatekeeper 隔离属性首次启动或用户 Finder 覆盖安装。ad-hoc 签名验证不能替代这些验证。
- Linux DEB 更新测试使用 CI 既有免密 sudo；交互式管理员提示、发行版差异和用户权限仍需实物验收。AppImage 独立分发时 USB 规则需按安装说明配置；DEB 内置规则。
- 以上设施边界由维护者明确接受并记录；已观察到的软件失败必须单独处理，不能借此记为通过。
