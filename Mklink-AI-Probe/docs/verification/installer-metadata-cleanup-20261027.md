# Windows 覆盖安装旧元数据清理（下个版本待发布）

2026-10-27，产品修复源 `cb30b703`，继续 `codex/v0.4.1-fixes`，通过 PR #63 合并。
本次仅本地构建、测试和主分支集成；正式 v0.4.1 标签、签名、公开包、云端资源和更新索引保持不变。

## 根因与改动

NSIS `/UPDATE` 覆盖写入新文件却保留旧 `mklink-0.3.6.dist-info`。
安装后的运行时代码为 0.4.1，但 `importlib.metadata.version("mklink")`
选中了旧元数据，导致更新检查误报当前版本 0.3.6；清空更新缓存不能解决此问题。

- PREINSTALL 先执行现有文件占用检查，再清理 `_internal` 下 MKLink 的旧
  `mklink.egg-info` 与版本化 `mklink-<数字开头版本>.dist-info/.egg-info`。
- 先预检全部候选，再逐文件删除；不递归清除目录。
  锁定、只读、嵌套目录、junction/reparse point 会停止安装，不写入新载荷。
- 保留其他发行包元数据和用户配置；新载荷随后恢复当前 MKLink 元数据。
- PyInstaller 冻结前从当前 `pyproject.toml` 重新生成元数据并核对名称/版本，
  确保当前源码优先于宿主环境中的旧 editable 安装记录。

## 验证

- 实际 NSIS 清理、构建元数据和构建器回归：62 项通过。
- 全 Python：5577 passed、2 optional HIL skipped；全 GUI：1133 passed。
- TypeScript/Vite、Rust/Tauri 与完整 Windows NSIS `--local-bundle` 构建成功。
  本地测试包 SHA-256：`34282c6692a517417a3a98bce1ef05cc8dbaf9fda5dc956c34545be993746690`。没有生成更新签名或执行发布。
- 从备份恢复真实旧版八个元数据文件：冻结 MCP 的运行时版本 0.4.1、
  更新检查当前版本 0.3.6，复现成功。
- 实际 `/S /UPDATE /P` 覆盖安装 exit 0；旧目录自动移除，新元数据与
  冻结 MCP/更新检查均识别为 0.4.1。没有手工删除来替代安装器验收。
- 207 个其他依赖元数据/用户配置及测试保留文件的 SHA-256 未变。
- 初次 MCP 检查被测试自建的非规范 `mklink-helper-1.0.dist-info` 目录
  干扰而返回 unknown；将该测试目录改为规范的下划线名称后通过。
  原始失败日志和修正说明已保留。真实旧 MKLink 元数据仍由安装器自动清理，
  没有用手工清除旧元数据代替验收，也未因此改动产品代码或重构建安装包。
- 实装 3626 个载荷逐文件一致；211 Python 源文件、
  41 Web 资产一致；完整内置 FLM/Pack 校验、冻结 CLI/MCP、后台健康与正常退出通过。
- Windows-only PATH、隔离用户目录下原生启动 3.767 秒健康；
  无宿主 Python 子进程；真实浏览器 Web 仪表盘和配置页面加载通过；
  正常关闭后端点和监听端口释放。
- 本轮没有操作目标 MCU、升级探针固件、改动 VCC/OTP；不扩大历史硬件验收结论。

## 清理与交接

已删除两份可从保留安装包重新解出的旧测试目录，释放 624.2 MiB；
正式包、候选安装包、独有证据、复现样本和共享缓存保留。
测试目录中的链接未强删，清单保存在本地 `cleanup-skipped-links.json`。
旧 detached 工作树和 E 盘原 main 工作区保留。

本机安装的是本次本地验证包（仍标记 0.4.1，未签名、未发布），
后续从 main 正常准备下个版本时包含此修复；不要重发 0.4.1。
Windows 现有未知发布者限制不变。没有执行断电中断或并发外部篡改安装目录的认证。

本地完整证据：`F:/MKLink-Build/artifacts/installer-metadata-cleanup-20261027`。
