# HPM USART ISP 脱机下载

在“脱机下载”中选择 HPM5301、V4，再选择 **USART ISP**。下载器必须运行启用 HPMLINK 且提供 USART ISP API v1 的固件；普通 V4 或旧固件不能使用此功能。当前适配 HPM5301、8N1，提供固定档位 115200、1M、2M、5M、10M，默认 2M。所选档位保存在本机，下次进入时恢复；旧版保存的任意值或 4M 等已移除档位，恢复为 2M。原 HPM JTAG ROM API 路径保持不变。

1. 连接下载器独立 UART 接口与目标，按目标板要求进入 ROM ISP。
2. Flash 范围自动采用应用内置 HPM5301 配置（基址 `0x80000000`、容量 2 MiB），无需在界面填写。该配置不是实测容量；使用其他容量的板卡时，API 仍可显式提供 `hpm_isp.flash_size`。默认 NOR 参数来自 HPM5301 示例；旧 JTAG `hpm_flash_cfg` 的第四字是控制器地址，不能复制为 NOR option。
3. 添加 1–8 个 BIN，写入地址默认 `0x80000400`，可按各固件布局修改，不要求等于 Flash 基址。重复文件名自动添加数字后缀，避免 SD 目标文件冲突；多个固件须分别设置不重叠的地址。
4. 设置次数、完成蜂鸣和复位。断电复位可选择 1.8V、3.3V 或 5V，默认 3.3V；执行前确认目标允许所选电压。硬件复位需要连接 RST。BOOT 引脚的恢复由用户或治具负责。
5. 生成预览后部署到下载器 SD 卡；在 V4 屏幕选择脚本执行，或在上位机触发测试。上位机仅部署文件和触发脚本，UART 协议及烧录在下载器上完成，不依赖 PC 逐包转发。

文件按地址升序执行；相邻文件合并为一次连续写命令。空文件、越界、地址重叠及不相邻但共享擦除扇区的文件会被拒绝。ROM 自动擦除并内部回读校验，不额外发送擦除或 Flash 回读命令。收到包 ACK 不代表完成，必须收到写命令的最终成功状态。

BIN 部署到 SD 根目录，配置中的 `file_name` 只填写文件名（例如 `app.bin`），不接受盘符或目录。生成脚本向固件传入无盘符的根路径 `/app.bin`，沿用脱机执行器当前挂载的 SD 盘。V4 的 FatFS `0:` 是 USB，不能用 `0:/app.bin` 代表 SD 文件。

高速档位需要包含相应支持的 HPMLINK 固件。每轮由固件先以 115200 握手，协商配置速度，写入成功后切回 115200 并查询确认，再执行完成动作。上位机前后端使用相同档位列表；固件仍接收数值参数并检查实际 UART 时钟/驱动及目标 ROM。不支持时返回失败，脚本停止，不自动回退或烧录。高速中断后，如果目标无法重新握手，需给目标重新上电以恢复默认速率。

档位依据 V4 原有 100MHz UART 时钟：1M/2M/5M/10M 使用 10 倍采样，整数分频分别为 10/5/2/1。115200 保留为 ROM 基础速率。4M 已按用户要求移除，避免增加备用外设时钟分频方案。12.5M 虽然下载器端可生成，但 HPM5301 实测切速后查询超时，未进入写入，因此不列为可选档位。实测结果与硬件范围见维护交接记录。

默认只执行一轮。多轮需要明确勾选“等待目标退出 ISP 后重新握手开始下一轮（不识别是否换板）”。固件等待连续多次完整 ROM 查询失联，再等待成功握手；通信错误不作为离线判断。**此机制不识别物理芯片身份，接触不良后同一块板重新握手也可能再次烧录。** 每轮等待均有超时，不能保证无限连续量产。

上位机显示 ISP 等待/连接状态，完成结果以匹配任务的 `HPM_ISP` JSON `result` 为准。未收到终态则显示结果未知，并禁止再次触发；先确认下载器状态。写入成功不等于已经验证应用正常启动。软件复位、硬件复位和断电复位仅按该协议能力提供；旧 HPM JTAG 内部自动复位不能关闭。其他调试下载可控制完成蜂鸣及原有硬件复位。

## 配置字段

既有脱机预览/部署 API、远程 CLI/MCP 使用同一配置校验：

```json
{
  "model": "V4",
  "target_part": "HPM5301",
  "programming_protocol": "hpm_rom_isp_uart",
  "script_name": "hpm-isp.py",
  "auto_download_count": 1,
  "algorithms": [],
  "hpm_isp": {
    "baud_rate": 2000000,
    "connect_timeout_ms": 30000,
    "command_timeout_ms": 10000,
    "config_address": "0x200",
    "memory_id": "0x10000",
    "flash_base": "0x80000000",
    "flash_size": "0x800000",
    "sector_size": 4096,
    "nor_options": ["0xFCF90002", "0x6", "0x1000"],
    "rearm_mode": "isp_reconnect",
    "confirm_reconnect_cycles": false,
    "completion": {
      "beep": true,
      "reset": "none",
      "restore_voltage_mv": null,
      "power_off_ms": 200
    }
  },
  "firmwares": [
    {"id": "app", "file_name": "app.bin", "format": "bin", "base_address": "0x80000400", "upload_index": 0}
  ]
}
```

上例容量与地址只是板级示例。`reset` 支持 `none/software/hardware/power_cycle`；断电恢复电压范围为 1201–5499mV，实际值必须适合目标。`power_off_ms` 同时用作硬件复位脉冲持续时间（10–5000ms）。USART ISP 不允许 OTP、选项字节、FLM、加解锁或全片擦除组合，不能隐式退回 JTAG。
