# 0.4.2 发布后归档（2026-11-02）

后续开发从[当前交接](CURRENT_HANDOFF.md)进入。0.4.2 的正式源码为 `0e82ba6f`，发布资产、固件版本和验收范围见[发布报告](../verification/v042-release-handoff.md)和[最终资格报告](../verification/v042-formal-qualification.md)。

当次清理移除了 29 个可重建目录（约 6.587 GiB），复核了 629 个保留文件的哈希，另有 135 组含链接目录留待人工检查。对应原包、逐项清单及恢复依据位于构建根的以下位置：

- `artifacts/v042-formal-20261102/` 保存正式包与发布证据。
- `reports/v042-cleanup-20261102/` 保存清理计划、文件哈希与人工检查清单。
- `artifacts/v042-postrelease-handoff-20261102/START_HERE.txt` 记录当时的 Git 状态和本机路径。

现行下载策略见[腾讯云下载维护说明](tencent-updates.md)。
