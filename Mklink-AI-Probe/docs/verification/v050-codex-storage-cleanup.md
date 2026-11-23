# 2026-11-17 Codex 存储清理与工作树位置交接

本轮只清理本机临时文件、记录目录约定；不修改产品代码、V0.5.0 版本信息或已发布文件。

## 用户要求与位置约定

- 主仓库保持 `E:/software/HPM5300/Mklink-AI-Probe`，源码为其中的 `Mklink-AI-Probe` 子目录。
- 新工作树优先 `E:/Codex-Worktrees`，构建和测试临时文件保持 `F:/MKLink-Build`；禁止新建到 C 盘。
- 约定已写入本机用户级 `.codex/AGENTS.md`。用户明确选择“暂时只清理并记录约定”，因此未修改 Codex 应用的 Worktree root 设置，也未整体迁移 `.codex`。
- 下一会话从 E 盘主仓库接手，获取最新 `microkeen/main` 后创建 `codex/v0.5.1-fixes`。先核对工具的实际输出目录；默认仍为 C 盘时不要创建，应先在设置中调整工作树根目录。

[Codex 官方说明](https://learn.chatgpt.com/docs/environments/git-worktrees)指出托管工作树默认位于 `$CODEX_HOME/worktrees`，可在设置的 Worktrees 页面修改根目录。本机旧 `v050-fixes` 正是该默认位置；其约 38 MiB 源码位于 C 盘，GUI 依赖和本地桥接构建分别链接到 E、F 盘。

## 完成的清理

不跟随重解析点的盘点显示，`.codex` 总计约 8.75 GiB；其中约 5.7 GiB 是会话记录和数据库。本轮保留这些数据以及登录信息、当前插件、已安装 Skill、图片、用户成果和未完成工程。

使用 PowerShell 7 原生路径操作，逐项验证绝对路径位于 `.codex` 内、父目录和子项不含重解析点、文件早于 11 月 15 日且不被运行进程引用，共删除 **59 项、360.71 MiB**：

- 40 个过期 `codex-command-runner`，保留 0.166/0.167 及当前主程序。
- 旧插件临时副本和备份，不删除 `plugins/cache` 下当前已安装插件。
- 4 个过期插件目录索引，保留最新索引。
- 2 个六月 MKLink 临时日志，以及 9 个旧状态写入临时文件；保留正式状态文件和最新备份。

本轮删除未遇到权限失败；未结束任何进程、提权或修改 ACL。清理完成时 C 盘可用约 13.62 GiB，实时值会随应用运行变化。

## 明确保留的工作目录

- `C:/Users/akqbd/.codex/worktrees/v050-fixes/Mklink-AI-Probe`：归档前无未提交修改，`48fc268c` 已推送；PR #87 仍开放。Codex `archive_worktree` 返回 `The task's primary checkout cannot be removed.`，所以本轮未移除，也未直接删除来绕过保护。本报告和记忆在随后文档提交中推送；最终文档提交以 Git 为准。
- `cli-symbol-reload` 尝试附加时返回 `This worktree is owned by another task.`；未抢占或删除其他会话工作树，其余旧工作树也保留供对应会话处理。
- `.codex/tmp/Mklink-AI-Probe` 虽是六月临时副本，但存在未推送提交 `9ae93de`，不能直接当缓存删除。
- E 盘 GUI `node_modules` 和 F 盘 `stcp-C2646996E728` 缓存仍存在，抽查文件 SHA-256 未变化；主仓库原有三个 stash 均保留。

本次不会创建 V0.5.1 分支。下一会话不要继续使用上述 C 盘工作树；如需清理其物理目录，先通过 Codex 支持的工作区切换/工作树管理方式解除当前会话保护，再归档。

## 本机证据

证据均保存在 `F:/MKLink-Build/reports`，未复制到 C 盘：

- `codex-inventory-20261117.json`：清理前分组占用、链接和大文件列表。
- `codex-cleanup-20261117-plan.json`、`codex-cleanup-20261117-result.json`：逐项白名单和结果。
- `codex-worktree-preserved-targets-20261117.json`：外部依赖路径及抽查 SHA-256。
- `cleanup-codex-20261117.ps1`：本轮原生清理脚本。
