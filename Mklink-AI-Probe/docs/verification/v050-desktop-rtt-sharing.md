# V0.5.0 桌面重开与 RTT 多客户端读取

2026-11-20 核查了原生桌面重连、macOS 本地服务启动和 Windows RTT 读取。Apple Silicon 正式包来自 `8d532019`。复现使用修复前的分支 `e9ef0bb3`，相关桌面代理、所有权、RTT 缓存及 CLI 入口与该发布源码一致。候选包使用 `eb463758`，产品版本 V0.5.0。

## macOS 本地服务启动

用户报告的 `~/AppData` 属于 root。发布版的 CMSIS-Pack 缓存回退到 `~/AppData/Local/MKLink/pyocd`。创建本地服务时，在线烧录模块会立即创建镜像目录，其权限错误可使后台在公布端口之前退出。前台随后提示无法连接本地服务。

候选版默认使用 `~/Library/Application Support/Mklink AI Probe/pyocd`，在检查烧录镜像时才创建所需目录。显式设置的 `MKLINK_PYOCD_HOME` 继续生效，可写且带已知目录记录的旧缓存也可复用。用户无需修改主目录权限或配置 launchctl。回归覆盖系统默认目录、显式覆盖、已有缓存与旧路径不可访问的场景。[缓存路径](../../mklink/cmsis_dap/paths.py) · [镜像检查](../../mklink/cmsis_dap/images.py)

Apple Silicon 原生 CI 在 macOS 15 上挂载候选 DMG、复制应用并校验最终签名。测试 HOME 下的 `AppData` 是普通文件，且未设置缓存目录覆盖。安装包内的桌面代理和本地服务在 4.482 秒内就绪，健康检查和三个生产前端资源全部通过，冻结 CLI、MCP 和正常退出通过。同轮 USB 回归通过，未连接物理探针。候选 DMG 的 SHA-256 为 `6642251d49f262a5238ab2fed65fb6b2457903a97de515044deeab026cdfff35`。此包使用 ad-hoc 签名，未经 Apple 公证。客户所用 macOS 27.0.1、图形安装和 Gatekeeper 首次打开仍待现场确认。[原生构建与验收](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/44664348398)

## 原生桌面重开

Tauri 启动 `desktop-proxy`。代理向 `ensure_runtime` 请求 `new_window=True` 和 `allow_lobby=True`，生成独立的待选探针后台。窗口选中探针后，代理把请求转发给自己的后台。该后台尝试取得此探针的 `owner.lock`。另一后台持锁时返回 HTTP 409 和 `probe_in_use`，窗口提示先在原客户端断开。原连接得以保留，新窗口没有转向持锁后台。相同的产品版本和协议号也会进入这条路径。[桌面代理](../../mklink/runtime_proxy.py) · [运行时发现](../../mklink/runtime.py) · [探针所有权](../../mklink/runtime_binding.py)

静态核对了留存的官方 Apple Silicon app 归档，SHA-256 为 `ac6554f108fd5a901a425b7e144f738cb919e83efd2d84ef031511ded3c9ba9b`。原生可执行文件包含 `desktop-proxy`，随包后台内含对应代理及所有权模块。Windows 隔离测试验证新建两个窗口会得到两个后台，选择已占用的探针会返回 409 并保留原状态。客户 Mac 的窗口重开过程未在本机实跑。[原生包来源](v050-native-release.md)

候选版在原生桌面的占用提示旁提供“在浏览器打开已有连接”。代理按所选探针的稳定 ID 查找持有物理连接的后台，核对实例和探针后申请一次性本机 GUI 票据，并在系统浏览器打开该后台。原窗口与原采集继续工作。MCP 的 `gui_open(probe=...)` 也可复用该后台。[GUI 后台选择](../../mklink/runtime_gui.py) · [桌面代理](../../mklink/runtime_proxy.py)

Windows 相关 Python 回归 167 项、配置页测试 53 项及前端生产构建通过。原持有者已退出或更换探针时将提示重新选择。

## 同一后台中的 RTT

采集线程将上行字节存入分通道缓存，并分发给 GUI 终端等订阅者。读取缓存使用采集会话、通道和每个读取者自带的游标，返回值带有丢失字节数。客户端读取不会推进其他客户端的游标。`WrOff == RdOff` 只表示观察时目标端该环形缓冲区没有待取数据。[采集与解码](../../mklink/remote/dashboards.py) · [字节缓存](../../mklink/rtt_cache.py)

默认的 `mklink rtt --duration 5` 可附着正在运行的 RTT，等待后返回 `rtt_history`。该接口保存解析成功的波形点。普通日志可同时出现在终端和字节缓存中，而 CLI 返回空的 `points`。已有采集时，CLI 还将显式 `--channels` 和 `--addr` 原样放入启动参数，即便与当前配置相同，后台也会将带参启动作为重新配置拒绝。逻辑上的修复是让读取端在用户请求的时间窗口内按通道游标读取字节；选择已有通道只影响本次读取，要求改变采集设置时另行处理。[CLI 入口](../../mklink/runtime_cli.py) · [订阅准入](../../mklink/runtime_api.py)

在实际 GUI HTTP 启动路径、CLI 命令入口和共享后台做了隔离试验，目标设备由模拟源代替。GUI 启动通道 0，终端收到 13 字节 `board ready\r\n`。默认 CLI 返回 `reused=true`、`points=[]`。两个客户端分别从游标 0 读取 `rtt_read_channel`，在同一采集会话得到相同的 13 个字节。再次指定相同通道或相同控制块地址，各自返回 409，原采集继续运行。86 项现有测试及上述专项试验通过。第二位用户当时连接的运行时实例、采集会话与通道未知，无法从单张截图确认其空输出具体由哪一条路径导致。

Windows 再用已安装的 V0.5.0 后台命令行、真实 Edge、两个本地后台及一个模拟目标复验。第二个后台选择同一探针得到 409，浏览器从新入口登录已有后台，成功读取设备状态并启动 RTT。在两个实时 WebSocket 订阅者就绪、独立 CLI 进程附着后注入 650 字节纯文本。两个订阅者逐字节收到全部数据，丢批、游标丢字节及 MUX 丢字节计数均为 0。两个独立的安装版 CLI 进程再从游标 0 读取，各得到相同的 650 字节。默认 CLI 同时返回空波形列表。采集只启动一次，全部读取完成时仍在运行，停止次数为 0。本次覆盖后台分发与客户端读取，客户现场 USB 传输与持续高负载未复测。[读取命令与缓存边界](../../references/shared-runtime.md)
