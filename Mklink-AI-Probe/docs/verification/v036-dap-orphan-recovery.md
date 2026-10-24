# Windows CMSIS-DAP 遗留占用恢复

2026-10-24，分支 `codex/dap-orphan-recovery`，基于 `microkeen/main` 的
`303a2667`。本次仅修改上位机源码，未覆盖桌面安装包或发布更新。

## 问题与处理

SES/OpenOCD 关闭 USB 句柄但未发送 CMSIS-DAP 结束通知时，下载器无法从
USB 总线获知主机句柄已关闭。固件仍保留 DAP 会话，后续独占命令可能返回
`DAP busy`。无流量也可能是正常的暂停调试，不能据此超时释放。

在新 CDC 连接已经取得端口所有权并重新核对物理身份后，上位机执行一次
有界的 Windows 所有权核对：

1. 被动枚举同一 VID/PID/序列号的 MI_00 CMSIS-DAP 接口；缺失或歧义时跳过。
2. 用 `CreateFileW` 的 `shareMode=0` 打开该接口。已有 IDE 持有句柄时拒绝清理。
3. 在同一个独占句柄内初始化 WinUSB、核对接口和端点、有限排空旧应答，
   只发送 `DAP_HostStatus(DEBUGGER_CONNECTED=false)` 并核对应答。
4. 释放接口，继续原 CDC 握手。失败保留原固件仲裁，不重放目标操作。

不发送 DAP Connect/Disconnect、暂停、复位、目标读写或缓存维护命令。
运行状态通知 `TARGET_RUNNING=false` 不构成释放理由。核对仅在新连接执行；
已连接期间发生的 IDE 异常退出需要显式断开并重新连接 MKLink。
非 Windows 保持原路径。旧固件未实现 HostStatus 所有权处理时，不承诺此
通知能解除其占用；当前 V2/V3/V4 源码已有该处理。

## 验证

- 24 项新增测试覆盖身份匹配、歧义、活动所有者拒绝、整个交互期间持有
  独占句柄、唯一允许的数据包、错误应答不重放、有界排空及资源释放。
- 与 bridge 身份/锁/能力、MUX、probe-only、runtime reconnect/probe/shared
  的回归合计 329 项通过。测试均经 `scripts/build_workspace.ps1` 执行。
- HPMLink V4.7.1 + HPM6E80 实物：用标准 DAP 连接和状态通知构造漏发断开
  通知的会话，直接关闭 USB 句柄。该夹具不发送 CPU 暂停或复位命令。
  旧版 0.3.6 共享 runtime 随后读取 16 字节失败，前端报返回 0 字节。
  修复版共享 runtime 新连接后读取成功，RTT 和两通道 SuperWatch 同时启动，
  274 个采样周期读错/丢样均为 0；CPU 参考计数递增，D-cache 仍开启。
- 实际持有 CMSIS-DAP 句柄期间，清理被 Windows 拒绝（错误 5），原客户端
  仍能读取 DAP 信息；关闭后清理成功。暂停状态通知同样不触发抢占。
- SES 界面尝试连接时出现 GDB socket closed，未完成 SES 原生完整连接/
  断开矩阵；同配置 OpenOCD init/shutdown 可退出。上述恢复证明来自实际
  USB 协议夹具，不将其描述为 SES 全流程通过。

原始硬件日志和脚本仅保存在本机受管理的构建报告目录，不提交设备标识或
目标工程路径。本次没有重新烧写目标、升级探针、修改供电或 OTP。
这里验证的是 DAP 所有权恢复；HPM6E80 脏缓存不可见的限制仍在，不属于
本次修复的成功范围。V2/V3 未连接实物，不继承 V4 的硬件结论。
