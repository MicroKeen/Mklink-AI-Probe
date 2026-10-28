# 0.4.1 收尾与 0.4.2 开始交接

2026-10-28 接手更新：E 盘主工作区已从 `microkeen/main` 的 `3cc474bb`
创建并切换到共用分支 `codex/v0.4.2-fixes`，无需再次创建。
按维护者要求保持 0.4.1，已完成 Linux x64 DEB 测试包，待用户实机测试；
证据见 [Linux 测试包报告](../verification/linux-deb-test-20261028.md)。
平台选择改动及交接记录在草稿 PR #66，未合并、未发布。
后续多个修复继续共用此分支，正式发布需要本次明确指令。
以下保留 2026-10-27 收尾时的交接背景，当前断点以 CURRENT_HANDOFF 为准。

维护者 2026-10-27 要求：完成交接后删除已无独有工作的 0.4.1 修复分支，
本地回到原 main 工作区；下个会话从最新 `microkeen/main` 新建
`codex/v0.4.2-fixes`。本次不提前创建新分支、不改版本号、不发布。

## 下个会话从这里开始

1. 主工作区为 `E:\software\HPM5300\Mklink-AI-Probe`，源码在同名子目录。
2. 读取 `docs/ai/CURRENT_HANDOFF.md`、本文件和
   `docs/verification/installer-metadata-cleanup-20261027.md`。
   通过 `scripts/build_workspace.ps1 -BuildRoot F:/MKLink-Build` 验证 AI memory。
3. 先检查 Git 实际状态、工作树和远端，再 fetch `microkeen`。确认 main 干净且
   可快进到最新远端，然后从最新 main 新建 `codex/v0.4.2-fixes`，不直接修改 main。
4. 0.4.2 的具体任务由维护者指定。不要自动开始公网中继、固件迁移或重新发布。
   已有安装器修复会随下个版本正常发布。

## 已完成与不可混淆的版本

- PR #61 已合并并正式发布 0.4.1，正式标签指向 `514efb86`。
  正式包不包含随后完成的旧元数据清理修复，不得重签、重传或重发相同版本。
- 正式安装包：
  `F:/MKLink-Build/artifacts/v041-release-corrected/release/Mklink-AI-Probe-v0.4.1-x64-Setup.exe`。
  SHA-256：`30333c335be4659d10dfa5123463f00553ae35446321931919df6aa84856c621`。
- PR #63 已合并，产品修复源 `cb30b703`，合并提交 `d5bb68e3`。
  NSIS 覆盖安装自动清理 MKLink 自身旧元数据，冻结前刷新并验证元数据。
  实际旧 0.3.6 元数据复现、自动清理覆盖、版本识别和启动退出验证已通过；
  5577 Python / 2 optional skips、1133 GUI、62 定点、71 文档及三项 CI 通过。
- 本机安装的是未发布的本地测试包，版本号仍为 0.4.1；
  正常用户配置下启动成功，原 10 MHz 设置保留。
  测试临时配置不等于用户配置丢失。完整证据在
  `F:/MKLink-Build/artifacts/installer-metadata-cleanup-20261027`。
- 自动审批拒绝清理安装目录内两个测试占位文件，共 82 字节；
  它们不在 Git 或安装包中，也不影响版本识别。路径及拒绝记录见证据目录的
  `cleanup-install-fixtures-blocked.txt`。不得将其当作产品文件或强删依据。

## 保留的约束与未完成项

- 原 main 工作区保留。旧 `firmware-keil-coexist` detached 工作树按维护者要求
  保留，不再尝试强删。0.4.1 工作树归档前先检查忽略文件并保存需要的内容；
  若 Codex 报告主工作树受保护，则保留该目录，不绕过保护。
- 上海 COS 仍为 90 GiB 告警、95 GiB 停下载，存在监控延迟，非绝对计费上限。
  套餐记录截止北京时间 2026-11-26 零点，未续费不自动恢复；保留流量账本。
  香港旧桶已删除，不重新创建、不申请新私钥。
- 下载保持云端优先、Git 备用。维护新 MicroKeen GitHub 与既有 Gitee；
  正式资源与更新指针保持不变。
- 本机此前使用 V4.7.2 私有候选，下一会话须重新核对现场，不降级或发布候选。
  双核脱机真实板验收、V3 长时间掉线等未闭环事项继续保留，不扩大既有验收结论。
- 公网中继留给维护者后续明确任务；固件 GitHub 备用源迁移等待办见 CURRENT_HANDOFF。

分支删除和归档的最终结果以 Git 实际状态及本地
`F:/MKLink-Build/artifacts/v042-session-handoff-20261027/START_HERE.txt` 为准。
