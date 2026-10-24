<div align="center">

# MKLink AI Probe

**把嵌入式烧录与调试交给 AI，用波形和日志看结果。**

[下载中心](https://download.microkeenai.com/) · [使用文档](https://microboot.readthedocs.io/zh-cn/latest/tools/microlink/microlink/) · [官方仓库](https://github.com/MicroKeen/Mklink-AI-Probe) · [问题反馈](https://github.com/MicroKeen/Mklink-AI-Probe/issues)

</div>

MKLink AI Probe 为 MKLink/MicroLink/HPMLink 下载器提供桌面界面、Web 界面，以及供 AI 使用的 Skill、CLI 和 MCP 工具。你可以直接操作界面，也可以让 AI 结合工程完成烧录、变量观察和故障排查。

## 从一句话开始

把下面这段话发给能够操作本机文件和软件的 AI 助手，例如 Codex、Claude Code 或 Cursor：

> 请从 https://github.com/MicroKeen/Mklink-AI-Probe 安装 MKLink AI Probe 最新正式版。按照仓库的 Skill 和安装文档，为你自己安装完整 Skill，配置运行环境并完成自检。优先从 https://download.microkeenai.com/ 下载，保留 GitHub/Gitee 备用。检查下载器和目标板连接，并打开调试界面；涉及烧录、供电或保护配置时，先说明操作内容。

AI 助手需要本地文件和程序执行能力。普通网页聊天需连接本地执行环境；系统授权提示由你在电脑上确认。将工程目录、目标芯片和要完成的任务告诉 AI，它会先检查设备能力与资源，再选择操作方式。

## 下载与安装

在[下载中心](https://download.microkeenai.com/)选择所需资源，也可以查看历史下载。最新正式版本与更新说明以下载中心和 [GitHub Releases](https://github.com/MicroKeen/Mklink-AI-Probe/releases/latest) 为准。

| 资源 | 用途 | 如何选择 |
| --- | --- | --- |
| Windows 安装包 | 在电脑上使用上位机 | 下载 `*-Setup.exe`；自带后台运行环境，无需单独安装 Python |
| 完整 AI Skill | 让 AI 使用烧录、调试和数据分析工具 | 下载 `*-Skill.zip`，按包内安装文档配置依赖与 MCP，并完成自检 |
| 下载器固件 | 升级下载器自身 | 按 V2、V3、V4，以及 MicroLink/HPMLink 的实际型号选择；不要混用 |
| Windows Site Agent | 在设备现场运行远程服务 | 下载 `*-windows-x86_64-portable.zip`，按远程连接文档配置 |

完整 Skill 已包含常用芯片的 FLM 和 Pack/SVD 资源。GitHub 自动生成的源码 ZIP 用于开发，不能替代完整 Skill 发布包。芯片名称不完整时，AI 可以模糊搜索候选型号，再结合工程和板卡信息确认。

下载资源优先使用腾讯云 COS，保留 [GitHub Releases](https://github.com/MicroKeen/Mklink-AI-Probe/releases) 和 [Gitee Releases](https://gitee.com/Aladdin-Wang/Mklink-AI-Probe/releases) 备用。软件默认提供 Windows 安装包；Linux/macOS 安装包是否可用，以对应发布页面为准。Gitee 受附件大小限制，部分安装包会使用页面注明的备用地址。

## 可以完成什么

| 功能 | 使用方式 |
| --- | --- |
| 在线烧录 | 根据芯片和固件选择算法，预览地址与扇区，执行擦除、下载、校验和复位，查看实际烧录进度 |
| 脱机烧录 | 将固件与配置部署到下载器，脱离电脑后烧录；BIN/HEX 校验默认开启，关闭前检查固件能力，不支持时提示升级 |
| SuperWatch | 从 ELF/AXF 符号选择变量、结构体成员和数组，连续采样、实时写入、分组观察；支持中文名称、公式、曲线颜色与日志回放 |
| 文件与波形 | 无设备时可加载符号或回放日志；重载文件会停止旧采集，断开后保留变量选择，方便继续分析 |
| RTT、VOFA、SystemView | 查看多通道运行日志、实时数据波形和任务时间轴，支持对应的记录与分析工作流 |
| 内存、寄存器与故障 | 读取目标内存和寄存器，结合工程符号调试、单步和分析 HardFault 现场 |
| 串口与 Modbus | 收发文本或二进制数据，进行 Modbus 设备读写；需要连接相应串口线路 |
| ISP 与 HPM | 按目标芯片和下载器能力使用串口 ISP、HPM JTAG、脱机配置及 OTP 工具；需要配套固件和实际接线 |
| 远程调试 | 在设备现场运行 Site Agent，从远端通过界面或 AI 工具访问设备 |
| 诊断导出 | 在“配置 → 后台管理”导出诊断包，保留带时间戳的连接、错误和重连记录，便于复现问题后反馈 |

具体能力取决于下载器型号、固件、目标芯片和接线。算法目录覆盖不等于每种芯片和功能均已完成真机验证；HPM 实时通道需要支持它的 V4 下载器，V2/V3 不支持。OTP、保护配置和供电操作应先核对目标与参数。

## 把任务告诉 AI

| 想完成的事 | 可以直接这样说 |
| --- | --- |
| 下载程序 | “板子已经接好，请检查这个工程，编译并下载固件，再确认运行结果。” |
| 观察变量 | “打开 SuperWatch，把目标转速和反馈转速放在一组，用不同颜色显示。” |
| 调节参数 | “帮我观察这个参数，确认写入值后修改，并记录变化前后的波形。” |
| 处理单位 | “将温度原始值按公式换算后显示，保留原始数据。” |
| 分析历史数据 | “导入这份采集日志，回放异常前后的波形并分析原因。” |
| 排查故障 | “程序进入 HardFault 了，请读取现场并结合工程定位问题。” |
| 配置脱机下载 | “把这些固件配置到下载器，保持下载后校验开启。” |
| 更新工具 | “检查正式版更新，更新上位机和完整 Skill，完成后重新自检。” |

## 桌面、Web 与 AI 一起使用

Windows 上位机安装后可直接打开，Web 界面提供同一套操作入口。GUI 和 AI 可以共享同一后台、符号文件和设备连接，避免为同一个下载器重复建连。多个下载器分别使用独立后台；切换目标工程或重载符号前，先停止旧采集。

详细连接方式见[共享后台与多下载器](https://github.com/MicroKeen/Mklink-AI-Probe/blob/main/Mklink-AI-Probe/references/shared-runtime.md)。远程设备使用 Site Agent，按文档配置连接与访问范围。

## 更新与问题反馈

上位机和 Skill 通过正式更新通道检查更新。下载器固件独立更新：在固件升级页检查实际型号及构建信息，按提示升级；固件能力不足时，上位机会提示需要升级。更新 Skill 后，重新启动 AI 的 MCP 会话，使新工具代码生效。

遇到异常时，尽量在重新拔插或重启前，从 **配置 → 后台管理 → 导出诊断包** 保存现场，并记录发生时间、操作步骤、下载器/目标型号和复现频率。可以让 AI 先分析诊断包，再整理反馈。

开发与问题反馈统一在 [MicroKeen/Mklink-AI-Probe Issues](https://github.com/MicroKeen/Mklink-AI-Probe/issues)。提交前检查诊断包，移除设备序列号、私有工程路径、私有固件和访问凭据；公开讨论中不要上传完整私有工程。

MIT License
