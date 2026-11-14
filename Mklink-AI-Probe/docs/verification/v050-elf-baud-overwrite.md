# ELF 与完整波特率修复：Windows 打包覆盖验收

日期：2026-11-13。源码固定为 `ad00c962558ca1b0e526276d09792b77a803ac12`，
包含 ELF 修复 `8ed8b8d5` 和波特率修复 `ef59cfb7`。
本地开发候选沿用产品版本 0.4.3，不代表 0.5.0 正式发布。

## 包与安装

维护者 builder 先执行 `--check`，再执行 `--local-bundle`；均通过
`scripts/build_workspace.ps1 -Action run -BuildRoot F:/MKLink-Build`。
在 F 盘固定源码副本构建，复用依赖与 Cargo 缓存。
标准 NSIS 未签名，无 updater 签名，不更改正式更新索引。

| 文件 | SHA-256 |
| --- | --- |
| `MKLink-0.4.3-ad00c962-current-user-x64.exe` | `ceaa80748315a3a8048c09eecb4bbfe7e51469be8a55dd8d87e18efaa73b1c5f` |
| `MKLink-Skill-0.4.3-ad00c962.zip` | `b8c2fb636c541395f8ee919c76a76958293fd3092ccb48c1fb8e605d27b3eb22` |

文件、SHA256SUMS 与本地证据保存在构建根的
`artifacts/v050-elf-baud-package-20261113`，不提交二进制、截图或设备标识。

- 先提取安装器，冻结 CLI 和真实 stdio MCP 预检通过后再覆盖原 `54e03336`。
- 安装时 PATH 仅含 Windows 系统目录。安装器和卸载器请求 `asInvoker`；
  实际安装器和原生桌面进程均为中完整性 RID 8192，未请求管理员权限。
- 覆盖退出码 0，安装后的 **3,676 个文件**与安装器载荷逐一匹配，
  包括完整 `_internal` 目录。
- **6 份既有配置**、USB 端口显示名和机器级注册信息保持不变；
  原生窗口启动及退出后再次检查，6 份配置仍匹配。

## 安装版功能验收

1. 原生窗口正常显示配置页，健康接口返回 `status=ok`，可枚举一只下载器。
   进程树使用安装目录的冻结 sidecar，无 `python.exe` 或 `pythonw.exe`。
   通过窗口关闭按钮正常退出，原生进程、后台和监听端口释放。
2. 在仅 Windows PATH 下再次执行安装版 CLI 和真实 MCP 初始化。
   58 个工具可用，`inspect_mcu`、`security_status` 和离线
   `peripheral_targets` 成功。FLM 校验为 7,059 目标 / 2,224 去重算法；
   SVD 校验为 4,800 目标。隔离项目从内置 Pack 恢复 STM32F407VE
   外设目录，读取到 157 个 GPIOA 描述项，无外部 Pack 依赖。
3. 客户 ELF 使用副本，原文件 SHA-256 不变。安装版 `symbols` CLI 找到
   `STO_PLL_M1`，地址 `0x200004B8`、大小 296。冻结 API 解析 1,184 个
   变量描述符，成员 `STO_PLL_M1._Super.hAvrMecSpeedUnit` 为
   `int16_t` / 2 字节 / `0x200004C4`。
4. 实际浏览器连接安装版冻结后台的生产 Web：搜索并加入上述成员，
   已选信号为 1；点击“重新解析符号”提示保留 1、更新 0、移除 0。
   选择保存在测试 ELF 副本旁，未出现 SRAM 越界。
5. 同一安装版后台分别读取下载器 UART / RS485 能力，均返回 34 档，
   范围 300～10,000,000。实际浏览器在串口助手选择 UART 并读取档位，
   在 Modbus 选择 RS485 并独立读取档位，两页均成功选择 10,000,000。
   第三方端口显示预设提示；固件查询后分别显示 UART / RS485 声明提示。
6. 生成同提交的完整 Skill ZIP，2,225 个 FLM 资源文件、74 个 Pack 文件、
   43 个生产 Web 文件均与安装版逐字节一致。所有交付 SHA-256 已重算。
7. 测试结束无 MKLink 原生/sidecar 进程，原生窗口和功能测试代理端口、
   默认 8765 均无监听；未留下硬件占用。

本次复用同一代码的既有 [ELF 400 项回归](v050-elf-load-segments.md)和
[波特率后端 870 项、GUI 25 项、Skill 69 项及生产构建](v050-uart-baud.md)。
打包提交 `ad00c962` 的 [共享后台及 GUI CI](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/43375264745)
与 [feedback-contract](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/43375264758) 均通过。

## 边界

本轮按用户要求完成 Windows 覆盖安装，未构建新的 macOS 包。
目标 MCU 全程未连接，未烧录、写 RAM、复位或更改电源，也未发送 UART/Modbus
载荷。因此不新增高速收发、客户板实时采样或性能 A/B 结论。
第三方串口驱动仍可能拒绝高档位；完整结构体仍需选择标量成员。

历史 SystemView 对齐丢字节、STOP 状态码和其他性能限制保留，见当前交接。
Windows 包仍未签名，可能显示未知发布者。未合并、签名或正式发布。
