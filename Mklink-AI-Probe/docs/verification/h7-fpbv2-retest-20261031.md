# H7 FPBv2 共享断点复测：仍未支持

用户在指定固件会话要求复测此前客户报告的 STM32H7 FPBv2 兼容问题。本轮范围是复测是否修复及移交待修项，没有实施宿主修复。指定会话负责实板，本会话仅核对保存的脚本、报告和当前源码。

## 实测与证据核对

同一 HPMLink control 固件、STM32H743IITx，报告读取 CPUID `0x411fc271`、FP_CTRL `0x10000080`、REV 字段 1、8 个指令断点比较器。分别使用实际安装的 0.4.2 sidecar 和不可变 `4be6ab66-verified` 候选，调用共享 API 的 `status`、`list`、`set`、`clear`，四项均返回 HTTP 422：

> Shared breakpoints currently support FPBv1 only

设置请求使用先与目标镜像回读核对的数值 Flash 地址，槽位 0，不依赖函数符号解析是否可用。测试前全部比较器未使能；测试后的 FP_CTRL、FP_REMAP 和八个比较器共 40 字节与之前完全相同，DHCSR 没有停核标志，目标计数增长。两轮均记录 `disconnect.device_closed=true`。因此是拒绝行为复现，不是断点命中或清除成功；没有绕过共享接口、暂停、复位或更新探针固件。

| 报告 | SHA256 |
| --- | --- |
| `installed-final.json` | `2b4fa3abcc8ad97b2a52b02ba347bcb0b285ce1aa936dc58030eff7577cfd028` |
| `candidate.json` | `4eb76d1aeb0eccae21a21b873241ceb2a048703227cd3dc4c8d207180bdcb2b6` |

已装 sidecar 的记录 SHA256 为 `8e759f082c3cfcf007df4392f9fd06b1132c1d165be65f62390853fd9ecd3ce0`。脚本核对实际启动进程的可执行文件路径；全局 Skill 模块哈希不能代替冻结后端身份。候选的两个调试模块原始哈希与报告一致；与当前分支比较时因 CRLF/LF 不同，统一行尾后的内容完全相同，未把原始哈希不等误判为已修复。

## 宿主待修范围

当前 `mklink/remote/debug_api.py` 拒绝非零 REV，并把地址限制、写入后的 expected 值固定为 FPBv1。`mklink/debug_control.py` 虽有 FPBv2 注释，状态解析和设置仍使用 FPBv1 编码。当前分支和测试候选都尚未补齐此功能。

后续修复需一并覆盖：

- 按已识别的 FPB 版本选择地址范围、对齐与比较器编码/解码；未知版本在写入前明确拒绝。
- 共享状态、列表、设置、清除和清除全部；回读校验使用同一版本规则，保留槽位边界、占用保护、资源串行化及结果未知不重放。
- 保留 FPBv1 回归；覆盖 FPBv2 的地址、比较器数量、无空闲槽、非法参数、回读不符和未知 REV。
- 离线通过后另行提供不可变候选，由指定会话协调验证实际命中、查询、清除和恢复运行；不能把本轮 HTTP 422 复现算作该验收。

本机独立核对结果为 `F:/MKLink-Build/artifacts/rtt-shared-20261030/fpbv2-retest-independent-review.json`，对应 `verify_fpbv2_retest.py`；只读取保存证据，没有执行实板脚本。更新记录不改变宿主候选、已安装软件、全局 Skill 或正式资产，没有构建安装包。
