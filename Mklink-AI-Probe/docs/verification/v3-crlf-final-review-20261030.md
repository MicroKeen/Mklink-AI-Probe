# V3 固件 CRLF 修复结果核对

2026-10-30，指定固件会话完成私有 V3.6.8 候选（build Oct 30 2026 17:56:49）验证并释放设备。
固件 SHA256：`751120c44691aaaf38c4e769c88fe9bcbb585968d76158c859e86ad864c4ee73`。
本会话只读取该会话保存的报告与产物进行核对，没有重新连接硬件、刷写固件或独立重复实机测试。

固件会话说明：stdio 仅对裸 LF 补 CR，已有 CRLF 及跨回调的 CRLF 不重复转换；背压写入失败不提交转换状态。
下列结果由保存的 `latest-results.json` / `latest-write-results.json` 核对：

- 共 51 轮采样；其中 legacy/B1 4 KiB 在 10/30 MHz 各三轮。六轮的丢弃字节、丢帧和 CRC 错误计数均为 0，`startup_control_bytes=51`；此前候选为丢弃 7 B、启动控制 45 B。
- 逐个比对 1600 个样本内各区域的载荷字节与测试缓冲预期内容，一致。保存的测量包含 800 次读和 600 次写时延。
- 216776 B 目标 Flash 比较一致，完整 RAM 缓冲恢复；两份最终共享会话记录均为 `device_closed=true`。
- UF2 文件 SHA256 与报告一致。当前已安装冻结后端 SHA256 与报告相同，仍为 `8e759f082c3cfcf007df4392f9fd06b1132c1d165be65f62390853fd9ecd3ce0`。
- 当前 Skill 安装标记仍为 0.4.2、归档源 `0d680d90`、包 SHA256 `a126d967ee85badda443cf20bba385186cde5007ada7fcc75f9e1fb441e947db`。
- `version-response.bin` 中已无 CRCRLF；这是 UTF-8 重编码的公共 `probe_version` 返回文本，保留 CR/LF，**不是原始 B1 抓包**。此次没有保存原始 B1 字节流；各计数字段不扩展解释为独立硬件校验。

本地核对摘要和脚本位于 `F:/MKLink-Build/artifacts/v3-final-review-20261030`；原始报告和固件位于固件工作区的 `firmware-releases/V3.6.8-mux-block-20261030`。
固件及硬件标识不复制到上位机仓库。该路径的 CRLF 兼容问题已有候选固件修复与复测证据，主机解析器和完整性检查无需放宽。

此轮 CRLF 验收没有测试长期空 RTT。随后指定会话另行完成一轮 30 分钟复测，结果未复现，历史根因仍未定位；见 [空 RTT 结果核对](v3-empty-rtt-review-20261030.md)。当前主机源码 `6ce79923` 的在线读取错误提示仍未重新打包安装；本次结果不改变该状态，也不构成正式发布。
