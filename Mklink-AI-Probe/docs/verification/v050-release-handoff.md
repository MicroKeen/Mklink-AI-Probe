# MKLink V0.5.0 发布准备与交接

2026-11-14 维护者明确授权正式发布 V0.5.0，并同时发布四款新固件。当前为发布准备记录，尚未创建正式标签、上传附件或切换更新索引。发布目标仅为 MicroKeen GitHub 与腾讯云；历史 Gitee 和旧 GitHub 不变。

## 发布门禁修正

- 应用更新索引改为获取现有 `release` 历史后快进推送，不再创建孤立提交并强推。真实本地 Git 远端验证保留其他文件、重复发布幂等、并发更新拒绝覆盖。
- CI 的冻结日志导出测试模拟了允许 breakaway，但 CI 自身 Job Object 不支持。受限 Job Object 本地复现 `WinError 5`；测试适配只在源码替身子进程去掉 breakaway 标志，仍验证产品调用带标志且三路标准流使用 DEVNULL。受限环境复测及发布/日志导出 34 项通过。产品代码未改动。
- 首轮完整 Python：7168 通过、2 跳过；4 项包测试因缺少显式 STCP DLL 路径未运行。补齐已验证 DLL 路径后重跑。最终 Python、GUI、构建、CI 和签名包验收结果待补充。

## 固件原件

固件会话确认下面是已合入固件主线的最终原件，本轮只按公开文件名复制，不重新编译或刷写。

| 公开文件名 | 字节 | SHA-256 |
| --- | ---: | --- |
| MicroLink_V2.9.4.rbl | 368944 | `3751d7f3ca9438c40f2002ebb3a91cc596fc1b7c7d8b66a8ea5a53689d3c9ead` |
| MicroLink_V3.7.0.uf2 | 851968 | `c41cdb180f2365d6a5929b1ee595de80aa3ed3a1759d20aa2bafc32c35e723f3` |
| MicroLink_V4.7.4.uf2 | 1649664 | `82d86c9f5de1611ee101f8ccd349deb8ee73b065340cb3a4958ac4c69f886917` |
| HPMLink_V4.7.4.uf2 | 1650176 | `a3c6f34c4179d54a46f28bc3e28b30a4da8d0622903d424ec3831a9d873f136b` |

UF2 与独立 V2 RBL 发布计划预检通过；V2 使用 `latest-v2.json`，其他三款使用 `latest.json`。两款 V4 均支持 Arm SWD/HPM JTAG，仍必须按下载器型号选择固件。先更新应用/Skill 索引，再更新固件索引。

功能、安装与硬件验收沿用 [GUI 控制最终验收](v050-gui-control.md)、[强制覆盖验收](v050-installer-force-acceptance.md)、[HPM/USB 验收](v050-usb-hpm-overwrite.md)及各专项报告。原有极限采集、10 Mbps 大帧、客户 STOP、Mac 原生实物等限制保留；不因正式发布宣称这些未验范围已通过。

原始证据在构建根 `artifacts/v050-official-20261114`。发布后补齐正式源提交、资产哈希、签名安装与升级结果、双渠道回读和历史归档证据。
