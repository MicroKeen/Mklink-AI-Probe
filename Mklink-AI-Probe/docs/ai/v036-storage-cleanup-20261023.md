# 2026-10-23 E / F 盘清理交接

用户要求清理近期构建、测试垃圾，并将无法安全删除的内容列清单。当前仍是唯一工作区 `Mklink-AI-Probe`，任务分支 `codex/hpm-isp-deployment-ux`；安装版本对应集成分支 `codex/v036-isp-ux-local`，未切换或修改源码。

## 清理结果

- 删除 61 个经过绝对路径、祖先和后代链接检查的普通目录：旧 E 盘 Cargo 编译输出、历史安装包解压副本、冻结程序遗留 `_MEI` 临时文件、旧站点构建中间文件及空临时运行目录。
- E 盘实际可用空间增加 **12.97 GiB**，清理后 **13.60 GiB**；F 盘增加 **10.38 GiB**，清理后 **37.16 GiB**。逻辑文件大小合计约 24.89 GiB，压缩等因素使实际释放量不同。
- 本次明确磁盘清理授权下删除可再生成的旧 E 盘编译缓存；保留 F 盘当前缓存和全部源码依赖。后续继续使用 `scripts/build_workspace.ps1` 与 `F:/MKLink-Build`，不要重新填满 E 盘。
- 删除过程同时持有两个构建根的排他锁；未终止用户进程、提权、修改 ACL、跟随链接或操作硬件。

## 人工清单与保留项

本机 `F:/MKLink-Build/reports/cleanup-20261023/` 保存：

- `清理结果与手动清单.md`：用户可读摘要及最大的待清目录。
- `manual-cleanup.csv`：**218 个含测试链接的目录，合计 11.55 GiB 普通文件**，逐项记录绝对路径、大小、链接数和示例目标；按仓库规则保留供人工处理，不计链接目标大小。
- `installer-inventory.csv`：历史安装包清单，标明最新包必须保留，其余供用户判断回退价值。
- `inventory.json`、`plan.json`、`result.json`、`disk-before.json`、`disk-after.json`：不跟随链接的盘点、删除计划、实际结果和磁盘空间证据。

另保留 E 盘约 3.93 GiB 历史 Skill 备份和约 1.92 GiB SystemView 原始采集日志，其独有价值未判定，摘要明确区分这些资料与可删临时文件。没有清理用户下载、微信、SDK、固件工程或系统目录。含链接目录只能人工检查所列临时根，不应沿链接删除源码、算法、依赖或 SDK；禁止整体清空 `.build` / `MKLink-Build`。

原安装包、正式 `release` 资产、原生 CI ZIP、唯一硬件日志/截图及受版本控制的 `gui/dist` 保留。旧安装包的解压副本可从同目录原包重新提取，资格报告未删。

## 当前交付

最新包及整个验收目录 `F:/MKLink-Build/artifacts/v036-watch-formulas-e7c49b04/` 未删除；安装包 SHA256 再次核对为 `818035c005e02978b0729facd7cafcfba91babc659aa209e6bbc6409495b202b`。已安装位置仍为 `D:/Program Files/Mklink AI Probe`。

SuperWatch 源 `870471b6`、组合源 `e7c49b04`、生产 Web `bcdc8474`；功能和实装验证见 [SuperWatch 交付记录](v036-superwatch-formulas.md)。本次仅清理和交接，没有重建包、发布版本或硬件操作。旧清理记录中的包路径/应用运行状态仅是当时快照，以当前交接为准。客户 N32 实物烧录、V2/V3/ARM 采集矩阵等未完事项继续保留，不继承历史一次性烧录授权。
