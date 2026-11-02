# HPM JTAG 时钟应答兼容与隔离 SDK

2026-10-31，指定固件会话按用户要求准备更换 HPM5301 目标并校准 JTAG，要求宿主提供旧/新固件可共用的隔离 SDK。本轮产品修复为 `a8aa8a16661c039c3b91561e00cf872b282074b1`，不操作探针、不改原固定候选，不重建安装包。

## 修复

HPMLink 新固件全局声明 `SWD_CLOCK_ACK=1`，但 JTAG 回复只有 `set clock N` 与 `JTAG profile=N`。之前宿主无论当前接口都要求 `SWD clock_state`，因此正常 JTAG 回复也失败。

- 根据已知接口和回复 profile 识别 JTAG，接受其 4/10/20/30 MHz 档位确认；全局 SWD 能力不会变成 JTAG 频率列表。已知 JTAG 的 8 MHz 请求在写命令前拒绝；未知接口的回复若声称不支持的 JTAG 档也不能确认为成功。
- JTAG 返回 `apply_state=acknowledged`、`configured_hz=N`、`applied_hz=None`。直接应用与 IDE 占用后的延迟配置回复相同，不能据此判为已应用，更不能认为改变了 IDE 当前时钟或实测 TCK。
- SWD 保留唯一、精确的 Hz 应答和 `configured` / `applied` 区分。拒绝重复、矛盾、混合接口、错误状态及错误频率；失败或超时清除先前确认，未知执行结果不自动重发。
- 保留旧固件明确 `profile=0` 的原一次保守回退，并仍向调用方报错；只有唯一、格式正确的显式不支持应答可进入该路径。现代 ACK 固件不自动回退。缺失、busy、错误或不匹配回复不再误触发旧回退。
- 共享 Runtime 原有身份、epoch、独占任务与资源准入不变；失败不保存新配置、不自动停止采集。不修改 4 µs 输入下限或添加界面提示。

本轮只处理 JTAG ACK 和相关错误边界。当前产品对新 V4 的 14 档 SWD 菜单仍有 V3 版本门控，属于单独待办；隔离 SDK 不带入新的 GUI、Device 配置页策略或采样下限。

## 验证

源码最终 **451 passed**：时钟 ACK、旧/新 JTAG 四档、延迟身份、SWD 14 档两种状态、Flash 高低频入口、目标初始化、探针连接、HPM 调试、共享调试及 Runtime 安全。初次扩大回归有四项旧测试仍期待“仅 set clock 就确认 HPM”或“Error 后自动回退”；按上述确认和未知结果边界更新断言后全部通过，失败报告保留。

实际隔离候选 **692 passed**，覆盖以上独立 ACK 契约、共享 Runtime 真实路由往返，以及原固定候选的 timing-v2、MUX、capture_dump、统计、STOP、共享调试和安全回归。测试前预导入候选包，并在测试后检查所有已加载 `mklink` 模块路径均位于候选目录；不是工作区测试冒充候选测试。唯一 warning 是 anyio 预导入后的 pytest assert 重写提示。所有文件及 ZIP 哈希在测试后重核对，原候选未变。

证据目录：`F:/MKLink-Build/artifacts/hpm-jtag-ack-20261031`，包含源码首次及最终 JUnit、导出脚本；候选目录内含逐文件 manifest、verification、JUnit 与使用说明。

## 交付

新候选：`candidate-7843-a8aa8a16-jtag-ack-verified`，源码子目录 `source`，入口 `enter-candidate.ps1`。它复制原 `candidate-7843-f1055aed-watch-stats-verified`，只增加 `mklink/capture_clock.py`、替换 `mklink/debug_speed.py` 和 `mklink/flash.py`；1263 文件中 1260 个与原候选逐字节相同。

源码 ZIP `source-7843-a8aa8a16-jtag-ack.zip`，SHA256 `aaf9eb1bc1d2dbfa584aee579308f2ac5532c57044602994b42e3e224a0c4195`。原统计候选 ZIP SHA256 仍为 `c2ac1e4b2475f657abe694c16b3385f687e146d626426f7efd87b3052d8f6bca`。

固件会话已收到路径、哈希、验证结果和接口语义。对照须用同一新候选的后台和客户端，验证实际导入路径，保持目标程序、地址、长度和频率相同；只有设备持有者可结束自身旧后台并启动替换实例，保留默认物理锁。JTAG 使用共享 `set_debug_speed` 的 low/medium/high/ultra，分别对应 4/10/20/30 MHz，不借用全局 SWD 14 档。隔离入口不自动连接或烧录。

当前安装版仍是产品源 `76d669de`，完整 Skill 仍 `0d680d90`；本修复尚未打入二者。HPM5301 的频率实测与功能回归由固件会话负责，宿主本轮没有宣称硬件通过；正式发布、合并均未进行。
