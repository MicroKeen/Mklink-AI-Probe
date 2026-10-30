# 历史后台端口复用导致发现中止

2026-10-30，指定固件会话测试 HPMLink + HPM6E80 时报告：历史 endpoint 端口被其他服务复用，返回 HTTP/2 SETTINGS 二进制；默认后台发现因 `http.client.BadStatusLine` 中止。该会话随后使用独立任务 runtime 目录继续原安装版测试。本会话未访问该设备、真实 endpoint 或其他服务。

根因与源码修复 `4551687d`：`request()` 原来只将 `URLError`、`TimeoutError` 和 `OSError` 归一化为 `RuntimeErrorResponse`，未覆盖 HTTP 协议解析异常。现在同时捕获 `HTTPException`，使已有 `discover()` 逻辑能跳过无效响应，继续检查其他记录。普通调用仍明确失败，不重发命令、不回退直接 CDC；不删除 endpoint，不改变设备锁、身份检查或版本不匹配时的拒绝行为。

验证在 PowerShell 7 / Python 3.14 下通过仓库构建工作区脚本运行，使用 F 盘临时 registry、回环地址和系统分配端口；不使用已安装运行时或硬件。

- 修复前，真实本地 TCP 服务返回 HTTP/2 SETTINGS 后，直接请求及 `running_runtimes`、`selected_runtime`、`control_runtime` 四项回归均以 `BadStatusLine` 失败。
- 修复后 18 项新增回归通过：HTTP/2、错误状态行、截断响应体、过长头部；无效 endpoint 不遮蔽有效后台；POST 仅一次；身份/版本/协议校验和结构化 401/409 保留。夹具禁止枚举设备、打开串口或启动后台。
- 连同 HTTP opener 复用、设备发现、重连、CLI、MCP 回归共 **133 项通过**。有效后台夹具初次遗漏 `runtime_id` 被现有身份检查拒绝，补全夹具后重跑通过；未放宽产品身份检查。
- JUnit 结果：`F:/MKLink-Build/artifacts/runtime-endpoint-errors-20261030/tests.xml`。测试服务均在夹具收尾关闭；工作区脚本检测到测试链接并保留 scratch，未强删。

该修复只解决协议异常中止发现，不解决 374 个历史目录逐个探测造成的启动延迟，也不改变已有响应格式校验范围。未重建安装包/Skill、覆盖安装或发布；安装版 0.4.2 暂不含此修复，和 `6ce79923` 在线读取提示修复一起留待下次授权构建。
