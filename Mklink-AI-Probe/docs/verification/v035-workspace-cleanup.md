# 0.3.5 发布后工作区清理

维护者明确要求合并主分支，仅保留原 Mklink-AI-Probe 工作区，并清理修复工作区和临时文件。本次没有产品代码变化，不重复发布或执行硬件操作。

## 主分支与工作区

- 已 fetch 并确认 PR43、PR44 均已合入 main，清理基线为 cd2aba8dc98d733ae8e0895824920fb211b269f8。
- 原 Mklink-AI-Probe 工作区由历史分支切换至最新 main；移除无未提交修改的 mklink-0.3.5-fixes 工作区。Git worktree 仅剩原工作区，源码仍在其同名子目录中。
- 删除已确认属于 main 祖先的两个本地分支 codex/0.3.5-fixes、codex/0.3.5-release-handoff。历史 0.3.4 分支有独立交接提交，保留其历史引用；它不是额外工作区。
- 工作区移除过程中，原生桥接 DLL 的联接影响到原目录；随后已从正式安装包提取副本恢复，并与已安装版本核对 SHA-256：c2646996e728f51f115dfa2c639f877afdfbb8f5e68d611aae054e82ea8708af。

## 清理结果

- 删除 212 项可再生成缓存、安全临时子目录及逐份核对大小/SHA-256 的重复发布文件，共 394,682,447 字节。
- 18 组匿名下载分片重新按偏移完整计算 SHA-256，与保留的正式 release 资产核对一致后删除，共 2,919,736,120 字节。
- 合计清理 3,314,418,567 字节（约 3.31 GB），不含移除工作区的体积。清理记录在构建根 reports/v035-workspace-cleanup.json 和 reports/v035-download-cleanup.json。
- 106 个含目录联接的历史测试目录按仓库规则保留，具体路径和联接目标列在本地清单。后续文档契约测试新增 1 个含测试联接的目录，同样保留。未提权、修改 ACL 或强制绕过权限。
- 保留正式 release、三平台原生归档、唯一验收/客户记录、Skill 备份、用户固件与配置、Pack/FLM、可复用依赖和受跟踪 gui/dist；0.3.5 安装包仍在构建根 artifacts/v035-official/release。

## 交接

当前交接已改为原工作区继续维护，避免继续引用已移除的修复目录。产品验收与未解决问题仍以 [0.3.5 发布交接](v035-release-handoff.md) 为准；本次仅进行文档契约验证、发布文件校验和 Git 状态检查。

记忆 render/validate、git diff --check 通过；test_ai_memory.py 与 test_skill_context_boundaries.py 合计 59 项通过。全部正式载荷仍按原发布清单保留，不改变版本标签和更新渠道。
