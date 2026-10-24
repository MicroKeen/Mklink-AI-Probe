# 0.3.6 修复候选本机覆盖安装

2026-10-19，维护者明确要求“直接打包覆盖安装，我测试一下”。从干净源码 `2b3d552831e5fff935998f433d81bd33643cf3e7` 构建本机 NSIS，包含 RTT 终端隔离解析和 SuperWatch 原生目录选择/提前记录改进。版本号仍为 `0.3.5`，界面构建号为 `2b3d552831e5`；这是本地测试包，不是正式发布。

## 构建与安装

- 通过 `scripts/build_workspace.ps1` 执行 Tauri builder `--local-bundle`，TypeScript、Vite、Rust 和 PyInstaller 构建成功。无更新签名或 Authenticode 签名。
- 首次构建缺少内置 Pack 路径而终止；显式指定现有已验证的内置数据后成功，未修改全局 Skill。最终包包含 7059 个 FLM 目标、2224 个算法 blob、4800 个 SVD 目标。
- 原安装版正常关闭后进程和监听端口释放；标准 NSIS 原地覆盖安装退出码为 0，保留用户配置。
- 安装包及本地证据保存在 `MKLINK_BUILD_ROOT/artifacts/v036-local-2b3d5528`，包括 `install-result.json`、`installed-qualification.json`、`sha256.json`、提取载荷和生产 Web 副本。
- 安装包 SHA256：`A69F9A7CB835C53EFE52B62A9CCA12C04CA42F929BD2F3469AA500DF7F46E96B`。

## 实装验证

| 检查 | 结果 |
| --- | --- |
| 源码与生产资源 | 冻结包内 198 份 Python 源文件、40 份 Web 资源逐字节一致 |
| 安装文件 | GUI、sidecar、STCP DLL、第三方声明四份载荷与提取安装包一致 |
| 独立运行 | Windows-only PATH 下 CLI、内置 SVD 查询、冻结 MCP 初始化及 inspect_mcu/security_status 通过 |
| 后台 | 独立运行 health、只读探针枚举、40 份 HTTP 资源一致，无宿主 python.exe 子进程 |
| 正常退出 | 独立验证后台正常退出且端点释放 |
| 实际页面 | 安装版原生窗口及 Chrome 生产页面显示 `v0.3.5 · 2b3d552831e5`、后台正常；Chrome 无控制台 error |

未绑定探针的独立运行时对 recording/start 返回既有身份保护 `409/unselected`，在进入记录处理器前拒绝请求。最初两次验证脚本错误地假定未绑定也能记录，因此失败；修正为验证身份保护后整套检查通过。该保护不同于已经移除的“必须先开始采集”限制。连接后提前记录与完整原生目录确认链留给用户实测；manager/HTTP 夹具验证见 [SuperWatch 报告](v036-superwatch-recording.md)。RTT 行为验证见 [RTT 报告](v036-rtt-hex-fix.md)。

最终保留新安装版窗口运行、设备未连接，交用户测试；只关闭本次创建的 Chrome 验证页。没有操作目标硬件、烧录、修改全局 Skill、合并 PR、发布或移动标签。构建后的 Web 资源和本报告另行提交，安装包固定使用上述源码提交，不因交接文档提交改变其构建号。
