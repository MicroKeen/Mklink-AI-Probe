# RTT 原始字节订阅

小量诊断用 MCP `rtt_read_channel` 的 cursor/session；大量采集或测速用
`RuntimeClient.rtt_subscribe_bytes(channel, session=...)`。它通过现有共享后台的
认证 WebSocket 读取原始字节，不打开串口、不启动第二个采集、不把二进制转成文本。
需要包含此接口的配套上位机与 Skill；旧后台缺接口时不退回裸串口。

配套固件协商 bit 8 后，后台显式启用 480 字节量子；旧会话保持 128。
新增短帧含头部/CRC不超过512字节，既有4KiB整块读保持独立契约。
不手动构造 MUX 指令；能力协商失败不得静默改道或重放。

先连接共享后台并启动/订阅已确认的 RTT 采集，检查 `rtt_status.running`、`error`
及通道是否已就绪。下面的 `client` 是已经 attach 的共享 RuntimeClient。
`output` 是用户工程 `.mklink/` 或已指定非系统盘目录下的文件路径。

```python
status = client.call('rtt_status')
if not status.get('running') or status.get('error'):
    raise RuntimeError('RTT capture is not ready')
with client.rtt_subscribe_bytes(1, session=status['session']) as stream:
    # 订阅成功后再让已获授权的目标测试程序开始输出，避免漏掉启动数据。
    # 不在此猜测控制地址；触发方法由目标测试程序协议决定。
    with open(output, 'wb') as destination:
        received = 0
        while received < expected_bytes:
            batch = stream.read(timeout=1.0)
            if any(batch[key] for key in ('missing_batches', 'lost_bytes', 'mux_dropped_bytes')):
                raise RuntimeError('RTT data was lost; keep evidence and invalidate this run')
            destination.write(batch['data'])
            received += len(batch['data'])
```

实际脚本必须增加总时限，超时保留现场，不自动重启目标或重放触发命令。
结束后核对总长度、目标序号/模式与 SHA256，并检查最终 `rtt_status` 的采集错误和
传输丢失计数。字节偏移属于单次采集 UUID；会话变化直接报错，须显式重新订阅。
关闭订阅只释放本客户端数据流，不停止别人正在使用的 RTT。

采集有界，慢消费者可能丢数据。二进制订阅报告序列缺口、字节偏移缺口和 MUX
消费者队列丢失；它不能检测目标程序未写入 RTT 的数据，仍需目标侧计数校验。
吞吐以收到并验证的数据计量，分别报告目标耗时和主机耗时；KiB/s 使用 1024 字节。
