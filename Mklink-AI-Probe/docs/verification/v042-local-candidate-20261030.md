# 0.4.2 Windows / 完整 Skill 本地候选验收

2026-10-30，维护者明确要求重新打包、覆盖安装和交付。两个包均为本地测试候选；未正式发布、签名、合并、改索引或覆盖 0.4.1 正式资产。

## 产物

| 产物 | 字节 | SHA256 |
| --- | ---: | --- |
| `Mklink-AI-Probe-v0.4.2-dce17d3e-test-x64-Setup.exe` | 185922428 | `f70e496074ff274ad33a1c64dec222d042d9c8ff26025e7468fcfebcbf463bec` |
| `Mklink-AI-Probe-v0.4.2-Skill-test-0d680d90.zip` | 99662264 | `a126d967ee85badda443cf20bba385186cde5007ada7fcc75f9e1fb441e947db` |

Windows 产品源为 `dce17d3e9d1631c3bd18bd465a27ae9ff3e82e89`；Skill 归档源为 `0d680d90e2bb1ac99d370de6f6578f5c9a96801c`。
后续提交仅保存本次编译的 Web 资源及修复归档换行转换，运行时代码一致。
Windows 的 `core.autocrlf=true` 会在子树 `git archive` 中改变资源字节，因为子树看不到仓库根属性；归档命令现显式关闭转换。真实归档回归通过，41 个 Web 文件与 NSIS 内置资源逐字节一致。

## 覆盖安装与实际运行

- Windows NSIS 覆盖退出码 0，保留用户设置；3,640 个安装载荷文件与安装包一致。
- 完整 Skill 从 0.4.1 更新为 0.4.2，2,638 个文件一致，5,339 个用户文件保留；旧 Skill 已备份。当前 AI 客户端需重连 MCP 使用新进程。
- 全局 Skill 实际 MCP 版本 0.4.2、47 工具；九个 HPM 系列及原始 XML SHA256 通过。7,059 个 FLM 型号、2,224 个算法块和 4,800 个 SVD 型号通过资源验证。
- 冻结 CLI/MCP/健康接口、HPM 系列及型号回退匹配、41 个原生服务 Web 文件通过；原生进程树未使用主机 Python，限定 Windows PATH 验证。临时计时模块及钩子未出现在 Skill 或冻结代码中。
- 真实桌面显示 v0.4.2、后端正常；版本记录包含 11 条本轮更新。正常关闭后原生进程退出，8765/8766 监听释放。

## 当前包的实机结果

普通 V4 / 私有 V4.7.2 配合 STM32H7，以本次安装的冻结后端和完整 Skill SDK 进行验证。
配套固件由指定会话交付并预先安装，UF2 SHA256 为 `ea5a6f9d14b7ac67ada733aec6dfbcce87a1d2fcc2614caf10ea0fe8b46a19ff`；本轮未再次升级固件。
首次读和首次写均自动建立 MUX。只在已批准 RAM 测试缓冲首 128 B 写入，逐次回读、恢复并检查完整 4 KiB，最终物理断开，未遗留恢复任务。无 Flash 写入、暂停/复位、VCC 或 OTP 操作。

下表是新版安装后的当前完整测量，不筛选最快一次。单位 ms，每项 20 次；P95 仅描述本次样本，不承诺时延上界，也不是 SuperWatch 连续采样率。

| 操作 | 字节 | 次数 | 中位数 | P95 | 最大 |
| --- | ---: | ---: | ---: | ---: | ---: |
| status | 0 | 20 | 3.848 | 14.477 | 16.971 |
| read | 4 | 20 | 7.514 | 17.837 | 18.229 |
| read | 32 | 20 | 13.375 | 19.631 | 26.161 |
| read | 128 | 20 | 17.987 | 18.961 | 24.099 |
| read | 4096 | 20 | 21.353 | 27.148 | 39.074 |
| write | 4 | 20 | 7.923 | 18.847 | 36.798 |
| write | 32 | 20 | 7.986 | 18.699 | 24.149 |
| write | 128 | 20 | 8.627 | 18.713 | 18.854 |
| write_verified | 128 | 20 | 12.039 | 22.455 | 28.671 |

## 验证范围

本次版本/打包回归：14 项元数据、5 项版本记录、10 项归档测试通过；Windows 生产构建成功。
底层运行时 1,224 项相关回归及前序 HPM Flash/RTT/XML 实机证据见已有报告，本轮未把旧硬件数据改标为新包验收。
HPM 新整块读、V3、其他芯片及并发需要单独实板验证；旧 Linux/macOS 候选未重建。

本地证据目录 `F:/MKLink-Build/artifacts/v042-combined-20261030`：
`latest-package-qualification.json`、`installer-manifest.json`、`test-skill-manifest.json`、`install-result.json`、`installed-payload.json`、`skill-install-verified.json`、`installed-hardware.json`、`installed-sdk-statistics.json`、`installed-smoke.json`、`native-qualification.json`、`native-ui-state.txt`、`native-exit.json`、`final-check.json` 和 `SHA256SUMS.txt`。
原始本地硬件标识及日志不提交仓库。用户交付只指向本次最新两个包及校验表。
