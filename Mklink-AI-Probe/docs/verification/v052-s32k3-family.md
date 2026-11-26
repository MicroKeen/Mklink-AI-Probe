# S32K3 上位机型号与验收

桌面、Web、CLI、共享 MCP 和在线烧录支持选择下表的 22 个规范型号。连接后检查 Cortex-M7 主核与型号，返回规范名和 MEM-AP 4。当前实板覆盖 S32K314、S32K344。其余型号可以按手册配置使用。

| 型号 | 内置在线算法 | 实板覆盖 |
| --- | --- | --- |
| S32K312、S32K322、S32K342 | S32K3x2 Code 和 Data | 待验 |
| S32K314、S32K324、S32K344 | S32K3x4 Code 和 Data | 314、344 的范围见下文 |
| S32K310、S32K311、S32K328、S32K338、S32K341、S32K348、S32K356、S32K358、S32K388、S32K389 | 按具体型号导入供应商 Pack 或 FLM | 待验 |
| S32K364、S32K366、S32K374、S32K376、S32K394、S32K396 | 按具体型号导入供应商 Pack 或 FLM | 待验 |

## 选择与识别

共享 MCP 调用 `list_target_profiles()`，再用 `connect(probe=…, mcu="S32K344", project_root=…)` 连接。回执应含 `target_attach.profile="S32K344"` 和 `mem_ap=4`。后续读变量、RTT、SuperWatch、MEM 复用这一会话。CLI 使用 `mklink target-profiles` 和 `mklink device-status --probe … --mcu s32k344`。桌面与 Web 通过配置页选择探针和型号。在线烧录页使用单独的 CMSIS-DAP 会话，同样先核对型号和主核。

两本参考手册的 MIDR1 枚举给出每个型号的独立 PART_NO。上位机检查 SIUL2.MIDR1 的位 31–26 为 K 系列值 0x0B，位 25–16 为所选型号的十进制数字。封装和硅修订位不用于区分 SKU。两册分别给出 M7_0、MDM、SDA 的 AP4、AP6、AP7 拓扑。仅绑定主核；其他内核和 AP 的数量按器件而不同。[NXP S32K3xx RM Rev.11，第 352–353 页、表 827](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/S32K3xx-Manual.pdf)；[NXP S32K39/37/36 RM Rev.4，第 208 页、表 753](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/6487/S32K3_Reference%20Manual.pdf)

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
- 同一台 S32K344 上，生产在线任务在 Init 返回 0 后于 EraseSector 期间失去 SWD。现场确认有外部看门狗，其作用尚未独立验证。按用户约定仅做短测。最终 GUI 已加载测试 ELF 并显示三个变量；台架最后观察到原应用的 VTOR。S32K344 完整在线擦写、两板的 Data Flash 实际擦写、其余 20 型号的硬件行为和同条件性能仍待验证。
