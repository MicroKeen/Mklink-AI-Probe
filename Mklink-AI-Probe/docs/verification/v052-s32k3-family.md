# S32K3 上位机型号与验收

USB SWD 调试通过下载器和目标芯片识别下表 22 个型号。桌面、Web、CLI 和 MCP 共享同一连接。ELF、AXF 和 IAR OUT 提供调试符号。表格列出在线算法及此前的实板覆盖，本次硬件识别的验收范围单列于下。

| 型号 | 内置在线算法 | 实板覆盖 |
| --- | --- | --- |
| S32K312、S32K322、S32K342 | S32K3x2 Code 和 Data | 待验 |
| S32K314、S32K324、S32K344 | S32K3x4 Code 和 Data | 314、344 的范围见下文 |
| S32K310、S32K311、S32K328、S32K338、S32K341、S32K348、S32K356、S32K358、S32K388、S32K389 | 按具体型号导入供应商 Pack 或 FLM | 待验 |
| S32K364、S32K366、S32K374、S32K376、S32K394、S32K396 | 按具体型号导入供应商 Pack 或 FLM | 待验 |

## 选择与识别

共享 MCP 调用 `connect(probe=…, project_root=…)`，CLI 使用 `mklink device-status --probe …`。回执 `target_attach` 含实际型号、MEM-AP、DPIDR、TARGETID 和原始 MIDR1。可选 `mcu` 要求实物符合指定型号。后续读变量、RTT、SuperWatch、MEM 复用该会话。在线烧录独立校验所选芯片、主核、FLM 及其地址范围。

