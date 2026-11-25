# Windows 0.5.1 修订包与完整 Skill

2026-11-25，腾讯云稳定更新索引和下载中心已切换到 `r20261125`。版本号为 0.5.1。修复来源为 [PR #96](https://github.com/MicroKeen/Mklink-AI-Probe/pull/96)，正式构建提交为 `11202db06a30c928e86ff3fd51806adbf9d7a3c8`。macOS、Linux、现场代理、下载器固件及 GitHub 正式下载沿用首发包。

## 已安装旧版的用户

0.5.0 的旧桌面会在有其他后台时拒绝安装。可从[腾讯云下载中心](https://download.microkeenai.com/)获取 Windows 修订版并覆盖安装。已安装 0.5.1 首发版的用户也可手动安装同版本修订。新版提示更新后点一次“立即安装”即可。遇到下载器固件升级时会等待并自动继续，等待期间可取消。

## 验证

- Windows 同时运行两个独立桌面后台，旧预约接口返回 HTTP 409。使用带修复代码、原生版本标识为 0.5.0 的验收客户端，点一次按钮后等待真实跨进程固件锁，释放后完成正式签名 NSIS 覆盖安装。新桌面报告 0.5.1，再检查无更新，并恢复原 STM32 工程连接。测试使用固件锁模拟写入阶段，未刷写下载器。
- Windows 安装程序在旧桌面退出后继续持锁。NSIS 与 Python 的双向互斥经实际进程测试，涵盖等待、写入和释放。
- 最终 PR 提交的 Python 全量 7991 项通过、2 项跳过。GUI 1,474 项和 Rust 24 项通过，安装器及固件专项 56 项通过。GitHub 三项 CI 均通过。
- 旧版完整 Skill 通过真实腾讯云稳定索引升级后，2,739 个文件逐项核对，保留用户文件，通过 MCP 握手和 SVD 查询。
- 公网对安装包、签名、完整 Skill、校验清单、发布清单做了完整 HTTPS 下载及 Range 校验。稳定索引与下载中心均指向修订件。

| 下载 | 字节 | SHA-256 |
| --- | ---: | --- |
| [Mklink-AI-Probe-v0.5.1-r20261125-x64-Setup.exe](https://download.microkeenai.com/mklink/releases/v0.5.1/Mklink-AI-Probe-v0.5.1-r20261125-x64-Setup.exe) | 188,128,318 | `1daac161daef69a1b85baa9a9050ed9db75a90d9e447bf34c93a568acbeb8a77` |
| [Mklink-AI-Probe-v0.5.1-r20261125-Skill.zip](https://download.microkeenai.com/mklink/releases/v0.5.1/Mklink-AI-Probe-v0.5.1-r20261125-Skill.zip) | 100,848,786 | `379a7f574a918f9efa6b398815c87a6c1961f776cdd6f800d49996c022c41af8` |
