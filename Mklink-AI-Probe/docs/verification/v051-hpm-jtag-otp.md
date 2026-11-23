# HPM 全系列 JTAG OTP 读取

2026-11-19。开发源 `b9249e23`，生产 GUI 资源 `e25de42b`，产品版本 V0.5.0。

## 型号与读取范围

脱机烧录选择 V4、芯片和 JTAG，打开 **OTP 操作 → 刷新**。可按 4 或 8 列查看 Word 0–127、字段位段、十六进制、二进制、熔丝、影子和写保护，导出可读取熔丝的 Word/Value CSV。Web、桌面共用页面，CLI 和 MCP 共用后端。完整读取参数见 [Skill 说明](../../references/probe-workflows.md)。

芯片目录收录[厂商选型表](https://www.hpmicro.com/product-center/microcontroller/all-product)的 41 个芯片型号、76 个封装料号，并保留系列入口和旧别名。UART ISP 已有的八份字段表供 JTAG 复用，HPM6400 与 HPM6700 共用一份。HPM5100 的 JTAG 字段取自 SDK 的 HPM5151 OTP 表。选定型号决定显示模板，通用 TAP ID 无法独立识别具体料号。

寄存器依据 [HPM SDK 1.13.0](https://github.com/hpmicro/hpm_sdk/tree/v1.13.0/soc) 的 `hpm_soc_ip.h`、`hpm_otp_regs.h` 和 OTP 驱动。按系列读取两组寄存器及各自的访问锁。禁读位置返回 null；传输失败、短读、芯片标识异常或读取期间检测到锁变化时丢弃快照。旧 HPM5301 公共字段、用户区写入和锁定配方沿用原有接口和资格检查。

## 实板和浏览器

用户指定 HPM6E80。已连接的 HPMLink V4.7.4 采用 JTAG 30 MHz。Chrome 加载本分支最终生产资源，通过器件搜索选择 HPM6E80，进入脱机 OTP 页面并刷新。测试调用候选 FastAPI 读取路由，设备适配器通过已安装后台的共享内存读取 API 使用现有探针，每次请求绑定探针身份与连接代次。该方式保留了用户桌面连接。

- 实际获得 128 个熔丝值、128 个影子值，以独立 4 字节请求逐项回读，256 次比较全部一致。
- 4 列、8 列分别显示 32、16 行。选择 Word 64 显示 CHIP_ID 位段。浏览器下载路径导出的 CSV 共 128 个数据行，索引及数值与快照逐项一致。此项在关闭原生文件选择器的隔离浏览器上下文中验证。
- 浏览器页面异常 0。验证前后同一探针、连接代次及 READY 状态一致；全程只读。原始 OTP 内容、CSV 和设备标识未纳入仓库。

## 回归与边界

通过 `scripts/build_workspace.ps1` 在 F 盘执行 452 项 Python 和 122 项 GUI 定向回归，TypeScript 检查与生产构建通过。覆盖每个系列前缀、熔丝与影子独立禁读、身份变化、短读、HPM5301 配方、ISP 兼容、CLI/MCP、目录查询、多客户端准入和 Skill 边界。

本轮实板覆盖 HPM6E80，其他型号为 SDK 映射及软件回归。测试没有替换本机安装包、执行 OTP 写入或更换固件；无采集、传输层或调试时钟实现变更。

构建脚本保留了 4 个含测试链接的 pytest 运行目录。普通文件约 292 KiB，位于 F 盘构建根的 runs 下。自动审批以 `blocked by policy` 拒绝清理这些目录，已原样保留。
