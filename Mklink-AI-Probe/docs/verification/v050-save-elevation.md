# V0.5.0 下载保存与受保护目录覆盖修复

用户要求保持产品版本、版本说明不变，修复后替换腾讯云 Windows 安装包和完整 Skill；2026-11-16 明确授权合并并同步 GitHub 备用包及校验索引。实现提交 `4ff4b9db`，生产 GUI 资产提交 `5bbc035b`，证据提交 `f278a821`。PR #86 在该精确 HEAD 的三项 CI 全通过后合并，main 为 `a38557b93ed0ec0efdb007ea72ebb06b4cff408b`。

## 原因与改动

- Web 固件下载先等待 HTTP 返回，再调用 `showSaveFilePicker`。慢速响应可能超过浏览器的临时用户激活期限。公共保存函数现在检查激活状态，过期时使用浏览器下载；选择器本身返回 `SecurityError` 时也回退。取消仍取消，选定文件后的写入错误仍报错，不再启动第二次下载。Tauri 原生保存路径不变。
- 当前按用户安装的 NSIS 能恢复旧 Program Files 路径，但普通令牌无法写入；旧检查直接报 Windows error 5。新安装器仅在文件或旧进程访问被拒绝时，通过 Windows UAC 重启同一个安装器，保留所选目录、安装参数及退出结果。拒绝提权不会写入新载荷；已经重启或已经提权时不再循环请求。
- 为避免把 HKCU 配置、快捷方式写入另一个管理员账户，自动提权校验原账户。不同账户在载荷写入前停止，不擅自迁移用户配置。首次用户安装仍为 `asInvoker`，不修改端口名称、目录 ACL 或设备权限。

## 已完成的验证

- Windows PowerShell 7、UTF-8；全部构建/测试经 `scripts/build_workspace.ps1`，BuildRoot 为 `F:/MKLink-Build`。
- Python 全量：7,195 通过、2 跳过，954.47 秒。包含独立 Site Agent 重建、现有安装文件占用/进程隔离检查和新 NSIS 测试。
- GUI 全量：114 文件、1,299 项通过，102.19 秒。
- NSIS 新增测试执行实际重启代码，仅将 ShellExecute 的 `runas` 替换为 `open`，验证中文/空格/单引号目录、参数、退出码 0/2/1223、目录页选择和不同账户拒绝。它不替代真实 UAC 验收。
- 真实 Chrome + 旧生产 GUI，HTTP 测试响应延迟 6.5 秒，复现与客户相同的 `Must be handling a user gesture`。未连接、升级或刷写任何探针；下载使用合成字节，仅用于保存校验。
- 新生产 GUI 及完整 Skill ZIP 内的 GUI 分别在真实 Chrome 完成相同慢响应测试：V2、V3、V4、HPMLink 四个文件名称及 409,600 字节逐一一致，激活已过期，无页面错误或设备操作请求。
- 实际打包安装器保持 `asInvoker`。受保护 NTFS 测试目录普通令牌确实不能写：取消 UAC 返回 1223，旧文件和安装登记保持；同意 UAC 返回 0，3,687 个载荷文件一致、指定路径保持，安装后启动的桌面进程令牌为 8192（普通用户）。此前另一次确认轮返回取消，重新执行成功轮后才记录通过。
- 新目录普通安装、显式 D 盘覆盖及无 `/D` 的 D 盘覆盖均退出 0。无 `/D` 轮验证六份设置保留、HKLM 安装登记和 USB 名称不变、无 C 盘用户目录副本、全部载荷一致。
- D 盘安装后的冻结后台在仅含 Windows 系统目录的 PATH 下通过 CLI、真实 stdio MCP 初始化及器件/安全状态/SVD 查询；59 个 MCP 工具，版本 0.5.0，7,059 算法目标/2,224 FLM、4,800 SVD 目标完整。真实桌面普通权限启动，健康检查/探针枚举通过，无 Python 子进程；包内 Web GUI 页面显示后端正常，正常关闭后进程树和监听端口释放。
- 完整 Skill 使用提交 `5bbc035b` 的运行时白名单构建，包含相同算法/SVD 资源及新 GUI；拒绝安装目录录制、允许用户工程目录录制。未替换全局 Skill。验收脚本的首次关闭检查仅捕获 `ConnectError`，Windows 关闭端口实际返回连接超时；改为直接核对监听表后，重新启动/正常关闭验证通过。
- 打包环境检查通过；产品版本文件及发布说明未修改。

## main 最终包复验

- 从干净 main `a38557b9` 经工作区构建脚本生成 Windows NSIS 和完整 Skill。最终安装包 187,248,206 字节，SHA-256 `29ff1d3450976fd2afa1a9ac88113f68f97b0fbd54b21a9333121c36e09c4517`；更新签名和 trusted comment 签名均验证通过。
- 完整 Skill 99,839,506 字节，SHA-256 `03aaa1093e2397965e0ba5dff2866490dd408048c4407556a982bfe5b01ed80d`。包内 47 个 GUI 资产与已验收的生产 GUI 一致。
- 最终签名安装器再次无 `/D` 覆盖现有 D 盘安装，普通令牌 8192、退出 0；3,687 文件一致，六份设置、HKLM 登记、USB 名称保留，无新增 C 盘副本。
- 最终安装版冻结 CLI/MCP、真实桌面和 Web GUI、正常关闭并释放端口均通过；安装版 GUI 四型号慢下载再次通过。未刷写探针或目标板，未替换全局 Skill。
- 构建生成的 GUI 资产已独立 stash 保留，未回写 main。最终包证据位于证据根目录的 `final/` 和 `browser-final/`。

