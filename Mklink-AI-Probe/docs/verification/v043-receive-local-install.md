# 0.4.3 接收修复的本地覆盖安装

2026-11-04，按用户授权在 `codex/v0.4.3-fixes` 构建并覆盖本机 Windows。
最终安装源 `f9b1ae8afd308dc15fbf4d4690f3b545104444aa`，采集实现与
`0a0c97b3` 相同；本次只修正中英文更新记录并同步生产 `gui/dist`。
已安装版本包含 [接收积压与连续性修复](v043-receive-backpressure.md)。

## 安装结果

- 标准 Windows x64 NSIS，版本 0.4.3，使用 `--local-bundle`。
- 文件 `Mklink-AI-Probe-v0.4.3-f9b1ae8a-local-x64-Setup.exe`，186042518 字节。
- SHA-256：`55d17d0ef4bfcbe639193efa2eb9480040b6a163c961c833337b6b471f22c893`，安装后再次核对。
- 覆盖退出码 0，两项已有配置哈希不变。无 updater 签名或 Authenticode，仍有未知发布者限制。
- 全部构建和测试经 `scripts/build_workspace.ps1`，根目录 `F:/MKLink-Build`。
  原正式资产和缓存保留；未合并、签名、发布、切换更新索引或修改探针固件。
  全局 Skill 和独立 SiteAgent 仍为 0.4.2。

## 验证

1. 冻结载荷与安装目录的 3649 文件逐一匹配，含整个 `_internal`。
2. 内置 FLM 7059 型号/2224 blobs、Pack 5065 型号/4800 SVD 型号验证通过。
3. Windows-only PATH 下冻结 MCP 初始化、56 工具、`inspect_mcu` 和
   `security_status` 通过；未打开硬件。
4. 冻结后台健康、版本 0.4.3、探针被动枚举、42 个 Web 资产逐字节匹配、
   STM32F407VE 内置 SVD 查询通过。安装包 SVD 用源码解析器另外验证 11601
   目录项；这项解析检查不冒充冻结后台的完整寄存器加载实测。
5. 原生窗口及真实内置浏览器显示健康的 0.4.3；SuperWatch 无旧的阈值统计。
   原生更新记录正确说明实际时间戳 Hz、明确缺失置灰、不以 20 µs 阈值判丢失。
6. 原生进程树无宿主 Python。正常关闭后本次 11 个进程及端口全部释放，
   未关闭其他开发后台。版本记录组件既有 5 项测试通过，生产构建通过。

首包源 `23150a8a` 已通过覆盖和冻结检查，但原生检查发现更新记录仍描述旧的
最大间隔/空隙数界面。修正文案后重新完整构建、覆盖并重做上述资格，首包及
证据保留。第一次安装命令使用了不存在的 PowerShell 路径，尚未执行安装即失败；
改用实际 `pwsh` 路径后通过。没有隐去失败或把首包作为最终交付。

本次安装资格不代替新的硬件性能测试。原采集实现的 A/B/A 完整性与性能见
[AHB 对照](v043-control-ahb-ab.md)；最大间隔 20 µs 和 40 µs 零漏采仍未达到。
用户另外授权的最小 ILM B 已完成 A/B/A：有局部 ECHO 间隔收益，最大间隔和
40 µs 零漏采仍未达，不采用候选；原 USB7 已恢复并反测，见[ILM 对照](v043-control-ilm-b-ab.md)。

后续 ILM 编译曾在链接前因 F 盘空间耗尽失败。先验证原 NSIS 的 SHA-256 和
7-Zip 完整性，再清理本次两个安装证据目录中的重复 `payload/` 副本，
释放 680533734 字节逻辑长度；安装匹配报告、安装器及其他原始证据保留。
用户随后明确不使用 D 盘，并授权清理 E/F 的旧记录和临时测试脚本；
这轮已完成，范围、保留边界和磁盘实测见[历史空间清理](v043-workspace-cleanup.md)。
ILM 链接/性能资格仍单独进行，清理本身没有刷设备。

证据根：`F:/MKLink-Build/artifacts/v043-install-f9b1ae8a-20261104/`。
安装器、`installer-manifest.json`、`install-result.json`、`installed-smoke.json`、
`native-check.json`、`exit-check.json`、`version-tests.log`、`version-notes.jpg`
及构建日志仅本地保留，不入 Git。
