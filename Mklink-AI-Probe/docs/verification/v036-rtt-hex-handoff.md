# 0.3.6 RTT 十六进制日志导致采集退出：修复交接

## 授权与基线

2026-10-19 维护者要求将已定位问题交给新会话执行，并新建 0.3.6 修复分支。此前本会话仅获只读排查授权，未修改产品代码或操作硬件；现交由新会话实施修复和相关验证。

- 唯一工作区为原 Mklink-AI-Probe，源码在 Git 根的同名子目录中。
- 分支：codex/0.3.6-fixes，从已 fetch 的 microkeen/main / bdc635331a422ad082c9135fe656a452fbc93715 创建。
- 0.3.5 已正式发布；不要移动其标签、重新发布或修改更新渠道。本次创建修复分支不等于授权发布 0.3.6。
- 遵循 AGENTS.md 和构建存储规则。继续使用唯一工作区，不重新创建已清理的 0.3.5 修复工作区。

## 客户现象与输入

MKLink RTT View 在终端模式收到日志后报 `could not convert string to float: '0C'`，后续输出停止；截图上方显示已断开。客户对比的 J-Link RTT Viewer 仍能显示同类日志。截图不是本机在线现场，不能把它当成本机硬件状态。

客户提供的发送代码：

```c
static void s_vDumpHex(const uint8_t *pucData, uint32_t ulLength)
{
    uint32_t ulIndex;
    SEGGER_RTT_WriteString(0, "S1| ");
    for (ulIndex = 0U; ulIndex < ulLength; ulIndex++) {
        SEGGER_RTT_printf(0, "%02X ", (unsigned int)pucData[ulIndex]);
    }
    SEGGER_RTT_WriteString(0, "\r\n");
}
```

离线复现输入：

```text
I/elog    [0.003] EasyLogger V2.2.99 is initialize success.
S1| F1 09 71 C6 0C 14 46 FC 00 00 00 ED 
S1 stats: total=12 avail=0 lost=0 err=0
```

每行实际以 CRLF 结束。

## 已确证的原因

1. mklink/rtt_viewer.py 的 RttLineParser.auto_detect 将这种混合十六进制日志识别为 csv 数值行。
2. _is_numeric 使用 rstrip("CcmVAdB%Hzs") 去单位，因而对 0C 返回 True；_parse_csv 却直接 float(p)，没有使用相同的归一化结果，抛出 ValueError。
3. mklink/remote/dashboards.py 的 RttChannelDecoder.feed_rtt_bytes 总会尝试数值解析，即使前端当前选的是终端；解析异常没有在可选曲线处理范围内隔离。
4. RttStreamManager 的 cdc-mux 轮询将异常作为 terminal_failure 退出，finally 调用 rtt_stop，并执行失败回调。remote/api.py 注册的回调释放 dashboard 资源。

离线验证使用真实解析器、真实 RttChannelDecoder 和真实 RttStreamManager，加一个不接触硬件的 FakeDevice。整段输入和逐字节输入均得到相同异常，raw_lines=1；worker.running=False、线程退出、rtt_stop 调用一次、失败回调一次。因此已确证采集退出链；截图中的物理断开详情尚无客户现场日志，不能扩大结论。

本地诊断脚本位于构建根 reports/v035-rtt-hex-diagnosis.py，不在产品仓库中。该脚本对旧行为做断言，修复后应以正式回归测试验证期望行为，不把旧断言失败当作修复失败。

## 修复与验收范围

- 修正数值检测与转换不一致的问题，检查同类单位、十六进制 token 和混合日志，保留合法十进制/科学计数法与明确支持的曲线格式。
- 曲线解释失败只能影响该条曲线数据，原始字节、文本、终端输出及采集生命周期应继续；不要宽泛吞掉真实设备、传输、资源或发布错误。
- 测试整段、逐字节、任意分块和跨批次 CRLF；错误日志后紧跟有效数值行与后续普通日志，均须继续处理。
- 覆盖多通道隔离：一个通道的文本不能终止其他通道或共享连接。验证终端/收发视图不依赖曲线解析成功。
- 搜索所有 RttLineParser 调用者，包括 remote/dashboards.py、rtt_viewer.py 独立入口和 mcp_stream_bridge.py，确保 Web、CLI、MCP/Skill 的相关路径行为一致。
- 添加有意义的解析器和采集生命周期回归测试，通过相关 Python/GUI 契约和必要真实界面验证。现场硬件、客户日志缺失时明确标注，不声称已经在客户板上验证。
- 在此分支提交、推送修复及更新交接，按仓库规则创建 PR；不要擅自发布、覆盖安装或升级探针固件。若需要这些操作，先按新会话实际授权判断。

其他 0.3.5 遗留问题见 [正式发布交接](v035-release-handoff.md)，本次不将其混同为同一根因。