## 双渠道发布完成

- 2026-11-16 GitHub 五个新附件与五个旧附件均经匿名完整下载校验。新附件名含 `a38557b9`，旧附件 ID、大小、哈希、原 `v0.5.0` 标签与发布正文保留。跨渠道文件名映射见发布 manifest；SHA256SUMS 使用腾讯云原文件名。
- GitHub `release` 最终为 `5539a7b51795299fe9f495d6bf8e036fe236a9f2`，仅更新 Windows 和 Skill 的索引字段。第一次发布辅助脚本用 Windows 文本 stdin 创建 Git tree，误将 `latest.json` 写成带 CR 的文件名；公开回读发现 404 后，以二进制 NUL 分隔输入生成修正提交，非强制推送。最终不带查询参数的公开索引回读与预期完全一致。没有改动 main、标签或版本说明。
- 腾讯云保持五个原下载路径，索引和目录中的新 URL 增加 SHA-256 查询参数，五条精确文件路由使用 `no-store`；回退 URL 指向 GitHub 新附件。服务器暂存哈希、公开 HEAD、Range 和完整 GET 下载哈希均一致。
- 临时移开签名文件进行 GET/HEAD 回退验证，两次均跳转正确的新 GitHub 附件，随后恢复签名。未移动安装包或固件。
- 腾讯云稳定索引、下载目录与 GitHub 索引公开回读通过；版本 `0.5.0`、原发布日期、发布说明、其他平台条目和两个固件索引保持不变。
- 上传中清单连接中断，检查已有文件哈希后仅补传缺失文件；本机 Python 3.14 的大文件 SSL 读取中断后改用 curl 完整下载校验。中断不计作通过。
- 临时 HTTPS 上传路由及 localhost 接收进程已移除，公开入口返回 404。确认新文件与历史 GitHub 文件完整后，仅删除服务器 10 份本轮暂存/回滚副本，共 574,180,374 字节；保留小型配置备份和验收记录。
- 腾讯云稳定索引 SHA-256：`fc35da3eb3c256b6c6c1dff8519f66749f347408b1a2cb5b57a3781a73cddae2`；下载目录 SHA-256：`f24f6ab1df4c9521153b6f3f9001812ad33eb990791acd8583117dea6e3b4635`。

用户已有 V0.5.0 时仍需重新下载并手动覆盖；同版本修订不会伪造更高版本号。覆盖后重新加载 Skill/MCP 宿主进程。普通新安装不提权；受保护旧目录需要同账户 UAC，不改变目录权限。

发布阶段自动审批曾以 `blocked by policy` 拒绝 `fresh-install`、`payload`、`skill-check` 清理。用户随后明确授权收尾清理，经重新盘点和路径校验后，本轮使用原生 PowerShell 删除成功；这三处目录已不再残留。

## 收尾清理与下一会话

- 2026-11-16 收尾清理删除 4,187,319,287 字节（3.90 GiB），其中安装测试副本/中间包/重复下载等 3,074,987,459 字节，测试运行目录 1,112,331,828 字节。F 盘盘点时余量 16.53 GiB。
- 核对并移除 5,233 个指向本轮 `runs` 内的测试符号链接，只删除链接本身；再经工作区清理入口和普通 PowerShell 清理无链接的运行内容。链接目标在解除链接时保持，最终无测试链接残留。没有改 ACL、提权或终止残留进程。
- 最新及上一版正式安装包、Skill、签名、manifest 和校验清单共 10 个文件保留，清理前后 SHA-256 一致。重复文件逐一与保留原件核对大小/哈希后删除；截图、日志、结果 JSON、主工作区生成资产 stash、可复用缓存和其他任务工作区保留。
- 当前用户无修改权限的 `F:/MKLink-Build/artifacts/v050-save-elevation-20261116/protected legacy 中文 install` 保留（约 326.6 MiB）。Windows 拒绝删除以下三个测试 EXE，共 143,760 字节；不改权限、不换手段重试，交维护者手动处理：
  - `F:/MKLink-Build/runs/run-20261116-104634-db54d3bf/pytest/test_preserves_directory_flags0/relaunch.exe`
  - `F:/MKLink-Build/runs/run-20261116-104634-db54d3bf/pytest/test_preserves_directory_flags1/relaunch.exe`
  - `F:/MKLink-Build/runs/run-20261116-104634-db54d3bf/pytest/test_preserves_directory_flags2/relaunch.exe`
- 清理清单和逐项证据：`F:/MKLink-Build/reports/cleanup-v050-20261116-summary.json`、`cleanup-v050-20261116-artifacts-result.json`、`cleanup-v050-20261116-links-result.json`、`cleanup-v050-20261116-runs-result.json`。手动处理路径另列于同目录 `cleanup-v050-20261116-manual-paths.txt`。
- 用户指定下一会话开始 0.5.1 修复：先 `git fetch microkeen`，核对 main、工作树和本交接 PR #87；从届时最新 `microkeen/main` 创建 `codex/v0.5.1-fixes`，不延续 0.5.0 修复分支。本轮不创建 0.5.1 分支、不修改当前 V0.5.0 版本或发布信息。

本机证据根目录：`F:/MKLink-Build/artifacts/v050-save-elevation-20261116`。浏览器测试文件是合成载荷，禁止刷写或发布。
