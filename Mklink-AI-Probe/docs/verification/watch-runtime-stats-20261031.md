# 共享 Watch 运行统计诊断

2026-10-31，指定固件会话为排查每批约 15 µs 的吞吐差异，请求读取固件既有 MUX `0x14` 统计。核对固件实现：无请求 body，成功状态后的 body 为 16B `<IIII batches, collected, collect_cycles, pack_cycles>`，Watch START 会清零这些 uint32 计数器。

宿主此前只有 `MuxTransport.stats()` 的事件/队列统计，无法读取上述固件采样与打包耗时。新增窄范围共享入口：

```python
# 使用已经连接、由验收者持有的 RuntimeClient。
result = client.call('capture_dump', {
    'regions': regions, 'period': 0, 'fastest': True,
    'frames': 10000, 'duration': 0,
})
# 仅当 capture_dump 正常返回、STOP 已确认后执行。
stats = client.call('watch_runtime_stats')
```

## 边界

- `POST /api/device/dump-memory/runtime-stats` 只允许共享 Runtime；参数必须为空。
- 使用既有共享身份、epoch、操作与资源准入。运行中采集/独占操作拒绝，不自动暂停、停止或恢复任何任务。
- 仅复用既有、健康、已声明的 MUX 对象；在命令锁内再次确认采集已停。不启用/重开 MUX，不建立新串口，不做 raw/exclusive 回退。
- 每次明确调用只发一次 `0x14`，严格验证 16 字节回复，保留四个原始 uint32 值。固件不支持返回 501、busy 返回 409、其他固件错误或不完整回复返回 502；传输失败不重试。
- 不要求 bit9：旧协议固件可能已有该只读命令。bit9 仍仅决定显式最快采样及 START 时基 ACK 的契约。
- 不读取时清零，不自动附加到采集热路径，不增加固件日志。统计不是保证性能的承诺，也不改变时钟、周期或数据时间戳。
- 调用者必须独占本次验收序列：另一轮 START 会替换计数，不能假定两次共享调用之间有跨调用事务。计数器按 32 位循环，长采集可能溢出；用短、有界采集比较，不能把溢出的累积值直接当总耗时。时间基准应来自该次固件证据/ACK，宿主不写死 360 MHz。

## 验证与交付

当前源码的统计入口、共享采集、内存回归共 70 passed，覆盖旧/新时基协议各 10000 样本后 STOP→单次统计的真实 MUX 帧路径、计数符号位保真、错误长度/固件拒绝/传输失败、失败 STOP、不重开 MUX、不停止任务、无参数与失效会话限制。

共享调试与 Runtime 安全回归另 66 passed，原有错误映射、权限与资源边界通过。所有测试通过 `scripts/build_workspace.ps1 -BuildRoot F:/MKLink-Build`；临时测试链接按构建脚本要求保留。

本次没有连接硬件、更新固件或重启其他会话的后台。固定 SDK 导出和隔离回归结果在交付完成后补充；原 7843、d08、644acc2b 候选目录均须保持不可变。本功能不新增 GUI 控件，不构建安装包或 Skill，不构成发布或合并。
