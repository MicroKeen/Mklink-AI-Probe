# macOS Apple Silicon 0.4.1 DMG 测试包（2026-10-28）

维护者在 Linux DEB 测试包之后要求再构建 macOS 安装包，并明确选择
Apple Silicon。产品版本保持 0.4.1，构建源为
`eefc68420f3cf4a9ad73e3d588d975ecccf4f2cd`；与 Linux 包源 `a6bdacbc`
相比只有交接文档变化，产品代码相同。

## 构建与交付

- 共用分支 `codex/v0.4.2-fixes`、草稿 [PR #66](https://github.com/MicroKeen/Mklink-AI-Probe/pull/66)，未合并。
- 使用现有 `desktop-unix.yml`，仅调度 `target=macos-arm64`，未重建 Linux 或 Intel 包。
- [CI 运行 40640511140](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/40640511140)
  成功；macOS 14.8.9 arm64 / Python 3.12.10，目标 `aarch64-apple-darwin`。
- 使用仓库 `build_unix.py` 和 `scripts/build_workspace.ps1`。
  本地下载及验证使用 `F:/MKLink-Build`，原生 runner 使用仓库规定的 `.build`。
- 交付文件：`Mklink-AI-Probe-v0.4.1-eefc6842-macos-arm64-test.dmg`，165,645,058 字节。
- SHA-256：`56dc8e0ae77f9fb83195f8f1c983b234d5d68f8a3e273ef9ce622f273fd658cc`。
- 本地目录：`F:/MKLink-Build/artifacts/macos-arm64-test-20261028-eefc6842`，
  包含安装说明、SHA256SUMS、构建清单、冻结资格报告和本地核验记录。
- 构建器还生成未签名的 `.app.tar.gz` 更新载荷并与 DMG 比较；本次本地交付
  仅提取 DMG 及小型报告。没有发布、读取发布私钥或修改正式资产、标签和更新索引。

## 验证

- USB 平台、接口、发现及卷枚举相关回归：58 passed / 1 skipped；
  跳过项为 Windows volume inventory。
- 内置资源校验：7,059 个 FLM 型号、2,224 个算法 blob，
  5,065 个 Pack 型号及 4,800 个带 SVD 的外设型号。
- 原生 CI 挂载实际 DMG，将 `.app` 复制到测试工作目录，使用包内后端完成
  冻结 CLI、stdio MCP 的 `inspect_mcu` / `security_status`，均通过。
- 限制 PATH、空工程目录下，后端 `/api/health` 返回 `ok`，内置 ELF 可用，
  3 项生产 Web 入口 JS/CSS 资源可读取，5.17 秒达到健康状态，正常关闭退出码 0。
- 解出 `.app.tar.gz`，核对桌面程序和 sidecar 与 DMG 内的可执行文件哈希一致，
  可执行权限保留。
- 本地通过 HTTP Range 从 CI artifact 提取 DMG，核对 ZIP entry CRC；
  DMG 字节数、SHA-256 与 CI 日志及构建清单一致，UDIF `koly` 尾部标记正确。
  构建清单的版本为 0.4.1、目标为 arm64。本地 Windows 不重复声称执行过 macOS 挂载。
- 构建源对应的 Feedback checks、Shared runtime checks 已通过；
  本次交接记录渲染及 AI memory 校验通过。

## 待用户测试与分发边界

将 DMG 复制到 Apple Silicon Mac，打开后把 Mklink AI Probe 拖到 Applications。
该测试包仅使用 ad-hoc 签名，没有 Apple Developer ID 签名或 Apple 公证，
首次启动可能受 Gatekeeper 拦截。未完成用户系统上的安装、原生 WebView
交互、USB/MSC 实物连接或签名覆盖升级认证；DMG 挂载与冻结资格不能替代这些结果。

正式 0.4.1 保持不变。未改动探针固件、VCC、OTP 或云端服务；后续正式发布仍需
本次明确指令。Linux 测试包及其证据继续保留。
