# Windows 0.4.1-rc.1 本地测试包

日期：2026-10-26。用户授权构建并安装包含固件升级、下载文件名和脱机下载器自动识别修复的 Windows 测试包，暂不正式发布。

## 构建

- 分支：`codex/v0.4.1-fixes`，源码提交 `15adc440`，对应生产 Web 资源单独保存为 `92e43811`。
- 版本：`0.4.1-rc.1`；标准 Windows x64 NSIS，使用 `build_workspace.ps1` 和 `build.py --local-bundle`。
- 文件：`F:/MKLink-Build/artifacts/v041-rc1-15adc440/Mklink-AI-Probe-v0.4.1-rc.1-15adc440-x64-Setup.exe`。
- 大小：184440324 字节。
- SHA256：`f968b7ca9876d14df46961ca490b21fd984524abad7d251ff1a9bf9a49e68dce`。
- 没有读取更新私钥，没有生成更新签名 `.sig`；没有 Authenticode，Windows 仍可能显示未知发布者。未创建 Release、标签、云端资产或更新索引。

FLM 复用主工作区已验证的资源，Pack 复用 F 盘校验缓存。STCP 源码与正式 main 相同，复用正式 0.4.0 解包中的同哈希 DLL；当前工作树的 `native/stcp_bridge/build` 是指向本测试包 `native` 目录的 junction，保留用于后续构建，不强删。

## 已通过的检查

- 完整构建成功，TypeScript、Vue、PyInstaller 和 Tauri/NSIS 完成。
- 解包后 211 份 Python 源文件、41 份 Web 资源与候选源码/构建结果逐字节一致。
- FLM：7059 型号、2224 个去重 blob 全部校验；Pack：5065 型号、4800 个 SVD 目标，STM32F407VE 寄存器目录实际加载成功。
- 仅 Windows 系统目录的 PATH、隔离空用户环境下，冻结 CLI/MCP 初始化、`inspect_mcu`、`security_status`、SVD 查询、后台健康、下载器枚举、Web 资源、诊断导出和正常退出通过；子进程没有宿主 Python。
- 构建及更新检查 60 项通过。原版本测试只接受纯数字正式版本，首次对 rc.1 失败；现允许正式版本或 rc.N，同时保留版本一致、签名启用、正式更新地址和公钥检查。

以上为包内容和冻结后台验证。尚未完成安装后的原生窗口与真实浏览器检查，不等同于正式发布验收。

## 安装断点

以仅 Windows 系统目录 PATH 启动 NSIS `/S /UPDATE /P` 后，Windows UAC 等待用户确认。已提示用户手动确认；随后系统返回“操作已被用户取消”，安装进程未启动成功。本次没有绕过 UAC 或重试安装。

当前已安装应用仍为 **0.4.0**。用户确认可以重试或自行完成安装后，再执行本地 `qualify-installed.ps1`、原生启动/退出及浏览器检查，最后交用户验证固件升级与脱机识别。

日志、解包内容、冻结资格结果、校验和及续接脚本都保留在同一 F 盘目录。正式包、主 main 工作区与旧 detached 工作树保持原状。
