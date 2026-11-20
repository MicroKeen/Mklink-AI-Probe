# 探针、离线下载与 HPM OTP

这些 MCP 工具复用共享后台协议 53。先 `connect(probe=...)`，按 `tools/list` 与
`ping.capabilities` 核对当前安装；旧后台报版本不匹配时需更新/重启后台，不另开串口绕过。
下列能力缺少固件应答时明确报错；不能把“入口存在”当作这台探针已经支持。

## 探针诊断与配置

| 工具 | 参数和结果 |
|---|---|
| `probe_presence` | `interface="SWD"` 或 `"JTAG"`。实时查询，不强制切换接口；`present=null` 表示错误/忙/未知，不能判定拔板。缓存 `probe_idcode` 不替代它。 |
| `probe_diagnostics` | `index=-1` 读探针堆；`-2` 读探针复位报告；`0..31` 读线程栈水位，遇 `MEM_END` 停止。不是目标 MCU 内存；水位不保证不会溢出。当前 V2 固件未提供此接口。 |
| `probe_control` | `setting="auto_scan"/"beep"/"auto_follow_vref"`、布尔 `enabled`、`confirm_user=true`。蜂鸣器开启后需明确关闭；扫描开关改变探针发现行为。 |
| `set_power_on` | `voltage_mv=1800/3300/5000`，每次先获用户具体电压确认，再传 `confirm_user=true`；5 V 另须 `confirm_5v=true`。 |
| `set_power_off` | 每次确认断电后传 `confirm_user=true`。 |
| `reboot_probe` | `confirm=true`，重启所选下载器而非 MCU；主动停止该探针的采集并结束其目标订阅，其他下载器不受影响。已接受的烧录操作先完成，不自动重连或重发。 |
| `isp_link_probe` | `baud_rate=115200/1000000/2000000/5000000/10000000`、`duration_ms=1000..120000`、可选 `strict=false`。目标预先处于匹配波特率的 ROM ISP；释放独立 UART 客户端。 |

所有操作要求采集空闲，不抢停任务。配置的 `acknowledged` 只确认固件返回值，
不证明持久化或物理电压；需要测量时另读 `get_power`。结果未知不重放写命令。
`auto_follow_vref=false` 可关闭跟随；开启暂拒绝，因为固件尚无可确认参考电压的受限接口。
不得用原始命令绕过，用单独确认的 `set_power_on` 设置具体电压。

ISP link probe 仅观察连接丢失/恢复；成功不等于烧录成功。不会写 Flash/OTP、复位或改 VCC。
普通串口的 `serial_ymodem_start` 是主机发送文件。固件 `ym.receive` 暂不作为已支持能力；
即使旧固件返回 0，也没有接收成功证据。

## 离线下载与 ROM UART ISP

按 `offline_download(action="status")` → `preview` → `deploy` → `trigger` 执行。
预览不写下载器；部署写绑定探针的磁盘，不烧目标；触发才运行已部署脚本。
部署/触发各保存不同的唯一 `request_id`，明确授权后传 `confirm=true`。
触发返回后台 job，使用 `job_status(job_id=...)` 查终态。响应丢失先按 request_id 查
保留任务；未知或已不在最近 64 项中都不允许盲目重放。

HPM JTAG 预览/部署的 `config` 示例（替换为实际工程）：

```json
{
  "model": "V4",
  "script_name": "hpm-project.py",
  "target_part": "HPM5301",
  "board": "hpm5301evklite",
  "swd_clock_hz": 10000000,
  "auto_download_count": 1,
  "algorithms": [],
  "firmwares": [{
    "id": "app", "file_name": "app.bin", "format": "bin",
    "base_address": "0x80000400", "algorithm_id": "",
    "source_path": "<后台机器上的固件绝对路径>"
  }]
}
```

`source_path` 和 `upload_index` 二选一；MCP 使用后台本地 `source_path`，不传二进制附件。
ARM 的 `algorithms` 可用 `source_kind="upload"` 加本地 `source_path`，或 GUI 目录返回的
Pack/profile token。固件的 `algorithm_id` 必须匹配；HPM 不提供 FLM。
BIN 必须给真实基址，HEX 使用文件中地址。新增时钟档位在部署前检查固件能力。

触发的 `config` 只含 `model`、`script_name`、`programming_protocol`（默认 `debug`）。
ROM UART ISP 使用 `programming_protocol="hpm_rom_isp_uart"`、V4、BIN，预览/部署还需
独立 `hpm_isp` 配置，不能同时传 JTAG `board/hpm_flash_cfg`。完整参数及启动条件见
[USART ISP](hpm-usart-isp.md)；不能根据示例猜目标 NOR 容量。
VCC、OTP、保护等配置中的操作仍需单独批准，普通烧录授权不替代不可逆操作确认。

## HPM OTP

`hpm_otp(transport="jtag"|"isp", action=..., arguments={...})` 复用 GUI 的身份和字段限制。
先读、预览，核对芯片身份及实际位变化；不可逆写入/锁定每次需用户明确授权。
不允许通用写内存或 ARM 安全工具绕过。失败、超时、断连均不自动重发。

