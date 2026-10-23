# V4 HPM 采集中软件复位验收（2026-10-23）

用户报告 V4 连接 HPM5301、RTT 采集运行时点击重启 MCU 返回 MUX status 1。固件 opcode 0x15 仅允许 ARM SWD，JTAG 在访问目标前被拒绝；旧文本命令的 HPM 分支未接入该通道。上位机的通用错误字符串把 unsupported 也描述为结果未知，提示分类问题未在此次固件修复中修改。

固件专用会话在 `codex/v4-hpm-mux-reset` 提交 `8b2a6ce`：仅 V4 HPMLINK 增加已检查的 HPM JTAG 软件复位；ARM 保持原路径，V2/V3 未改。避免旧初始化的暂停/复位回退，单次断言及释放，确认新的复位标志和运行状态；未知结果不重放。保留 MUX 会话、订阅和完整历史，清除旧游标与不完整采样组，使用既有恢复窗口。

42 条本地回归命令、普通/HPMLINK 两种完整构建和 SWD 布局检查通过。宿主实际解码器解析生产 C 模型的 81 帧，得到 25 个完整 Watch 采样及 RTT CH0/CH7 启动文本，无跨复位拼组；此部分属于模型证据。

用户确认停止测试并关闭上位机后升级。首次软件进入 Bootloader 未观察到升级盘，尚未复制固件；用户手动进入后重新核对同一物理下载器身份，写入一次 UF2。应用重新枚举，构建时间为 `Oct 23 2026 13:34:27`，版本 V4.7.0；MUX capabilities 63、软件复位及 ISP/OTP 能力检查通过。候选 UF2 SHA256：`378d3710875d2771a7a6bfc06f27ca2ccf9431fd9d325de0d0ee031b90480a54`。未修改目标 Flash、OTP 或供电。

已安装的 0.3.6（组合源 f4221d96）实际冻结 API 进行一次 HPM5301 软件复位：30 MHz JTAG、RTT CH0 与 SuperWatch 10 ms 同时运行。任务 succeeded，约 35.75 ms，stopped=[]、replay=false；同一 RTT session 保留。RTT 捕获 `tick=1 telemetry=1` 及后续每 500 ms 输出；Watch 的 wave_tick 从 141433 回到首次观察值 56，随后 149、262、352 持续增长。五秒观察中两项采集保持运行，读错、丢样、事件缺口计数为零。此短测不保证任意负载无损或所有 HPM 型号行为。

本地证据在构建根 reports：`upgrade-v4-hpm-mux-reset.json`、`hpm-reset-before.json`、`hpm-reset-hardware.json`、`v4-hpm-mux-reset-host-frames.json`。原始设备身份、目标工程路径及 request ID 仅保留本地。固件仓库保存对应软件/实机验证说明；未合并主分支或发布。本次未修改或重新打包上位机。
