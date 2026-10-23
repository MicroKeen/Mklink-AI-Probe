# HPM RTT / SuperWatch 启动顺序修复（2026-10-23）

用户在 V4 连接 HPM5301、RTT 已运行时启动 SuperWatch，HTTP 返回 500。运行日志定位到 `supports_hpm_dump_write()` 调用旧文本 `cmd.get_version()`，触发 `_leave_multiplex()` 的活动采集保护。错误发生在能力查询阶段，尚未读取所选变量；与此前已修复的固件 HPM 软件复位分支是两个问题。

任务提交 `77f0f004` 在 bridge 内缓存一次连接的完整固件能力响应。MUX 握手和 ARM/HPM 写能力检查共用缓存，后续启动另一项采集不再退出 MUX。新连接清空缓存，查询异常不缓存失败结果；保留旧固件能力判定和已有活动采集保护。0.3.6 中英文版本信息增加一句修复说明。

组合分支 `codex/v036-isp-ux-local` 集成源 `a8a5dfad49bed3eefca6cbdc6492e045c17e64ca`，生产 Web 提交 `f579b0c4`。保留此前烧录进度、合并 HEX 和其他 0.3.6 修改。

## 验证

- 组合源 445 项 Python 回归通过，覆盖实际 MUX 编解码、两种启动顺序、缺少 HPM 写能力的固件、重连能力刷新、查询失败重试、采集管理和复位相关路径。不是整库测试。
- TypeScript/Vite、全新冻结后台、Tauri/NSIS 构建成功；内置 7,059 个目标、2,224 个算法文件及 4,800 个外设目标校验通过。
- 解包与实装各核对 206 个 Python 源文件和 41 个 Web 资源；四个安装载荷一致。Windows-only PATH 下冻结 CLI/SVD、真实 stdio MCP、HTTP、探针枚举及合并 HEX 1,027 扇区检查通过；不依赖宿主 Python，独立验证后台正常退出。
- 原 V4 与 HPM5301、30 MHz JTAG、RTT CH0/1、SuperWatch 10 ms 的 `xTickCount`/`xYieldPending`：解包原生候选和安装版均分别从新连接测试 RTT→Watch、Watch→RTT。安装版观察阶段分别采集 265/283 组，RTT 收到新遥测文本；两项持续运行、读错/丢样均为 0。每种顺序再分别停止/重启一项，另一项保持运行，全部通过。
- 安装版真实浏览器加载对应 HPM ELF 后，先开 RTT 再开 SuperWatch；可见 Watch 运行中、约 88 Hz、计数增长，切回 RTT 后持续显示新的 HPM5301 遥测。控制台无错误。新隔离 GUI 初次未加载 ELF 时，RAM 地址准入拒绝按预期生效；加载正确 ELF 后完成上述验证。
- 用户确认关闭旧上位机后，管理员覆盖安装于 2026-10-23 14:04:28 +08:00 完成，NSIS exit 0。测试原生候选在主动断开目标后清理；最终安装版原生程序与两项采集保持运行，供用户继续测试。

本轮未更新下载器固件，未复位目标或写入 Flash、OTP、VCC，也未执行变量写入。HPM 实物短测不代表任意负载无损，历史高负载限制仍保留；ARM 本轮为回归证据，未换板实测。

## 本地包与证据

构建根 `artifacts/v036-capture-order-a8a5dfad`：

- `Mklink-AI-Probe-0.3.6-local-a8a5dfad-Setup.exe`
- SHA256：`90361fe45063167cad76cba2b3b46e574b1390f600aaabb0de3d7834924c6395`
- `manifest.json`、`install-result.json`、`extracted-qualification.json`、`installed-qualification.json`
- `extracted-hardware.json`、`installed-hardware.json`、`installed-superwatch.png`、`installed-rtt.png`

原始设备身份、目标 ELF 路径及截图仅保留本地。标准 Windows NSIS 无 Authenticode/updater 签名，仅本地覆盖安装，未发布或合并主分支。测试产生的含链接 run 目录按构建器提示保留，不强制删除。
