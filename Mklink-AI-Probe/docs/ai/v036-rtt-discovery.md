# 新连接 RTT 自动搜索与采集兼容性（2026-10-23）

HPM 自动搜索能从 ELF 找到 RTT 地址，但随后校验目标控制块时返回 0/24 字节；手动启动 RTT 却可正常读取。代码确认 `rtt_inspect()` 未准备 MUX，可能走旧文本读取，而 `rtt_start()` 先启用 MUX。诊断时已有连接的同一地址可正常读取，因此没有把旧固件读取失败的具体原因宣称为已完整复现。

任务提交 `dc751650`：搜索与启动共用 `_prepare_rtt_transport()`，根据连接内缓存的固件能力选择通道。已有 MUX 及其 RTT/Watch 订阅保持不变；旧固件继续文本读取。握手或读取失败不自动回退、重放或启动采集。保留控制块签名、RAM 范围和描述符验证。0.3.6 中英文版本信息加入简短说明。

安装源为组合分支 `codex/v036-isp-ux-local` 的 `ef51d4d3`，生产 Web 提交 `5aeb2da2`；保留此前全部组合修复。本轮没有修改或升级下载器固件。

## 验证

- 462 项相关 Python 测试通过，包含新增 17 项搜索/协议测试。ARM 覆盖 V2/V3/V4 旧文本能力形态、V3/V4 MUX，另含 V4 HPM JTAG。使用实际 Device 解析器、bridge 和 MUX 编解码，验证首次搜索、两种采集顺序、活动采集中的再次搜索及数据缓冲保留，错误不回退。型号标签表示协议覆盖，不代表实际设备验收。旧固件的并行能力限制没有被绕过。
- 70 项相关 GUI 测试、TypeScript/Vite、全新 PyInstaller/Tauri/NSIS 构建通过。
- 原 V4 与 HPM5301，30 MHz JTAG，RTT CH0/1、SuperWatch 10 ms：源码两种顺序通过。安装版四组全新连接分别覆盖先搜索与不先搜索、RTT→Watch 与 Watch→RTT；在第一项及两项采集运行时再次搜索均成功。观察阶段 Watch 分别累计 317/413/317/415 组，读错/丢样均为 0，RTT 收到新的遥测文本。每组分别停止重开一项，另一项继续运行。
- 安装版真实浏览器从新连接点击自动搜索，显示正确地址与 CH0/CH1；点击启动 RTT、选择两个变量启动 Watch，然后返回 RTT 再搜索成功，RTT 文本持续输出，浏览器控制台无错误。
- 解包与实装分别核对 206 个 Python 源文件、41 个 Web 资源，实装四个载荷一致。内置 7,059 个算法目标/2,224 个算法文件及 4,800 个外设目标通过验证。Windows-only PATH 下冻结 CLI、实际 stdio MCP、SVD、HTTP、探针枚举、合并 HEX 几何与后台退出通过，不依赖宿主 Python。
- 管理员覆盖安装成功，NSIS exit 0；正常关闭原生窗口后后台进程退出，随后重新打开安装版供用户测试。

本轮未写目标 Flash/OTP、修改变量/VCC或复位目标。V2/V3 设备和 ARM 目标未连接，本轮只有协议回归，没有这些组合的真机结论。短时采集不代表任意负载下长期无损。

## 验证过程中的修正

新增模拟端最初没有剥离 MUX 请求的会话 nonce，8 项测试在测试夹具内报解包错误；修正夹具后 17 项及扩大回归全部通过。首次构建因未设置内置 Pack 路径停止，指定已有、经过验证的缓存后构建成功。原生退出检查最初误用后台退出接口，只关闭 sidecar 并触发原生监控重启；改为正常关闭原生窗口，并等待依赖进程退出后通过。上述均保留本地原始证据。

## 本地安装包

构建根 `artifacts/v036-rtt-discovery-ef51d4d3`：

- `Mklink-AI-Probe-0.3.6-local-ef51d4d3-Setup.exe`
- SHA256：`42f9156a2dcb80dd1b206ca3d4c6412740cd170625830e72247d6409e965c61d`
- `manifest.json`、`install-result.json`、`extracted-qualification.json`、`installed-qualification.json`
- `installed-hardware.json`、`installed-browser-native.json`

源码真机报告在构建根 `artifacts/v036-rtt-discovery-source/hardware.json`。设备身份、目标 ELF 路径和原始本机记录不提交仓库。标准 NSIS 无签名，仅本地覆盖安装，未发布或合并主分支；本轮未再次同步全局 Skill。
