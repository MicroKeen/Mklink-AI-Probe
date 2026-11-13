# ELF 可写加载段与 SuperWatch 变量范围

日期：2026-11-13。代码提交：`8ed8b8d5`，分支 `codex/v0.5.0-fixes`。

## 复现与根因

用户提供的 ELF 可独立复现变量遗漏。截图中的 `nm T` 不能直接等同于
MKLink 把变量识别成函数：原始 ELF 符号表中的 `STO_PLL_M1` 为
`STT_OBJECT`，地址 `0x200004B8`，大小 296 字节，DWARF 类型也完整。

| 映射 | 执行地址 | 大小 | 标志 |
| --- | --- | --- | --- |
| `.data` 节 | `0x20000000` | `0x12D0` | AX，缺 SHF_WRITE |
| `.bss` 节 | `0x200012D0` | `0xAD8` | WA |
| RAM `PT_LOAD` 段 | `0x20000000` | 文件 `0x12D0` / 内存 `0x1DA8` | RWX，含 PF_W |

旧实现只合并可写、已分配节，因而仅返回
`[0x200012D0, 0x20001DA8)`，遗漏 `.data` 中的变量及结构体成员。
实际复现的是符号目录和搜索结果遗漏；截图提到的完整
“address outside SRAM” 用户操作未在客户板上复现。

## 修复

- 合并可写节与带 `PF_W` 的非空 `PT_LOAD` 执行范围；本例结果为
  `[0x20000000, 0x20001DA8)`。
- 使用 `p_vaddr` 和 `p_memsz`，包括零初始化内存；不使用本例指向
  Flash 初始化镜像的 `p_paddr=0x080075E4`。
- 仅有 AX、RAM 地址或非 LOAD 段均不足以放宽可写范围。
  已知映射全部只读时返回空范围；只有缺少映射信息时保留旧回退。
- 内置 pyelftools 和显式选择的 GNU readelf 后端使用同一规范化段接口；
  不自动启用外部工具，不改写用户 ELF 的节标志或链接脚本。
- 符号目录、SuperWatch 以及 CLI/MCP 使用的共享解析服务受益于同一修复。
  结构体仍须选择标量成员，296 字节根对象不作为一个标量通道。

字段语义依据 [ELF gABI Program Header](https://gabi.xinuos.com/elf/07-pheader.html)。

## 验证

Windows、PowerShell 7、UTF-8，所有测试通过
`scripts/build_workspace.ps1 -Action run -BuildRoot F:/MKLink-Build`。

1. ELF/DWARF、符号目录、离线符号、共享 watch、对齐、采集中写入、
   采集启动、map 回退、RTT 地址/会话、HardFault 相关 **400 项通过**。
   最终一次 13.31 秒；早期 91 项包含在上述范围中，不累加。
2. 回归用例覆盖 AX `.data` + RWX 加载段、只读 Flash 拒绝、函数排除、
   内存长度与文件长度、执行地址与装载地址、ELF32/64 外部输出、全部
   PF 位组合、非 LOAD / 空段，以及已知只读映射不误入 SRAM 回退。
   CI 额外纳入 `test_elf_builtin.py`，已有 `test_elf_backend.py` 保留。
3. 真实提供文件离线解析：API 返回 1,184 个变量描述符；
   `STO_PLL_M1._Super.hAvrMecSpeedUnit` 解析为 `int16_t`、2 字节、
   `0x200004C4`。真实 SuperWatchRuntime 加入该成员成功。
4. 真实生产 Web 资源接本轮源码 API，保持设备未连接，搜索并选择该成员。
   已选信号变为 1，成员保存到测试 ELF 副本旁的 SuperWatch 配置，
   未出现 SRAM 越界。后台正常退出、监听端口释放。
5. 原始 ELF 的 SHA-256 前后相同。未提交客户 ELF、截图或本地日志；
   证据保存在构建根的 `artifacts/v050-elf-data-20261113`。
   清理本轮 445 个测试链接和 3 个临时运行目录，零失败。

可重复测试文件选择：

```powershell
$tests = @(Get-ChildItem _maintainer/testing/tests -File |
  Where-Object Name -match '^test_(elf.*|dwarf.*|symbol_catalog|offline_symbols|shared_watch|superwatch_alignment|superwatch_live_write|capture_startup_regressions|watch_map_fallback|rtt_addr|rtt_session|hardfault)\.py$' |
  ForEach-Object FullName)
./scripts/build_workspace.ps1 -Action run -BuildRoot F:/MKLink-Build `
  -Executable python -ArgumentList (@('-m', 'pytest', '-q') + $tests)
```

## 边界

本轮未烧录或连接客户电机板，未进行实时采样、RAM 写入或硬件性能 A/B。
没有修改固件或目标工程链接脚本，也未认定是谁产生了 AX 节属性。
权限来自 ELF 声明，不替代目标 MPU、安全域或总线访问检查。
外部 GNU 输出解析经过夹具验证，实际客户文件使用默认内置解析器。

本机已安装 Windows 仍为 `54e03336`，不包含本轮 ELF 修复和前轮波特率修复；
本轮未生成或覆盖安装新包。未合并、签名或正式发布。
