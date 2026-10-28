# Linux 0.4.1 DEB 测试包（2026-10-28）

维护者要求暂不升级版本，构建 Linux DEB 交其测试。产品版本保持 0.4.1，
源码为 `a6bdacbc04a53dbf8f31e72bb23457189cd8179d`，基于 main/`3cc474bb`。
正式 0.4.1 标签、资产、签名和更新索引均未改变。

## 构建与交付

- 共用分支 `codex/v0.4.2-fixes`，草稿 [PR #66](https://github.com/MicroKeen/Mklink-AI-Probe/pull/66)，未合并。
- 原生工作流原先同时启动全部 Unix 平台。本次增加 `target` 选择，实际仅调度
  `linux-x64`；macOS 未构建。工作流产物名称改为平台及源码提交，不再写死旧版本。
- [CI 运行 40637027269](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/40637027269)
  成功；Ubuntu 22.04 / x86_64、glibc 2.35、Python 3.12.15。
- 使用仓库 `build_unix.py` 和 `scripts/build_workspace.ps1`。本地验证及下载使用
  `F:/MKLink-Build`；Linux runner 使用仓库规定的 `.build`。
- 既有 Linux builder 同时生成 DEB/AppImage 并检查两种载荷。本次本地交付只提取
  DEB 与验证报告，不发布任何资源。
- 交付文件：`Mklink-AI-Probe-v0.4.1-a6bdacbc-linux-x64-test.deb`，184,069,386 字节。
- SHA-256：`7309f3772caf492942937d441bf4bdce0e6dcf12494273305012836da4cd9c8a`。
- 本地目录：`F:/MKLink-Build/artifacts/linux-deb-test-20261028-a6bdacbc`。
  含安装说明、SHA256SUMS、原始构建清单、冻结资格报告与本地 DEB 核验报告。

## 验证

- actionlint 1.7.12 通过；AI memory 测试 2 项通过。
- Linux USB 回归 58 passed / 1 skipped，跳过项是 Windows volume inventory。
- 构建校验内置 7,059 个 FLM 型号、2,224 个算法 blob，5,065 个 Pack 型号及
  4,800 个带 SVD 的外设型号。
- 从真实 DEB 解出后端，以限制 PATH 和空工程目录执行冻结 CLI 与 stdio MCP；
  `inspect_mcu`、`security_status` 通过，未连接硬件。
- 冻结后端 `/api/health` 返回 `ok`，3 项 Web 入口 JS/CSS 资源可读取，
  启动到健康 5.016 秒，正常关闭退出码 0。
- 本地核对 DEB 控制信息：包名 `mklink-ai-probe`、版本 `0.4.1`、架构 `amd64`。
  桌面程序和 sidecar 均为 x86_64 ELF，执行权限 0755；应用菜单文件和限定
  MKLink USB/tty 的 udev 规则存在，规则与构建产物一致。
- 完整 CI ZIP 为 622,990,579 字节，连接器超过 512 MiB 上限，CLI 全量下载缓慢。
  改用存储服务 HTTP Range 提取 DEB 与小型报告，验证 ZIP entry CRC 和 DEB
  SHA-256 与 CI 日志、构建清单一致；未声称完成整个 ZIP 的哈希验证。
  已清理中断的本地下载片段。

## 待用户测试与边界

本次是未发布测试包，没有 updater 签名。尚未认证用户 Linux 上的系统安装、
原生 WebView 交互、USB/MSC 实物连接或签名覆盖升级。冻结资格检查不能替代这些结果。
复制 DEB 到 Linux 后，在文件所在目录运行：

```sh
sudo apt install ./Mklink-AI-Probe-v0.4.1-a6bdacbc-linux-x64-test.deb
```

安装后从应用菜单打开 Mklink AI Probe，或运行 `mklink-ai-probe`；重新插入
下载器以应用包内 USB 权限规则。未改动探针固件、VCC、OTP 或云端服务。

本地 memory 测试留下含链接的临时目录
`F:/MKLink-Build/runs/run-20261028-132031-ed74f465`，按存储规则保留供人工处理，未强删。
