# 随 AXF/ELF 保存 SuperWatch 配置

首次成功加载后台可访问的符号文件，会自动在它旁边创建配置：
`app.axf` 对应 `app.axf.superwatch.json`，`app.elf` 对应 `app.elf.superwatch.json`。
重新加载该文件时恢复配置；不同 AXF/ELF 各自独立。移动工程时将这两个文件一起移动。
符号解析失败时不创建配置。

保存变量名称、常用变量、分组、别名、颜色、公式、数组快照范围、采样间隔，以及
波形缓冲区、触发参数、阈值、坐标显示、面板宽度和曲线显隐。变量地址不写入配置，
重新编译后从当前符号表解析；找不到的变量会提示并保留配置中的名称。
外设选择仍使用目标工程的 SVD/Pack 配置，不将寄存器地址混入符号文件配置。
采样数据、运行/暂停状态、设备连接和电压不保存，恢复配置不会自动开始采集。

GUI 操作自动保存；拖动和连续显示调整合并为约 250 ms 后一次保存，采样数据到来不会
触发配置写盘。切换符号文件前会提交待保存的显示配置。配置写入采用临时文件替换。
目录只读、配置损坏或被其他窗口/程序修改时显示错误，不覆盖损坏文件。
修复文件后重新加载 AXF/ELF；有配置冲突时先刷新配置再重新操作，不盲目重试覆盖。

配置位于**后台电脑上的 AXF/ELF 旁边**。桌面选择本机文件可直接保存到工程目录；
浏览器上传的是副本，配置保存在后台副本旁，不能越过浏览器权限写回客户端原目录。
需要工程携带配置时，使用后台可访问的工程原路径，并将配置文件一同保留。

## Web、Skill/CLI、MCP 使用同一份配置

以下接口均连接共享后台，不另建独立配置。

| 操作 | CLI runtime capability | MCP `superwatch(action=...)` | Web API |
|---|---|---|---|
| 查看配置、路径、错误 | `superwatch_profile` | `profile` | GET `/api/dash/superwatch/profile` |
| 保存波形/布局设置 | `superwatch_profile_save` | `profile_save` | PUT `/api/dash/superwatch/profile` |
| 查看/保存分组样式 | `superwatch_workspace` / `superwatch_workspace_save` | `workspace` / `workspace_save` | GET/PUT `/api/dash/superwatch/workspace` |
| 查看/保存常用变量 | `superwatch_pins` / `superwatch_pins_save` | `pins` / `pins_save` | GET/PUT `/api/dash/superwatch/pins` |

先读取当前配置。保存显示配置使用 `section: "viewer"` 或 `"layout"`、
`value`（完整该节）和读取结果中该节的 `revision`。分组和常用变量保存分别使用
`workspace` / `pins` 加它们各自的 `revision`。旧修订返回 409，不覆盖新配置。
采样间隔通过 `superwatch_interval` / MCP `interval` 应用并保存；
显示配置保存不会更改采样间隔。变量增删和数组快照选择继续使用既有共享接口，
成功后自动保存。API 的 `profile_error` 或配置查询的 `error` 表示本次未成功持久化，
不能仅凭变量已添加就报告“配置已保存”。

```powershell
mklink runtime call superwatch_profile --probe <ID>
mklink runtime call superwatch_interval --probe <ID> --arguments '{"interval":0.000001}'
```

CLI `superwatch` 省略 `--period` 时沿用保存的间隔，新配置默认 0.001 秒；
显式传入时应用并保存该值。已运行的采集只允许无配置参数订阅。
缓冲区为 GUI 每通道历史容量，保存在配置中，不能用它改变设备侧采样协议。
