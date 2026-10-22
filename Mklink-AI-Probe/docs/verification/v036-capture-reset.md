# 采集中软件复位

主机功能源527a1339、恢复边界207b47c7。配套固件另见原固件会话验收。

- 仪表盘原“重启 MCU”按钮保留。共享任务日志继续通过request_id去重，复位可与支持该能力的RTT/SuperWatch MUX采集共存；烧录、安全操作和其他控制任务仍互斥。
- API不停止采集、不释放采集租约、不清历史；只临时取得目标命令租约。Device使用现有MUX命令槽发送一次0x15（nonce后空业务载荷），HELLO capability bit5协商。无MUX旧路径保留原兼容行为；新MUX路径纯软件复位，不退回raw命令或硬件复位。
- MUX epoch、RTT/Watch订阅和已排队事件保留。0x95成功/可能不确定的status5响应产生本地reset generation；入队Watch字节携带该代号，跨代丢弃不完整组，保留完整历史。即使新轮首片被背压丢弃，也不拼接复位前后的半组数据。busy6不改变代号。
- 固件恢复时重新读取RTT控制块及目标游标；5秒内按有界间隔重试，恢复超时status8只结束未恢复的流。主机显示复位恢复超时，不重放复位。真实DAP接管的status7仍作失效处理。
- 当前新命令适用于ARM/SWD的MUX RTT/SuperWatch。HPM/JTAG、SystemView/旧原始流不能据此宣称支持穿插；拒绝不支持的采集组合时保留原采集。独立UART/Modbus不需要停止。

验证：最终7个相关Python模块361项全部通过；生产Web构建通过。新增恢复代号及status8用例覆盖完整样本保留、半组丢弃、busy不改变代号及恢复超时统计。

真实浏览器使用生产Web、真实API/Device/MUX和RTT管理器，目标由模拟桥提供。点击按钮后1次复位、0次stop、epoch保持17、RTT继续输出boot1。初版测试桥遗漏debug-speed上下文，补全后重跑，后台无异常、浏览器无控制台错误。测试未访问硬件。

固件生产mux_protocol.c/mux_runtime.c/rtt_channels.c导出81帧，主机逐帧分片输入真实解码器：25组完整Watch样本，RTT通道0/7分别收到BOOT0/BOOT7，epoch201不变，1个恢复边界，无跨复位半组拼接。硬件复位helper与runtime模型分别验证，不将模型当作物理复位验收。

本次安装包同时包含自动烧录次数左移、每次页面打开默认1、只有次数大于1可编辑等待时间。早期构建在恢复边界补充前启动，未归档或安装；最终包重新完整构建。

组合候选8e402491安装包已通过提取资格：205个Python源和41个Web资源匹配，冻结CLI/MCP/SVD/HTTP、Windows-only PATH、无宿主Python及正常退出通过。SHA256 d40c633b29164c7ac5bda317ddf06317614597aea0a80312214522d887e956b2。配套固件源8f56bd6，38项CI及双宏SES通过，UF2 SHA256 1a4acb0a23aaf36336baa9fdb484ba5a0cedb3eda395dc5a7181f9724b037ee2。两者均为本地候选，未签名发布。

安装、固件升级和实机验收：等待用户关闭当前上位机，尚未执行。无Flash/OTP/VCC写入授权被沿用，本轮软件复位实测需在用户结束当前任务后协调。
