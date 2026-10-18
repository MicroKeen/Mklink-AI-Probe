# V3 / V4 固件发布核对

2026-10-18 按维护者明确请求，发布其提供的 MicroLink V3.6.5 与 V4.6.9 原始 UF2。文件未改写，未放入应用 NSIS 或用户 Skill。

| 文件 | 字节 | SHA256 |
| --- | ---: | --- |
| MicroLink_V3.6.5.uf2 | 806400 | 739af38c1e2441fa83a61c22ddbe5aeb514a73cafce3608c954b1a4d5f1f74eb |
| MicroLink_V4.6.9.uf2 | 1623552 | 96330d006efc42e01bf253b9663e3405af59db5293da9041c5550b347d86c324 |

UF2 framing/块计数与版本字段检查通过。两处 GitHub firmware-assets 以及 Gitee 的实际附件均通过匿名下载大小/SHA256 校验；三个公开 latest.json 均为 V3.6.5 / V4.6.9，HPMLink V4.6.8 保持不变。两处 GitHub latest-v2.json blob 完全不变。

- MicroKeen firmware 提交：927ee94232e05eea1cb0e1e6682e0d0fef660de4。
- Aladdin-Wang firmware 提交：bd31c8846f3d9c9843fa759ff8effbda28b1318e。
- Gitee firmware 提交：b890b2c214a2a868da1753898f335b308bb488c8。

索引仅修改 latest.json，保留其他文件；网络失败后回读远端，再续传未完成步骤，没有强推、移动已有标签或覆盖旧资产。Gitee 原无 firmware-assets 标签/Release，按既有兼容标签创建。此次没有将两个新文件刷入实体下载器，发布校验不扩大为这两个文件的硬件升级验收。

证据位于构建根 artifacts/v035-probe-firmware，保留 preflight、计划、实际附件、索引及公开回读报告。