文件可以通过 ELF 非加载节 `.mklink.target` 的版本 1 JSON（`schema_version` 和 `device`）、明确的 ARM 属性、DWARF 编译单元或行表中的器件文件名声明型号。使用构建旁证时，Keil `.uvprojx` 和 IAR `.ewp` 逐个目标或配置核对输出目录和文件名，CMSIS `.cbuild-run.yml` 核对 `output[].file` 和 `type: elf`，GNU 构建可使用同名 `.map` 中带具体型号的启动对象。关联工程只解析数据。独立交付的 ELF 可使用 `<文件名>.mklink.json`，以整个 ELF 的 SHA-256 绑定型号。浏览器上传单文件时，可用依据仅来自文件内部。[CMSIS 构建信息格式](https://open-cmsis-pack.github.io/cmsis-toolbox/YML-CBuild-Format/)

`mklink image-target <文件>` 可离线查看文件标注的型号及来源。连接后打开或更换符号文件沿用同一 AP4。文件资料冲突记录在 `axf.image_target`，有明确文件型号时 `matches_hardware` 表示它与当前目标是否相符。

两本参考手册的 MIDR1 枚举给出每个型号的独立 PART_NO。上位机检查 SIUL2.MIDR1 的位 31–26 为 K 系列值 0x0B，位 25–16 为所选型号的十进制数字。封装和硅修订位不用于区分 SKU。两册分别给出 M7_0、MDM、SDA 的 AP4、AP6、AP7 拓扑。仅绑定主核；其他内核和 AP 的数量按器件而不同。[NXP S32K3xx RM Rev.11，第 352–353 页、表 827](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/S32K3xx-Manual.pdf)；[NXP S32K39/37/36 RM Rev.4，第 208 页、表 753](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/6487/S32K3_Reference%20Manual.pdf)

## 硬件识别验收（2026-11-27）

上位机功能提交 `17ddf0ac`。原生 MUX HELLO 要求 0x2000 和 0x4000。0x19 只读 SWD DPIDR 和 TARGETID。系列筛选使用手册表 829 与表 755 的设计者和部件号，容许 TREVISION 不同。系列命中后在同一 claim 的 0x18 中复核完整 TARGETID，核对 AP4/6/7 和已有调试权限，执行 AP7 更新及 CPUID 检查，最后采集 AP4 SIUL2.MIDR1。固件把型号位固定在绑定中，目标更换后拒绝旧绑定。未命中系列时退出探测，使用普通连接。

主机与固件 C 调度器联测覆盖目录全部 22 个 MIDR1、模拟换板拒绝旧会话、无关 TARGETID 零 AP 访问。型号覆盖是模型测试，S32K3 新时序的冷启动实板验证待补。配套固件来源为 [MicroLink_Plus PR #29](https://github.com/Aladdin-Wang/MicroLink_Plus/pull/29)。

固件会话在配套 MicroLink V4.7.5 与 STM32F103 实板上读到 DPIDR 0x1BA01477、TARGETID 0；线缆记录含一次普通 0x13、零次 0x18。Flash 回读 118272 字节与 AXF 相同，变量写回后恢复。RTT 收 2523 字节，同时 SuperWatch 交付 61 项、零丢弃。原始记录位于 `F:/MKLink-Build/runs/s32k3-hw-discovery-20261127/STM32F103-physical.json`。

## 0.5.2 Windows、完整 Skill 与 Web GUI

桌面、共享后台、Skill 与 Web 版本均为 0.5.2。功能与版本源为 `5904f9b6`，从该版构建的 Web 资源收录于 `8c8423e9`。完整 Skill ZIP 和 NSIS 自带 92 个相同的前端文件。客户包存放于 `F:/MKLink-Build/artifacts/V0.5.2-Customer-5904f9b6/`，两个 SHA-256 列入同目录的 `SHA256SUMS.txt`。

| 客户验证包 | SHA-256 |
| --- | --- |
| Windows x64 NSIS | `f8299da241bc7f024475e3844b24f49693c7e98838681a3e860a2d6d15b3fa48` |
| 完整 Skill ZIP | `43676c2cb79feb77e0fff78280c79b2a4b4918c64c15c298d17add6b2b58ce2a` |

本轮软件回归通过 1996 项 Python 测试及 62 项前端测试。本机在原目录覆盖安装 Windows 版后逐文件核对 3756 项，保留原设置和快捷方式。安装目录的桌面、Web、CLI 与真实 stdio MCP 验证通过。固件 C 模型与安装包内代码再次对接 22 种 MIDR1，并验证换型号后旧会话拒绝访问。

完整 Skill 由 0.5.1 覆盖至 0.5.2，核对全部 2751 个文件，独立 Python 运行环境的元数据与实际导入目录一致。包中含 7059 条算法目录记录、2224 个去重 FLM 文件和覆盖 4800 个目标的外设资源。实际安装的 Skill MCP 启动并列出 60 个工具。Edge 打开其 Web GUI，在模拟 S32K344 上加载标注 S32K312 的符号文件，同时显示了文件型号和实际硬件型号。窗口生产资源、安装记录和截图见 `F:/MKLink-Build/reports/s32k3-customer-5904f9b6/`。

## 先前精确型号连接的现场诊断

一次现场截图显示请求 S32K312，MUX 返回 `step=7, reason=8, actual=0x2D580000`。这次失败的操作是 AP4 上的 SIUL2.MIDR1 比较，地址为 `0x40290004`，期望值为 `0x2D380000`，掩码为 `0xFFFF0000`。按 NXP 手册中的产品线和 PART_NO 字段，实读值中的 `0x158` 对应 S32K344。上位机显示“本次配置 S32K312，目标寄存器报告 S32K344”，并提供已知的配置来源和原始失败回执。查看截图时无法追溯当时的配置来源。

客户随后反馈接的是 S32K312，此前选错了 ELF。更换 ELF 后，同一块板的原始读数待补。此前 S32K344 台架的读数来自另一块板。

`92ee8eed` 回放了这条原始报文。当前调试连接直接采集型号，在线烧录仍对显式目标执行精确比较。

## 在线擦写与复位

算法目录可通过 `GET /api/online-flash/targets/{part}/algorithms` 查询。缺少资产的型号可以连接、读变量和复位。匹配的供应商 Pack 导入后按设备条目发现算法；独立 FLM 需明确导入到对应型号，并由 FlashDevice 提供几何。S32K322 与 S32K342 在 RM 表 102 中具有相同的两块 1 MiB Code Flash 和 Data Flash 块号。内置目录只有在两份 x2 供应商资产摘要匹配时才给 S32K322 提供它们。39/37/36 的 Flash 按 2 MiB 分块，S32K389 含两个控制器，不能从相同的起始地址推导可用算法。[Keil S32K3xx DFP](https://www.keil.arm.com/packs/s32k3xx_dfp-keil/devices/)

| 内置算法 | 可用地址范围（结束地址不含） |
| --- | --- |
| x2 Code | 0x00400000 至 0x005E0000 |
| x4 Code | 0x00400000 至 0x007E0000 |
| x2、x4 各自的 Data | 0x10000000 至 0x10020000 |

这六个型号的内置工作 RAM 为 0x20400000 至 0x20410000。独立导入 FLM 时，如无 Pack 提供工作区，按两册附带的 memory_map 表限制首块 SRAM0。S32K310 最多 16 KiB，S32K311 最多 32 KiB，其余上限为 64 KiB。

在线明确选定 Pack 时，从该文件的精确设备条目创建 pyOCD 目标。Keil 1.0.1 的 S32K344 主核名为 Cortex-M7_0，Flash 区域名为 PFlash 与 DFlash。软件复位优先执行已载入 Pack 的复位序列。没有 Pack 时，DFP 定义的四个型号 312、314、324、344 使用其 FunctionalReset 序列。其余型号使用手册定义的 MDM-AP 功能复位位，并保留其他控制位。复位后重新建立会话并复核身份；遇到结果不确定的写入需要人工确认目标状态。

## 验收范围

- 软件回归逐一核对 22 个 MIDR1、主核绑定与复位路由，模拟六个型号各自的 Code/Data 在线下载、校验和读回。真实 stdio MCP 通过模拟串口对 314、344 验证能力协商、绑定、内存访问和失败诊断。
- 使用真实 Keil 1.0.1 Pack、模拟探针，验证选中的 S32K344 实例来自该 Pack。真实 Edge 运行生产 Web 资源，模拟探针目录下选择 S32K396 后读回入口可用，擦写需要导入算法，切换 S32K344 后出现内置 Code 与 Data。
- S32K314 的产品在线完整擦写、软件复位、独立全页回读和真实浏览器读回见[314 验收记录](v052-mux-profile-attach.md)。
- S32K344 台架由固件会话操作。AP4 实读 CPUID 为 0x411FC272，MIDR1 为 0x2D580000。10 MHz 通过供应商 Code FLM 写入 1592 字节，独立 MUX 会话逐字节核对完整 8192 字节。测试程序短时运行时，SuperWatch 计数 213→337，RTT 连续收到 207 条，下行消费 4 字节，MEM 回显 AD BA 12 AB。
- 随后经用户另行授权，固件会话直接调用供应商 Code FLM，在 10 MHz SWD 下擦除原启动扇区 0x00400000–0x00401FFF，写入 3640 字节测试镜像。现场未备份原扇区。独立原生 MUX 会话通过 AP4 读回整扇区 8192 字节，SHA-256 为 `9cc7c603d14513bcb54011222550373318900971cb626c6d599ddac4bd2dcaa9`。AP6 功能复位的四步均收到应答，复位后读到 VTOR 0x00400800 和测试标识 0x4D4B3331。GUI 加载 `boot/fixture.elf` 后，SuperWatch 实测计数 3012546→3013543。RTT 和 MEM 的数据来自上一轮短测。
- 上位机生产在线任务此前在 Init 返回 0 后于 EraseSector 期间失去 SWD。现场确认板上有外部看门狗，其与掉线的因果关系待验证。完整 GUI 一键擦写、两板的 Data Flash 实际擦写、其余 20 型号的硬件行为和同条件性能仍待验证。

- ELF 自动识别软件验收覆盖启动版 ELF、Keil 实际工程文件、IAR 实际配置、GNU map、CMSIS run、无 SKU、不关联的工程和错误摘要。启动版 ELF 的“文件来源”解析出 482 个变量。固件会话在独立空工程中只传探针和 ELF，实板回执为 S32K344 / AP4，读回 MIDR1 0x2D580000、VTOR 0x00400800 和测试标识 0x4D4B3331。Web SuperWatch 实测计数 7324690→7326485。
- Windows x64 客户验证包使用功能提交 `c55de23d`，保持 0.5.1，未签名。SHA-256 为 `5a37f09741e02e830d7c5719adb818e7b6a4ce4542f6a31e971628cd705ae72a`。覆盖安装后逐文件核对 3756 项，原设置和快捷方式保留。安装目录的 CLI 和真实 stdio MCP 独立启动，Edge 点击“解析符号”显示 S32K344 和 482 个变量。软件回归 297 项 Python 和 89 项 GUI 通过。