JTAG 完整读取使用 `action="read", arguments={"part_number":"HPM6E80","model":"V4","extended":true}`。
脱机页选择 V4、目标型号和 JTAG 后，在 OTP 操作中点刷新，可查看 0–127 字、字段、熔丝和影子寄存器，并导出可读熔丝值。
所选型号决定字段和地址映射。TAP ID 为系列共用；当前接线须与所选型号一致。禁止访问的字在对应列显示为 —。

HPM6E80（含 IGN、IVM）的 JTAG 用户字写入需要 HPMLink 的 `otp_rom_version() == 1`。宿主按已核对的 CHIP_ID、ROM ABI、暂存 RAM 和 3.3 V 板级供电配置生成参数，固件现场核对电压、保护和原值。Word 69–79 可存应用数据。先确认目标由 Flash 启动、复位后 hart 0 的 ILM 尾部 4 KiB 可临时使用，其他内核和总线主设备不会使用这段 RAM。每块板的业务位分配由用户确认。读出 0 不能证明位置空闲。

桌面和 Web 的脱机 OTP 页刷新后可切到写视图。展开「直接写入当前芯片」可预览并单次写入，下面的编辑器可将用户字加入脱机配方。V4.7.4 能读取 HPM6E80，缺少 ROM v1 能力时预检返回升级提示。CLI 和 MCP 的 `plan` 接受型号、Word、原值和目标值，`program` 只接受同一型号、预览返回的 `plan_id` 和 `confirm_irreversible=true`。凭据绑定探针、连接代次和芯片 UID，60 秒有效，提交时即消耗。其他型号按可信配置逐一接入。

HPM5301 旧接口支持用户字 69..79、锁定组 18/19。以下为旧接口参数。

### 增加已核对的型号或修订

HPM51、53、5E、62、63、64、67、68、6E、6P 的寄存器和 ILM 地址映射均在上位机。新增型号时，启动后台前可将环境变量 `MKLINK_HPM_OTP_QUALIFICATIONS` 指向维护者审核的本地 JSON 绝对路径。桌面、Web、CLI、MCP 和脱机配方均使用该配置。默认只加载内置型号。

文件顶层是 `{"schema":1,"parts":{...}}`。`parts` 的键为具体七位芯片型号，封装后缀复用对应芯片。每项需要以下字段。

| 字段 | 取值依据 |
|---|---|
| `chip_id`、`driver_version` | 已独立确认丝印、型号和修订的参考板及厂商 ROM 资料，分别对应 OTP Word 64 和 OTP 驱动接口版本。禁止在一次写入请求中复制当前目标读数作为匹配依据。 |
| `scratch_offset` | hart 0 ILM 内 16 字节对齐的 4 KiB 可用窗口偏移。结合已验证的启动方式、芯片容量、其他内核及总线主设备用途确定。 |
| `min_mv`、`max_mv` | 已确认 JTAG VREF 接目标 3.3 V 电源，填写板卡和芯片共同允许的毫伏范围，限 3000–3600。 |
| `user_words`、`evidence` | 在该型号资料中验证 Word 69–79 全部属于应用数据后填 `[69,79]`，并记录板卡、手册章节、ROM 和供电核对记录。芯片安全、引导、密钥和锁定位不属于该通用接口。 |

### HPM5301 兼容接口参数

脱机页的 JTAG OTP 采用读/写视图，可刷新所选已连接下载器的用户区、导入/导出 CSV，
编辑预期旧值并确认随镜像部署。配置仍走 `offline_download` 的 `hpm_user_otp`，
不立即写熔丝；编辑、换设备或连接代次变化后确认失效。系统字段只读，范围不因界面统一而扩大。

- `read`：`part_number="HPM5301"`，可选 `model="V4"`。
- `plan`：再加明确的 `word`、`expected`、`desired`；值可为整数/十六进制字符串。
- `program`：使用确认过的同一组值，加 `confirm_irreversible=true`，后端执行前重新核对原值。
- `lock-plan/lock-program`：`word`、`expected`，锁定操作另加 `confirm_irreversible=true`；不传 desired。

ISP 支持 `read/plan/program/batch-plan/batch-program`：

- `read`：`part_number`、`model="V4"`、可选 `extended=false`。
- `plan`：增加整数 `word/expected` 和整数或十六进制字符串 `desired`。
- `batch-plan`：增加 `changes=[{"word":...,"expected":...,"desired":...}]`。
  扩展系列使用 `extended=true`，只走 batch，按返回结果核对 `target_identity`。
- `program/batch-program`：只提交相同 `part_number/model/extended`、返回的 `plan_id`、
  `confirm_irreversible=true`。不重新附加可变的写入数据。

ISP plan_id 有有效期，绑定探针、连接代次和型号；程序开始前即消耗，仅能使用一次。
预览若 `qualified/write_supported` 不为 true 或没有 plan_id，禁止继续。实际支持系列和
字段以 [ISP OTP 指南](hpm-usart-isp.md) 及当前配置描述为准，不从系列相似性推断 OTP 可写。
