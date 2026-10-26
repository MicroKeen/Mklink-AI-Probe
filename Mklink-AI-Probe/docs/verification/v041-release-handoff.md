# 0.4.1 正式发布交接

日期：2026-10-27。用户明确授权合并、使用现有更新密钥签名并正式发布，不需要再次等待确认。公网远程中继延后，不发布或降级下载器固件。

## 来源和资格

PR #61 已合并，正式不可变源为 `514efb86bef5d0b45f3a7332372d21103a12bf69`，标签 `v0.4.1`。从干净、与 `microkeen/main` 一致的原 main 工作区重新构建；后续交接修改继续 `codex/v0.4.1-fixes`，不直接修改 main。

完整回归、实际 NSIS 安装和硬件验收见 [发布准备](v041-release-preparation.md)：5565 Python 通过/2 可选硬件观察跳过，1133 GUI 通过；V4.7.2 + H743 在线和四组脱机各自 216036 字节回读一致，19 项采集调试通过。发布源相对于该已验证产品代码仅有文档和生成 Web 更新，运行时、GUI 源码与安装器逻辑未变。正式 Web 按合并提交重新构建。

正式包包含 211 份对应 Python 源、41 份 Web 资源，冻结 CLI/MCP、版本、SVD、后台、枚举和正常退出通过；7059 FLM 型号/2224 blob、5065 Pack 型号/4800 SVD 目标完整验证。完整 Skill 和 Site Agent 使用同一正式源与已验证资源。

## 冻结版本元数据修正

切换任何稳定索引之前，追加检查发现首次 main 构建沿用了忽略目录 `mklink.egg-info` 的旧 0.3.6 元数据。已刷新该生成元数据并从同一不可变提交重新签名构建；没有移动正式标签。最终包内 `PKG-INFO`、冻结 MCP `ping.version` 与更新检查的 `current_version` 均为 0.4.1。

首次暂存 Release 已转为可恢复的撤回草稿，保留审计资料；稳定索引从未引用错误包。正式文件只认 `F:/MKLink-Build/artifacts/v041-release-corrected`，不使用同级 `v041-release-final` 中被撤回的安装包。以后构建应在冻结前刷新并核对 distribution metadata，在冻结后核验实际 MCP 和更新检查版本，不能只检查源码版本或 UI 页脚。

| 文件 | SHA256 |
| --- | --- |
| Windows NSIS | `30333c335be4659d10dfa5123463f00553ae35446321931919df6aa84856c621` |
| 完整 Skill ZIP | `7f210a8712bdbd4b33262d26081a250c1626b4df22d6b11d0f386251a5394a92` |
| Site Agent ZIP | `bbbcbb04595fde27f28b446c0dfe42ee1383112c908364b55d7303a2835c4e48` |

现有 Tauri 更新公钥验签通过；没有申请新私钥或 Authenticode 证书。

## 正式交付与下载验证

MicroKeen GitHub Release、Gitee Skill 镜像和上海 COS 已完成。七个 GitHub 文件及真实 Gitee Skill 均匿名完整下载并核对大小/SHA256。Gitee 明确返回安装包超过 100 MB 的 HTTP 400 限制，因此安装包备用使用已验证的 MicroKeen GitHub URL。

上海 COS 的七个文件直连和正式下载域名均完整下载一致，并通过 HEAD、Range 206 检查。正式域名下安装包耗时 9.581 秒、Skill 7.632 秒（维护者当前网络环境，非速度保证）。解析器停止时七条路径均返回正确 Git 备用地址；测试最后恢复服务并确认 active。原 21 条资源保留，新增七条，共 28 条，保护函数和解析配置对应一致。

所有资源验证完成后才切换稳定索引；云端、MicroKeen `release/latest.json`、Gitee `updates/latest.json` 的版本、签名、大小、哈希和源提交已核对，preview 仍为 404。默认入口为云端，备用索引保留各自可用的 Git 资源。

使用原始 0.4.0 Skill 内的更新器，分别通过默认云端入口、以及测试环境模拟云端和 GitHub 不可用后的真实 Gitee 入口完成 0.4.0→0.4.1 升级：各 2623 个文件逐字节一致，用户文件保留，二次检查无更新；MCP 模糊查询 20 候选、保护状态、SVD 查询均通过。故障注入仅在本地资格检查进程中，不修改线上保护状态。

修正的正式 NSIS 解包程序在空用户环境、Windows-only PATH 下 3.658 秒健康；41 个 Web 资源内容和 MIME 正确，无宿主 Python 子进程，原生页面显示 0.4.1、未连接目标时自动识别 V4.7.2，正常退出并释放端口/后台端点。

本机已安装的是通过覆盖安装验收的 0.4.1 候选，安装载荷版本元数据实际为 0.4.1。正式包再次覆盖安装未执行：旧窗口最小化后，桌面工具恢复与刷新状态互相阻塞，未强杀现有客户端。最终正式包以解包原生和冻结资格检查补充验证；不得把该结果写成已完成正式包覆盖安装。

## 正式入口

- [Windows 安装包](https://download.microkeenai.com/mklink/releases/v0.4.1/Mklink-AI-Probe-v0.4.1-x64-Setup.exe)
- [完整 Skill](https://download.microkeenai.com/mklink/releases/v0.4.1/Mklink-AI-Probe-v0.4.1-Skill.zip)
- [MicroKeen Release](https://github.com/MicroKeen/Mklink-AI-Probe/releases/tag/v0.4.1)
- [Gitee Skill 备用](https://gitee.com/Aladdin-Wang/Mklink-AI-Probe/releases/download/v0.4.1/Mklink-AI-Probe-v0.4.1-Skill.zip)

本地证据在上述 corrected 目录：`extracted-qualification.json`、`corrected-extracted-native-qualification.json`、`cos-direct-downloads.json`、`cos-release-downloads.json`、`route-backup-assets-verified.json`、`final-public-channels.json`、两份 `skill-upgrade-*-report.json` 和控制台操作截图。正式 Web 原样保存于后续提交 `93db90db`；这不改变不可变发布源。


## 保留约束

上海保护保持 90 GiB 告警、95 GiB 锁停，累计账本和现有周期保留；套餐截止北京时间 2026-11-26 00:00，未核验续费不得自动恢复。监控延迟、已签短链和在途传输可能造成超额，95 GiB 不是绝对计费上限。

旧 detached 工作树按用户要求保留，不强删；E 盘 main 工作区保留。双核实体正向脱机、V3 长时间掉线、UART 及历史限制不因本轮 V4 短测关闭。没有修改 VCC、OTP 或保护位。
